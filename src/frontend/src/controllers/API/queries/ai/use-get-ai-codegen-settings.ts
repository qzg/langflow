import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface AICodegenSettings {
  ai_codegen_enabled: boolean;
  ai_codegen_cli: string;
  ai_codegen_profile?: string | null;
  ai_codegen_timeout_ms: number;
  ai_codegen_working_dir: "repo_root" | "workspace" | string;
  ai_codegen_api_key_env?: string | null;
  overridden_by_env?: Record<string, boolean>;
}

export const useGetAICodegenSettings: useQueryFunctionType<
  undefined,
  AICodegenSettings
> = (options) => {
  const { query } = UseRequestProcessor();

  const getSettingsFn = async () => {
    const { data } = await api.get<AICodegenSettings>(
      `${getURL("AI_CODEGEN_SETTINGS")}`,
    );
    return data;
  };

  return query(["useGetAICodegenSettings"], getSettingsFn, {
    refetchOnWindowFocus: false,
    ...options,
  });
};
