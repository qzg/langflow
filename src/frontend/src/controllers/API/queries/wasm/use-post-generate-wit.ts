import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";

export type GenerateWITPayload = {
  twin_id?: string;
  flow_id?: string;
  component_id?: string;
  io_schema: Record<string, any>;
  world_name?: string;
  func_name?: string;
};

export function usePostGenerateWit() {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: ["usePostGenerateWit"],
    mutationFn: async (payload: GenerateWITPayload) => {
      const url = getURL("WASM_GENERATE_WIT");
      const { data } = await api.post(url, payload);
      return data as { twin: { id: string } };
    },
    onSuccess: (data, variables) => {
      const twinId = data?.twin?.id;
      if (variables.flow_id && variables.component_id) {
        qc.invalidateQueries({
          queryKey: [
            "useListComponentTwinsByKeys",
            variables.flow_id,
            variables.component_id,
          ],
        });
      }
      if (twinId) {
        qc.invalidateQueries({ queryKey: ["useGetComponentTwin", twinId] });
        qc.invalidateQueries({ queryKey: ["useGetWasmCapabilities", twinId] });
      }
    },
  });
}
