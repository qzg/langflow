from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import status

if TYPE_CHECKING:
    import pytest
    from httpx import AsyncClient


async def _create_flow(client: AsyncClient, headers: dict) -> str:
    payload = {"name": f"publish-flow-{uuid.uuid4()}", "description": "test flow for publish dry run", "data": {}}
    resp = await client.post("api/v1/flows/", json=payload, headers=headers)
    assert resp.status_code in (status.HTTP_201_CREATED, status.HTTP_200_OK)
    body = resp.json()
    assert "id" in body
    return body["id"]


async def test_wasm_publish_dry_run_with_oras(monkeypatch: pytest.MonkeyPatch, client: AsyncClient, logged_in_headers):
    # Pretend oras is available on PATH to validate plan generation
    from langflow.services.wasm import publish as publish_mod

    monkeypatch.setattr(publish_mod.shutil, "which", lambda name: "/usr/bin/oras" if name == "oras" else None)

    flow_id = await _create_flow(client, logged_in_headers)

    # Create a minimal twin with a wasm_blob path so the publish endpoint accepts it
    create_twin_payload = {
        "flow_id": flow_id,
        "component_id": "Node-Echo",
        "wit_source": "world component { export process: func(input: input) -> output }",
        "wasm_blob": "/tmp/fake.wasm",  # noqa: S108
        "build_status": "built",
    }
    resp = await client.post("api/v1/component_twins", json=create_twin_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    twin = resp.json()

    pub_payload = {"twin_id": twin["id"], "oci_ref": "ghcr.io/qzg/lf-component:test", "dry_run": True}
    resp = await client.post("/api/v1/wasm/publish", json=pub_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK

    body = resp.json()
    assert body["success"] is True
    assert body["planned_tool"]
    assert body["planned_args"] is not None
    assert "push" in body["planned_args"]


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


async def test_wasm_publish_non_dry_run_success(
    monkeypatch: pytest.MonkeyPatch,
    client: AsyncClient,
    logged_in_headers,
):
    # Pretend oras is available and publish succeeds without actually running the command
    from langflow.services.wasm import publish as publish_mod

    monkeypatch.setattr(publish_mod.shutil, "which", lambda name: "/usr/bin/oras" if name == "oras" else None)

    def _fake_run(*_args, **_kwargs):
        return None

    monkeypatch.setattr(publish_mod.subprocess, "run", _fake_run)

    flow_id = await _create_flow(client, logged_in_headers)

    create_twin_payload = {
        "flow_id": flow_id,
        "component_id": "Node-Echo",
        "wit_source": "world component { export process: func(input: input) -> output }",
        "wasm_blob": "/tmp/fake.wasm",  # noqa: S108
        "build_status": "built",
    }
    resp = await client.post("api/v1/component_twins", json=create_twin_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    twin = resp.json()

    pub_payload = {"twin_id": twin["id"], "oci_ref": "ghcr.io/qzg/lf-component:test", "dry_run": False}
    resp = await client.post("/api/v1/wasm/publish", json=pub_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK

    body = resp.json()
    assert body["success"] is True


async def test_wasm_build_dry_run_workspace(client: AsyncClient, logged_in_headers):
    flow_id = await _create_flow(client, logged_in_headers)
    wit_payload = {
        "flow_id": flow_id,
        "component_id": "Node-Echo",
        "io_schema": {"inputs": [{"name": "text", "type": "string"}], "outputs": [{"name": "text", "type": "string"}]},
    }
    resp = await client.post("api/v1/wasm/generate_wit", json=wit_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    twin = resp.json()["twin"]

    rust_payload = {"twin_id": twin["id"], "package_name": "lf_node_echo"}
    resp = await client.post("/api/v1/wasm/generate_rust", json=rust_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK

    build_payload = {"twin_id": twin["id"], "dry_run": True}
    resp = await client.post("/api/v1/wasm/build", json=build_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["workspace"]
    assert isinstance(body["workspace"], str)
