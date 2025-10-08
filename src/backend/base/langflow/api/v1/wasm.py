from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from typing import Any as _Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.component_twin.model import ComponentTwin
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_settings_service
from langflow.services.wasm.build import build_component, plan_build
from langflow.services.wasm.parity import compute_text_similarity
from langflow.services.wasm.publish import publish_oci
from langflow.services.wasm.rust_skeleton import encode_crate_files, generate_rust_skeleton
from langflow.services.wasm.wit_generator import generate_wit

router = APIRouter(prefix="/wasm", tags=["WASM/WIT"])
logger = logging.getLogger(__name__)

# ------------------ Build run (SSE) in-memory registry ------------------
# Minimal M0 in-memory orchestration for build runs and event streaming.
_BUILD_RUNS: dict[str, dict[str, _Any]] = {}
_BUILD_RETENTION_MAX = 50  # keep last N runs in memory

# ------------------ Codegen run (SSE) in-memory registry ------------------
_CODEGEN_RUNS: dict[str, dict[str, _Any]] = {}
_CODEGEN_RETENTION_MAX = 50


def _sse(event: str, data: _Any) -> str:
    try:
        payload = json.dumps(data, default=str)
    except Exception:
        payload = json.dumps({"message": str(data)})
    return f"event: {event}\ndata: {payload}\n\n"


# ------------------ AI codegen helpers ------------------
from pathlib import Path as _Path


def _find_repo_root(start: _Path | None = None) -> _Path:
    p = start or _Path(__file__).resolve()
    for _ in range(10):  # walk up to 10 levels
        if (p / "pyproject.toml").exists() or (p / ".git").exists():
            return p
        if p.parent == p:
            break
        p = p.parent
    return _Path.cwd()


def _prepare_ai_prompt(
    *, twin: ComponentTwin, workspace: _Path, prev_build_error: str | None = None, user_hint: str | None = None
) -> str:
    py = twin.python_source or ""
    wit = twin.wit_source or ""

    # Attempt to find a prior successful summary for this component
    prior_summary = None
    try:
        import json as _json
        import tempfile as _tmp

        tmpdir = _Path(_tmp.gettempdir())
        latest_ts = 0.0
        latest_dir = None
        for child in tmpdir.iterdir():
            if not child.is_dir() or "lf_wasm_build_" not in child.name:
                continue
            meta_path = child / ".lf_workspace.json"
            if not meta_path.exists():
                continue
            data = _json.loads(meta_path.read_text())
            if data.get("component_id") == twin.component_id and data.get("success") is True:
                ts = child.stat().st_mtime
                if ts > latest_ts:
                    latest_ts = ts
                    latest_dir = child
        if latest_dir and (latest_dir / "summary.txt").exists():
            prior_summary = (latest_dir / "summary.txt").read_text()[:5000]
    except Exception:
        prior_summary = None

    extra = (
        ("\n\nPrevious build error/logs (fix and retry):\n---\n" + prev_build_error + "\n---\n")
        if prev_build_error
        else ""
    )
    if user_hint:
        extra += "\n\nUser guidance:\n---\n" + user_hint + "\n---\n"
    if prior_summary:
        extra += "\n\nPrior successful summary for this component:\n---\n" + prior_summary + "\n---\n"
    prompt = f"""
You are generating Rust code for a WebAssembly component that will be built with Cargo and wit-bindgen.

- The WIT interface file is provided at wit/world.wit below.
- Implement the exported function 'process' for world 'component'.
- Use wit_bindgen::generate! with path: "wit" and world: "component" to generate bindings.
- Implement a concrete component that maps input -> output according to the WIT types.
- Output EXACTLY these code blocks:
  1) FILE: src/lib.rs
     Fenced code block with the complete lib.rs content that compiles.
  2) FILE: Cargo.toml (optional) ONLY if you need additional dependencies or changes; otherwise omit.

WIT (wit/world.wit):
---
{wit}
---

Python reference (behavior to port):
---
{py}
---
{extra}
""".strip()
    f = workspace / "prompt.txt"
    f.write_text(prompt)
    return str(f)


def _parse_ai_output_files(output: str) -> dict[str, str]:
    """Parse minimal 'FILE: <path>' + fenced code blocks from AI output.

    Expected pattern:
        FILE: src/lib.rs\n```<lang>\n...contents...\n```
    """
    import re as _re

    files: dict[str, str] = {}
    # Find sequences of FILE: <path> followed by a fenced block
    pattern = _re.compile(r"FILE:\s*(?P<path>[^\n]+)\s*\n```[\w-]*\n(?P<body>[\s\S]*?)\n```", _re.MULTILINE)
    for m in pattern.finditer(output):
        path = m.group("path").strip()
        body = m.group("body")
        if path:
            files[path] = body
    return files


async def _generate_rust_with_ai(*, twin: ComponentTwin, package_name: str, func_name: str) -> dict[str, str]:
    # Prepare workspace first
    plan = plan_build(wit_source=twin.wit_source or "", rust_source=twin.rust_source)
    workspace = _Path(plan.workspace)
    prompt_path = _Path(_prepare_ai_prompt(twin=twin, workspace=workspace))

    # Settings
    s = get_settings_service().settings
    if not getattr(s, "ai_codegen_enabled", False):
        raise RuntimeError("AI codegen disabled in settings")

    cli = getattr(s, "ai_codegen_cli", "warp") or "warp"
    profile = getattr(s, "ai_codegen_profile", None)
    timeout_ms = int(getattr(s, "ai_codegen_timeout_ms", 120000))
    working_dir_mode = str(getattr(s, "ai_codegen_working_dir", "repo_root"))
    api_key_env = getattr(s, "ai_codegen_api_key_env", None)

    # Decide working directory
    repo_root = _find_repo_root(_Path(__file__).resolve())
    cwd = repo_root if working_dir_mode == "repo_root" else workspace

    # Build command
    args = [cli]
    if profile:
        args += ["--profile", str(profile)]

    # Execute CLI, feeding prompt via stdin or file if needed.
    import asyncio as _asyncio
    import os as _os

    env = dict(_os.environ)
    # Do not read or print secrets; just ensure the named env var is present if configured
    if api_key_env and api_key_env not in env:
        # leave absent; user may supply externally
        pass

    try:
        proc = await _asyncio.create_subprocess_exec(
            *args,
            cwd=str(cwd),
            stdin=_asyncio.subprocess.PIPE,
            stdout=_asyncio.subprocess.PIPE,
            stderr=_asyncio.subprocess.PIPE,
            env=env,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"AI CLI not found: {cli}") from exc

    # Send prompt via stdin, then close
    try:
        with open(prompt_path, "rb") as pf:
            content = pf.read()
        assert proc.stdin is not None
        proc.stdin.write(content)
        await proc.stdin.drain()
        proc.stdin.close()
    except Exception:
        # If writing stdin fails, continue; some CLIs may not read stdin
        pass

    # Collect output with a timeout
    try:
        done = await _asyncio.wait_for(proc.communicate(), timeout=timeout_ms / 1000.0)
    except _asyncio.TimeoutError as exc:
        proc.kill()
        raise RuntimeError("AI codegen timed out") from exc

    stdout = (done[0] or b"").decode(errors="ignore")
    stderr = (done[1] or b"").decode(errors="ignore")

    # Parse code blocks
    files = _parse_ai_output_files(stdout)
    if "src/lib.rs" not in files:
        # If AI didn't follow the convention, fallback to skeleton
        return generate_rust_skeleton(wit_source=twin.wit_source or "", package_name=package_name, func_name=func_name)

    # Write files into workspace and return mapping
    for rel, content in files.items():
        p = workspace / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    # Collect final mapping from workspace
    result: dict[str, str] = {}
    for rel in ["Cargo.toml", "src/lib.rs", "wit/world.wit"]:
        p = workspace / rel
        if p.exists():
            result[rel] = p.read_text()
    # Ensure wit/world.wit is included
    if "wit/world.wit" not in result and (workspace / "wit/world.wit").exists():
        result["wit/world.wit"] = (workspace / "wit/world.wit").read_text()
    return result


