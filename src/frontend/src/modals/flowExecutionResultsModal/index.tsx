import {
  AlertCircle,
  CheckCircle2,
  Clock,
  PlayCircle,
  XCircle,
} from "lucide-react";
import { memo, useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ExecuteFlowResponse } from "@/controllers/API/queries/wasm/use-post-execute-flow";
import { cn } from "@/utils/utils";

type FlowExecutionResultsModalProps = {
  open: boolean;
  setOpen: (open: boolean) => void;
  result: ExecuteFlowResponse | null;
  flowName?: string;
};

const FlowExecutionResultsModal = memo(function FlowExecutionResultsModal({
  open,
  setOpen,
  result,
  flowName = "Flow",
}: FlowExecutionResultsModalProps) {
  const overallSuccess = result?.success ?? false;
  const totalDuration = result?.total_duration_ms?.toFixed(2) ?? "0";

  const nodeResultsList = useMemo(() => {
    if (!result?.node_results) return [];
    return Object.entries(result.node_results).map(([nodeId, nodeResult]) => ({
      nodeId,
      ...nodeResult,
    }));
  }, [result]);

  const successCount = nodeResultsList.filter((n) => n.success).length;
  const failureCount = nodeResultsList.filter((n) => !n.success).length;

  const batchesInfo = useMemo(() => {
    if (!result?.batches) return [];
    return result.batches.map((batch) => ({
      ...batch,
      nodeCount: batch.nodes.length,
      nodeIds: batch.nodes.map((n) => n.node_id),
    }));
  }, [result]);

  if (!result) return null;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-h-[80vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <PlayCircle className="h-5 w-5" />
            {flowName} Execution Results
          </DialogTitle>
          <DialogDescription>
            Run ID: <code className="text-xs">{result.run_id}</code>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Overall Status */}
          <div className="rounded-lg border p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {overallSuccess ? (
                  <CheckCircle2 className="h-6 w-6 text-green-500" />
                ) : (
                  <XCircle className="h-6 w-6 text-red-500" />
                )}
                <div>
                  <h3 className="font-semibold">
                    {overallSuccess ? "Success" : "Failed"}
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    {successCount} succeeded, {failureCount} failed
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Clock className="h-4 w-4" />
                {totalDuration} ms
              </div>
            </div>
            {result.error && (
              <div className="mt-3 flex items-start gap-2 rounded-md bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
                <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                <span>{result.error}</span>
              </div>
            )}
          </div>

          <Tabs defaultValue="nodes" className="w-full">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="nodes">Node Results</TabsTrigger>
              <TabsTrigger value="batches">Execution Batches</TabsTrigger>
            </TabsList>

            <TabsContent value="nodes" className="space-y-2">
              {nodeResultsList.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No node results available
                </p>
              ) : (
                nodeResultsList.map((node) => (
                  <div
                    key={node.nodeId}
                    className={cn(
                      "rounded-lg border p-4 transition-colors",
                      node.success
                        ? "border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950"
                        : "border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950",
                    )}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          {node.success ? (
                            <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
                          ) : (
                            <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
                          )}
                          <h4 className="font-medium">{node.nodeId}</h4>
                          <Badge variant="outline" className="text-xs">
                            {node.component_id}
                          </Badge>
                        </div>
                        {node.error && (
                          <p className="mt-2 text-sm text-red-700 dark:text-red-300">
                            Error: {node.error}
                          </p>
                        )}
                        {node.output && (
                          <details className="mt-2">
                            <summary className="cursor-pointer text-sm text-muted-foreground hover:text-foreground">
                              View output
                            </summary>
                            <pre className="mt-2 max-h-40 overflow-auto rounded bg-muted p-2 text-xs">
                              {JSON.stringify(node.output, null, 2)}
                            </pre>
                          </details>
                        )}
                      </div>
                      <div className="ml-4 flex items-center gap-1 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        {node.duration_ms.toFixed(2)} ms
                      </div>
                    </div>
                  </div>
                ))
              )}
            </TabsContent>

            <TabsContent value="batches" className="space-y-2">
              {batchesInfo.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No batch information available
                </p>
              ) : (
                batchesInfo.map((batch) => (
                  <div key={batch.batch_id} className="rounded-lg border p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="font-medium">Batch {batch.batch_id}</h4>
                        <p className="text-sm text-muted-foreground">
                          {batch.nodeCount} node
                          {batch.nodeCount !== 1 ? "s" : ""} executed in
                          parallel
                        </p>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {batch.nodes.map((node) => {
                        const nodeResult = result.node_results[node.node_id];
                        return (
                          <Badge
                            key={node.node_id}
                            variant={
                              nodeResult?.success ? "default" : "destructive"
                            }
                            className="flex items-center gap-1"
                          >
                            {nodeResult?.success ? (
                              <CheckCircle2 className="h-3 w-3" />
                            ) : (
                              <XCircle className="h-3 w-3" />
                            )}
                            {node.node_id}
                          </Badge>
                        );
                      })}
                    </div>
                    {batch.nodes.length > 0 && (
                      <details className="mt-3">
                        <summary className="cursor-pointer text-sm text-muted-foreground hover:text-foreground">
                          View batch details
                        </summary>
                        <pre className="mt-2 max-h-40 overflow-auto rounded bg-muted p-2 text-xs">
                          {JSON.stringify(batch.nodes, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                ))
              )}
            </TabsContent>
          </Tabs>
        </div>
      </DialogContent>
    </Dialog>
  );
});

export default FlowExecutionResultsModal;
