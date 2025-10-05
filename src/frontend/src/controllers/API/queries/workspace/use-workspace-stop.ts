import type { UseMutationResult } from "@tanstack/react-query";
import { BASE_URL_API } from "@/constants/constants";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { UseRequestProcessor } from "../../services/request-processor";

export interface WorkspaceStopRequest {
  name: string;
}

export interface WorkspaceStopResponse {
  name: string;
  stopped: boolean;
  reason?: string | null;
}

export const useWorkspaceStop: useMutationFunctionType<
  undefined,
  WorkspaceStopRequest,
  WorkspaceStopResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function fn(
    body: WorkspaceStopRequest,
  ): Promise<WorkspaceStopResponse> {
    const { data } = await api.post<WorkspaceStopResponse>(
      `${BASE_URL_API}workspace/dev/stop`,
      body,
    );
    return data;
  }

  const mutation: UseMutationResult<
    WorkspaceStopResponse,
    any,
    WorkspaceStopRequest
  > = mutate(["useWorkspaceStop"], fn, {
    ...options,
  });

  return mutation;
};
