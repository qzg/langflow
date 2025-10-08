#!/usr/bin/env python3
"""End-to-End Test Script for Multi-Node WASM Flow Orchestration

This script tests the complete flow orchestration pipeline:
1. Creates a test flow with 3 nodes (A -> [B, C])
2. Creates mock WASM components for each node
3. Publishes them to a test OCI registry (or mocks this)
4. Loads them into wasmCloud
5. Executes the flow via the orchestration API
6. Validates the execution results

Prerequisites:
- wasmCloud running locally (wash up)
- Test OCI registry or mock
- WASM components built and available
"""

import asyncio
import json

import httpx


async def create_test_flow(api_base_url: str) -> dict:
    """Create a test flow with 3 nodes in a diamond pattern."""
    flow_data = {
        "name": "E2E Test Flow",
        "description": "Test flow for WASM orchestration",
        "data": {
            "nodes": [
                {
                    "id": "node-A",
                    "type": "CustomComponent",
                    "data": {
                        "component_name": "InputProcessor",
                        "inputs": {},
                    },
                },
                {
                    "id": "node-B",
                    "type": "CustomComponent",
                    "data": {
                        "component_name": "TextTransformer",
                        "inputs": {"text": {"node": "node-A", "output": "result"}},
                    },
                },
                {
                    "id": "node-C",
                    "type": "CustomComponent",
                    "data": {
                        "component_name": "DataAnalyzer",
                        "inputs": {"data": {"node": "node-A", "output": "result"}},
                    },
                },
            ],
            "edges": [
                {"id": "edge-1", "source": "node-A", "target": "node-B"},
                {"id": "edge-2", "source": "node-A", "target": "node-C"},
            ],
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(f"{api_base_url}/api/v1/flows", json=flow_data)
        response.raise_for_status()
        flow = response.json()

    print(f"✓ Created test flow: {flow['id']}")
    return flow


async def create_component_twins(api_base_url: str, flow_id: str) -> dict:
    """Create component twins for each node in the flow."""
    twins = {}

    nodes = ["node-A", "node-B", "node-C"]
    for node_id in nodes:
        twin_data = {
            "flow_id": flow_id,
            "component_id": node_id,
            "wasm_module_url": f"oci://localhost:5000/test/{node_id}:latest",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{api_base_url}/api/v1/wasm/twins", json=twin_data)
            response.raise_for_status()
            twin = response.json()

        twins[node_id] = twin
        print(f"✓ Created component twin for {node_id}: {twin['id']}")

    return twins


async def execute_flow(api_base_url: str, flow_id: str, inputs: dict = None) -> dict:
    """Execute the flow via the orchestration API."""
    request_data = {"flow_id": flow_id}
    if inputs:
        request_data["inputs"] = inputs

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{api_base_url}/api/v1/wasm/execute_flow", json=request_data)
        response.raise_for_status()
        result = response.json()

    return result


async def validate_execution_result(result: dict, expected_nodes: list[str]):
    """Validate that the execution result is correct."""
    print("\n=== Validating Execution Result ===")

    # Check overall success
    assert result["success"], f"Flow execution failed: {result.get('error')}"
    print("✓ Flow execution succeeded")

    # Check that all expected nodes executed
    node_results = result["node_results"]
    for node_id in expected_nodes:
        assert node_id in node_results, f"Node {node_id} not found in results"
        assert node_results[node_id]["success"], f"Node {node_id} execution failed"
        print(f"✓ Node {node_id} executed successfully")

    # Check execution batches (should be 2: [A], [B, C])
    batches = result["batches"]
    assert len(batches) == 2, f"Expected 2 batches, got {len(batches)}"
    print(f"✓ Correct number of batches: {len(batches)}")

    # Validate batch 0 contains node-A
    batch_0_nodes = [n["node_id"] for n in batches[0]["nodes"]]
    assert "node-A" in batch_0_nodes, "Batch 0 should contain node-A"
    print("✓ Batch 0 contains node-A")

    # Validate batch 1 contains node-B and node-C
    batch_1_nodes = [n["node_id"] for n in batches[1]["nodes"]]
    assert set(batch_1_nodes) == {"node-B", "node-C"}, "Batch 1 should contain node-B and node-C"
    print("✓ Batch 1 contains node-B and node-C (parallel execution)")

    # Check timing
    total_duration = result["total_duration_ms"]
    assert total_duration > 0, "Total duration should be positive"
    print(f"✓ Total execution time: {total_duration:.2f}ms")

    print("\n✓✓✓ All validations passed! ✓✓✓")


async def cleanup_test_resources(api_base_url: str, flow_id: str):
    """Clean up test flow and component twins."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.delete(f"{api_base_url}/api/v1/flows/{flow_id}")
        print(f"✓ Cleaned up test flow: {flow_id}")
    except Exception as e:
        print(f"⚠ Warning: Could not clean up flow {flow_id}: {e}")


async def main():
    """Main test execution."""
    api_base_url = "http://localhost:7860"  # Default Langflow API URL
    flow_id = None

    try:
        print("=== Starting E2E WASM Flow Orchestration Test ===\n")

        # Step 1: Create test flow
        print("Step 1: Creating test flow...")
        flow = await create_test_flow(api_base_url)
        flow_id = flow["id"]

        # Step 2: Create component twins
        print("\nStep 2: Creating component twins...")
        twins = await create_component_twins(api_base_url, flow_id)

        # Step 3: Execute the flow
        print("\nStep 3: Executing flow...")
        initial_inputs = {"input_text": "Hello from E2E test!", "number": 42}
        result = await execute_flow(api_base_url, flow_id, initial_inputs)

        # Step 4: Validate results
        print("\nStep 4: Validating results...")
        expected_nodes = ["node-A", "node-B", "node-C"]
        await validate_execution_result(result, expected_nodes)

        # Print detailed results
        print("\n=== Execution Summary ===")
        print(f"Flow ID: {flow_id}")
        print(f"Run ID: {result['run_id']}")
        print(f"Total Duration: {result['total_duration_ms']:.2f}ms")
        print(f"Nodes Executed: {len(result['node_results'])}")
        print("\nNode Results:")
        for node_id, node_result in result["node_results"].items():
            status = "✓" if node_result["success"] else "✗"
            print(f"  {status} {node_id}: {node_result['duration_ms']:.2f}ms")
            if node_result.get("output"):
                print(f"    Output: {json.dumps(node_result['output'], indent=6)}")

        print("\n=== E2E Test Completed Successfully ===")

    except httpx.HTTPStatusError as e:
        print(f"\n✗ HTTP Error: {e.response.status_code}")
        print(f"  Response: {e.response.text}")
        return 1

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    finally:
        # Cleanup
        if flow_id:
            print("\nCleaning up test resources...")
            await cleanup_test_resources(api_base_url, flow_id)

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
