"""Tests for WASM Flow Orchestrator."""

from uuid import UUID, uuid4

import pytest
from langflow.services.wasm.orchestrator import (
    ExecutionBatch,
    ExecutionNode,
    WasmFlowOrchestrator,
)


class MockComponentTwin:
    """Mock ComponentTwin for testing."""

    def __init__(self, id: UUID, component_id: str, flow_id: UUID):
        self.id = id
        self.component_id = component_id
        self.flow_id = flow_id


class MockFlow:
    """Mock Flow for testing."""

    def __init__(self, id: UUID, data: dict):
        self.id = id
        self.data = data


class MockWasmCloudService:
    """Mock wasmCloud service for testing."""

    async def call_component(self, component_id: str, operation: str, payload: bytes, timeout_ms: int | None = None):
        """Mock wRPC call."""
        import orjson

        # Echo inputs back as outputs for testing
        inputs = orjson.loads(payload) if payload else {}
        output = {"result": f"processed_{component_id}", "inputs_received": inputs}
        return orjson.dumps(output)


@pytest.fixture
def mock_wasmcloud_service(monkeypatch):
    """Replace wasmcloud service with mock."""
    mock_svc = MockWasmCloudService()

    def mock_get_wasmcloud_service():
        return mock_svc

    monkeypatch.setattr(
        "langflow.services.wasm.orchestrator.get_wasmcloud_service",
        mock_get_wasmcloud_service,
    )
    return mock_svc


@pytest.mark.asyncio
async def test_plan_execution_simple_dag(mock_wasmcloud_service):
    """Test planning a simple 3-node DAG: A -> B -> C."""
    orchestrator = WasmFlowOrchestrator()

    flow_id = uuid4()
    node_a_id = "node-A"
    node_b_id = "node-B"
    node_c_id = "node-C"

    flow_data = {
        "nodes": [
            {"id": node_a_id},
            {"id": node_b_id},
            {"id": node_c_id},
        ],
        "edges": [
            {"source": node_a_id, "target": node_b_id},
            {"source": node_b_id, "target": node_c_id},
        ],
    }

    twins = {
        node_a_id: MockComponentTwin(uuid4(), node_a_id, flow_id),
        node_b_id: MockComponentTwin(uuid4(), node_b_id, flow_id),
        node_c_id: MockComponentTwin(uuid4(), node_c_id, flow_id),
    }

    flow = MockFlow(flow_id, flow_data)
    batches = await orchestrator.plan_execution(flow, twins, flow_data)

    # Should have 3 batches (sequential execution)
    assert len(batches) == 3

    # First batch should contain only A (no dependencies)
    assert len(batches[0].nodes) == 1
    assert batches[0].nodes[0].node_id == node_a_id

    # Second batch should contain only B (depends on A)
    assert len(batches[1].nodes) == 1
    assert batches[1].nodes[0].node_id == node_b_id

    # Third batch should contain only C (depends on B)
    assert len(batches[2].nodes) == 1
    assert batches[2].nodes[0].node_id == node_c_id


@pytest.mark.asyncio
async def test_plan_execution_parallel(mock_wasmcloud_service):
    """Test planning with parallel nodes: A -> [B, C] -> D."""
    orchestrator = WasmFlowOrchestrator()

    flow_id = uuid4()
    node_ids = {
        "A": "node-A",
        "B": "node-B",
        "C": "node-C",
        "D": "node-D",
    }

    flow_data = {
        "nodes": [{"id": nid} for nid in node_ids.values()],
        "edges": [
            {"source": node_ids["A"], "target": node_ids["B"]},
            {"source": node_ids["A"], "target": node_ids["C"]},
            {"source": node_ids["B"], "target": node_ids["D"]},
            {"source": node_ids["C"], "target": node_ids["D"]},
        ],
    }

    twins = {nid: MockComponentTwin(uuid4(), nid, flow_id) for nid in node_ids.values()}

    flow = MockFlow(flow_id, flow_data)
    batches = await orchestrator.plan_execution(flow, twins, flow_data)

    # Should have 3 batches: [A], [B, C], [D]
    assert len(batches) == 3

    # Batch 0: A
    assert len(batches[0].nodes) == 1
    assert batches[0].nodes[0].node_id == node_ids["A"]

    # Batch 1: B and C (can run in parallel)
    assert len(batches[1].nodes) == 2
    batch_1_ids = {n.node_id for n in batches[1].nodes}
    assert batch_1_ids == {node_ids["B"], node_ids["C"]}

    # Batch 2: D
    assert len(batches[2].nodes) == 1
    assert batches[2].nodes[0].node_id == node_ids["D"]


