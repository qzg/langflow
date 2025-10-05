import { keepPreviousData } from "@tanstack/react-query";
import { BASE_URL_API } from "@/constants/constants";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { UseRequestProcessor } from "../../services/request-processor";

export interface WorkspaceStatusResponse {
  name: string;
  running: boolean;
  pid?: number | null;
}

export const useWorkspaceStatus: useQueryFunctionType<
  { name?: string },
  WorkspaceStatusResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  async function fn() {
    const name = (params?.name || "").trim();
    const { data } = await api.get<WorkspaceStatusResponse>(
      `${BASE_URL_API}workspace/dev/status?name=${encodeURIComponent(name)}`,
    );
    return data;
  }

  return query(["useWorkspaceStatus", params?.name || ""], fn, {
    placeholderData: keepPreviousData,
    refetchOnWindowFocus: false,
    enabled: Boolean((params?.name || "").trim()),
    retry: false,
    ...options,
  });
};
