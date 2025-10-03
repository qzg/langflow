import type { UseMutationResult } from "@tanstack/react-query";
import { BASE_URL_API } from "@/constants/constants";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { UseRequestProcessor } from "../../services/request-processor";

export interface DevtoolsScreenshotRequest {
  fullPage?: boolean;
  server_name?: string;
  workspace?: string;
}

export interface DevtoolsScreenshotResponse {
  saved: boolean;
  path?: string | null;
  note?: string | null;
}

export const useDevtoolsScreenshot: useMutationFunctionType<
  undefined,
  DevtoolsScreenshotRequest,
  DevtoolsScreenshotResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function fn(
    body: DevtoolsScreenshotRequest,
  ): Promise<DevtoolsScreenshotResponse> {
    const { data } = await api.post<DevtoolsScreenshotResponse>(
      `${BASE_URL_API}devtools/screenshot`,
      body,
    );
    return data;
  }

  const mutation: UseMutationResult<
    DevtoolsScreenshotResponse,
    any,
    DevtoolsScreenshotRequest
  > = mutate(["useDevtoolsScreenshot"], fn, {
    ...options,
  });

  return mutation;
};
