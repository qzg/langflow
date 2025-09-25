from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import status

if TYPE_CHECKING:
    from httpx import AsyncClient


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
