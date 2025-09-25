from __future__ import annotations

import base64
import time
from typing import Any

import orjson
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from langflow.services.deps import get_settings_service, get_wasmcloud_service

router = APIRouter(prefix="/wasmcloud", tags=["WASM/wasmCloud"])


class WasmCloudSettingsResponse(BaseModel):
    wasmcloud_enabled: bool
    wasmcloud_nats_url: str
    wasmcloud_lattice: str
    wasmcloud_timeout_ms: int
    wasmcloud_creds_path: str | None = None


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
async def get_settings() -> WasmCloudSettingsResponse:
    svc = get_settings_service()
    s = svc.settings
    return WasmCloudSettingsResponse(
        wasmcloud_enabled=bool(getattr(s, "wasmcloud_enabled", False)),
        wasmcloud_nats_url=str(getattr(s, "wasmcloud_nats_url", "nats://127.0.0.1:4222")),
        wasmcloud_lattice=str(getattr(s, "wasmcloud_lattice", "default")),
        wasmcloud_timeout_ms=int(getattr(s, "wasmcloud_timeout_ms", 30000)),
        wasmcloud_creds_path=getattr(s, "wasmcloud_creds_path", None),
    )


@router.put("/settings", response_model=WasmCloudSettingsResponse)
async def set_settings(payload: WasmCloudSettingsUpdate) -> WasmCloudSettingsResponse:
    svc = get_settings_service()
    s = svc.settings
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(s, key, value)
    # Return effective values after update
    return await get_settings()


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
        await svc.connect()
        latency_ms = (time.monotonic() - start) * 1000.0
        # Immediately disconnect for a lightweight probe
        await svc.disconnect()
        return TestConnectionResponse(
            configured=True,
            available=True,
            connected=True,
            latency_ms=latency_ms,
        )
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
        data = await svc.call_component(req.component_id, req.operation, payload, timeout_ms=req.timeout_ms)
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
