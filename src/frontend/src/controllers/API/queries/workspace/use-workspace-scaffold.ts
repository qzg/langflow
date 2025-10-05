import type { UseMutationResult } from "@tanstack/react-query";
import { BASE_URL_API } from "@/constants/constants";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { UseRequestProcessor } from "../../services/request-processor";

export interface WorkspaceScaffoldRequest {
  name: string;
  template?: string;
  package_manager?: string;
}

export interface WorkspaceScaffoldResponse {
  name: string;
  scaffolded: boolean;
  reason?: string | null;
}

export const useWorkspaceScaffold: useMutationFunctionType<
  undefined,
  WorkspaceScaffoldRequest,
  WorkspaceScaffoldResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function fn(
    body: WorkspaceScaffoldRequest,
  ): Promise<WorkspaceScaffoldResponse> {
    const { data } = await api.post<WorkspaceScaffoldResponse>(
      `${BASE_URL_API}workspace/scaffold`,
      body,
    );
    return data;
  }

  const mutation: UseMutationResult<
    WorkspaceScaffoldResponse,
    any,
    WorkspaceScaffoldRequest
  > = mutate(["useWorkspaceScaffold"], fn, {
    ...options,
  });

  return mutation;
};
