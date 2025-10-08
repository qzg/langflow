from __future__ import annotations

from contextlib import suppress

from fastapi import APIRouter
from pydantic import BaseModel, Field

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.deps import get_settings_service, get_variable_service
from langflow.services.variable.constants import GENERIC_TYPE

router = APIRouter(prefix="/ai_codegen", tags=["AI Codegen"])

# ------------- Workspace management -------------
import base64 as _b64
import shutil as _shutil
import tempfile as _tmp
from pathlib import Path as _Path

from fastapi import HTTPException

_WORKSPACE_PREFIX = "lf_wasm_build_"


def _safe_decode_root(root_b64: str) -> _Path:
    try:
        p = _Path(_b64.urlsafe_b64decode(root_b64.encode()).decode())
    except Exception as e:
        raise HTTPException(status_code=400, detail="invalid root path") from e
    # Constrain to temp dir and our prefix
    tmpdir = _Path(_tmp.gettempdir()).resolve()
    p = p.resolve()
    if not str(p).startswith(str(tmpdir)) or _WORKSPACE_PREFIX not in p.name:
        raise HTTPException(status_code=400, detail="root outside allowed area")
    return p


def _scan_workspaces() -> list[dict]:
    tmpdir = _Path(_tmp.gettempdir())
    entries: list[dict] = []
    for child in tmpdir.iterdir():
        if not child.is_dir():
            continue
        if not child.name.startswith(_WORKSPACE_PREFIX):
            continue
        item = {
            "root": str(child),
            "root_b64": _b64.urlsafe_b64encode(str(child).encode()).decode(),
            "name": child.name,
            "type": None,
            "twin_id": None,
            "component_id": None,
            "flow_id": None,
            "run_id": None,
            "started_at": None,
            "updated_at": None,
            "success": None,
            "logs_uri": None,
        }
        meta = child / ".lf_workspace.json"
        if meta.exists():
            import json as _json

            try:
                data = _json.loads(meta.read_text())
                item.update(
                    {
                        "type": data.get("type"),
                        "twin_id": data.get("twin_id"),
                        "component_id": data.get("component_id"),
                        "flow_id": data.get("flow_id"),
                        "run_id": data.get("run_id"),
                        "started_at": data.get("started_at"),
                        "updated_at": data.get("updated_at"),
                        "success": data.get("success"),
                        "logs_uri": data.get("logs_uri"),
                    }
                )
            except Exception:
                pass
        try:
            item["updated_at"] = child.stat().st_mtime
        except Exception:
            pass
        entries.append(item)
    # sort by updated_at desc
    entries.sort(key=lambda e: e.get("updated_at") or 0, reverse=True)
    return entries


class WorkspaceListResponse(BaseModel):
    workspaces: list[dict]


@router.get("/workspaces", response_model=WorkspaceListResponse)
async def list_workspaces() -> WorkspaceListResponse:
    return WorkspaceListResponse(workspaces=_scan_workspaces())


class WorkspaceLsResponse(BaseModel):
    root: str
    path: str
    entries: list[dict]


@router.get("/workspaces/{root_b64}/ls", response_model=WorkspaceLsResponse)
async def ls_workspace(root_b64: str, path: str = "") -> WorkspaceLsResponse:
    root = _safe_decode_root(root_b64)
    base = (root / path).resolve()
    if not str(base).startswith(str(root)):
        raise HTTPException(status_code=400, detail="path escapes root")
    if not base.exists() or not base.is_dir():
        raise HTTPException(status_code=404, detail="dir not found")
    items: list[dict] = []
    for child in base.iterdir():
        try:
            st = child.stat()
            items.append(
                {
                    "name": child.name,
                    "is_dir": child.is_dir(),
                    "size": None if child.is_dir() else st.st_size,
                    "mtime": st.st_mtime,
                }
            )
        except Exception:
            continue
    items.sort(key=lambda e: (not e["is_dir"], e["name"]))
    return WorkspaceLsResponse(root=str(root), path=str(base.relative_to(root)), entries=items)


class WorkspaceFileResponse(BaseModel):
    root: str
    path: str
    content: str


