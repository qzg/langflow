from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.component_twin.model import ComponentTwin
from langflow.services.database.models.flow.model import Flow
from langflow.services.wasm.builder import BuildResult, build_twin
from langflow.services.wasm.wit import synthesize_wit_from_io_schema

router = APIRouter(prefix="/component_twins", tags=["Component Twins"])


class ComponentTwinCreate(BaseModel):
    flow_id: UUID
    component_id: str
    python_hash: str | None = None
    python_source: str | None = None
    io_schema: dict[str, Any] | None = None
    wit_source: str | None = None
    rust_source: str | None = None
    wasm_blob: str | None = None
    capability_manifest: dict[str, Any] | None = None
    build_status: str | None = Field(default=None, description="stale|building|built|error")
    build_logs_uri: str | None = None
    last_verified_at: datetime | None = None
    determinism_mode: str | None = None
    parity_metrics: dict[str, Any] | None = None


class ComponentTwinUpdate(BaseModel):
    python_hash: str | None = None
    python_source: str | None = None
    io_schema: dict[str, Any] | None = None
    wit_source: str | None = None
    rust_source: str | None = None
    wasm_blob: str | None = None
    capability_manifest: dict[str, Any] | None = None
    build_status: str | None = Field(default=None, description="stale|building|built|error")
    build_logs_uri: str | None = None
    last_verified_at: datetime | None = None
    determinism_mode: str | None = None
    parity_metrics: dict[str, Any] | None = None


