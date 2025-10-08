import { useMutation } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";

export function usePostWasmParity() {
  return useMutation({
    mutationKey: ["usePostWasmParity"],
    mutationFn: async (payload: {
      twin_id: string;
      inputs?: Record<string, any>;
      expected_text?: string;
      threshold_text?: number;
    }) => {
      const url = getURL("WASM_PARITY");
      const { data } = await api.post(url, payload);
      return data as {
        metrics: Record<string, number>;
        passes?: Record<string, boolean>;
      };
    },
  });
}
