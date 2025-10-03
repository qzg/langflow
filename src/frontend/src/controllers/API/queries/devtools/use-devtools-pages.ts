import { keepPreviousData } from "@tanstack/react-query";
import { BASE_URL_API } from "@/constants/constants";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { UseRequestProcessor } from "../../services/request-processor";

export interface DevtoolsPagesResponse {
  pages: string[];
}

export const useDevtoolsPages: useQueryFunctionType<
  { server_name?: string },
  DevtoolsPagesResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  async function fn() {
    const server_name = params?.server_name ?? "chrome-devtools";
    const { data } = await api.get<DevtoolsPagesResponse>(
      `${BASE_URL_API}devtools/pages?server_name=${encodeURIComponent(server_name)}`,
    );
    return data;
  }

  return query(
    ["useDevtoolsPages", params?.server_name ?? "chrome-devtools"],
    fn,
    {
      placeholderData: keepPreviousData,
      refetchOnWindowFocus: false,
      retry: false,
      ...options,
    },
  );
};
