# Flow Execution UI

## Overview

The Flow Execution UI provides a user-friendly interface for executing multi-node WASM flows directly from the Langflow editor. This feature integrates with the WASM Flow Orchestration backend to enable visual execution of flows with real-time results.

## Features

### 1. Execute Flow Button

Located in the flow editor toolbar (top-right), the "Execute Flow" button triggers execution of the current flow using the WASM orchestration engine.

**Features:**
- One-click flow execution
- Automatic flow validation
- Loading state with spinner during execution
- Disabled state when no flow is available

**Location:** Flow Editor Toolbar → Execute Flow button (next to Playground and Publish buttons)

### 2. Flow Execution Results Modal

After execution completes, a comprehensive results modal displays:

#### Overall Status Section
- ✅ Success/❌ Failure indicator
- Success/failure count summary
- Total execution duration
- Error message (if any)

#### Node Results Tab
Shows detailed results for each node in the flow:

- **Node Information:**
  - Node ID and Component ID
  - Success/failure status with icons
  - Execution duration (ms)

- **Output Display:**
  - Expandable output viewer
  - JSON formatted output
  - Scrollable for large outputs

- **Error Display:**
  - Error messages for failed nodes
  - Red highlighting for failures
  - Green highlighting for successes

#### Execution Batches Tab
Visualizes how the flow was executed in parallel batches:

- **Batch Information:**
  - Batch number (execution order)
  - Number of nodes in batch
  - Parallel execution indicator

- **Node Badges:**
  - Color-coded by success/failure
  - Shows which nodes ran in parallel
  - Quick visual status overview

- **Batch Details:**
  - Expandable JSON view
  - Shows node inputs and configuration

## User Flow

### Executing a Flow

1. **Prepare Your Flow:**
   - Create a multi-node flow in the editor
   - Ensure all components have WASM twins created
   - Save the flow

2. **Execute:**
   - Click the "Execute Flow" button in the toolbar
   - Wait for execution (button shows "Executing..." with spinner)

3. **View Results:**
   - Results modal opens automatically
   - View overall success/failure status
   - Explore node-by-node results
   - Check execution batches to understand parallel execution

4. **Review Output:**
   - Click on individual node cards to expand outputs
   - Use the batch view to understand execution order
   - Identify failures and error messages

### Toast Notifications

The UI provides immediate feedback via toast notifications:

- ✅ **Success:** "Flow Executed Successfully in X ms"
- ❌ **Failure:** "Flow Execution Failed: [error message]"
- ⚠️ **Error:** "Execution Error: [error details]"

## Technical Details

### Frontend Components

#### Execute Flow Button Component
**Location:** `src/frontend/src/components/core/flowToolbarComponent/components/execute-flow-button.tsx`

- Uses `usePostExecuteFlow` React Query hook
- Manages execution state and results modal
- Integrates with Langflow alert store for notifications

#### Flow Execution Results Modal
**Location:** `src/frontend/src/modals/flowExecutionResultsModal/index.tsx`

- Displays comprehensive execution results
- Tabbed interface for different views
- Color-coded success/failure indicators
- Expandable details for outputs and batch information

### React Query Hook

**Location:** `src/frontend/src/controllers/API/queries/wasm/use-post-execute-flow.ts`

```typescript
export function usePostExecuteFlow() {
  return useMutation<ExecuteFlowResponse, Error, ExecuteFlowPayload>({
    mutationKey: ["usePostExecuteFlow"],
    mutationFn: async (payload) => {
      const url = getURL("WASM_EXECUTE_FLOW");
      const { data } = await api.post(url, payload);
      return data as ExecuteFlowResponse;
    },
  });
}
```

### API Endpoint

**Endpoint:** `POST /api/v1/wasm/execute_flow`

**Request:**
```json
{
  "flow_id": "550e8400-e29b-41d4-a716-446655440000",
  "inputs": {
    "optional_initial_inputs": "value"
  }
}
```

**Response:**
```json
{
  "flow_id": "550e8400-e29b-41d4-a716-446655440000",
  "run_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "success": true,
  "batches": [...],
  "node_results": {...},
  "total_duration_ms": 38.2,
  "error": null
}
```

