from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import status

if TYPE_CHECKING:
    from httpx import AsyncClient


@pytest.mark.asyncio
async def test_wasmcloud_settings_get_put_and_masking(client, logged_in_headers):
    # Initial GET
    resp = await client.get("/api/v1/wasmcloud/settings", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert set(body.keys()) >= {
        "wasmcloud_enabled",
        "wasmcloud_nats_url",
        "wasmcloud_lattice",
        "wasmcloud_timeout_ms",
        "wasmcloud_creds_path",
        "wasmcloud_creds_present",
    }
    assert body["wasmcloud_creds_path"] is None
    assert body.get("wasmcloud_creds_present") in (False, None)

    # Update non-secret fields
    payload = {
        "wasmcloud_enabled": True,
        "wasmcloud_nats_url": "nats://localhost:4222",
        "wasmcloud_lattice": "alpha",
        "wasmcloud_timeout_ms": 40000,
    }
    resp = await client.put("/api/v1/wasmcloud/settings", json=payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["wasmcloud_enabled"] is True
    assert body["wasmcloud_nats_url"] == "nats://localhost:4222"
    assert body["wasmcloud_lattice"] == "alpha"
    assert body["wasmcloud_timeout_ms"] == 40000
    assert body["wasmcloud_creds_path"] is None
    assert body.get("wasmcloud_creds_present") in (False, None)

    # Set creds path and verify masking + presence flag
    resp = await client.put(
        "/api/v1/wasmcloud/settings",
        json={"wasmcloud_creds_path": "test.creds"},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["wasmcloud_creds_path"] is None
    assert body["wasmcloud_creds_present"] is True

    # GET again: should reflect presence True
    resp = await client.get("/api/v1/wasmcloud/settings", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["wasmcloud_creds_path"] is None
    assert body["wasmcloud_creds_present"] is True


@pytest.mark.asyncio
async def test_wasmcloud_test_connection_configured_flag(client, logged_in_headers):
    # Without enabling, configured should be False or True depending on defaults; we only ensure the endpoint responds
    resp = await client.get("/api/v1/wasmcloud/test_connection", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert "configured" in body
    assert "available" in body
    assert "connected" in body


async def test_wasmcloud_settings_get(client: AsyncClient, logged_in_headers):
    resp = await client.get("/api/v1/wasmcloud/settings", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    for key in [
        "wasmcloud_enabled",
        "wasmcloud_nats_url",
        "wasmcloud_lattice",
        "wasmcloud_timeout_ms",
        "wasmcloud_creds_path",
    ]:
        assert key in body


async def test_wasmcloud_settings_put_roundtrip(client: AsyncClient, logged_in_headers):
    # Flip enabled and set a different lattice, then read back
    upd = {"wasmcloud_enabled": True, "wasmcloud_lattice": "test-lattice"}
    resp = await client.put("/api/v1/wasmcloud/settings", json=upd, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["wasmcloud_enabled"] is True
    assert body["wasmcloud_lattice"] == "test-lattice"
