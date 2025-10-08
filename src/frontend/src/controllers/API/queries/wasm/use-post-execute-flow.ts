import { useMutation } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";

export type ExecuteFlowPayload = {
  flow_id: string;
  inputs?: Record<string, any>;
};

export type NodeResult = {
  node_id: string;
  component_id: string;
  success: boolean;
  output: Record<string, any> | null;
  error: string | null;
  duration_ms: number;
};

export type ExecutionNode = {
  node_id: string;
  component_id: string;
  twin_id: string;
  inputs: Record<string, any>;
  predecessors: string[];
  successors: string[];
};

export type ExecutionBatch = {
  batch_id: number;
  nodes: ExecutionNode[];
};

export type ExecuteFlowResponse = {
  flow_id: string;
  run_id: string;
  success: boolean;
  batches: ExecutionBatch[];
  node_results: Record<string, NodeResult>;
  total_duration_ms: number;
  error: string | null;
};

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