@pytest.mark.asyncio
async def test_invoke_component(mock_wasmcloud_service):
    """Test invoking a single component."""
    orchestrator = WasmFlowOrchestrator()

    twin = MockComponentTwin(uuid4(), "test-component", uuid4())
    inputs = {"input1": "value1", "input2": 42}

    result = await orchestrator.invoke_component(twin, inputs)

    assert result.success
    assert result.node_id == "test-component"
    assert result.component_id == "test-component"
    assert result.output is not None
    assert result.output["result"] == "processed_test-component"
    assert result.output["inputs_received"] == inputs
    assert result.duration_ms is not None
    assert result.duration_ms > 0


@pytest.mark.asyncio
async def test_execute_flow_simple(mock_wasmcloud_service):
    """Test executing a simple 2-node flow."""
    orchestrator = WasmFlowOrchestrator()

    flow_id = uuid4()
    node_a_id = "node-A"
    node_b_id = "node-B"

    flow_data = {
        "nodes": [
            {"id": node_a_id},
            {"id": node_b_id},
        ],
        "edges": [
            {"source": node_a_id, "target": node_b_id},
        ],
    }

    twins = {
        node_a_id: MockComponentTwin(uuid4(), node_a_id, flow_id),
        node_b_id: MockComponentTwin(uuid4(), node_b_id, flow_id),
    }

    flow = MockFlow(flow_id, flow_data)
    run_id = str(uuid4())

    result = await orchestrator.execute_flow(flow, twins, flow_data, run_id)

    assert result.success
    assert result.flow_id == flow_id
    assert result.run_id == run_id
    assert len(result.node_results) == 2
    assert node_a_id in result.node_results
    assert node_b_id in result.node_results
    assert result.node_results[node_a_id].success
    assert result.node_results[node_b_id].success
    assert result.total_duration_ms > 0


@pytest.mark.asyncio
async def test_execute_batch_with_outputs(mock_wasmcloud_service):
    """Test executing a batch and passing outputs between nodes."""
    orchestrator = WasmFlowOrchestrator()

    flow_id = uuid4()
    node_a_id = "node-A"
    twin_a = MockComponentTwin(uuid4(), node_a_id, flow_id)

    # Create a batch with one node
    exec_node = ExecutionNode(
        node_id=node_a_id,
        component_id=node_a_id,
        twin_id=twin_a.id,
        inputs={},
        predecessors=[],
        successors=[],
    )
    batch = ExecutionBatch(batch_id=0, nodes=[exec_node])

    twins = {node_a_id: twin_a}
    outputs = {}

    results = await orchestrator.execute_batch(batch, twins, outputs)

    assert len(results) == 1
    assert results[0].success
    assert results[0].node_id == node_a_id


@pytest.mark.asyncio
async def test_plan_execution_with_diamond_dag(mock_wasmcloud_service):
    """Test planning with diamond pattern: A -> [B, C] -> D."""
    # This is the same as test_plan_execution_parallel
    # but explicitly tests the "diamond" pattern
    orchestrator = WasmFlowOrchestrator()

    flow_id = uuid4()
    nodes = ["A", "B", "C", "D"]
    node_ids = {n: f"node-{n}" for n in nodes}

    flow_data = {
        "nodes": [{"id": nid} for nid in node_ids.values()],
        "edges": [
            {"source": node_ids["A"], "target": node_ids["B"]},
            {"source": node_ids["A"], "target": node_ids["C"]},
            {"source": node_ids["B"], "target": node_ids["D"]},
            {"source": node_ids["C"], "target": node_ids["D"]},
        ],
    }

    twins = {nid: MockComponentTwin(uuid4(), nid, flow_id) for nid in node_ids.values()}

    flow = MockFlow(flow_id, flow_data)
    batches = await orchestrator.plan_execution(flow, twins, flow_data)

    # Diamond pattern should execute in 3 layers
    assert len(batches) == 3

    # Verify D only appears in the last batch (after both B and C)
    last_batch_ids = {n.node_id for n in batches[-1].nodes}
    assert node_ids["D"] in last_batch_ids
