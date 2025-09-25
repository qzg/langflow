from pathlib import Path

from fastapi import status
from httpx import AsyncClient

WORKSPACES_DIR = Path.cwd() / "workspaces"


async def test_workspace_init_creates_dir(client: AsyncClient):
    name = "ws_test_1"
    resp = await client.post("api/v1/workspace/init", json={"name": name})
    assert resp.status_code == status.HTTP_200_OK, resp.text
    data = resp.json()
    assert data["name"] == name
    assert "path" in data
    assert "created" in data
    ws_path = WORKSPACES_DIR / name
    assert ws_path.exists()
    assert ws_path.is_dir()


async def test_workspace_status_not_running(client: AsyncClient):
    name = "ws_test_2"
    await client.post("api/v1/workspace/init", json={"name": name})
    resp = await client.get(f"api/v1/workspace/dev/status?name={name}")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["name"] == name
    assert data["running"] is False


async def test_workspace_stop_not_running(client: AsyncClient):
    name = "ws_test_3"
    await client.post("api/v1/workspace/init", json={"name": name})
    resp = await client.post("api/v1/workspace/dev/stop", json={"name": name})
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["stopped"] is False


async def test_workspace_start_gated_or_missing_package_json(client: AsyncClient):
    name = "ws_test_4"
    await client.post("api/v1/workspace/init", json={"name": name})
    resp = await client.post("api/v1/workspace/dev/start", json={"name": name})
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["started"] is False
