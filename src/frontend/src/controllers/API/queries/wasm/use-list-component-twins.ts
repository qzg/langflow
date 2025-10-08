import { useQuery } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";

export type ComponentTwinListItem = {
  id: string;
  flow_id: string;
  component_id: string;
  last_verified_at?: string | null;
  parity_metrics?: Record<string, any> | null;
  build_status?: string | null;
};

export function useListComponentTwinsByKeys(
  flow_id: string | undefined,
  component_id: string | undefined,
) {
  return useQuery<ComponentTwinListItem[]>({
    queryKey: ["useListComponentTwinsByKeys", flow_id, component_id],
    queryFn: async () => {
      if (!flow_id || !component_id) return [];
      const base = getURL("COMPONENT_TWINS");
      const { data } = await api.get(base, {
        params: { flow_id, component_id, limit: 1 },
      });
      return data as ComponentTwinListItem[];
    },
    enabled: !!flow_id && !!component_id,
  });
}
