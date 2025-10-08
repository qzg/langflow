import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";

export function usePutWasmCapabilities() {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: ["usePutWasmCapabilities"],
    mutationFn: async (payload: {
      twin_id: string;
      overrides: Record<string, any>;
    }) => {
      const url = getURL("WASM_CAPABILITIES");
      const { data } = await api.put(url, payload);
      return data;
    },
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({
        queryKey: ["useGetWasmCapabilities", variables.twin_id],
      });
    },
  });
}