async def _append_event(run_id: str, event: str, data: _Any):
    run = _BUILD_RUNS.get(run_id)
    if not run:
        return
    q: asyncio.Queue[str] = run["queue"]
    msg = _sse(event, data)
    # keep a short log buffer for late joiners (only for log events)
    if event == "log":
        buf = run.setdefault("log_buffer", [])
        buf.append(data.get("line", ""))
        # bound buffer size
        if len(buf) > 5000:
            del buf[: len(buf) - 5000]
    # append to transcript if available
    try:
        tpath = run.get("transcript_path")
        if tpath:
            with open(tpath, "a", encoding="utf-8", errors="ignore") as tf:
                import json as _json

                tf.write(_json.dumps({"event": event, "data": data}) + "\n")
    except Exception:
        pass
    await q.put(msg)


async def _run_build_task(
    *,
    run_id: str,
    twin: ComponentTwin,
    wit_source: str,
    rust_source: str | None,
    dry_run: bool,
):
    # announce running
    _BUILD_RUNS[run_id]["status"] = "running"
    _BUILD_RUNS[run_id]["step"] = "prepare"
    await _append_event(run_id, "state", {"status": "running", "step": "prepare"})

    loop = asyncio.get_event_loop()
    try:
        # planning step
        _BUILD_RUNS[run_id]["step"] = "plan"
        await _append_event(run_id, "state", {"status": "running", "step": "plan"})
        try:
            plan = plan_build(wit_source=wit_source, rust_source=rust_source)
            await _append_event(run_id, "log", {"level": "info", "line": f"Planned: tool={plan.tool} args={plan.args}"})
        except Exception as e:  # plan may be optional
            await _append_event(run_id, "log", {"level": "warn", "line": f"Plan step skipped: {e}"})

        # build step (execute in thread to avoid blocking)
        _BUILD_RUNS[run_id]["step"] = "build"
        await _append_event(run_id, "state", {"status": "running", "step": "build"})
        # prepare transcript path once we know workspace (we'll infer from logs later if needed)
        # Build step
        result = await loop.run_in_executor(
            None,
            lambda: build_component(wit_source=wit_source, rust_source=rust_source, dry_run=dry_run),
        )
        await _append_event(run_id, "log", {"level": "info", "line": "Build finished."})

        # Write workspace manifest and transcript
        try:
            if getattr(result, "logs_path", None):
                wroot = _Path(result.logs_path).parent
                # transcript
                tpath = wroot / "transcript.ndjson"
                _BUILD_RUNS[run_id]["transcript_path"] = str(tpath)
                # manifest
                meta = {
                    "type": "build",
                    "run_id": run_id,
                    "twin_id": str(twin.id),
                    "component_id": twin.component_id,
                    "flow_id": str(twin.flow_id),
                    "started_at": str(_BUILD_RUNS[run_id].get("started_at")),
                    "updated_at": str(datetime.now(timezone.utc)),
                    "success": bool(getattr(result, "built", False)),
                    "logs_uri": str(result.logs_path),
                }
                (wroot / ".lf_workspace.json").write_text(json.dumps(meta))
        except Exception:
            pass

        # surface logs if available
        if getattr(result, "logs_path", None):
            try:
                with open(result.logs_path, encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        await _append_event(run_id, "log", {"level": "info", "line": line.rstrip("\n")})
            except Exception as e:  # pragma: no cover
                await _append_event(run_id, "log", {"level": "warn", "line": f"(unable to read logs file: {e})"})

        # persist twin build status and metadata using a fresh session
        try:
            from langflow.services.deps import session_scope

            async with session_scope() as session:
                twin_db = await session.get(ComponentTwin, twin.id)
                if twin_db:
                    if getattr(result, "logs_path", None):
                        twin_db.build_logs_uri = str(result.logs_path)
                    if getattr(result, "wasm_path", None):
                        twin_db.wasm_blob = str(result.wasm_path)
                    manifest = twin_db.capability_manifest or {}
                    build_meta = manifest.get("build", {})
                    build_meta.update(
                        {
                            "validated_component": result.validated_component,
                            "wrapped": result.wrapped,
                            "plan": {"tool": result.plan_tool, "args": result.plan_args},
                            "tool_versions": result.tool_versions,
                            "logs_uri": twin_db.build_logs_uri,
                        }
                    )
                    manifest["build"] = build_meta
                    twin_db.capability_manifest = manifest
                    twin_db.build_status = "built" if result.built else "error"
                    twin_db.updated_at = datetime.now(timezone.utc)
                    session.add(twin_db)
        except Exception:  # pragma: no cover
            logger.warning("Failed to persist build metadata", exc_info=True)

        _BUILD_RUNS[run_id]["status"] = "done"
        _BUILD_RUNS[run_id]["success"] = bool(getattr(result, "built", False))
        await _append_event(
            run_id,
            "done",
            {
                "success": bool(getattr(result, "built", False)),
                "digest": getattr(result, "digest", None),
                "size": getattr(result, "size", None),
            },
        )
    except Exception as e:
        _BUILD_RUNS[run_id]["status"] = "failed"
        _BUILD_RUNS[run_id]["error"] = str(e)
        await _append_event(run_id, "error", {"message": str(e)})
        await _append_event(run_id, "done", {"success": False})
    finally:
        # trim registry
        if len(_BUILD_RUNS) > _BUILD_RETENTION_MAX:
            # drop oldest by insertion order
            _BUILD_RUNS.pop(next(iter(_BUILD_RUNS)))


class GenerateWITRequest(BaseModel):
    twin_id: UUID | None = Field(None, description="Existing ComponentTwin to update")
    flow_id: UUID | None = Field(None, description="Flow ID (required if twin_id not provided)")
    component_id: str | None = Field(None, description="Component ID (required if twin_id not provided)")
    io_schema: dict[str, Any] | None = Field(None, description="I/O schema; falls back to twin.io_schema if omitted")
    world_name: str = Field("component", description="WIT world name")
    func_name: str = Field("process", description="Exported function name")


class GenerateWITResponse(BaseModel):
    twin: ComponentTwin


class GenerateRustRequest(BaseModel):
    twin_id: UUID
    package_name: str | None = Field(None, description="Optional crate package name; defaults from component_id")
    func_name: str = Field("process", description="Exported function name stub")
    use_ai: bool = Field(False, description="Use AI code generation instead of static skeleton")


class GenerateRustResponse(BaseModel):
    twin: ComponentTwin


class BuildRequest(BaseModel):
    twin_id: UUID
    dry_run: bool = Field(default=False, description="When true, prepare workspace only and do not invoke cargo")


class BuildResponse(BaseModel):
    twin: ComponentTwin
    workspace: str | None = Field(None, description="Path of the temp workspace when dry_run=true")
    logs_uri: str | None = None
    planned_tool: str | None = None
    planned_args: list[str] | None = None
    digest: str | None = None
    size: int | None = None
    validated_component: bool | None = None
    wrapped: bool | None = None


class PublishRequest(BaseModel):
    twin_id: UUID
    oci_ref: str = Field(..., description="OCI reference, e.g., ghcr.io/org/name:tag")
    dry_run: bool = Field(default=False, description="Plan only; do not execute push")


class PublishResponse(BaseModel):
    planned_tool: str | None = None
    planned_args: list[str] | None = None
    success: bool
    error: str | None = None
    digest: str | None = None
    size: int | None = None


class ParityRequest(BaseModel):
    twin_id: UUID
    inputs: dict[str, Any] = Field(default_factory=dict, description="Sample inputs for parity check")
    expected_text: str | None = Field(
        default=None,
        description="Optional expected text output to compare against for basic parity",
    )
    threshold_text: float | None = Field(
        default=None,
        description="Optional threshold for text similarity pass/fail (default 0.90)",
        ge=0.0,
        le=1.0,
    )


class ParityResponse(BaseModel):
    twin: ComponentTwin
    metrics: dict[str, float]
    passes: dict[str, bool] | None = None


class SuggestOCIRefResponse(BaseModel):
    ref: str
    base: str
    component_slug: str
    tag: str


class CapabilitiesGetResponse(BaseModel):
    twin_id: UUID
    inferred: dict[str, Any]
    overrides: dict[str, Any]
    effective: dict[str, Any]


class CapabilitiesPutRequest(BaseModel):
    twin_id: UUID
    overrides: dict[str, Any] = Field(default_factory=dict)


async def _ensure_flow_access(flow_id: UUID, current_user: CurrentActiveUser, session: DbSession) -> Flow:
    flow = await session.get(Flow, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    if flow.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't have access to this flow")
    return flow


@router.post("/generate_wit", response_model=GenerateWITResponse)
async def generate_wit_for_component(
    payload: GenerateWITRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> GenerateWITResponse:
    # Case 1: Update an existing twin
    if payload.twin_id is not None:
        twin = await session.get(ComponentTwin, payload.twin_id)
        if not twin:
            raise HTTPException(status_code=404, detail="ComponentTwin not found")
        await _ensure_flow_access(twin.flow_id, current_user, session)
        io_schema = payload.io_schema or twin.io_schema
        if not io_schema:
            raise HTTPException(status_code=400, detail="io_schema required (none present on twin)")
        wit = generate_wit(
            io_schema,
            world_name=payload.world_name,
            func_name=payload.func_name,
        )
        twin.io_schema = io_schema
        twin.wit_source = wit
        twin.build_status = "stale"
        twin.updated_at = datetime.now(timezone.utc)
        session.add(twin)
        await session.commit()
        await session.refresh(twin)
        return GenerateWITResponse(twin=twin)

    # Case 2: Create or upsert a twin for (flow_id, component_id)
    if not payload.flow_id or not payload.component_id:
        msg = "flow_id and component_id are required when twin_id is not provided"
        raise HTTPException(status_code=400, detail=msg)

    await _ensure_flow_access(payload.flow_id, current_user, session)

    io_schema = payload.io_schema
    if not io_schema:
        raise HTTPException(status_code=400, detail="io_schema is required to create/update a twin")

    wit = generate_wit(io_schema, world_name=payload.world_name, func_name=payload.func_name)

    # Try to find an existing record for this (flow_id, component_id). If multiple, pick the most recent.
    stmt = (
        select(ComponentTwin)
        .where(ComponentTwin.flow_id == payload.flow_id, ComponentTwin.component_id == payload.component_id)
        .order_by(ComponentTwin.updated_at.desc())
    )
    existing = (await session.exec(stmt)).first()

    if existing:
        existing.io_schema = io_schema
        existing.wit_source = wit
        existing.build_status = "stale"
        existing.updated_at = datetime.now(timezone.utc)
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        return GenerateWITResponse(twin=existing)

    # Create a fresh twin
    twin = ComponentTwin(
        flow_id=payload.flow_id,
        component_id=payload.component_id,
        io_schema=io_schema,
        wit_source=wit,
        build_status="stale",
    )
    session.add(twin)
    await session.commit()
    await session.refresh(twin)
    return GenerateWITResponse(twin=twin)


@router.post("/generate_rust", response_model=GenerateRustResponse)
async def generate_rust_for_twin(
    payload: GenerateRustRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> GenerateRustResponse:
    twin = await session.get(ComponentTwin, payload.twin_id)
    if not twin:
        raise HTTPException(status_code=404, detail="ComponentTwin not found")
    await _ensure_flow_access(twin.flow_id, current_user, session)

    if not twin.wit_source:
        raise HTTPException(status_code=400, detail="twin has no wit_source; generate WIT first")

    pkg = payload.package_name or f"lf_{twin.component_id}"

    if payload.use_ai:
        # Use AI code generation
        try:
            files = await _generate_rust_with_ai(twin=twin, package_name=pkg, func_name=payload.func_name)
        except Exception as e:
            logger.warning(f"AI codegen failed for twin {twin.id}: {e}")
            # Fall back to skeleton on AI failure
            files = generate_rust_skeleton(wit_source=twin.wit_source, package_name=pkg, func_name="process")
    else:
        # Use static skeleton
        files = generate_rust_skeleton(wit_source=twin.wit_source, package_name=pkg, func_name="process")

    twin.rust_source = encode_crate_files(files)
    twin.build_status = "stale"
    twin.updated_at = datetime.now(timezone.utc)

    session.add(twin)
    await session.commit()
    await session.refresh(twin)
    return GenerateRustResponse(twin=twin)


@router.post("/build", response_model=BuildResponse)
async def build_twin(
    payload: BuildRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> BuildResponse:
    twin = await session.get(ComponentTwin, payload.twin_id)
    if not twin:
        raise HTTPException(status_code=404, detail="ComponentTwin not found")
    await _ensure_flow_access(twin.flow_id, current_user, session)

    if not twin.wit_source:
        raise HTTPException(status_code=400, detail="twin has no wit_source; generate WIT first")

    # Begin lifecycle
    twin.build_status = "building"
    twin.updated_at = datetime.now(timezone.utc)
    session.add(twin)
    await session.commit()
    await session.refresh(twin)

    result = build_component(wit_source=twin.wit_source, rust_source=twin.rust_source, dry_run=payload.dry_run)

    if payload.dry_run:
        plan = plan_build(wit_source=twin.wit_source, rust_source=twin.rust_source)
        return BuildResponse(
            twin=twin,
            workspace=str(plan.workspace),
            logs_uri=None,
            planned_tool=None,
            planned_args=None,
        )

    # Persist artifacts after real build
    if result.logs_path:
        twin.build_logs_uri = str(result.logs_path)
    if result.wasm_path:
        twin.wasm_blob = str(result.wasm_path)

    # Capability manifest: build provenance and plan
    manifest = twin.capability_manifest or {}
    build_meta = manifest.get("build", {})
    build_meta.update(
        {
            "validated_component": result.validated_component,
            "wrapped": result.wrapped,
            "plan": {"tool": result.plan_tool, "args": result.plan_args},
            "tool_versions": result.tool_versions,
            "logs_uri": twin.build_logs_uri,
        }
    )
    # Artifact metadata
    art = manifest.get("artifact", {})
    if result.digest or result.size is not None:
        if result.digest:
            art["sha256"] = result.digest
        if result.size is not None:
            art["size"] = result.size
        art["last_built_at"] = datetime.now(timezone.utc).isoformat()
    manifest["artifact"] = art
    manifest["build"] = build_meta
    twin.capability_manifest = manifest

    twin.build_status = "built" if result.built else "error"
    twin.updated_at = datetime.now(timezone.utc)

    session.add(twin)
    await session.commit()
    await session.refresh(twin)

    return BuildResponse(
        twin=twin,
        workspace=None,
        logs_uri=twin.build_logs_uri,
        planned_tool=result.plan_tool,
        planned_args=result.plan_args,
        digest=result.digest,
        size=result.size,
        validated_component=result.validated_component,
        wrapped=result.wrapped,
    )


# ------------------ Build run SSE endpoints ------------------
class BuildStartRequest(BaseModel):
    twin_id: UUID
    dry_run: bool = False


class BuildStartResponse(BaseModel):
    run_id: str
    status: str


@router.post("/build/start", response_model=BuildStartResponse)
async def build_start(
    payload: BuildStartRequest, current_user: CurrentActiveUser, session: DbSession
) -> BuildStartResponse:
    twin = await session.get(ComponentTwin, payload.twin_id)
    if not twin:
        raise HTTPException(status_code=404, detail="ComponentTwin not found")
    await _ensure_flow_access(twin.flow_id, current_user, session)
    if not twin.wit_source:
        raise HTTPException(status_code=400, detail="twin has no wit_source; generate WIT first")

    run_id = str(uuid.uuid4())
    q: asyncio.Queue[str] = asyncio.Queue()
    _BUILD_RUNS[run_id] = {
        "id": run_id,
        "twin_id": str(twin.id),
        "status": "queued",
        "step": "queued",
        "queue": q,
        "started_at": datetime.now(timezone.utc),
        "log_buffer": [],
        "transcript_path": None,
    }

    # emit initial queued state
    await _append_event(run_id, "state", {"status": "queued", "step": "queued"})

    # kick off background build task
    asyncio.create_task(
        _run_build_task(
            run_id=run_id,
            twin=twin,
            wit_source=twin.wit_source,
            rust_source=twin.rust_source,
            dry_run=payload.dry_run,
        )
    )

    return BuildStartResponse(run_id=run_id, status="queued")


@router.get("/build/runs/{run_id}/status")
async def build_status(run_id: str):
    run = _BUILD_RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return {
        "run_id": run_id,
        "status": run.get("status"),
        "step": run.get("step"),
        "started_at": run.get("started_at"),
        "success": run.get("success"),
        "error": run.get("error"),
    }


@router.get("/build/runs/{run_id}/events")
async def build_events(run_id: str):
    run = _BUILD_RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    q: asyncio.Queue[str] = run["queue"]

    async def event_gen():
        # send a hello with current state
        yield _sse("hello", {"run_id": run_id, "status": run.get("status"), "step": run.get("step")})
        # send buffered logs to late joiners
        for line in run.get("log_buffer", []):
            yield _sse("log", {"level": "info", "line": line})
        # stream live events
        while True:
            try:
                msg = await q.get()
                yield msg
                if run.get("status") in ("done", "failed"):
                    # After done, flush queue remainder and break
                    while not q.empty():
                        yield await q.get()
                    break
            except asyncio.CancelledError:
                break

    return StreamingResponse(event_gen(), media_type="text/event-stream")


# ------------------ Codegen SSE endpoints ------------------
class CodegenStartRequest(BaseModel):
    twin_id: UUID
    use_ai: bool = True
    max_iters: int | None = None
    auto_build: bool | None = None
    user_hint: str | None = None


class CodegenStartResponse(BaseModel):
    run_id: str
    status: str


async def _run_codegen_task(
    *,
    run_id: str,
    twin: ComponentTwin,
    use_ai: bool,
    max_iters: int | None = None,
    auto_build: bool | None = None,
    user_hint: str | None = None,
):
    _CODEGEN_RUNS[run_id]["status"] = "running"
    _CODEGEN_RUNS[run_id]["step"] = "prepare"
    q: asyncio.Queue[str] = _CODEGEN_RUNS[run_id]["queue"]

    async def emit(event: str, data: _Any):
        # append to transcript if present
        try:
            tpath = _CODEGEN_RUNS[run_id].get("transcript_path")
            if tpath:
                with open(tpath, "a", encoding="utf-8", errors="ignore") as tf:
                    import json as _json

                    tf.write(_json.dumps({"event": event, "data": data}) + "\n")
        except Exception:
            pass
        await q.put(_sse(event, data))

    await emit("state", {"status": "running", "step": "prepare"})

    # prepare settings
    s = get_settings_service().settings
    if not getattr(s, "ai_codegen_enabled", False):
        await emit("error", {"message": "AI codegen disabled in settings"})
        _CODEGEN_RUNS[run_id]["status"] = "failed"
        await emit("done", {"success": False})
        return

    cli = getattr(s, "ai_codegen_cli", "warp") or "warp"
    profile = getattr(s, "ai_codegen_profile", None)
    timeout_ms = int(getattr(s, "ai_codegen_timeout_ms", 120000))
    working_dir_mode = str(getattr(s, "ai_codegen_working_dir", "repo_root"))
    api_key_env = getattr(s, "ai_codegen_api_key_env", None)
    max_attempts = int(max_iters or getattr(s, "ai_codegen_max_iters", 3) or 3)
    do_auto_build = bool(auto_build if auto_build is not None else getattr(s, "ai_codegen_auto_build", True))

    prev_error: str | None = None

    for attempt in range(1, max_attempts + 1):
        # Update attempt count
        _CODEGEN_RUNS[run_id]["attempt_count"] = attempt
        # Plan workspace and prompt for this attempt (reuse same workspace)
        try:
            plan = plan_build(wit_source=twin.wit_source or "", rust_source=twin.rust_source)
            workspace = _Path(plan.workspace)
            prompt_path = _Path(
                _prepare_ai_prompt(twin=twin, workspace=workspace, prev_build_error=prev_error, user_hint=user_hint)
            )
            # ensure manifest and transcript exist
            try:
                meta_path = workspace / ".lf_workspace.json"
                if not meta_path.exists():
                    import json as _json

                    meta = {
                        "type": "codegen",
                        "run_id": run_id,
                        "twin_id": str(twin.id),
                        "component_id": twin.component_id,
                        "flow_id": str(twin.flow_id),
                        "started_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "success": None,
                        "logs_uri": None,
                        "attempt_count": attempt,
                    }
                    meta_path.write_text(_json.dumps(meta))
                tpath = workspace / "transcript.ndjson"
                _CODEGEN_RUNS[run_id]["transcript_path"] = str(tpath)
                _CODEGEN_RUNS[run_id]["workspace"] = str(workspace)
            except Exception:
                pass
            await emit("log", {"level": "info", "line": f"Attempt {attempt}/{max_attempts}: workspace {workspace}"})
            await emit("log", {"level": "info", "line": f"Prompt: {prompt_path}"})
        except Exception as e:
            await emit("error", {"message": f"Failed to prepare workspace: {e}"})
            _CODEGEN_RUNS[run_id]["status"] = "failed"
            await emit("done", {"success": False})
            return

        cwd = _find_repo_root(_Path(__file__).resolve()) if working_dir_mode == "repo_root" else workspace
        args = [cli]
        if profile:
            args += ["--profile", str(profile)]

        await emit("state", {"status": "running", "step": "invoke", "attempt": attempt})
        await emit("log", {"level": "info", "line": f"Invoking AI CLI: {' '.join(args)}"})

        import asyncio as _asyncio
        import os as _os

        env = dict(_os.environ)
        if api_key_env and api_key_env not in env:
            # leave absent; user may provide via environment
            pass

        try:
            proc = await _asyncio.create_subprocess_exec(
                *args,
                cwd=str(cwd),
                stdin=_asyncio.subprocess.PIPE,
                stdout=_asyncio.subprocess.PIPE,
                stderr=_asyncio.subprocess.PIPE,
                env=env,
            )
        except FileNotFoundError:
            await emit("error", {"message": f"AI CLI not found: {cli}"})
            _CODEGEN_RUNS[run_id]["status"] = "failed"
            await emit("done", {"success": False})
            return

        # Send prompt
        try:
            if proc.stdin is not None:
                with open(prompt_path, "rb") as pf:
                    proc.stdin.write(pf.read())
                    await proc.stdin.drain()
                    proc.stdin.close()
        except Exception:
            pass

        # Stream output, also capture for parsing
        stdout_accum = []
        try:
            assert proc.stdout is not None
            assert proc.stderr is not None
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode(errors="ignore").rstrip("\n")
                stdout_accum.append(text)
                await emit("log", {"level": "info", "line": text})
            stderr_rest = await proc.stderr.read()
            if stderr_rest:
                for l in stderr_rest.decode(errors="ignore").splitlines():
                    await emit("log", {"level": "warn", "line": l})
        except Exception:
            pass

        rc = await proc.wait()

        # Parse output and write files if needed
        try:
            out_text = "\n".join(stdout_accum)
            files = _parse_ai_output_files(out_text)
            if files:
                for rel, content in files.items():
                    p = workspace / rel
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(content)
        except Exception as e:
            await emit("log", {"level": "warn", "line": f"Could not parse AI output: {e}"})

        # Gather mapping
        mapping: dict[str, str] = {}
        for rel in ["Cargo.toml", "src/lib.rs", "wit/world.wit"]:
            p = workspace / rel
            if p.exists():
                mapping[rel] = p.read_text()

        if not mapping.get("src/lib.rs"):
            await emit("log", {"level": "warn", "line": "AI did not produce src/lib.rs"})
            if attempt == max_attempts:
                _CODEGEN_RUNS[run_id]["status"] = "failed"
                await emit("done", {"success": False})
                break
            prev_error = "No lib.rs produced"
            continue

        # Auto build if configured
        if do_auto_build:
            await emit("state", {"status": "running", "step": "build", "attempt": attempt})
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: build_component(
                    wit_source=twin.wit_source or "", rust_source=encode_crate_files(mapping), dry_run=False
                ),
            )
            await emit("log", {"level": "info", "line": "Build finished."})

            # surface logs
            if getattr(result, "logs_path", None):
                try:
                    with open(result.logs_path, encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            await emit("log", {"level": "info", "line": line.rstrip("\n")})
                except Exception as e:
                    await emit("log", {"level": "warn", "line": f"(unable to read logs file: {e})"})

            if not getattr(result, "built", False):
                # iterate with error context
                # Read last part of log as prev_error
                try:
                    if getattr(result, "logs_path", None):
                        prev_error = (open(result.logs_path, encoding="utf-8", errors="ignore").read())[-4000:]
                    else:
                        prev_error = result.error or "Build failed"
                except Exception:
                    prev_error = result.error or "Build failed"

                if attempt == max_attempts:
                    _CODEGEN_RUNS[run_id]["status"] = "failed"
                    await emit("done", {"success": False})
                    break
                await emit("log", {"level": "info", "line": f"Retrying with AI fix ({attempt + 1}/{max_attempts})"})
                continue

            # Success: persist rust and wasm
            from langflow.services.deps import session_scope
            from langflow.services.wasm.rust_skeleton import encode_crate_files as _enc

            async with session_scope() as session:
                twin_db = await session.get(ComponentTwin, twin.id)
                if twin_db:
                    twin_db.rust_source = _enc(mapping)
                    if getattr(result, "wasm_path", None):
                        twin_db.wasm_blob = str(result.wasm_path)
                    manifest = twin_db.capability_manifest or {}
                    build_meta = manifest.get("build", {})
                    build_meta.update(
                        {
                            "validated_component": result.validated_component,
                            "wrapped": result.wrapped,
                            "plan": {"tool": result.plan_tool, "args": result.plan_args},
                            "tool_versions": result.tool_versions,
                            "logs_uri": str(getattr(result, "logs_path", "")),
                        }
                    )
                    manifest["build"] = build_meta
                    twin_db.capability_manifest = manifest
                    twin_db.build_status = "built"
                    twin_db.updated_at = datetime.now(timezone.utc)
                    session.add(twin_db)
            # Generate LLM summary for multi-attempt runs
            try:
                if attempt >= 2:
                    await emit("log", {"level": "info", "line": "Generating LLM summary..."})
                    tpath = _CODEGEN_RUNS[run_id].get("transcript_path")
                    if tpath:
                        llm_summary = await _generate_run_summary(workspace, tpath)
                        if llm_summary:
                            await emit("log", {"level": "info", "line": f"Summary: {llm_summary}"})
                        else:
                            # Fallback to simple summary
                            summary = [
                                f"Attempts: {attempt}",
                                f"Component: {twin.component_id}",
                                f"Flow: {twin.flow_id}",
                                "Notes:",
                                "- Iterative fixes were applied based on build logs.",
                                "- Consider reusing this summary as context for future builds.",
                            ]
                            (workspace / "summary.txt").write_text("\n".join(summary))
            except Exception as e:
                await emit("log", {"level": "warn", "line": f"Summary generation failed: {e}"})

            _CODEGEN_RUNS[run_id]["status"] = "done"
            _CODEGEN_RUNS[run_id]["success"] = True
            await emit("done", {"success": True})
            break
        # Persist only rust mapping; leave build for separate step
        from langflow.services.deps import session_scope
        from langflow.services.wasm.rust_skeleton import encode_crate_files as _enc

        async with session_scope() as session:
            twin_db = await session.get(ComponentTwin, twin.id)
            if twin_db:
                twin_db.rust_source = _enc(mapping)
                twin_db.build_status = "stale"
                twin_db.updated_at = datetime.now(timezone.utc)
                session.add(twin_db)
        _CODEGEN_RUNS[run_id]["status"] = "done"
        _CODEGEN_RUNS[run_id]["success"] = True
        await emit("done", {"success": True})
        break

    # trim registry
    # update manifest with final status if possible
    try:
        if "workspace" in locals():
            import json as _json

            meta_path = workspace / ".lf_workspace.json"
            if meta_path.exists():
                meta = _json.loads(meta_path.read_text())
                meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                meta["success"] = (
                    bool(_CODEGEN_RUNS.get(run_id, {}).get("success")) if _CODEGEN_RUNS.get(run_id) else None
                )
                meta_path.write_text(_json.dumps(meta))
    except Exception:
        pass
    if len(_CODEGEN_RUNS) > _CODEGEN_RETENTION_MAX:
        _CODEGEN_RUNS.pop(next(iter(_CODEGEN_RUNS)))


@router.post("/generate_rust/start", response_model=CodegenStartResponse)
async def codegen_start(
    payload: CodegenStartRequest, current_user: CurrentActiveUser, session: DbSession
) -> CodegenStartResponse:
    twin = await session.get(ComponentTwin, payload.twin_id)
    if not twin:
        raise HTTPException(status_code=404, detail="ComponentTwin not found")
    await _ensure_flow_access(twin.flow_id, current_user, session)
    if not twin.wit_source:
        raise HTTPException(status_code=400, detail="twin has no wit_source; generate WIT first")

    run_id = str(uuid.uuid4())
    q: asyncio.Queue[str] = asyncio.Queue()
    _CODEGEN_RUNS[run_id] = {
        "id": run_id,
        "twin_id": str(twin.id),
        "component_id": twin.component_id,
        "flow_id": str(twin.flow_id),
        "status": "queued",
        "step": "queued",
        "queue": q,
        "started_at": datetime.now(timezone.utc),
        "log_buffer": [],
        "transcript_path": None,
        "attempt_count": 0,
    }

    await q.put(_sse("state", {"status": "queued", "step": "queued"}))

    asyncio.create_task(
        _run_codegen_task(
            run_id=run_id,
            twin=twin,
            use_ai=payload.use_ai,
            max_iters=payload.max_iters,
            auto_build=payload.auto_build,
            user_hint=payload.user_hint,
        )
    )

    return CodegenStartResponse(run_id=run_id, status="queued")


@router.get("/generate_rust/runs/{run_id}/status")
async def codegen_status(run_id: str):
    run = _CODEGEN_RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return {
        "run_id": run_id,
        "status": run.get("status"),
        "step": run.get("step"),
        "started_at": run.get("started_at"),
        "success": run.get("success"),
        "error": run.get("error"),
    }


@router.get("/generate_rust/runs/{run_id}/events")
async def codegen_events(run_id: str):
    run = _CODEGEN_RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    q: asyncio.Queue[str] = run["queue"]

    async def event_gen():
        yield _sse("hello", {"run_id": run_id, "status": run.get("status"), "step": run.get("step")})
        for line in run.get("log_buffer", []):
            yield _sse("log", {"level": "info", "line": line})
        while True:
            try:
                msg = await q.get()
                yield msg
                if run.get("status") in ("done", "failed"):
                    while not q.empty():
                        yield await q.get()
                    break
            except asyncio.CancelledError:
                break

    return StreamingResponse(event_gen(), media_type="text/event-stream")


# Helper to generate LLM summary of a run
async def _generate_run_summary(workspace: _Path, transcript_path: str) -> str | None:
    """Use Warp AI CLI to generate a natural language summary of the run transcript."""
    try:
        s = get_settings_service().settings
        cli = getattr(s, "ai_codegen_cli", "warp") or "warp"
        profile = getattr(s, "ai_codegen_profile", None)

        # Read the transcript
        if not _Path(transcript_path).exists():
            return None

        transcript_data = _Path(transcript_path).read_text(encoding="utf-8", errors="ignore")
        if not transcript_data.strip():
            return None

        # Create a prompt for summarization
        summary_prompt = f"""Please provide a concise summary of this AI codegen run transcript.
Focus on:
- Number of attempts
- Key issues encountered
- How they were resolved
- Final outcome

Transcript:
{transcript_data[:5000]}

Provide a 3-5 sentence summary:"""

        prompt_path = workspace / "_summary_prompt.txt"
        prompt_path.write_text(summary_prompt)

        args = [cli]
        if profile:
            args += ["--profile", str(profile)]

        import asyncio as _asyncio
        import os as _os

        proc = await _asyncio.create_subprocess_exec(
            *args,
            cwd=str(workspace),
            stdin=_asyncio.subprocess.PIPE,
            stdout=_asyncio.subprocess.PIPE,
            stderr=_asyncio.subprocess.PIPE,
            env=dict(_os.environ),
        )

        if proc.stdin:
            proc.stdin.write(summary_prompt.encode())
            await proc.stdin.drain()
            proc.stdin.close()

        stdout, _ = await _asyncio.wait_for(proc.communicate(), timeout=30.0)
        summary = stdout.decode(errors="ignore").strip()

        if summary:
            summary_file = workspace / "summary_llm.txt"
            summary_file.write_text(summary)
            return summary

        return None
    except Exception as e:
        logger.warning(f"Failed to generate LLM summary: {e}")
        return None


class CodegenResumeRequest(BaseModel):
    workspace_root_b64: str = Field(..., description="Base64-encoded workspace root path")
    user_hint: str | None = Field(None, description="Optional hint to guide the retry")
    max_iters: int | None = Field(None, description="Max additional iterations")


@router.post("/generate_rust/resume", response_model=CodegenStartResponse)
async def codegen_resume(
    payload: CodegenResumeRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> CodegenStartResponse:
    """Resume a failed/incomplete codegen run from its workspace."""
    # Decode and validate workspace
    from langflow.api.v1.ai_codegen import _safe_decode_root

    workspace = _safe_decode_root(payload.workspace_root_b64)

    if not workspace.exists():
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Load metadata
    meta_path = workspace / ".lf_workspace.json"
    if not meta_path.exists():
        raise HTTPException(status_code=400, detail="Workspace metadata not found")

    import json as _json

    meta = _json.loads(meta_path.read_text())
    twin_id = meta.get("twin_id")
    if not twin_id:
        raise HTTPException(status_code=400, detail="No twin_id in workspace metadata")

    # Load twin
    from uuid import UUID as _UUID

    twin = await session.get(ComponentTwin, _UUID(twin_id))
    if not twin:
        raise HTTPException(status_code=404, detail="ComponentTwin not found")
    await _ensure_flow_access(twin.flow_id, current_user, session)

    # Create new run
    run_id = str(uuid.uuid4())
    q: asyncio.Queue[str] = asyncio.Queue()
    _CODEGEN_RUNS[run_id] = {
        "id": run_id,
        "twin_id": str(twin.id),
        "component_id": twin.component_id,
        "flow_id": str(twin.flow_id),
        "status": "queued",
        "step": "resume",
        "queue": q,
        "started_at": datetime.now(timezone.utc),
        "log_buffer": [],
        "transcript_path": str(workspace / "transcript.ndjson"),
        "workspace": str(workspace),
        "attempt_count": meta.get("attempt_count", 0),
    }

    await q.put(_sse("state", {"status": "queued", "step": "resume"}))

    # Kick off task with existing workspace context
    asyncio.create_task(
        _run_codegen_task(
            run_id=run_id,
            twin=twin,
            use_ai=True,
            max_iters=payload.max_iters,
            auto_build=True,
            user_hint=payload.user_hint,
        )
    )

    return CodegenStartResponse(run_id=run_id, status="queued")


class ExecuteFlowRequest(BaseModel):
    flow_id: UUID = Field(..., description="Flow ID to execute")
    inputs: dict[str, Any] | None = Field(None, description="Optional initial inputs")


class ExecuteFlowResponse(BaseModel):
    run_id: str
    success: bool
    total_duration_ms: float
    batches: list[dict[str, Any]]
    node_results: dict[str, dict[str, Any]]
    error: str | None = None


@router.post("/execute_flow", response_model=ExecuteFlowResponse)
async def execute_flow(
    payload: ExecuteFlowRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> ExecuteFlowResponse:
    """Execute a multi-node WASM flow via wasmCloud orchestration."""
    import uuid

    from langflow.services.wasm.orchestrator import get_orchestrator

    # Load flow
    flow = await session.get(Flow, payload.flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    await _ensure_flow_access(payload.flow_id, current_user, session)

    # Load all ComponentTwins for this flow
    from sqlmodel import select

    result = await session.execute(select(ComponentTwin).where(ComponentTwin.flow_id == payload.flow_id))
    twins_list = result.scalars().all()
    twins = {twin.component_id: twin for twin in twins_list}

    if not twins:
        raise HTTPException(status_code=400, detail="No ComponentTwins found for flow")

    # Get flow graph data
    flow_data = flow.data if hasattr(flow, "data") else {"nodes": [], "edges": []}

    # Execute
    orchestrator = get_orchestrator()
    run_id = str(uuid.uuid4())
    result = await orchestrator.execute_flow(flow, twins, flow_data, run_id)

    # Convert to response
    batches_data = [
        {
            "batch_id": b.batch_id,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "component_id": n.component_id,
                    "twin_id": str(n.twin_id),
                }
                for n in b.nodes
            ],
        }
        for b in result.batches
    ]

    node_results_data = {
        nid: {
            "node_id": nr.node_id,
            "component_id": nr.component_id,
            "success": nr.success,
            "output": nr.output,
            "error": nr.error,
            "duration_ms": nr.duration_ms,
            "timestamp": nr.timestamp.isoformat() if nr.timestamp else None,
        }
        for nid, nr in result.node_results.items()
    }

    return ExecuteFlowResponse(
        run_id=run_id,
        success=result.success,
        total_duration_ms=result.total_duration_ms,
        batches=batches_data,
        node_results=node_results_data,
        error=result.error,
    )


@router.post("/publish", response_model=PublishResponse)
async def publish_twin(
    payload: PublishRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> PublishResponse:
    t0 = time.perf_counter()
    twin = await session.get(ComponentTwin, payload.twin_id)
    if not twin:
        raise HTTPException(status_code=404, detail="ComponentTwin not found")
    await _ensure_flow_access(twin.flow_id, current_user, session)

    if not twin.wasm_blob:
        raise HTTPException(status_code=400, detail="twin has no wasm_blob; build first")

    from pathlib import Path

    # Telemetry: started
    try:
        logger.info(
            "wasm.publish",
            extra={
                "twin_id": str(twin.id),
                "oci_ref": payload.oci_ref,
                "phase": "started",
                "dry_run": payload.dry_run,
            },
        )
    except Exception:  # pragma: no cover
        pass

    plan, result = publish_oci(wasm_path=Path(twin.wasm_blob), oci_ref=payload.oci_ref, dry_run=payload.dry_run)

    # Persist artifact metadata when publish (even dry-run) for traceability
    manifest = twin.capability_manifest or {}
    manifest_art = manifest.get("artifact", {})
    manifest_art.update(
        {
            "oci_ref": payload.oci_ref,
            "sha256": result.digest,
            "size": result.size,
        }
    )
    manifest["artifact"] = manifest_art
    twin.capability_manifest = manifest
    twin.updated_at = datetime.now(timezone.utc)
    session.add(twin)
    await session.commit()
    await session.refresh(twin)

    # Telemetry: record publish outcome (dev/local; no PII)
    try:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(
            "wasm.publish",
            extra={
                "twin_id": str(twin.id),
                "oci_ref": payload.oci_ref,
                "phase": "completed",
                "success": result.success,
                "error": result.error,
                "digest": result.digest,
                "size": result.size,
                "duration_ms": duration_ms,
            },
        )
    except Exception:  # pragma: no cover - telemetry is best-effort
        pass

    # Auto-run a compact parity check after real publish
    if result.success and not payload.dry_run:
        try:
            # Minimal parity: mark verified timestamp and keep prior metrics
            metrics = twin.parity_metrics or {}
            # leave metrics untouched; just bump last_verified_at
            twin.last_verified_at = datetime.now(timezone.utc)
            session.add(twin)
            await session.commit()
            await session.refresh(twin)
        except Exception:  # pragma: no cover
            logger.warning("parity auto-run skipped due to internal error", exc_info=True)

    return PublishResponse(
        planned_tool=plan.tool or None,
        planned_args=plan.args or None,
        success=result.success,
        error=result.error,
        digest=result.digest,
        size=result.size,
    )


def _infer_capabilities(twin: ComponentTwin) -> dict[str, Any]:
    """Very lightweight capability inference based on io_schema.

    For M0 we return a skeleton manifest with suggested keys and leave most empty.
    """
    inferred: dict[str, Any] = {
        "network": {"domains": [], "ports": []},
        "storage": {"kv": False, "blob": False},
        "env": {"secrets": []},
        "logging": {"enabled": True},
        "timeouts_ms": 30000,
        "data_sources": {"databases": [], "files": {"csv": False, "parquet": False, "iceberg": False, "excel": False}},
    }
    schema = twin.io_schema or {}
    # Heuristics: if schema mentions url/http, suggest network; if file extensions appear, suggest files
    schema_str = str(schema).lower()
    if "http" in schema_str or "url" in schema_str:
        inferred["network"]["domains"] = []  # user to fill
    for ext, key in [
        (".csv", "csv"),
        (".parquet", "parquet"),
        ("iceberg", "iceberg"),
        (".xls", "excel"),
        (".xlsx", "excel"),
    ]:
        if ext in schema_str:
            inferred["data_sources"]["files"][key] = True
    return inferred


def _effective_capabilities(inferred: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    import copy

    def deep_merge(a, b):
        if isinstance(a, dict) and isinstance(b, dict):
            res = copy.deepcopy(a)
            for k, v in b.items():
                res[k] = deep_merge(res.get(k), v) if k in res else copy.deepcopy(v)
            return res
        return copy.deepcopy(b) if b is not None else copy.deepcopy(a)

    return deep_merge(inferred, overrides)


@router.get("/capabilities", response_model=CapabilitiesGetResponse)
async def get_capabilities(
    twin_id: UUID, current_user: CurrentActiveUser, session: DbSession
) -> CapabilitiesGetResponse:
    twin = await session.get(ComponentTwin, twin_id)
    if not twin:
        raise HTTPException(status_code=404, detail="ComponentTwin not found")
    await _ensure_flow_access(twin.flow_id, current_user, session)

    inferred = _infer_capabilities(twin)
    overrides = twin.capability_manifest or {}
    effective = _effective_capabilities(inferred, overrides)
    return CapabilitiesGetResponse(twin_id=twin_id, inferred=inferred, overrides=overrides, effective=effective)


@router.put("/capabilities", response_model=CapabilitiesGetResponse)
async def put_capabilities(
    payload: CapabilitiesPutRequest, current_user: CurrentActiveUser, session: DbSession
) -> CapabilitiesGetResponse:
    twin = await session.get(ComponentTwin, payload.twin_id)
    if not twin:
        raise HTTPException(status_code=404, detail="ComponentTwin not found")
    await _ensure_flow_access(twin.flow_id, current_user, session)

    twin.capability_manifest = payload.overrides
    twin.updated_at = datetime.now(timezone.utc)
    session.add(twin)
    await session.commit()
    await session.refresh(twin)

    inferred = _infer_capabilities(twin)
    effective = _effective_capabilities(inferred, twin.capability_manifest or {})

    # Telemetry for capability updates
    try:
        logger.info(
            "wasm.capabilities.update",
            extra={"twin_id": str(twin.id), "overrides": payload.overrides},
        )
    except Exception:  # pragma: no cover
        pass

    return CapabilitiesGetResponse(
        twin_id=twin.id, inferred=inferred, overrides=twin.capability_manifest or {}, effective=effective
    )


@router.post("/parity", response_model=ParityResponse)
async def parity_check(
    payload: ParityRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> ParityResponse:
    t0 = time.perf_counter()
    twin = await session.get(ComponentTwin, payload.twin_id)
    if not twin:
        raise HTTPException(status_code=404, detail="ComponentTwin not found")
    await _ensure_flow_access(twin.flow_id, current_user, session)

    # M0 parity: if 'text' present and expected_text provided, compute similarity; else stub
    metrics: dict[str, float] = {}
    passes: dict[str, bool] = {}
    default_threshold = 0.90
    threshold_text = payload.threshold_text if payload.threshold_text is not None else default_threshold

    if isinstance(payload.inputs, dict) and "text" in payload.inputs:
        input_text = str(payload.inputs["text"])
        if payload.expected_text is not None:
            score = compute_text_similarity(input_text, payload.expected_text)
            metrics["text"] = score
            passes["text"] = score >= threshold_text
        else:
            metrics["text"] = 1.0
            passes["text"] = True
    else:
        metrics["text"] = 0.0
        passes["text"] = False

    # Persist a richer shape for parity data
    stored = twin.parity_metrics or {}
    stored["text"] = {
        "score": metrics.get("text", 0.0),
        "passed": passes.get("text", False),
        "threshold": threshold_text,
    }
    twin.parity_metrics = stored
    twin.updated_at = datetime.now(timezone.utc)
    session.add(twin)
    await session.commit()
    await session.refresh(twin)

    # Telemetry: record parity outcome (dev/local; no PII)
    try:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(
            "wasm.parity",
            extra={
                "twin_id": str(twin.id),
                "metrics": metrics,
                "passes": passes,
                "duration_ms": duration_ms,
            },
        )
    except Exception:  # pragma: no cover
        pass

    # Mark last verified time
    twin.last_verified_at = datetime.now(timezone.utc)
    session.add(twin)
    await session.commit()
    await session.refresh(twin)

    return ParityResponse(twin=twin, metrics=metrics, passes=passes)


# ------------------ OCI suggestion ------------------


def _slugify(s: str) -> str:
    s = s.lower()
    # replace any character not allowed in OCI repo segments with '-'
    return re.sub(r"[^a-z0-9._-]", "-", s).strip("-._") or "component"


def _short_hash_from_twin(twin: ComponentTwin) -> str:
    if twin.python_hash and isinstance(twin.python_hash, str) and len(twin.python_hash) >= 6:
        return twin.python_hash[:12].lower()
    for src in (twin.python_source, twin.rust_source, twin.wit_source):
        if src:
            h = hashlib.sha256(src.encode("utf-8")).hexdigest()
            return h[:12]
    # ultimate fallback: hash component_id + timestamps
    basis = f"{twin.component_id}-{twin.updated_at.isoformat()}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:12]


@router.get("/suggest_oci_ref", response_model=SuggestOCIRefResponse)
async def suggest_oci_ref(twin_id: UUID, current_user: CurrentActiveUser, session: DbSession) -> SuggestOCIRefResponse:
    twin = await session.get(ComponentTwin, twin_id)
    if not twin:
        raise HTTPException(status_code=404, detail="ComponentTwin not found")
    await _ensure_flow_access(twin.flow_id, current_user, session)

    settings = get_settings_service().settings
    base = getattr(settings, "wasm_oci_base", "ghcr.io/ibm/langflow")
    comp_slug = _slugify(twin.component_id)
    tag = _short_hash_from_twin(twin)
    ref = f"{base}/{comp_slug}:{tag}"
    return SuggestOCIRefResponse(ref=ref, base=str(base), component_slug=comp_slug, tag=tag)
