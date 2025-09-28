import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface WasmCloudSettings {
  wasmcloud_enabled?: boolean;
  wasmcloud_nats_url?: string | null;
  wasmcloud_lattice?: string | null;
  wasmcloud_timeout_ms?: number | null;
  // Always masked from server responses; only send this on change
  wasmcloud_creds_path?: string | null;
  // Presence flag for credentials; returned by server, do not send
  wasmcloud_creds_present?: boolean | null;
}

export const useGetWasmCloudSettings: useQueryFunctionType<
  undefined,
  WasmCloudSettings
> = (options) => {
  const { query } = UseRequestProcessor();

  const getSettingsFn = async () => {
    const { data } = await api.get<WasmCloudSettings>(
      `${getURL("WASMCLOUD_SETTINGS")}`,
    );
    return data;
  };

  return query(["useGetWasmCloudSettings"], getSettingsFn, {
    refetchOnWindowFocus: false,
    ...options,
  });
};