async def _ensure_flow_access(flow_id: UUID, current_user: CurrentActiveUser, session: AsyncSession) -> Flow:
    flow = await session.get(Flow, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    if flow.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't have access to this flow")
    return flow


@router.post("", response_model=ComponentTwin)
@router.post("/", response_model=ComponentTwin)
async def create_component_twin(
    payload: ComponentTwinCreate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> ComponentTwin:
    await _ensure_flow_access(payload.flow_id, current_user, session)

    record = ComponentTwin(**payload.model_dump())
    # Force timestamps
    now = datetime.now(timezone.utc)
    record.created_at = now
    record.updated_at = now

    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


@router.get("/{twin_id}", response_model=ComponentTwin)
async def get_component_twin(
    twin_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> ComponentTwin:
    record = await session.get(ComponentTwin, twin_id)
    if not record:
        raise HTTPException(status_code=404, detail="ComponentTwin not found")
    await _ensure_flow_access(record.flow_id, current_user, session)
    return record


@router.get("", response_model=list[ComponentTwin])
@router.get("/", response_model=list[ComponentTwin])
async def list_component_twins(
    current_user: CurrentActiveUser,
    session: DbSession,
    flow_id: Annotated[UUID | None, Query()] = None,
    component_id: Annotated[str | None, Query()] = None,
    python_hash: Annotated[str | None, Query()] = None,
    build_status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ComponentTwin]:
    # Build filters
    filt = []
    if flow_id:
        # check access
        await _ensure_flow_access(flow_id, current_user, session)
        filt.append(ComponentTwin.flow_id == flow_id)
    else:
        # If no flow_id specified, scope to user's flows
        # Join against Flow to filter by user
        stmt = select(ComponentTwin).join(Flow, ComponentTwin.flow_id == Flow.id).where(Flow.user_id == current_user.id)
        if component_id:
            stmt = stmt.where(col(ComponentTwin.component_id) == component_id)
        if python_hash:
            stmt = stmt.where(col(ComponentTwin.python_hash) == python_hash)
        if build_status:
            stmt = stmt.where(col(ComponentTwin.build_status) == build_status)
        stmt = stmt.order_by(ComponentTwin.updated_at.desc()).limit(limit).offset(offset)
        return (await session.exec(stmt)).all()

    if component_id:
        filt.append(col(ComponentTwin.component_id) == component_id)
    if python_hash:
        filt.append(col(ComponentTwin.python_hash) == python_hash)
    if build_status:
        filt.append(col(ComponentTwin.build_status) == build_status)

    stmt = (
        select(ComponentTwin).where(and_(*filt)).order_by(ComponentTwin.updated_at.desc()).limit(limit).offset(offset)
    )
    return (await session.exec(stmt)).all()


class GenerateWitRequest(BaseModel):
    flow_id: UUID | None = None
    component_id: str | None = None
    world_name: str | None = None
    io_schema: dict[str, Any] | None = None


def _extract_io_schema_from_flow_data(flow_data: dict, component_id: str) -> dict[str, Any]:
    # Very lightweight extractor: look for node with matching id and read data.node.template
    # Fallback to a simple string->string schema
    nodes = (flow_data or {}).get("data", {}).get("nodes", []) if isinstance(flow_data, dict) else []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        data = n.get("data")
        if not isinstance(data, dict):
            continue
        node = data.get("node")
        if not isinstance(node, dict):
            continue
        nid = n.get("id") or node.get("id")
        if nid != component_id:
            continue
        tmpl = node.get("template")
        if not isinstance(tmpl, dict):
            break
        inputs: list[dict[str, Any]] = []
        for key, meta in sorted(tmpl.items()):
            if isinstance(meta, dict):
                t = meta.get("type") or meta.get("input_type") or "string"
                inputs.append({"name": key, "type": str(t)})
        return {"inputs": inputs, "outputs": [{"type": "string"}]}
    return {"inputs": [{"name": "data", "type": "string"}], "outputs": [{"type": "string"}]}


@router.post("/{twin_id}/generate_wit", response_model=ComponentTwin)
async def generate_wit_for_twin(
    twin_id: UUID,
    payload: GenerateWitRequest | None,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> ComponentTwin:
    record = await session.get(ComponentTwin, twin_id)
    if not record:
        raise HTTPException(status_code=404, detail="ComponentTwin not found")
    await _ensure_flow_access(record.flow_id, current_user, session)

    # Determine io_schema
    io_schema = (payload.io_schema if payload else None) or _extract_io_schema_from_flow_data(
        (await session.get(Flow, record.flow_id)).data if await session.get(Flow, record.flow_id) else {},
        record.component_id,
    )
    wit = synthesize_wit_from_io_schema(io_schema, world_name=(payload.world_name if payload else None) or "component")

    record.wit_source = wit
    record.updated_at = datetime.now(timezone.utc)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


@router.post("/generate_wit", response_model=ComponentTwin)
async def generate_wit(
    payload: GenerateWitRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> ComponentTwin:
    if not payload.flow_id or not payload.component_id:
        raise HTTPException(status_code=400, detail="flow_id and component_id are required")
    flow = await _ensure_flow_access(payload.flow_id, current_user, session)

    # find or create twin
    stmt = select(ComponentTwin).where(
        (ComponentTwin.flow_id == payload.flow_id) & (col(ComponentTwin.component_id) == payload.component_id)
    )
    existing = (await session.exec(stmt)).first()
    if existing is None:
        existing = ComponentTwin(flow_id=payload.flow_id, component_id=payload.component_id)

    io_schema = payload.io_schema or _extract_io_schema_from_flow_data(flow.data or {}, payload.component_id)
    wit = synthesize_wit_from_io_schema(io_schema, world_name=payload.world_name or "component")

    existing.wit_source = wit
    existing.io_schema = io_schema
    existing.updated_at = datetime.now(timezone.utc)

    session.add(existing)
    await session.commit()
    await session.refresh(existing)
    return existing


@router.post("/{twin_id}/build", response_model=ComponentTwin)
async def build_component_twin(
    twin_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> ComponentTwin:
    record = await session.get(ComponentTwin, twin_id)
    if not record:
        raise HTTPException(status_code=404, detail="ComponentTwin not found")
    await _ensure_flow_access(record.flow_id, current_user, session)

    # mark building
    record.build_status = "building"
    record.updated_at = datetime.now(timezone.utc)
    session.add(record)
    await session.commit()

    result: BuildResult = await build_twin(session, record)
    if not result.ok:
        # do not expose internal error details beyond message
        record = await session.get(ComponentTwin, twin_id)
        assert record is not None
        record.build_status = "error"
        record.build_logs_uri = result.logs_uri
        record.updated_at = datetime.now(timezone.utc)
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record

    # record already refreshed by builder
    return await session.get(ComponentTwin, twin_id)  # type: ignore[return-value]


@router.post("/{twin_id}/evaluate", response_model=ComponentTwin)
async def evaluate_component_twin(
    twin_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> ComponentTwin:
    """Compute basic parity/determinism metrics.

    This implementation uses a lightweight heuristic until a full execution harness
    is available: sets io_consistency to 1.0 when an io_schema exists and marks
    determinism_mode to 'strict' when the build is 'built'.
    """
    record = await session.get(ComponentTwin, twin_id)
    if not record:
        raise HTTPException(status_code=404, detail="ComponentTwin not found")
    await _ensure_flow_access(record.flow_id, current_user, session)

    parity = {"io_consistency": 1.0 if record.io_schema else 0.0}
    mode = "strict" if record.build_status == "built" else "nondet"

    record.parity_metrics = parity
    record.determinism_mode = mode
    record.updated_at = datetime.now(timezone.utc)

    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


@router.patch("/{twin_id}", response_model=ComponentTwin)
async def update_component_twin(
    twin_id: UUID,
    payload: ComponentTwinUpdate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> ComponentTwin:
    record = await session.get(ComponentTwin, twin_id)
    if not record:
        raise HTTPException(status_code=404, detail="ComponentTwin not found")
    await _ensure_flow_access(record.flow_id, current_user, session)

    for key, val in payload.model_dump(exclude_unset=True).items():
        setattr(record, key, val)
    record.updated_at = datetime.now(timezone.utc)

    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record
