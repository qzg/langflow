import type { UseMutationResult } from "@tanstack/react-query";
import { BASE_URL_API } from "@/constants/constants";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { UseRequestProcessor } from "../../services/request-processor";

export interface WorkspaceStartRequest {
  name: string;
  env?: Record<string, string>;
}

export interface WorkspaceStartResponse {
  name: string;
  started: boolean;
  pid?: number | null;
  reason?: string | null;
}

export const useWorkspaceStart: useMutationFunctionType<
  undefined,
  WorkspaceStartRequest,
  WorkspaceStartResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function fn(
    body: WorkspaceStartRequest,
  ): Promise<WorkspaceStartResponse> {
    const { data } = await api.post<WorkspaceStartResponse>(
      `${BASE_URL_API}workspace/dev/start`,
      body,
    );
    return data;
  }

  const mutation: UseMutationResult<
    WorkspaceStartResponse,
    any,
    WorkspaceStartRequest
  > = mutate(["useWorkspaceStart"], fn, {
    ...options,
  });

  return mutation;
};
