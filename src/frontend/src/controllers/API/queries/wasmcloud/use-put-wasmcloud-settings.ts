import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { WasmCloudSettings } from "./use-get-wasmcloud-settings";

export const usePutWasmCloudSettings: useMutationFunctionType<
  undefined,
  Partial<WasmCloudSettings>,
  WasmCloudSettings
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const putSettingsFn = async (
    updates: Partial<WasmCloudSettings>,
  ): Promise<WasmCloudSettings> => {
    // Build payload: include booleans and numbers even if falsy; exclude undefined
    // Only include creds_path if non-empty string is provided
    const payload: Record<string, any> = {};
    for (const [key, value] of Object.entries(updates)) {
      if (key === "wasmcloud_creds_path") {
        if (typeof value === "string" && value.trim() !== "") {
          payload[key] = value;
        }
      } else if (value !== undefined) {
        payload[key] = value;
      }
    }

    const { data } = await api.put<WasmCloudSettings>(
      `${getURL("WASMCLOUD_SETTINGS")}`,
      payload,
    );
    return data;
  };

  const mutation: UseMutationResult<
    WasmCloudSettings,
    any,
    Partial<WasmCloudSettings>
  > = mutate(["usePutWasmCloudSettings"], putSettingsFn, {
    ...options,
    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({ queryKey: ["useGetWasmCloudSettings"] });
      options?.onSuccess?.(data, variables, context);
    },
  });

  return mutation;
};
