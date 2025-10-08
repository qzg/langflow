# WASM Flow Orchestration

This document describes the implementation of multi-node flow orchestration for WebAssembly (WASM) components in Langflow, enabling execution of complex DAG-based workflows via wasmCloud.

## Overview

The WASM Flow Orchestration system allows Langflow to:

1. **Plan execution**: Analyze flow DAGs and compute optimal execution batches
2. **Execute in parallel**: Run independent nodes concurrently for performance
3. **Chain outputs**: Pass outputs from predecessor nodes as inputs to successors
4. **Handle failures**: Gracefully manage component failures and report errors
5. **Track metrics**: Capture timing and execution details for observability

## Architecture

### Components

#### 1. Flow Orchestrator (`langflow/services/wasm/orchestrator.py`)

The core orchestration engine responsible for:

- **Execution Planning**: Uses topological sorting to create execution batches
- **Parallel Execution**: Executes independent nodes in batches using asyncio
- **Output Chaining**: Captures outputs and passes them as inputs to dependent nodes
- **Error Handling**: Manages failures and continues execution where possible

Key classes:

```python
class WasmFlowOrchestrator:
    async def execute_flow(flow, twins, flow_data, run_id, inputs) -> FlowExecutionResult
    async def plan_execution(flow, twins, flow_data) -> List[ExecutionBatch]
    async def execute_batch(batch, twins, outputs) -> List[NodeResult]
    async def invoke_component(twin, inputs) -> NodeResult
```

#### 2. API Endpoint (`langflow/api/v1/wasm.py`)

REST API for flow execution:

```
POST /api/v1/wasm/execute_flow
{
  "flow_id": "uuid",
  "inputs": {...}  // optional initial inputs
}
```

Returns comprehensive execution results including:
- Overall success status
- Per-node execution results and outputs
- Execution batches and timing metrics
- Error messages if any

### Data Models

#### ExecutionNode

Represents a node ready for execution:

```python
@dataclass
class ExecutionNode:
    node_id: str
    component_id: str
    twin_id: UUID
    inputs: dict
    predecessors: List[str]
    successors: List[str]
```

#### ExecutionBatch

Group of nodes that can execute in parallel:

```python
@dataclass
class ExecutionBatch:
    batch_id: int
    nodes: List[ExecutionNode]
```

#### NodeResult

Result of executing a single node:

```python
@dataclass
class NodeResult:
    node_id: str
    component_id: str
    success: bool
    output: dict | None
    error: str | None
    duration_ms: float
```

#### FlowExecutionResult

Complete flow execution result:

```python
@dataclass
class FlowExecutionResult:
    flow_id: UUID
    run_id: str
    success: bool
    batches: List[ExecutionBatch]
    node_results: Dict[str, NodeResult]
    total_duration_ms: float
    error: str | None
```

## Execution Flow

### 1. Planning Phase

```python
batches = await orchestrator.plan_execution(flow, twins, flow_data)
```

The planner:
1. Builds dependency graph from flow edges
2. Detects cycles (raises error if found)
3. Performs topological sort using Kahn's algorithm
4. Groups nodes into execution batches
   - Nodes with no pending dependencies go in the same batch
   - Ensures all predecessors execute before successors

Example for flow `A -> [B, C] -> D`:
- Batch 0: [A]
- Batch 1: [B, C] (parallel)
- Batch 2: [D]

### 2. Execution Phase

```python
for batch in batches:
    results = await orchestrator.execute_batch(batch, twins, outputs)
```

For each batch:
1. Creates tasks for all nodes in batch
2. Executes tasks concurrently using `asyncio.gather`
3. Captures outputs from each node
4. Updates global outputs dictionary
5. Continues to next batch

### 3. Component Invocation

```python
result = await orchestrator.invoke_component(twin, inputs)
```

For each component:
1. Retrieves wasmCloud service
2. Serializes inputs to JSON/bytes
3. Calls component via wRPC with timeout
4. Deserializes output
5. Returns NodeResult with timing and status

## Usage

### Basic Flow Execution

```python
from langflow.services.wasm.orchestrator import WasmFlowOrchestrator

orchestrator = WasmFlowOrchestrator()

# Execute flow
result = await orchestrator.execute_flow(
    flow=flow,
    twins=component_twins,
    flow_data=flow_data,
    run_id=str(uuid4()),
    inputs={"initial_data": "test"}
)

# Check result
if result.success:
    for node_id, node_result in result.node_results.items():
        print(f"{node_id}: {node_result.output}")
else:
    print(f"Error: {result.error}")
```

