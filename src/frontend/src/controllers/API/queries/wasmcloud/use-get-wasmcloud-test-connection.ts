import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface WasmCloudTestConnectionResponse {
  configured: boolean;
  available?: boolean | null;
  connected?: boolean | null;
  message?: string;
}

export const useGetWasmCloudTestConnection: useMutationFunctionType<
  undefined,
  void,
  WasmCloudTestConnectionResponse
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const testFn = async (): Promise<WasmCloudTestConnectionResponse> => {
    const { data } = await api.get<WasmCloudTestConnectionResponse>(
      `${getURL("WASMCLOUD_TEST_CONNECTION")}`,
    );
    return data;
  };

  return mutate(["useGetWasmCloudTestConnection"], testFn, {
    ...options,
  });
};
