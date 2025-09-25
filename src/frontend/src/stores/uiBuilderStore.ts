import { create } from "zustand";

export type UiBuilderAgent = "claude" | "warp";

export type UiBuilderPreflight = {
  node?: string;
  npm?: string;
  playwright?: string;
  claude?: string;
  warp?: string;
  timestamp?: string;
};

export type UiBuilderSession = {
  workspacePath: string;
  agent: UiBuilderAgent;
  devServerUrl?: string;
  devServerRunning: boolean;
  preflight?: UiBuilderPreflight;
};

export type UiBuilderState = {
  sessions: Record<string, UiBuilderSession>;
  getSession: (nodeId: string) => UiBuilderSession;
  setWorkspacePath: (nodeId: string, path: string) => void;
  setAgent: (nodeId: string, agent: UiBuilderAgent) => void;
  setDevServerStatus: (
    nodeId: string,
    data: { running: boolean; url?: string },
  ) => void;
  setPreflight: (nodeId: string, data: UiBuilderPreflight) => void;
};

const defaultSession = (): UiBuilderSession => ({
  workspacePath: "",
  agent: "warp",
  devServerRunning: false,
});

export const useUiBuilderStore = create<UiBuilderState>((set, get) => ({
  sessions: {},
  getSession: (nodeId) => {
    const current = get().sessions[nodeId];
    if (current) return current;
    const created = defaultSession();
    set((state) => ({ sessions: { ...state.sessions, [nodeId]: created } }));
    return created;
  },
  setWorkspacePath: (nodeId, path) => {
    set((state) => ({
      sessions: {
        ...state.sessions,
        [nodeId]: {
          ...(state.sessions[nodeId] ?? defaultSession()),
          workspacePath: path,
        },
      },
    }));
  },
  setAgent: (nodeId, agent) => {
    set((state) => ({
      sessions: {
        ...state.sessions,
        [nodeId]: { ...(state.sessions[nodeId] ?? defaultSession()), agent },
      },
    }));
  },
  setDevServerStatus: (nodeId, data) => {
    set((state) => ({
      sessions: {
        ...state.sessions,
        [nodeId]: {
          ...(state.sessions[nodeId] ?? defaultSession()),
          devServerRunning: data.running,
          devServerUrl: data.url ?? state.sessions[nodeId]?.devServerUrl,
        },
      },
    }));
  },
  setPreflight: (nodeId, data) => {
    set((state) => ({
      sessions: {
        ...state.sessions,
        [nodeId]: {
          ...(state.sessions[nodeId] ?? defaultSession()),
          preflight: data,
        },
      },
    }));
  },
}));
