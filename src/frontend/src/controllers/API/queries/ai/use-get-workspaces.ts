import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface WorkspaceItem {
  root: string;
  root_b64: string;
  name: string;
  type?: string | null;
  twin_id?: string | null;
  component_id?: string | null;
  flow_id?: string | null;
  run_id?: string | null;
  started_at?: string | null;
  updated_at?: number | string | null;
  success?: boolean | null;
  logs_uri?: string | null;
}

export interface WorkspaceListResponse {
  workspaces: WorkspaceItem[];
}

export const useGetWorkspaces: useQueryFunctionType<
  undefined,
  WorkspaceListResponse
> = (options) => {
  const { query } = UseRequestProcessor();
  const fn = async () => {
    const { data } = await api.get<WorkspaceListResponse>(
      getURL("AI_CODEGEN_WORKSPACES"),
    );
    return data;
  };
  return query(["useGetWorkspaces"], fn, {
    refetchOnWindowFocus: false,
    ...options,
  });
};
