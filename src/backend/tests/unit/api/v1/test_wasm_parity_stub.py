from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import status

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _create_flow(client: AsyncClient, headers: dict) -> str:
    payload = {"name": f"parity-flow-{uuid.uuid4()}", "description": "test flow for parity stub", "data": {}}
    resp = await client.post("api/v1/flows/", json=payload, headers=headers)
    assert resp.status_code in (status.HTTP_201_CREATED, status.HTTP_200_OK)
    body = resp.json()
    assert "id" in body
    return body["id"]


async def test_parity_stub_text_equals_1(client: AsyncClient, logged_in_headers):
    flow_id = await _create_flow(client, logged_in_headers)
    wit_payload = {
        "flow_id": flow_id,
        "component_id": "Node-Echo",
        "io_schema": {"inputs": [{"name": "text", "type": "string"}], "outputs": [{"name": "text", "type": "string"}]},
    }
    resp = await client.post("api/v1/wasm/generate_wit", json=wit_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    twin = resp.json()["twin"]

    parity_payload = {"twin_id": twin["id"], "inputs": {"text": "hello"}}
    resp = await client.post("api/v1/wasm/parity", json=parity_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["twin"]["id"] == twin["id"]
    assert body["metrics"]["text"] == 1.0
    assert body["passes"]["text"] is True


async def test_parity_expected_text_similarity(client: AsyncClient, logged_in_headers):
    flow_id = await _create_flow(client, logged_in_headers)
    wit_payload = {
        "flow_id": flow_id,
        "component_id": "Node-Echo",
        "io_schema": {"inputs": [{"name": "text", "type": "string"}], "outputs": [{"name": "text", "type": "string"}]},
    }
    resp = await client.post("api/v1/wasm/generate_wit", json=wit_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    twin = resp.json()["twin"]

    parity_payload = {"twin_id": twin["id"], "inputs": {"text": "hello world"}, "expected_text": "hello world"}
    resp = await client.post("api/v1/wasm/parity", json=parity_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["metrics"]["text"] == 1.0
    assert body["passes"]["text"] is True
