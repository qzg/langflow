from __future__ import annotations

import asyncio
import base64
import time
from contextlib import suppress
from typing import Any

import orjson
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.deps import (
    get_settings_service,
    get_variable_service,
    get_wasmcloud_service,
)
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE

router = APIRouter(prefix="/wasmcloud", tags=["WASM/wasmCloud"])


class WasmCloudSettingsResponse(BaseModel):
    wasmcloud_enabled: bool
    wasmcloud_nats_url: str
    wasmcloud_lattice: str
    wasmcloud_timeout_ms: int
    # Do not echo creds path back; expose presence flag instead
    wasmcloud_creds_path: str | None = None
    wasmcloud_creds_present: bool | None = None


class WasmCloudSettingsUpdate(BaseModel):
    wasmcloud_enabled: bool | None = None
    wasmcloud_nats_url: str | None = None
    wasmcloud_lattice: str | None = None
    wasmcloud_timeout_ms: int | None = None
    wasmcloud_creds_path: str | None = None


class TestConnectionResponse(BaseModel):
    configured: bool
    available: bool
    connected: bool
    latency_ms: float | None = None
    error: str | None = None
    details: dict[str, Any] | None = None


@router.get("/settings", response_model=WasmCloudSettingsResponse)
async def get_settings(current_user: CurrentActiveUser, session: DbSession) -> WasmCloudSettingsResponse:
    """Return effective wasmCloud settings.

    Reads current SettingsService values and overlays DB variables for the current user if present.
    Does not return secret values; instead, indicates presence with a boolean.
    """
    settings_svc = get_settings_service()
    var_svc = get_variable_service()
    s = settings_svc.settings

    # Start from Settings values
    enabled = bool(getattr(s, "wasmcloud_enabled", False))
    nats_url = str(getattr(s, "wasmcloud_nats_url", "nats://127.0.0.1:4222"))
    lattice = str(getattr(s, "wasmcloud_lattice", "default"))
    timeout_ms = int(getattr(s, "wasmcloud_timeout_ms", 30000))
    creds_present = False

    # Overlay from DB variables when available
    with suppress(Exception):
        # list once to avoid many queries
        vars_read = await var_svc.get_all(user_id=current_user.id, session=session)
        m = {v.name: (v.value or "") for v in vars_read}
        if "wasmcloud_enabled" in m:
            enabled = m["wasmcloud_enabled"].lower() in {"1", "true", "yes", "on"}
        if m.get("wasmcloud_nats_url"):
            nats_url = m["wasmcloud_nats_url"]
        if m.get("wasmcloud_lattice"):
            lattice = m["wasmcloud_lattice"]
        if "wasmcloud_timeout_ms" in m and m["wasmcloud_timeout_ms"].isdigit():
            timeout_ms = int(m["wasmcloud_timeout_ms"])
        if "wasmcloud_creds_path" in m:
            creds_present = True

    return WasmCloudSettingsResponse(
        wasmcloud_enabled=enabled,
        wasmcloud_nats_url=nats_url,
        wasmcloud_lattice=lattice,
        wasmcloud_timeout_ms=timeout_ms,
        wasmcloud_creds_path=None,  # never echo back
        wasmcloud_creds_present=creds_present,
    )