### Via API

```bash
curl -X POST http://localhost:7860/api/v1/wasm/execute_flow \
  -H "Content-Type: application/json" \
  -d '{
    "flow_id": "550e8400-e29b-41d4-a716-446655440000",
    "inputs": {"text": "Hello World"}
  }'
```

Response:
```json
{
  "flow_id": "550e8400-e29b-41d4-a716-446655440000",
  "run_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "success": true,
  "batches": [
    {
      "batch_id": 0,
      "nodes": [
        {
          "node_id": "node-A",
          "component_id": "input-processor",
          "inputs": {"text": "Hello World"}
        }
      ]
    },
    {
      "batch_id": 1,
      "nodes": [
        {
          "node_id": "node-B",
          "component_id": "transformer"
        },
        {
          "node_id": "node-C",
          "component_id": "analyzer"
        }
      ]
    }
  ],
  "node_results": {
    "node-A": {
      "success": true,
      "output": {"processed": "HELLO WORLD"},
      "duration_ms": 15.3
    },
    "node-B": {
      "success": true,
      "output": {"transformed": "hello world"},
      "duration_ms": 12.7
    },
    "node-C": {
      "success": true,
      "output": {"analysis": "11 chars"},
      "duration_ms": 10.2
    }
  },
  "total_duration_ms": 38.2
}
```

## Testing

### Unit Tests

Located in `tests/unit/services/wasm/test_orchestrator.py`:

```bash
uv run pytest src/backend/tests/unit/services/wasm/test_orchestrator.py -v
```

Tests cover:
- Simple sequential DAGs (A -> B -> C)
- Parallel execution (A -> [B, C] -> D)
- Diamond patterns
- Component invocation
- Batch execution
- Error handling

### Integration Tests

Located in `tests/integration/test_wasm_api.py`:

```bash
uv run pytest src/backend/tests/integration/test_wasm_api.py -v
```

Tests cover:
- API endpoint validation
- Flow creation and execution
- Error responses
- Input handling

### End-to-End Test

Script: `tests/e2e_wasm_flow_test.py`

```bash
python tests/e2e_wasm_flow_test.py
```

Requires:
- Running Langflow instance
- wasmCloud cluster (via `wash up`)
- WASM components deployed

## Performance Considerations

### Parallel Execution

The orchestrator automatically identifies independent nodes and executes them in parallel:

```
Sequential (no orchestration): A(10ms) -> B(10ms) -> C(10ms) = 30ms
Parallel (with orchestration): A(10ms) -> [B(10ms), C(10ms)] = 20ms
```

### Timeout Handling

Default timeout per component: 30 seconds
- Can be configured per component
- Failures don't block other nodes in same batch
- Dependent nodes skip execution if predecessors fail

### Memory Management

- Outputs stored in memory during execution
- Large outputs should be passed by reference
- Consider streaming for large data flows

## Error Handling

### Cycle Detection

```python
if has_cycle(graph):
    raise ValueError("Flow contains cycles")
```

### Component Failures

```python
try:
    output = await call_component(...)
except Exception as e:
    return NodeResult(success=False, error=str(e))
```

### Partial Failures

- Failed nodes don't stop execution of independent branches
- Dependent nodes marked as skipped
- Overall flow marked as failed if any node fails

## Future Enhancements

1. **Conditional Branching**: Support for conditional edges
2. **Looping**: Support for iterative subflows
3. **Checkpointing**: Save and resume long-running flows
4. **Streaming**: Support for streaming outputs
5. **Distributed Execution**: Execute across multiple wasmCloud hosts
6. **Resource Limits**: Per-node memory and CPU limits
7. **Retry Logic**: Automatic retry on transient failures
8. **Monitoring**: Integration with observability platforms

## References

- [wasmCloud Documentation](https://wasmcloud.com/docs)
- [wRPC Protocol](https://github.com/bytecodealliance/wrpc)
- [Topological Sorting](https://en.wikipedia.org/wiki/Topological_sorting)
- [Kahn's Algorithm](https://en.wikipedia.org/wiki/Topological_sorting#Kahn's_algorithm)
