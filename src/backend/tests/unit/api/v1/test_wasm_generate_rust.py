from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import status

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _create_flow(client: AsyncClient, headers: dict) -> str:
    payload = {"name": f"rustgen-flow-{uuid.uuid4()}", "description": "test flow for rust generation", "data": {}}
    resp = await client.post("api/v1/flows/", json=payload, headers=headers)
    assert resp.status_code in (status.HTTP_201_CREATED, status.HTTP_200_OK)
    body = resp.json()
    assert "id" in body
    return body["id"]


async def test_generate_rust_from_wit(client: AsyncClient, logged_in_headers):
    flow_id = await _create_flow(client, logged_in_headers)
    # First create a WIT twin
    wit_payload = {
        "flow_id": flow_id,
        "component_id": "Node-Echo",
        "io_schema": {"inputs": [{"name": "text", "type": "string"}], "outputs": [{"name": "text", "type": "string"}]},
        "world_name": "echo",
        "func_name": "process",
    }
    resp = await client.post("api/v1/wasm/generate_wit", json=wit_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    twin = resp.json()["twin"]

    # Now generate Rust skeleton
    rust_payload = {"twin_id": twin["id"], "package_name": "lf_echo", "func_name": "process"}
    resp = await client.post("api/v1/wasm/generate_rust", json=rust_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    twin2 = resp.json()["twin"]

    assert twin2["id"] == twin["id"]
    assert isinstance(twin2["rust_source"], str)
    assert "Cargo.toml" in twin2["rust_source"]
