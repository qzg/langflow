import { useMutation } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";

export type BuildStartPayload = {
  twin_id: string;
  dry_run?: boolean;
};

export type BuildStartResponse = {
  run_id: string;
  status: string;
};

export function usePostBuildStart() {
  return useMutation<BuildStartResponse, unknown, BuildStartPayload>({
    mutationKey: ["usePostBuildStart"],
    mutationFn: async (payload) => {
      const url = getURL("WASM_BUILD_START");
      const { data } = await api.post(url, payload);
      return data as BuildStartResponse;
    },
  });
}