## Visual Design

### Color Scheme

- **Success:** Green (green-500, green-600)
  - Border: `border-green-200 dark:border-green-900`
  - Background: `bg-green-50 dark:bg-green-950`

- **Failure:** Red (red-500, red-600)
  - Border: `border-red-200 dark:border-red-900`
  - Background: `bg-red-50 dark:bg-red-950`

### Icons

- **PlayCircle:** Execute flow action
- **CheckCircle2:** Success indicator
- **XCircle:** Failure indicator
- **Clock:** Duration/timing
- **AlertCircle:** Error messages
- **Loader2:** Loading/executing state

## Integration with Existing Features

### Flow Toolbar
The Execute Flow button integrates seamlessly with:
- **Playground Button:** For testing individual components
- **Publish Dropdown:** For deployment options
- **API Modal:** For API access

### Alert System
Uses the existing `useAlertStore` for notifications:
- `setSuccessData()` for successful executions
- `setErrorData()` for failures and errors

### Flow Store
Reads flow information from `useFlowStore`:
- `flowId` - Current flow identifier
- `name` - Flow name for display

## Error Handling

### Common Errors

1. **No Flow ID Available**
   - **Cause:** Flow not saved
   - **Message:** "No flow ID available. Please save your flow first."
   - **Solution:** Save the flow before executing

2. **Execution Failed**
   - **Cause:** One or more nodes failed
   - **Message:** "Flow Execution Failed: [error details]"
   - **Solution:** Check individual node results for errors

3. **API Error**
   - **Cause:** Network or server error
   - **Message:** "Execution Error: [error message]"
   - **Solution:** Check network connection and server status

## Future Enhancements

The following features are planned for future releases:

1. **Real-time Execution Progress (In Progress)**
   - SSE streaming for live updates
   - Progress bar showing batch completion
   - Live node status updates

2. **Execution History (Planned)**
   - View past executions in Logs modal
   - Re-run previous executions
   - Compare execution results

3. **Input Configuration**
   - UI for specifying initial inputs
   - Input validation
   - Default input values

4. **Export Results**
   - Download execution results as JSON
   - Export node outputs
   - Generate execution reports

5. **Execution Controls**
   - Pause/resume execution
   - Cancel running execution
   - Retry failed nodes

## Testing

### Manual Testing

1. **Simple Sequential Flow:**
   ```
   Node A → Node B → Node C
   ```
   - Verify execution order: A, then B, then C
   - Check outputs are chained correctly

2. **Parallel Execution Flow:**
   ```
   Node A → [Node B, Node C] → Node D
   ```
   - Verify B and C execute in parallel (same batch)
   - Verify D waits for both B and C
   - Check timing shows parallel optimization

3. **Diamond Pattern Flow:**
   ```
        Node A
       /      \
   Node B    Node C
       \      /
        Node D
   ```
   - Verify correct batch execution
   - Check all edges are respected

4. **Error Handling:**
   - Trigger a node failure
   - Verify error is displayed
   - Verify downstream nodes are handled correctly

### Automated Testing

Run the orchestration tests:
```bash
uv run pytest src/backend/tests/unit/services/wasm/test_orchestrator.py -v
```

## Troubleshooting

### Button is Disabled
- Ensure flow is saved (flowId exists)
- Check browser console for errors

### Modal Not Opening
- Check that execution completed
- Verify no JavaScript errors in console

### Empty Results
- Ensure nodes have WASM twins created
- Verify wasmCloud is running
- Check backend logs for orchestration errors

### Incorrect Execution Order
- Review the Execution Batches tab
- Verify flow edges are correct
- Check for cycles in the flow graph

## Related Documentation

- [WASM Orchestration](./WASM_ORCHESTRATION.md) - Backend orchestration engine
- [Component Deployment](./COMPONENT_DEPLOYMENT.md) - Creating WASM twins
- [wasmCloud Quickstart](./wasmcloud_quickstart.md) - Setting up wasmCloud

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review backend logs for orchestration errors
3. Open an issue on GitHub with:
   - Flow structure
   - Execution results
   - Error messages
   - Browser console logs
