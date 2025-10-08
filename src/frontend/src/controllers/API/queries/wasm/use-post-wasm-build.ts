import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";

export type BuildPayload = {
  twin_id: string;
  dry_run?: boolean;
};

export function usePostWasmBuild() {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: ["usePostWasmBuild"],
    mutationFn: async (payload: BuildPayload) => {
      const url = getURL("WASM_BUILD");
      const { data } = await api.post(url, payload);
      return data as { twin: { id: string; build_status?: string } };
    },
    onSuccess: (data) => {
      const twinId = data?.twin?.id;
      if (twinId) {
        qc.invalidateQueries({ queryKey: ["useGetComponentTwin", twinId] });
        qc.invalidateQueries({ queryKey: ["useGetWasmCapabilities", twinId] });
      }
    },
  });
}
