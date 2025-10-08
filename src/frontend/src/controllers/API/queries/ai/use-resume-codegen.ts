import { UseMutationResult, useMutation } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { UseRequestProcessor } from "@/controllers/API/services/request-processor";

interface ResumeCodegenRequest {
  workspace_root_b64: string;
  user_hint?: string | null;
  max_iters?: number | null;
}

interface ResumeCodegenResponse {
  run_id: string;
  status: string;
}

export const useResumeCodegen = (): UseMutationResult<
  ResumeCodegenResponse,
  any,
  ResumeCodegenRequest
> => {
  const { mutate } = UseRequestProcessor();

  const resumeCodegenFn = async (
    payload: ResumeCodegenRequest,
  ): Promise<ResumeCodegenResponse> => {
    const res = await api.post<ResumeCodegenResponse>(
      `/api/v1/wasm/generate_rust/resume`,
      payload,
    );
    return res.data;
  };

  return useMutation({
    mutationFn: resumeCodegenFn,
    onError: (error: any) => {
      mutate("error", { title: "Resume Failed", list: [error?.message] });
    },
  });
};
