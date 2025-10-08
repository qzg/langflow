import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";

export type GenerateRustPayload = {
  twin_id: string;
  package_name?: string;
  func_name?: string;
};

export function usePostGenerateRust() {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: ["usePostGenerateRust"],
    mutationFn: async (payload: GenerateRustPayload) => {
      const url = getURL("WASM_GENERATE_RUST");
      const { data } = await api.post(url, payload);
      return data as { twin: { id: string } };
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