@router.put("/settings", response_model=WasmCloudSettingsResponse)
async def set_settings(
    payload: WasmCloudSettingsUpdate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> WasmCloudSettingsResponse:
    """Persist wasmCloud settings to DB variables and update in-memory settings for immediate effect."""
    settings_svc = get_settings_service()
    var_svc = get_variable_service()
    s = settings_svc.settings

    updates = payload.model_dump(exclude_unset=True)

    # Persist to DB (upsert behavior)
    existing_names: list[str] = []
    with suppress(Exception):
        existing_names = await var_svc.list_variables(user_id=current_user.id, session=session)

    for key, value in updates.items():
        # normalize to string storage for variables
        str_value: str
        if isinstance(value, bool):
            str_value = "true" if value else "false"
        else:
            str_value = str(value) if value is not None else ""

        if key in existing_names:
            await var_svc.update_variable(current_user.id, key, str_value, session)
        else:
            vtype = CREDENTIAL_TYPE if key == "wasmcloud_creds_path" else GENERIC_TYPE
            await var_svc.create_variable(
                user_id=current_user.id,
                name=key,
                value=str_value,
                default_fields=[],
                type_=vtype,
                session=session,
            )
        # Update in-memory settings for immediate effectiveness (non-secret)
        with suppress(Exception):
            setattr(s, key, value)

    # Return effective values after update
    return await get_settings(current_user=current_user, session=session)


@router.get("/test_connection", response_model=TestConnectionResponse)
async def test_connection() -> TestConnectionResponse:
    svc = get_wasmcloud_service()

    configured = bool(svc.is_configured())
    available = bool(svc.is_available())

    if not configured:
        return TestConnectionResponse(
            configured=False,
            available=available,
            connected=False,
            error="wasmCloud integration disabled",
        )

    if not available:
        return TestConnectionResponse(
            configured=True,
            available=False,
            connected=False,
            error="nats-py not installed or unavailable",
        )

    start = time.monotonic()
    try:
        # Enforce a 10-second timeout for the probe connect
        await asyncio.wait_for(svc.connect(), timeout=10.0)
        latency_ms = (time.monotonic() - start) * 1000.0
        # Immediately disconnect for a lightweight probe
        await svc.disconnect()
        return TestConnectionResponse(
            configured=True,
            available=True,
            connected=True,
            latency_ms=latency_ms,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "configured": True,
                "available": True,
                "connected": False,
                "error": "timeout waiting for NATS connect (10s)",
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"configured": True, "available": True, "connected": False, "error": str(exc)},
        ) from exc


class InvokeRequest(BaseModel):
    component_id: str = Field(..., description="Component ID as known to the lattice")
    operation: str = Field(..., description="Operation name (subject segment) for wRPC call")
    payload_b64: str | None = Field(None, description="Base64-encoded payload bytes")
    payload_text: str | None = Field(None, description="UTF-8 text payload")
    payload_json: Any | None = Field(None, description="JSON payload; will be encoded as UTF-8 JSON bytes")
    timeout_ms: int | None = Field(None, description="Optional per-call timeout override in milliseconds")
    lattice: str | None = Field(None, description="Optional lattice override for this call")


class InvokeResponse(BaseModel):
    success: bool
    latency_ms: float | None = None
    data_b64: str | None = None
    data_text: str | None = None
    error: str | None = None


@router.post("/invoke", response_model=InvokeResponse)
async def invoke(req: InvokeRequest) -> InvokeResponse:
    svc = get_wasmcloud_service()

    if not svc.is_configured():
        return InvokeResponse(success=False, error="wasmCloud integration disabled")
    if not svc.is_available():
        return InvokeResponse(success=False, error="nats-py not installed or unavailable")

    # Derive payload bytes
    payload: bytes
    if req.payload_b64 is not None:
        try:
            payload = base64.b64decode(req.payload_b64)
        except Exception as exc:  # noqa: BLE001
            return InvokeResponse(success=False, error=f"Invalid base64 payload: {exc}")
    elif req.payload_json is not None:
        try:
            payload = orjson.dumps(req.payload_json)
        except Exception as exc:  # noqa: BLE001
            return InvokeResponse(success=False, error=f"Invalid JSON payload: {exc}")
    elif req.payload_text is not None:
        payload = req.payload_text.encode("utf-8")
    else:
        payload = b""

    start = time.monotonic()
    try:
        data = await svc.call_component(
            req.component_id,
            req.operation,
            payload,
            timeout_ms=req.timeout_ms,
            lattice_override=req.lattice,
        )
        latency_ms = (time.monotonic() - start) * 1000.0
        # Return both b64 and best-effort utf-8
        data_b64 = base64.b64encode(data).decode("ascii")
        data_text: str | None
        try:
            data_text = data.decode("utf-8")
        except UnicodeDecodeError:
            data_text = None
        return InvokeResponse(success=True, latency_ms=latency_ms, data_b64=data_b64, data_text=data_text)
    except Exception as exc:  # noqa: BLE001
        return InvokeResponse(success=False, error=str(exc))
