import { create } from "zustand";

export type DevSettingsState = {
  defaultDevUrl: string;
  setDefaultDevUrl: (url: string) => void;
};

const DEFAULT_URL = "http://localhost:5173/";
const STORAGE_KEY = "uiBuilderDefaultDevUrl";

export const useDevSettingsStore = create<DevSettingsState>((set, get) => ({
  defaultDevUrl: (() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored && stored.trim().length > 0 ? stored : DEFAULT_URL;
  })(),
  setDefaultDevUrl: (url: string) => {
    const sanitized = url.trim();
    set(() => ({ defaultDevUrl: sanitized || DEFAULT_URL }));
    window.localStorage.setItem(STORAGE_KEY, sanitized || DEFAULT_URL);
  },
}));
