import { useMutation } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";

export type CodegenStartPayload = {
  twin_id: string;
  use_ai?: boolean;
  max_iters?: number;
  auto_build?: boolean;
  user_hint?: string;
};

export type CodegenStartResponse = {
  run_id: string;
  status: string;
};

export function usePostCodegenStart() {
  return useMutation<CodegenStartResponse, unknown, CodegenStartPayload>({
    mutationKey: ["usePostCodegenStart"],
    mutationFn: async (payload) => {
      const url = getURL("WASM_CODEGEN_START");
      const { data } = await api.post(url, payload);
      return data as CodegenStartResponse;
    },
  });
}
