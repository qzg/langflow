import type { UseMutationResult } from "@tanstack/react-query";
import { BASE_URL_API } from "@/constants/constants";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { UseRequestProcessor } from "../../services/request-processor";

export interface DevtoolsNavigateRequest {
  url: string;
  server_name?: string;
}

export interface DevtoolsNavigateResponse {
  ok: boolean;
}

export const useDevtoolsNavigate: useMutationFunctionType<
  undefined,
  DevtoolsNavigateRequest,
  DevtoolsNavigateResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function fn(
    body: DevtoolsNavigateRequest,
  ): Promise<DevtoolsNavigateResponse> {
    const { data } = await api.post<DevtoolsNavigateResponse>(
      `${BASE_URL_API}devtools/navigate`,
      body,
    );
    return data;
  }

  const mutation: UseMutationResult<
    DevtoolsNavigateResponse,
    any,
    DevtoolsNavigateRequest
  > = mutate(["useDevtoolsNavigate"], fn, {
    ...options,
  });

  return mutation;
};
