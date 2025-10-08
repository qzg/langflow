import { useQuery } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";

export type SuggestOCIResponse = {
  ref: string;
  base: string;
  component_slug: string;
  tag: string;
};

export function useGetWasmSuggestOCI(twin_id: string | undefined) {
  return useQuery<SuggestOCIResponse>({
    queryKey: ["useGetWasmSuggestOCI", twin_id],
    queryFn: async () => {
      if (!twin_id) throw new Error("twin_id is required");
      const url = getURL("WASM_SUGGEST_OCI");
      const { data } = await api.get(url, { params: { twin_id } });
      return data as SuggestOCIResponse;
    },
    enabled: !!twin_id,
  });
}
