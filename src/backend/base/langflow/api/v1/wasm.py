from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.component_twin.model import ComponentTwin
from langflow.services.database.models.flow.model import Flow
from langflow.services.wasm.build import build_component, plan_build
from langflow.services.wasm.parity import compute_text_similarity
from langflow.services.wasm.publish import publish_oci
from langflow.services.wasm.rust_skeleton import encode_crate_files, generate_rust_skeleton
from langflow.services.wasm.wit_generator import generate_wit

router = APIRouter(prefix="/wasm", tags=["WASM/WIT"])


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


class GenerateRustResponse(BaseModel):
    twin: ComponentTwin


class BuildRequest(BaseModel):
    twin_id: UUID
    dry_run: bool = Field(default=False, description="When true, prepare workspace only and do not invoke cargo")


class BuildResponse(BaseModel):
    twin: ComponentTwin
    workspace: str | None = Field(None, description="Path of the temp workspace when dry_run=true")
    logs_uri: str | None = None


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

    result = build_component(wit_source=twin.wit_source, rust_source=twin.rust_source, dry_run=payload.dry_run)

    if payload.dry_run:
        plan = plan_build(wit_source=twin.wit_source, rust_source=twin.rust_source)
        return BuildResponse(twin=twin, workspace=str(plan.workspace), logs_uri=None)

    # Persist artifacts after real build
    if result.logs_path:
        twin.build_logs_uri = str(result.logs_path)
    if result.wasm_path:
        twin.wasm_blob = str(result.wasm_path)
    twin.build_status = "built" if result.built else "error"
    twin.updated_at = datetime.now(timezone.utc)

    session.add(twin)
    await session.commit()
    await session.refresh(twin)

    return BuildResponse(twin=twin, workspace=None, logs_uri=twin.build_logs_uri)


@router.post("/publish", response_model=PublishResponse)
async def publish_twin(
    payload: PublishRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> PublishResponse:
    twin = await session.get(ComponentTwin, payload.twin_id)
    if not twin:
        raise HTTPException(status_code=404, detail="ComponentTwin not found")
    await _ensure_flow_access(twin.flow_id, current_user, session)

    if not twin.wasm_blob:
        raise HTTPException(status_code=400, detail="twin has no wasm_blob; build first")

    from pathlib import Path

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

    return PublishResponse(
        planned_tool=plan.tool or None,
        planned_args=plan.args or None,
        success=result.success,
        error=result.error,
        digest=result.digest,
        size=result.size,
    )


@router.post("/parity", response_model=ParityResponse)
async def parity_check(
    payload: ParityRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> ParityResponse:
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

    return ParityResponse(twin=twin, metrics=metrics, passes=passes)
