import { Loader2, PlayCircle } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { usePostExecuteFlow } from "@/controllers/API/queries/wasm";
import type { ExecuteFlowResponse } from "@/controllers/API/queries/wasm/use-post-execute-flow";
import FlowExecutionResultsModal from "@/modals/flowExecutionResultsModal";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";

type ExecuteFlowButtonProps = {
  flowId?: string;
  flowName?: string;
};

export default function ExecuteFlowButton({
  flowId,
  flowName,
}: ExecuteFlowButtonProps) {
  const [showResults, setShowResults] = useState(false);
  const [executionResult, setExecutionResult] =
    useState<ExecuteFlowResponse | null>(null);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const currentFlowId = useFlowStore((state) => state.flowId);
  const currentFlowName = useFlowStore((state) => state.name);

  const effectiveFlowId = flowId || currentFlowId;
  const effectiveFlowName = flowName || currentFlowName || "Flow";

  const { mutate: executeFlow, isPending } = usePostExecuteFlow();

  const handleExecuteFlow = () => {
    if (!effectiveFlowId) {
      setErrorData({
        title: "Error: No flow ID available. Please save your flow first.",
      });
      return;
    }

    executeFlow(
      { flow_id: effectiveFlowId },
      {
        onSuccess: (data) => {
          setExecutionResult(data);
          setShowResults(true);

          if (data.success) {
            setSuccessData({
              title: `Flow Executed Successfully in ${data.total_duration_ms.toFixed(2)} ms`,
            });
          } else {
            setErrorData({
              title:
                "Flow Execution Failed: " +
                (data.error || "Some nodes failed to execute"),
            });
          }
        },
        onError: (error) => {
          setErrorData({
            title:
              "Execution Error: " +
              (error.message || "Failed to execute flow. Please try again."),
          });
        },
      },
    );
  };

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        onClick={handleExecuteFlow}
        disabled={isPending || !effectiveFlowId}
        className="gap-2"
      >
        {isPending ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Executing...
          </>
        ) : (
          <>
            <PlayCircle className="h-4 w-4" />
            Execute Flow
          </>
        )}
      </Button>

      <FlowExecutionResultsModal
        open={showResults}
        setOpen={setShowResults}
        result={executionResult}
        flowName={effectiveFlowName}
      />
    </>
  );
}
