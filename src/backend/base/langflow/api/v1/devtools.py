from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from lfx.base.mcp.util import MCPStdioClient
from pydantic import BaseModel, Field

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v2.mcp import get_server
from langflow.services.deps import get_shared_component_cache_service

router = APIRouter(prefix="/devtools", tags=["DevTools MCP"])


class NavigateRequest(BaseModel):
    url: str = Field(..., description="URL to navigate the browser to")
    server_name: str = Field(default="chrome-devtools", description="Configured MCP server name")


class ScreenshotRequest(BaseModel):
    full_page: bool = Field(
        default=True,
        alias="fullPage",
        description="Capture full page if true (alias: fullPage)",
    )
    server_name: str = Field(default="chrome-devtools")
    workspace: str | None = Field(
        default=None,
        description="Optional workspace name to store artifacts under workspaces/<name>/.builder-artifacts",
    )


class ScreenshotResponse(BaseModel):
    saved: bool
    path: str | None = None
    note: str | None = None


class PagesResponse(BaseModel):
    pages: list[str] = Field(default_factory=list)


async def _get_server_config_or_default(
    server_name: str,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    """Fetch MCP server config by name; fallback to default chrome-devtools stdio config."""
    cfg = await get_server(server_name, current_user, session)
    if cfg:
        return cfg
    # Fallback to ephemeral stdio config using npx
    return {"command": "npx", "args": ["-y", "chrome-devtools-mcp@latest"], "env": {}}


def _build_full_command(cfg: dict[str, Any]) -> tuple[str, dict[str, str]]:
    command = cfg.get("command")
    if not command:
        msg = "MCP server must be configured with 'command' for stdio mode"
        raise HTTPException(status_code=400, detail=msg)
    args = cfg.get("args", [])
    env = cfg.get("env", {})
    full = " ".join([command, *args])
    return full, env


async def _connect_client(
    server_cfg: dict[str, Any],
    user_context: str,
) -> MCPStdioClient:
    cache = get_shared_component_cache_service()
    client = MCPStdioClient(component_cache=cache)
    client.set_session_context(user_context)
    full_cmd, env = _build_full_command(server_cfg)
    await client.connect_to_server(full_cmd, env)
    return client


@router.post("/navigate")
async def navigate(
    body: NavigateRequest,
    current_user: Annotated[CurrentActiveUser, Depends()],
    session: Annotated[DbSession, Depends()],
):
    cfg = await _get_server_config_or_default(body.server_name, current_user, session)
    client = await _connect_client(cfg, user_context=f"devtools:{current_user.id}")
    await client.run_tool("navigate_page", {"url": body.url})
    return {"ok": True}


@router.get("/pages", response_model=PagesResponse)
async def list_pages(
    server_name: Annotated[str, Query(default="chrome-devtools")],
    current_user: Annotated[CurrentActiveUser, Depends()],
    session: Annotated[DbSession, Depends()],
):
    cfg = await _get_server_config_or_default(server_name, current_user, session)
    client = await _connect_client(cfg, user_context=f"devtools:{current_user.id}")
    res = await client.run_tool("list_pages", {})
    # Try to parse text content; fallback to raw string list
    pages: list[str] = []
    try:
        # res may be a list of TextContent objects or strings
        if isinstance(res, list):
            for item in res:
                text = getattr(item, "text", None) or str(item)
                pages.append(text)
        else:
            pages.append(str(res))
    except Exception:  # noqa: BLE001
        pages = [str(res)]
    return PagesResponse(pages=pages)


@router.post("/screenshot", response_model=ScreenshotResponse)
async def screenshot(
    body: ScreenshotRequest,
    current_user: Annotated[CurrentActiveUser, Depends()],
    session: Annotated[DbSession, Depends()],
):
    cfg = await _get_server_config_or_default(body.server_name, current_user, session)
    client = await _connect_client(cfg, user_context=f"devtools:{current_user.id}")
    res = await client.run_tool("take_screenshot", {"format": "png", "fullPage": body.fullPage})

    # Attempt to extract saved path from textual response
    raw = ""
    try:
        raw = getattr(res[0], "text", "") or str(res[0]) if isinstance(res, list) and res else str(res)
    except Exception:  # noqa: BLE001
        raw = str(res)

    m = re.search(r"Saved screenshot to\s+(.+)$", raw, re.MULTILINE)
    if not m:
        return ScreenshotResponse(saved=False, note="Could not parse screenshot path from MCP response")

    tmp_path = Path(m.group(1)).expanduser()
    if not tmp_path.exists():
        return ScreenshotResponse(saved=False, note="Screenshot file not found on disk")

    # Where to store artifacts
    workspace_name = body.workspace or "_artifacts"
    # sanitize name to safe folder name
    workspace_name = re.sub(r"[^a-zA-Z0-9_-]", "_", workspace_name)[:64] or "_artifacts"

    artifacts_dir = (Path.cwd() / "workspaces" / workspace_name / ".builder-artifacts").resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Compute destination filename
    import datetime as _dt
    from datetime import timezone as _tz

    dest = artifacts_dir / f"screenshot-{_dt.datetime.now(tz=_tz.utc).strftime('%Y%m%d-%H%M%S')}.png"
    try:
        dest.write_bytes(tmp_path.read_bytes())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to copy screenshot: {exc}") from exc

    return ScreenshotResponse(saved=True, path=str(dest))
