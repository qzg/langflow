import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";

export function usePostComponentTwin() {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: ["usePostComponentTwin"],
    mutationFn: async (payload: { flow_id: string; component_id: string }) => {
      const url = getURL("COMPONENT_TWINS");
      const { data } = await api.post(url, payload);
      return data as {
        id: string;
        flow_id: string;
        component_id: string;
        [key: string]: any;
      };
    },
    onSuccess: (_data, variables) => {
      // Invalidate related twin queries
      qc.invalidateQueries({
        queryKey: [
          "useListComponentTwinsByKeys",
          variables.flow_id,
          variables.component_id,
        ],
      });
      qc.invalidateQueries({ queryKey: ["useGetComponentTwin"] });
    },
  });
}
