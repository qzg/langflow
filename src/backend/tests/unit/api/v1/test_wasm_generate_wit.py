from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import status

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _create_flow(client: AsyncClient, headers: dict) -> str:
    payload = {
        "name": f"witgen-flow-{uuid.uuid4()}",
        "description": "test flow for wit generation",
        "data": {},
    }
    resp = await client.post("api/v1/flows/", json=payload, headers=headers)
    assert resp.status_code in (status.HTTP_201_CREATED, status.HTTP_200_OK)
    body = resp.json()
    assert "id" in body
    return body["id"]


async def test_generate_wit_creates_twin(client: AsyncClient, logged_in_headers):
    flow_id = await _create_flow(client, logged_in_headers)
    payload = {
        "flow_id": flow_id,
        "component_id": "Node-Echo",
        "io_schema": {"inputs": [{"name": "text", "type": "string"}], "outputs": [{"name": "text", "type": "string"}]},
        "world_name": "echo",
        "func_name": "process",
    }
    resp = await client.post("api/v1/wasm/generate_wit", json=payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert "twin" in body
    twin = body["twin"]
    assert twin["flow_id"] == flow_id
    assert twin["component_id"] == "Node-Echo"
    assert twin["build_status"] == "stale"
    assert isinstance(twin["wit_source"], str)
    assert "world echo" in twin["wit_source"]
