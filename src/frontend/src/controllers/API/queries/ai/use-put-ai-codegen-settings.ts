import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { AICodegenSettings } from "./use-get-ai-codegen-settings";

export const usePutAICodegenSettings: useMutationFunctionType<
  undefined,
  Partial<AICodegenSettings>,
  AICodegenSettings
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const putSettingsFn = async (
    updates: Partial<AICodegenSettings>,
  ): Promise<AICodegenSettings> => {
    // Only include defined values; send strings/booleans/numbers
    const payload: Record<string, any> = {};
    for (const [k, v] of Object.entries(updates)) {
      if (v !== undefined) payload[k] = v;
    }
    const { data } = await api.put<AICodegenSettings>(
      `${getURL("AI_CODEGEN_SETTINGS")}`,
      payload,
    );
    return data;
  };

  const mutation: UseMutationResult<
    AICodegenSettings,
    any,
    Partial<AICodegenSettings>
  > = mutate(["usePutAICodegenSettings"], putSettingsFn, {
    ...options,
    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({ queryKey: ["useGetAICodegenSettings"] });
      options?.onSuccess?.(data, variables, context);
    },
  });

  return mutation;
};
