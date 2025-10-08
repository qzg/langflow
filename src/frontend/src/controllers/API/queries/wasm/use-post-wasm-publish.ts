import { useMutation } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";

export function usePostWasmPublish() {
  return useMutation({
    mutationKey: ["usePostWasmPublish"],
    mutationFn: async (payload: {
      twin_id: string;
      oci_ref: string;
      dry_run?: boolean;
    }) => {
      const url = getURL("WASM_PUBLISH");
      const { data } = await api.post(url, payload);
      return data as {
        planned_tool?: string;
        planned_args?: string[];
        success: boolean;
        error?: string | null;
        digest?: string | null;
        size?: number | null;
      };
    },
  });
}
