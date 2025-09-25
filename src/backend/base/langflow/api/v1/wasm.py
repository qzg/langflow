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
