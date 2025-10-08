import { useQuery } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";

export type ComponentTwin = {
  id: string;
  flow_id: string;
  component_id: string;
  python_hash?: string | null;
  python_source?: string | null;
  rust_source?: string | null;
  wit_source?: string | null;
  capability_manifest?: Record<string, any> | null;
  build_status?: string;
  last_verified_at?: string | null;
  parity_metrics?: Record<string, any> | null;
};

export function useGetComponentTwin(twin_id: string | undefined) {
  return useQuery<ComponentTwin>({
    queryKey: ["useGetComponentTwin", twin_id],
    queryFn: async () => {
      if (!twin_id) throw new Error("twin_id is required");
      const base = getURL("COMPONENT_TWINS");
      const { data } = await api.get(`${base}/${twin_id}`);
      return data as ComponentTwin;
    },
    enabled: !!twin_id,
  });
}
