"""WASM Flow Orchestration Service.

Implements topological planning and wRPC-based execution for multi-node WASM flows.
Includes output capture and round-trip for parity comparison.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from langflow.services.database.models.component_twin.model import ComponentTwin
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_wasmcloud_service

logger = logging.getLogger(__name__)


@dataclass
class ExecutionNode:
    """Represents a node in the execution plan."""

    node_id: str
    component_id: str
    twin_id: UUID
    inputs: dict[str, Any]
    predecessors: list[str]
    successors: list[str]


@dataclass
class ExecutionBatch:
    """A batch of nodes that can execute concurrently."""

    batch_id: int
    nodes: list[ExecutionNode]


@dataclass
class NodeResult:
    """Result from executing a single node."""

    node_id: str
    component_id: str
    success: bool
    output: Any
    error: str | None = None
    duration_ms: float | None = None
    timestamp: datetime | None = None


@dataclass
class FlowExecutionResult:
    """Complete result of flow execution."""

    flow_id: UUID
    run_id: str
    success: bool
    batches: list[ExecutionBatch]
    node_results: dict[str, NodeResult]
    total_duration_ms: float
    error: str | None = None


class WasmFlowOrchestrator:
    """Orchestrates execution of multi-node WASM flows in wasmCloud."""

    def __init__(self):
        self.wasmcloud_svc = get_wasmcloud_service()

    async def plan_execution(
        self,
        flow: Flow,
        twins: dict[str, ComponentTwin],
        flow_data: dict[str, Any],
    ) -> list[ExecutionBatch]:
        """Plan execution batches using topological sort.

        Args:
            flow: The Flow model
            twins: Map of node_id -> ComponentTwin
            flow_data: Flow graph data (nodes, edges)

        Returns:
            List of execution batches in topological order
        """
        nodes_data = flow_data.get("nodes", [])
        edges_data = flow_data.get("edges", [])

        # Build adjacency maps
        predecessor_map: dict[str, list[str]] = defaultdict(list)
        successor_map: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = defaultdict(int)

        node_ids = {node["id"] for node in nodes_data}

        for edge in edges_data:
            source = edge.get("source")
            target = edge.get("target")
            if source and target:
                predecessor_map[target].append(source)
                successor_map[source].append(target)
                in_degree[target] += 1

        # Initialize in_degree for nodes with no incoming edges
        for node_id in node_ids:
            if node_id not in in_degree:
                in_degree[node_id] = 0

        # Perform layered topological sort (Kahn's algorithm with batching)
        batches: list[ExecutionBatch] = []
        visited = set()
        queue = deque([nid for nid in node_ids if in_degree[nid] == 0])
        batch_num = 0

        while queue:
            # All nodes in the queue can execute concurrently (same batch)
            batch_size = len(queue)
            batch_nodes: list[ExecutionNode] = []

            for _ in range(batch_size):
                node_id = queue.popleft()
                visited.add(node_id)

                # Find corresponding twin
                twin = twins.get(node_id)
                if not twin:
                    logger.warning(f"No ComponentTwin found for node {node_id}")
                    continue

                exec_node = ExecutionNode(
                    node_id=node_id,
                    component_id=twin.component_id,
                    twin_id=twin.id,
                    inputs={},
                    predecessors=predecessor_map[node_id],
                    successors=successor_map[node_id],
                )
                batch_nodes.append(exec_node)

                # Reduce in_degree of successors
                for successor in successor_map[node_id]:
                    in_degree[successor] -= 1
                    if in_degree[successor] == 0:
                        queue.append(successor)

            if batch_nodes:
                batches.append(ExecutionBatch(batch_id=batch_num, nodes=batch_nodes))
                batch_num += 1

        # Check for cycles (unvisited nodes)
        unvisited = node_ids - visited
        if unvisited:
            logger.warning(f"Cycle detected or unreachable nodes: {unvisited}")

        return batches

    async def invoke_component(
        self,
        twin: ComponentTwin,
        inputs: dict[str, Any],
        timeout_ms: int | None = None,
    ) -> NodeResult:
        """Invoke a single component via wRPC.

        Args:
            twin: ComponentTwin with component metadata
            inputs: Input data for the component
            timeout_ms: Optional timeout override

        Returns:
            NodeResult with execution outcome
        """
        start = datetime.now(timezone.utc)
        component_id = twin.component_id

        try:
            # Serialize inputs to bytes (msgpack or JSON)
            import orjson

            payload = orjson.dumps(inputs)

            # Call via wRPC
            # Subject format: wasmrpc.{lattice}.{component_id}.process
            response_bytes = await self.wasmcloud_svc.call_component(
                component_id=component_id,
                operation="process",
                payload=payload,
                timeout_ms=timeout_ms,
            )

            # Deserialize response
            output = orjson.loads(response_bytes) if response_bytes else {}

            end = datetime.now(timezone.utc)
            duration_ms = (end - start).total_seconds() * 1000.0

            return NodeResult(
                node_id=twin.component_id,
                component_id=component_id,
                success=True,
                output=output,
                duration_ms=duration_ms,
                timestamp=end,
            )

        except Exception as e:
            end = datetime.now(timezone.utc)
            duration_ms = (end - start).total_seconds() * 1000.0
            logger.exception(f"Failed to invoke component {component_id}")

            return NodeResult(
                node_id=twin.component_id,
                component_id=component_id,
                success=False,
                output=None,
                error=str(e),
                duration_ms=duration_ms,
                timestamp=end,
            )

    async def execute_batch(
        self,
        batch: ExecutionBatch,
        twins: dict[str, ComponentTwin],
        outputs: dict[str, Any],
    ) -> list[NodeResult]:
        """Execute all nodes in a batch concurrently.

        Args:
            batch: ExecutionBatch to execute
            twins: Map of node_id -> ComponentTwin
            outputs: Accumulated outputs from previous batches

        Returns:
            List of NodeResults
        """
        tasks = []

        for node in batch.nodes:
            twin = twins.get(node.node_id)
            if not twin:
                continue

            # Gather inputs from predecessor outputs
            inputs = {}
            for pred_id in node.predecessors:
                if pred_id in outputs:
                    # Map predecessor output to this node's input
                    # For now, pass the entire output dict
                    inputs[pred_id] = outputs[pred_id]

            task = self.invoke_component(twin, inputs)
            tasks.append(task)

        # Execute all nodes in batch concurrently
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return results

    async def execute_flow(
        self,
        flow: Flow,
        twins: dict[str, ComponentTwin],
        flow_data: dict[str, Any],
        run_id: str,
    ) -> FlowExecutionResult:
        """Execute a complete flow with multiple nodes.

        Args:
            flow: Flow model
            twins: Map of node_id -> ComponentTwin
            flow_data: Flow graph data
            run_id: Unique run identifier

        Returns:
            FlowExecutionResult with complete execution data
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Plan execution batches
            batches = await self.plan_execution(flow, twins, flow_data)

            logger.info(f"Planned {len(batches)} execution batches for flow {flow.id}")

            # Execute batches in order, accumulating outputs
            outputs: dict[str, Any] = {}
            node_results: dict[str, NodeResult] = {}

            for batch in batches:
                logger.info(f"Executing batch {batch.batch_id} with {len(batch.nodes)} nodes")

                results = await self.execute_batch(batch, twins, outputs)

                for result in results:
                    node_results[result.node_id] = result
                    if result.success and result.output is not None:
                        outputs[result.node_id] = result.output
                    elif not result.success:
                        # Fail fast on error
                        error_msg = f"Node {result.node_id} failed: {result.error}"
                        logger.error(error_msg)

                        end_time = datetime.now(timezone.utc)
                        total_duration_ms = (end_time - start_time).total_seconds() * 1000.0

                        return FlowExecutionResult(
                            flow_id=flow.id,
                            run_id=run_id,
                            success=False,
                            batches=batches,
                            node_results=node_results,
                            total_duration_ms=total_duration_ms,
                            error=error_msg,
                        )

            end_time = datetime.now(timezone.utc)
            total_duration_ms = (end_time - start_time).total_seconds() * 1000.0

            return FlowExecutionResult(
                flow_id=flow.id,
                run_id=run_id,
                success=True,
                batches=batches,
                node_results=node_results,
                total_duration_ms=total_duration_ms,
            )

        except Exception as e:
            logger.exception(f"Flow execution failed for {flow.id}")
            end_time = datetime.now(timezone.utc)
            total_duration_ms = (end_time - start_time).total_seconds() * 1000.0

            return FlowExecutionResult(
                flow_id=flow.id,
                run_id=run_id,
                success=False,
                batches=[],
                node_results={},
                total_duration_ms=total_duration_ms,
                error=str(e),
            )


# Singleton instance
_orchestrator: WasmFlowOrchestrator | None = None


def get_orchestrator() -> WasmFlowOrchestrator:
    """Get or create the singleton orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WasmFlowOrchestrator()
    return _orchestrator
