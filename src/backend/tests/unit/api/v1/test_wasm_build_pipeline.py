from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import status

if TYPE_CHECKING:
    import pytest
    from httpx import AsyncClient


async def _create_flow(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "api/v1/flows/",
        json={"name": "build-pipeline", "description": "test wasm build pipeline", "data": {}},
        headers=headers,
    )
    assert resp.status_code in (status.HTTP_201_CREATED, status.HTTP_200_OK)
    return resp.json()["id"]


async def test_wasm_build_success_happy_path(monkeypatch: pytest.MonkeyPatch, client: AsyncClient, logged_in_headers):
    # Arrange: create flow and twin with WIT and Rust
    flow_id = await _create_flow(client, logged_in_headers)
    wit_payload = {
        "flow_id": flow_id,
        "component_id": "Node-Echo",
        "io_schema": {"inputs": [{"name": "text", "type": "string"}], "outputs": [{"name": "text", "type": "string"}]},
    }
    resp = await client.post("/api/v1/wasm/generate_wit", json=wit_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    twin = resp.json()["twin"]

    resp = await client.post(
        "/api/v1/wasm/generate_rust",
        json={"twin_id": twin["id"], "package_name": "lf_node_echo"},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK

    # Monkeypatch planner to create a fake workspace and wasm artifact; skip external tools
    import langflow.services.wasm.build as build_mod

    real_plan_build = build_mod.plan_build

    def fake_plan_build(*, wit_source: str, rust_source: str | None):
        plan = real_plan_build(wit_source=wit_source, rust_source=rust_source)
        target = Path(plan.workspace) / "target"
        target.mkdir(parents=True, exist_ok=True)
        (target / "fake.wasm").write_bytes(b"00asm\x01\x00\x00\x00")
        return plan

    monkeypatch.setattr(build_mod, "plan_build", fake_plan_build)
    monkeypatch.setattr(
        build_mod, "plan_build_command", lambda: build_mod.BuildCommandPlan(tool="/usr/bin/cargo", args=["build"])
    )

    import shutil as _sh

    monkeypatch.setattr(_sh, "which", lambda _name: None)  # no wasm-tools

    import subprocess as _sp

    def _fake_run(*_args, **_kwargs):
        return None

    monkeypatch.setattr(_sp, "run", _fake_run)

    # Act: build
    resp = await client.post(
        "/api/v1/wasm/build", json={"twin_id": twin["id"], "dry_run": False}, headers=logged_in_headers
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()

    # Assert response surface
    assert body["twin"]["build_status"] == "built"
    assert body["logs_uri"]
    assert body["digest"]
    assert isinstance(body["size"], int)

    # Fetch twin back and check metadata persisted
    resp = await client.get(f"/api/v1/component_twins/{twin['id']}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    twin2 = resp.json()
    manifest = twin2.get("capability_manifest", {})
    assert manifest.get("artifact", {}).get("sha256") == body["digest"]
    assert manifest.get("artifact", {}).get("size") == body["size"]
    build_meta = manifest.get("build", {})
    assert "plan" in build_meta
    assert "tool_versions" in build_meta


async def test_wasm_build_error_path(monkeypatch: pytest.MonkeyPatch, client: AsyncClient, logged_in_headers):
    # Arrange
    flow_id = await _create_flow(client, logged_in_headers)
    wit_payload = {
        "flow_id": flow_id,
        "component_id": "Node-Err",
        "io_schema": {"inputs": [{"name": "text", "type": "string"}], "outputs": [{"name": "text", "type": "string"}]},
    }
    resp = await client.post("/api/v1/wasm/generate_wit", json=wit_payload, headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    twin = resp.json()["twin"]

    import langflow.services.wasm.build as build_mod

    real_plan_build = build_mod.plan_build

    def fake_plan_build(*, wit_source: str, rust_source: str | None):
        # No wasm file written -> will force error when wasms not found after fake failing subprocess
        return real_plan_build(wit_source=wit_source, rust_source=rust_source)

    monkeypatch.setattr(build_mod, "plan_build", fake_plan_build)
    monkeypatch.setattr(
        build_mod, "plan_build_command", lambda: build_mod.BuildCommandPlan(tool="/usr/bin/cargo", args=["build"])
    )

    # Force subprocess error
    import subprocess as _sp

    def _fail_run(*_args, **_kwargs):
        raise _sp.CalledProcessError(1, "cargo")

    monkeypatch.setattr(_sp, "run", _fail_run)

    # Act
    resp = await client.post(
        "/api/v1/wasm/build", json={"twin_id": twin["id"], "dry_run": False}, headers=logged_in_headers
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["twin"]["build_status"] == "error"
    assert body["logs_uri"]
