"""Integration tests for WASM Flow Execution API endpoint."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langflow.main import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_flow_data():
    """Mock flow data for testing."""
    return {
        "id": str(uuid4()),
        "data": {
            "nodes": [
                {"id": "node-A"},
                {"id": "node-B"},
            ],
            "edges": [
                {"source": "node-A", "target": "node-B"},
            ],
        },
    }


@pytest.fixture
def mock_db_session(monkeypatch):
    """Mock database session and flow/twin retrieval."""

    class MockFlow:
        def __init__(self, id, data):
            self.id = id
            self.data = data

    class MockComponentTwin:
        def __init__(self, id, component_id, flow_id):
            self.id = id
            self.component_id = component_id
            self.flow_id = flow_id

    async def mock_get_flow(session, flow_id):
        return MockFlow(
            id=flow_id,
            data={
                "nodes": [
                    {"id": "node-A"},
                    {"id": "node-B"},
                ],
                "edges": [
                    {"source": "node-A", "target": "node-B"},
                ],
            },
        )

    async def mock_get_twins(session, flow_id):
        return {
            "node-A": MockComponentTwin(uuid4(), "node-A", flow_id),
            "node-B": MockComponentTwin(uuid4(), "node-B", flow_id),
        }

    monkeypatch.setattr(
        "langflow.api.v1.wasm.get_flow_by_id",
        mock_get_flow,
    )
    monkeypatch.setattr(
        "langflow.api.v1.wasm.get_component_twins_for_flow",
        mock_get_twins,
    )


@pytest.fixture
def mock_orchestrator(monkeypatch):
    """Mock orchestrator for testing."""

    class MockOrchestrator:
        async def execute_flow(self, flow, twins, flow_data, run_id, inputs=None):
            from langflow.services.wasm.orchestrator import FlowExecutionResult, NodeResult

            return FlowExecutionResult(
                flow_id=flow.id,
                run_id=run_id,
                success=True,
                batches=[],
                node_results={
                    "node-A": NodeResult(
                        node_id="node-A",
                        component_id="node-A",
                        success=True,
                        output={"result": "A processed"},
                        duration_ms=10.5,
                    ),
                    "node-B": NodeResult(
                        node_id="node-B",
                        component_id="node-B",
                        success=True,
                        output={"result": "B processed"},
                        duration_ms=12.3,
                    ),
                },
                total_duration_ms=22.8,
                error=None,
            )

    monkeypatch.setattr(
        "langflow.api.v1.wasm.WasmFlowOrchestrator",
        MockOrchestrator,
    )


def test_execute_flow_success(client, mock_db_session, mock_orchestrator):
    """Test successful flow execution."""
    flow_id = str(uuid4())

    response = client.post(
        "/api/v1/wasm/execute_flow",
        json={
            "flow_id": flow_id,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["flow_id"] == flow_id
    assert "run_id" in data
    assert len(data["node_results"]) == 2
    assert "node-A" in data["node_results"]
    assert "node-B" in data["node_results"]
    assert data["node_results"]["node-A"]["success"] is True
    assert data["node_results"]["node-B"]["success"] is True
    assert data["total_duration_ms"] > 0


def test_execute_flow_with_inputs(client, mock_db_session, mock_orchestrator):
    """Test flow execution with initial inputs."""
    flow_id = str(uuid4())
    inputs = {"input1": "value1", "input2": 42}

    response = client.post(
        "/api/v1/wasm/execute_flow",
        json={
            "flow_id": flow_id,
            "inputs": inputs,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["flow_id"] == flow_id


def test_execute_flow_missing_flow_id(client):
    """Test flow execution with missing flow_id."""
    response = client.post(
        "/api/v1/wasm/execute_flow",
        json={},
    )

    assert response.status_code == 422  # Validation error


def test_execute_flow_invalid_flow_id(client, monkeypatch):
    """Test flow execution with invalid flow_id."""

    async def mock_get_flow(session, flow_id):
        return None

    monkeypatch.setattr(
        "langflow.api.v1.wasm.get_flow_by_id",
        mock_get_flow,
    )

    response = client.post(
        "/api/v1/wasm/execute_flow",
        json={
            "flow_id": str(uuid4()),
        },
    )

    assert response.status_code == 404


def test_execute_flow_with_orchestrator_error(client, mock_db_session, monkeypatch):
    """Test flow execution when orchestrator raises error."""

    class MockOrchestrator:
        async def execute_flow(self, flow, twins, flow_data, run_id, inputs=None):
            from langflow.services.wasm.orchestrator import FlowExecutionResult

            return FlowExecutionResult(
                flow_id=flow.id,
                run_id=run_id,
                success=False,
                batches=[],
                node_results={},
                total_duration_ms=0,
                error="Mock orchestration error",
            )

    monkeypatch.setattr(
        "langflow.api.v1.wasm.WasmFlowOrchestrator",
        MockOrchestrator,
    )

    response = client.post(
        "/api/v1/wasm/execute_flow",
        json={
            "flow_id": str(uuid4()),
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is False
    assert "error" in data
    assert data["error"] == "Mock orchestration error"
