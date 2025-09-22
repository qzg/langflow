import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface KnowledgeBaseDocument {
  id: string;
  document: string;
  metadata?: Record<string, any> | null;
}

export interface KnowledgeBaseDocumentsResponse {
  total: number;
  items: KnowledgeBaseDocument[];
}

interface GetKnowledgeBaseDocumentsParams {
  kb_name: string;
  limit?: number;
  offset?: number;
}

export const useGetKnowledgeBaseDocuments: useQueryFunctionType<
  GetKnowledgeBaseDocumentsParams,
  KnowledgeBaseDocumentsResponse
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getDocumentsFn = async (
    p: GetKnowledgeBaseDocumentsParams,
  ): Promise<KnowledgeBaseDocumentsResponse> => {
    const { kb_name, limit = 50, offset = 0 } = p;
    const { data } = await api.get<KnowledgeBaseDocumentsResponse>(
      `${getURL("KNOWLEDGE_BASES")}/${kb_name}/documents`,
      { params: { limit, offset } },
    );
    return data;
  };

  const queryResult: UseQueryResult<KnowledgeBaseDocumentsResponse, any> =
    query(
      [
        "useGetKnowledgeBaseDocuments",
        params?.kb_name,
        params?.limit ?? 50,
        params?.offset ?? 0,
      ],
      () => getDocumentsFn(params as GetKnowledgeBaseDocumentsParams),
      {
        enabled: Boolean(params?.kb_name),
        refetchOnWindowFocus: false,
        ...options,
      },
    );

  return queryResult;
};