@router.get("/workspaces/{root_b64}/file", response_model=WorkspaceFileResponse)
async def get_workspace_file(root_b64: str, path: str) -> WorkspaceFileResponse:
    root = _safe_decode_root(root_b64)
    p = (root / path).resolve()
    if not str(p).startswith(str(root)):
        raise HTTPException(status_code=400, detail="path escapes root")
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    try:
        # text files only; limit size for safety
        data = p.read_text(encoding="utf-8", errors="ignore")
        if len(data) > 500_000:
            data = data[:500_000] + "\n...\n(truncated)"
        return WorkspaceFileResponse(root=str(root), path=str(p.relative_to(root)), content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


class DeleteAllResponse(BaseModel):
    deleted: int


@router.delete("/workspaces", response_model=DeleteAllResponse)
async def delete_all_workspaces() -> DeleteAllResponse:
    count = 0
    for item in _scan_workspaces():
        try:
            _shutil.rmtree(item["root"], ignore_errors=True)
            count += 1
        except Exception:
            pass
    return DeleteAllResponse(deleted=count)


class DeleteOneResponse(BaseModel):
    deleted: bool


@router.delete("/workspaces/{root_b64}", response_model=DeleteOneResponse)
async def delete_workspace(root_b64: str) -> DeleteOneResponse:
    root = _safe_decode_root(root_b64)
    try:
        _shutil.rmtree(root, ignore_errors=True)
        return DeleteOneResponse(deleted=True)
    except Exception:
        return DeleteOneResponse(deleted=False)


# ------------- Existing settings APIs below -------------


class AICodegenSettingsResponse(BaseModel):
    ai_codegen_enabled: bool
    ai_codegen_cli: str
    ai_codegen_profile: str | None
    ai_codegen_timeout_ms: int
    ai_codegen_working_dir: str
    ai_codegen_api_key_env: str | None
    overridden_by_env: dict[str, bool] = Field(default_factory=dict)


class AICodegenSettingsUpdate(BaseModel):
    ai_codegen_enabled: bool | None = None
    ai_codegen_cli: str | None = None
    ai_codegen_profile: str | None = None
    ai_codegen_timeout_ms: int | None = None
    ai_codegen_working_dir: str | None = None
    ai_codegen_api_key_env: str | None = None


@router.get("/settings", response_model=AICodegenSettingsResponse)
async def get_ai_settings(current_user: CurrentActiveUser, session: DbSession) -> AICodegenSettingsResponse:
    settings_svc = get_settings_service()
    var_svc = get_variable_service()
    s = settings_svc.settings

    enabled = bool(getattr(s, "ai_codegen_enabled", False))
    cli = str(getattr(s, "ai_codegen_cli", "warp"))
    profile = getattr(s, "ai_codegen_profile", None)
    timeout_ms = int(getattr(s, "ai_codegen_timeout_ms", 120000))
    working_dir = str(getattr(s, "ai_codegen_working_dir", "repo_root"))
    api_key_env = getattr(s, "ai_codegen_api_key_env", None)

    # Overlay from DB variables when available
    with suppress(Exception):
        vars_read = await var_svc.get_all(user_id=current_user.id, session=session)
        m = {v.name: (v.value or "") for v in vars_read}
        if "ai_codegen_enabled" in m:
            enabled = m["ai_codegen_enabled"].lower() in {"1", "true", "yes", "on"}
        if m.get("ai_codegen_cli"):
            cli = m["ai_codegen_cli"]
        if "ai_codegen_profile" in m:
            profile = m.get("ai_codegen_profile") or None
        if m.get("ai_codegen_timeout_ms") and str(m["ai_codegen_timeout_ms"]).isdigit():
            timeout_ms = int(m["ai_codegen_timeout_ms"])  # type: ignore[arg-type]
        if m.get("ai_codegen_working_dir"):
            working_dir = m["ai_codegen_working_dir"]
        if "ai_codegen_api_key_env" in m:
            api_key_env = m.get("ai_codegen_api_key_env") or None

    # Compute env overrides annotation
    import os

    overridden_by_env: dict[str, bool] = {}
    ENV_MAP = {
        "ai_codegen_enabled": "AI_CODEGEN_ENABLED",
        "ai_codegen_cli": "AI_CODEGEN_CLI",
        "ai_codegen_profile": "AI_CODEGEN_PROFILE",
        "ai_codegen_timeout_ms": "AI_CODEGEN_TIMEOUT_MS",
        "ai_codegen_working_dir": "AI_CODEGEN_WORKING_DIR",
        "ai_codegen_api_key_env": "AI_CODEGEN_API_KEY_ENV",
    }
    for k, env_name in ENV_MAP.items():
        overridden_by_env[k] = env_name in os.environ

    return AICodegenSettingsResponse(
        ai_codegen_enabled=enabled,
        ai_codegen_cli=cli,
        ai_codegen_profile=profile,
        ai_codegen_timeout_ms=timeout_ms,
        ai_codegen_working_dir=working_dir,
        ai_codegen_api_key_env=api_key_env,
        overridden_by_env=overridden_by_env,
    )


@router.put("/settings", response_model=AICodegenSettingsResponse)
async def put_ai_settings(
    payload: AICodegenSettingsUpdate, current_user: CurrentActiveUser, session: DbSession
) -> AICodegenSettingsResponse:
    settings_svc = get_settings_service()
    var_svc = get_variable_service()
    s = settings_svc.settings

    updates = payload.model_dump(exclude_unset=True)

    # Persist to DB variables
    existing_names: list[str] = []
    with suppress(Exception):
        existing_names = await var_svc.list_variables(user_id=current_user.id, session=session)

    for key, value in updates.items():
        # normalize to string storage
        if isinstance(value, bool):
            str_value = "true" if value else "false"
        else:
            str_value = str(value) if value is not None else ""

        if key in existing_names:
            await var_svc.update_variable(current_user.id, key, str_value, session)
        else:
            await var_svc.create_variable(
                user_id=current_user.id,
                name=key,
                value=str_value,
                default_fields=[],
                type_=GENERIC_TYPE,
                session=session,
            )
        # Update in-memory non-secret settings immediately
        with suppress(Exception):
            setattr(s, key, value)

    return await get_ai_settings(current_user=current_user, session=session)
