from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from langflow.api.v1.preflight import _run_checks as run_preflight

router = APIRouter(prefix="/workspace", tags=["workspace"])

WORKSPACES_ROOT = (Path.cwd() / "workspaces").resolve()
WORKSPACES_ROOT.mkdir(parents=True, exist_ok=True)

_PROCS: dict[str, asyncio.subprocess.Process] = {}
_PROCS_LOCK = asyncio.Lock()

NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _sanitize_name(name: str) -> str:
    if not NAME_PATTERN.match(name):
        msg = "Invalid workspace name. Use letters, numbers, dash or underscore (max 64)."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return name


def _workspace_path(name: str) -> Path:
    safe = _sanitize_name(name)
    path = (WORKSPACES_ROOT / safe).resolve()
    if WORKSPACES_ROOT not in path.parents and path != WORKSPACES_ROOT:
        msg = "Invalid workspace path"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return path


class WorkspaceInitRequest(BaseModel):
    name: str
    template: str = Field(default="vite-react")
    package_manager: str = Field(default="npm")


class WorkspaceInitResponse(BaseModel):
    name: str
    path: str
    created: bool


class WorkspaceStartRequest(BaseModel):
    name: str
    env: dict[str, str] | None = None


class WorkspaceStartResponse(BaseModel):
    name: str
    started: bool
    pid: int | None = None
    reason: str | None = None


class WorkspaceStopRequest(BaseModel):
    name: str


class WorkspaceStopResponse(BaseModel):
    name: str
    stopped: bool
    reason: str | None = None


class WorkspaceStatusResponse(BaseModel):
    name: str
    running: bool
    pid: int | None = None


@router.post("/init", response_model=WorkspaceInitResponse)
async def init_workspace(req: WorkspaceInitRequest) -> WorkspaceInitResponse:
    path = _workspace_path(req.name)
    created = False
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        (path / "README.md").write_text(f"# Workspace {req.name}\n\nTemplate: {req.template}\n", encoding="utf-8")
        (path / ".gitignore").write_text("node_modules\n.dist\n.build\n.tmp\n.env\n", encoding="utf-8")
        created = True
    return WorkspaceInitResponse(name=req.name, path=str(path), created=created)


async def _is_running(name: str) -> tuple[bool, asyncio.subprocess.Process | None]:
    async with _PROCS_LOCK:
        proc = _PROCS.get(name)
        if proc is None:
            return False, None
        if proc.returncode is not None:
            _PROCS.pop(name, None)
            return False, None
        return True, proc


@router.post("/dev/start", response_model=WorkspaceStartResponse)
async def start_dev(req: WorkspaceStartRequest) -> WorkspaceStartResponse:
    preflight = await run_preflight()
    if not preflight.ok:
        reasons = ", ".join(preflight.missing) or "dependencies do not meet minimum requirements"
        return WorkspaceStartResponse(name=req.name, started=False, reason=f"Preflight failed: {reasons}")

    running, _ = await _is_running(req.name)
    if running:
        return WorkspaceStartResponse(name=req.name, started=False, reason="Dev server already running")

    path = _workspace_path(req.name)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    pkg = path / "package.json"
    if not pkg.exists():
        return WorkspaceStartResponse(
            name=req.name, started=False, reason="No package.json found. Initialize a dev script to start."
        )

    try:
        text = pkg.read_text(encoding="utf-8")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read package.json: {exc}") from exc

    if '"dev"' not in text:
        return WorkspaceStartResponse(name=req.name, started=False, reason="No 'dev' script in package.json.")

    try:
        proc = await asyncio.create_subprocess_exec(
            "npm",
            "run",
            "dev",
            cwd=str(path),
            env={**os.environ, **(req.env or {})},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError:
        return WorkspaceStartResponse(name=req.name, started=False, reason="npm not found")
    except Exception as exc:  # noqa: BLE001
        return WorkspaceStartResponse(name=req.name, started=False, reason=f"Failed to start: {exc}")

    async with _PROCS_LOCK:
        _PROCS[req.name] = proc
    return WorkspaceStartResponse(name=req.name, started=True, pid=proc.pid)


@router.post("/dev/stop", response_model=WorkspaceStopResponse)
async def stop_dev(req: WorkspaceStopRequest) -> WorkspaceStopResponse:
    async with _PROCS_LOCK:
        proc = _PROCS.get(req.name)
        if proc is None or proc.returncode is not None:
            _PROCS.pop(req.name, None)
            return WorkspaceStopResponse(name=req.name, stopped=False, reason="Not running")
        try:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                proc.kill()
        except ProcessLookupError:
            pass
        finally:
            _PROCS.pop(req.name, None)
    return WorkspaceStopResponse(name=req.name, stopped=True)


@router.get("/dev/status", response_model=WorkspaceStatusResponse)
async def status_dev(name: Annotated[str, Query(description="Workspace name")]) -> WorkspaceStatusResponse:
    running, proc = await _is_running(name)
    return WorkspaceStatusResponse(name=name, running=running, pid=(proc.pid if proc else None))
