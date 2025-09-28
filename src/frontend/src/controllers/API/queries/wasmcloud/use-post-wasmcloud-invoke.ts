import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface WasmCloudInvokeRequest {
  component_id: string;
  operation: string;
  payload_b64?: string | null;
  payload_text?: string | null;
  payload_json?: any;
  timeout_ms?: number | null;
  lattice?: string | null;
}

export interface WasmCloudInvokeResponse {
  success: boolean;
  latency_ms?: number | null;
  data_b64?: string | null;
  data_text?: string | null;
  error?: string | null;
}

export const usePostWasmCloudInvoke: useMutationFunctionType<
  undefined,
  WasmCloudInvokeRequest,
  WasmCloudInvokeResponse
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const fn = async (
    body: WasmCloudInvokeRequest,
  ): Promise<WasmCloudInvokeResponse> => {
    const { data } = await api.post<WasmCloudInvokeResponse>(
      `${getURL("WASMCLOUD_SETTINGS").replace("/settings", "/invoke")}`,
      body,
    );
    return data;
  };

  return mutate(["usePostWasmCloudInvoke"], fn, {
    ...options,
  });
};
