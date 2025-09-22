from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.component_twin.model import ComponentTwin
from langflow.services.database.models.flow.model import Flow

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
    flow_id: Annotated[UUID | None, Query(default=None)],
    component_id: Annotated[str | None, Query(default=None)],
    python_hash: Annotated[str | None, Query(default=None)],
    build_status: Annotated[str | None, Query(default=None)],
    limit: Annotated[int, Query(default=100, ge=1, le=500)],
    offset: Annotated[int, Query(default=0, ge=0)],
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
