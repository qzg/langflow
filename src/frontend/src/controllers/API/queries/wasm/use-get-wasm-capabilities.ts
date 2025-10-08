import { useQuery } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";

export type WasmCapabilities = {
  twin_id: string;
  inferred: Record<string, any>;
  overrides: Record<string, any>;
  effective: Record<string, any>;
};

export function useGetWasmCapabilities(twin_id: string | undefined) {
  return useQuery<WasmCapabilities>({
    queryKey: ["useGetWasmCapabilities", twin_id],
    queryFn: async () => {
      if (!twin_id) throw new Error("twin_id is required");
      const url = getURL("WASM_CAPABILITIES");
      const { data } = await api.get(url, { params: { twin_id } });
      return data as WasmCapabilities;
    },
    enabled: !!twin_id,
  });
}
