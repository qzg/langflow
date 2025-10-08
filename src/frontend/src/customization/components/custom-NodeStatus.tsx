import NodeStatus from "@/CustomNodes/GenericNode/components/NodeStatus";
import { Badge } from "@/components/ui/badge";
import type { BuildStatus } from "@/constants/enums";
import { useListComponentTwinsByKeys } from "@/controllers/API/queries/wasm";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { VertexBuildTypeAPI } from "@/types/api";
import type { NodeDataType } from "@/types/flow";

export function CustomNodeStatus({
  nodeId,
  display_name,
  selected,
  setBorderColor,
  frozen,
  showNode,
  data,
  buildStatus,
  dismissAll,
  isOutdated,
  isUserEdited,
  isBreakingChange,
  getValidationStatus,
}: {
  nodeId: string;
  display_name: string;
  selected?: boolean;
  setBorderColor: (color: string) => void;
  frozen?: boolean;
  showNode: boolean;
  data: NodeDataType;
  buildStatus: BuildStatus;
  dismissAll: boolean;
  isOutdated: boolean;
  isUserEdited: boolean;
  isBreakingChange: boolean;
  getValidationStatus: (data) => VertexBuildTypeAPI | null;
}) {
  const currentFlow = useFlowsManagerStore((s) => s.currentFlow);
  const flowId = currentFlow?.id;
  const { data: twins } = useListComponentTwinsByKeys(flowId, nodeId);
  const twin = twins && twins.length > 0 ? twins[0] : undefined;
  const last = twin?.last_verified_at
    ? new Date(twin.last_verified_at).getTime()
    : 0;
  const ageHrs = last ? (Date.now() - last) / (1000 * 60 * 60) : Infinity;
  const passed = !!(twin as any)?.parity_metrics?.text?.passed;

  let badgeText: string | null = null;
  let badgeClass = "";
  if (passed && ageHrs <= 24) {
    badgeText = "Parity";
    badgeClass =
      "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300";
  } else if (passed && ageHrs > 24) {
    badgeText = "Stale";
    badgeClass =
      "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300";
  } else if (twin) {
    badgeText = "Diverged";
    badgeClass = "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300";
  }

  return (
    <div className="flex items-center gap-2">
      <NodeStatus
        nodeId={nodeId}
        display_name={display_name}
        selected={selected}
        setBorderColor={setBorderColor}
        frozen={frozen}
        showNode={showNode}
        data={data}
        buildStatus={buildStatus}
        isOutdated={isOutdated}
        isUserEdited={isUserEdited}
        getValidationStatus={getValidationStatus}
        dismissAll={dismissAll}
        isBreakingChange={isBreakingChange}
      />
      {badgeText && (
        <Badge className={`h-4 text-[10px] font-normal ${badgeClass}`}>
          {badgeText}
        </Badge>
      )}
    </div>
  );
}

export default CustomNodeStatus;
