import { keepPreviousData } from "@tanstack/react-query";
import { BASE_URL_API } from "@/constants/constants";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { UseRequestProcessor } from "../../services/request-processor";

export interface PreflightCheckResult {
  name: string;
  installed: boolean;
  version?: string | null;
  path?: string | null;
  meets_minimum?: boolean | null;
  minimum_required?: string | null;
  note?: string | null;
}

export interface PreflightResponse {
  ok: boolean;
  system: Record<string, unknown>;
  checks: PreflightCheckResult[];
  missing: string[];
  warnings: string[];
}

export const useGetPreflightQuery: useQueryFunctionType<
  void,
  PreflightResponse
> = (_params, options) => {
  const { query } = UseRequestProcessor();

  async function getPreflightFn() {
    const response = await api.get<PreflightResponse>(
      `${BASE_URL_API}preflight`,
    );
    return response.data;
  }

  const queryResult = query(["useGetPreflightQuery"], getPreflightFn, {
    placeholderData: keepPreviousData,
    refetchOnWindowFocus: false,
    retry: false,
    ...options,
  });

  return queryResult;
};
