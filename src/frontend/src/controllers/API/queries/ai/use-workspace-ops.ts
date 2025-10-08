import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export function useGetWorkspaceLs(root_b64?: string, path?: string) {
  return useQuery({
    queryKey: ["useGetWorkspaceLs", root_b64, path],
    queryFn: async () => {
      if (!root_b64) return null;
      const url = `${getURL("AI_CODEGEN_WORKSPACES")}/${encodeURIComponent(root_b64)}/ls`;
      const { data } = await api.get(url, { params: { path: path ?? "" } });
      return data as {
        root: string;
        path: string;
        entries: {
          name: string;
          is_dir: boolean;
          size?: number;
          mtime?: number;
        }[];
      };
    },
    enabled: !!root_b64,
  });
}

export function useGetWorkspaceFile(root_b64?: string, path?: string) {
  return useQuery({
    queryKey: ["useGetWorkspaceFile", root_b64, path],
    queryFn: async () => {
      if (!root_b64 || !path) return null;
      const url = `${getURL("AI_CODEGEN_WORKSPACES")}/${encodeURIComponent(root_b64)}/file`;
      const { data } = await api.get(url, { params: { path } });
      return data as { root: string; path: string; content: string };
    },
    enabled: !!root_b64 && !!path,
  });
}

export function useDeleteWorkspace() {
  return useMutation({
    mutationKey: ["useDeleteWorkspace"],
    mutationFn: async (root_b64: string) => {
      const url = `${getURL("AI_CODEGEN_WORKSPACES")}/${encodeURIComponent(root_b64)}`;
      const { data } = await api.delete(url);
      return data as { deleted: boolean };
    },
  });
}

export function useDeleteAllWorkspaces() {
  return useMutation({
    mutationKey: ["useDeleteAllWorkspaces"],
    mutationFn: async () => {
      const url = getURL("AI_CODEGEN_WORKSPACES");
      const { data } = await api.delete(url);
      return data as { deleted: number };
    },
  });
}
