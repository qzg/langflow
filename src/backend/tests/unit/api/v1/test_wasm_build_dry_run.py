from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import status

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _create_flow(client: AsyncClient, headers: dict) -> str:
    payload = {"name": f"build-flow-{uuid.uuid4()}", "description": "test flow for build dry run", "data": {}}
    resp = await client.post("api/v1/flows/", json=payload, headers=headers)
    assert resp.status_code in (status.HTTP_201_CREATED, status.HTTP_200_OK)
    body = resp.json()
    assert "id" in body
    return body["id"]


async def test_build_dry_run(client: AsyncClient, logged_in_headers):
    flow_id = await _create_flow(client, logged_in_headers)
    # WIT first
    wit_payload = {
        "flow_id": flow_id,
        "component_id": "Node-Echo",
        "io_schema": {"inputs": [{"name": "text", "type": "string"}], "outputs": [{"name": "text", "type": "string"}]},
    }
    resp = await client.post("api/v1/wasm/generate_wit", json=wit_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    twin = resp.json()["twin"]

    # Dry run build
    build_payload = {"twin_id": twin["id"], "dry_run": True}
    resp = await client.post("api/v1/wasm/build", json=build_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["twin"]["id"] == twin["id"]
    assert isinstance(body.get("workspace"), str)
    assert len(body["workspace"]) > 0
