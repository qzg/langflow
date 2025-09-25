from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import status

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _create_flow(client: AsyncClient, headers: dict) -> str:
    payload = {"name": f"publish-flow-{uuid.uuid4()}", "description": "test flow for publish dry run", "data": {}}
    resp = await client.post("api/v1/flows/", json=payload, headers=headers)
    assert resp.status_code in (status.HTTP_201_CREATED, status.HTTP_200_OK)
    body = resp.json()
    assert "id" in body
    return body["id"]


async def test_publish_dry_run_requires_wasm(client: AsyncClient, logged_in_headers):
    flow_id = await _create_flow(client, logged_in_headers)
    # WIT only, no build
    wit_payload = {
        "flow_id": flow_id,
        "component_id": "Node-Echo",
        "io_schema": {"inputs": [{"name": "text", "type": "string"}], "outputs": [{"name": "text", "type": "string"}]},
    }
    resp = await client.post("api/v1/wasm/generate_wit", json=wit_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    twin = resp.json()["twin"]

    pub_payload = {"twin_id": twin["id"], "oci_ref": "ghcr.io/example/lf-echo:dev", "dry_run": True}
    resp = await client.post("api/v1/wasm/publish", json=pub_payload, headers=logged_in_headers)
    # Expect 400: needs build first
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
