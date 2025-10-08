import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Loading from "@/components/ui/loading";
import { Switch } from "@/components/ui/switch";
import { useGetAICodegenSettings } from "@/controllers/API/queries/ai/use-get-ai-codegen-settings";
import { useGetWorkspaces } from "@/controllers/API/queries/ai/use-get-workspaces";
import { usePutAICodegenSettings } from "@/controllers/API/queries/ai/use-put-ai-codegen-settings";
import {
  useDeleteAllWorkspaces,
  useDeleteWorkspace,
  useGetWorkspaceFile,
  useGetWorkspaceLs,
} from "@/controllers/API/queries/ai/use-workspace-ops";
import useAlertStore from "@/stores/alertStore";

export default function AICodegenPage() {
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  const { data: settings, isLoading } = useGetAICodegenSettings();
  const { mutate: saveSettings, isPending: isSaving } = usePutAICodegenSettings(
    {
      onSuccess: () => setSuccessData({ title: "AI Codegen settings saved" }),
      onError: (e: any) =>
        setErrorData({ title: "Error saving settings", list: [e?.message] }),
    },
  );

  const [enabled, setEnabled] = useState(false);
  const [cli, setCli] = useState("warp");
  const [profile, setProfile] = useState("");
  const [timeoutMs, setTimeoutMs] = useState<number | "">(120000);
  const [workingDir, setWorkingDir] = useState<
    "repo_root" | "workspace" | string
  >("repo_root");
  const [apiKeyEnv, setApiKeyEnv] = useState("");
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!settings) return;
    setEnabled(Boolean(settings.ai_codegen_enabled));
    setCli(settings.ai_codegen_cli || "warp");
    setProfile(settings.ai_codegen_profile || "");
    setTimeoutMs(settings.ai_codegen_timeout_ms ?? 120000);
    setWorkingDir((settings.ai_codegen_working_dir as any) || "repo_root");
    setApiKeyEnv(settings.ai_codegen_api_key_env || "");
    // Only update overrides if the content actually changed (deep comparison via JSON)
    const newOverrides = settings.overridden_by_env || {};
    setOverrides((prev) => {
      if (JSON.stringify(prev) === JSON.stringify(newOverrides)) return prev;
      return newOverrides;
    });
  }, [settings]);

  function EnvBadge({ k }: { k: string }) {
    const active = overrides?.[k];
    return active ? (
      <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-300">
        env override
      </span>
    ) : null;
  }

  // Workspaces state - must be before any conditional returns!
  const { data: wsList, refetch: refetchWs } = useGetWorkspaces();
  const delOne = useDeleteWorkspace();
  const delAll = useDeleteAllWorkspaces();

  const [selectedRoot, setSelectedRoot] = useState<string | undefined>(
    undefined,
  );
  const [cwd, setCwd] = useState<string>("");
  const { data: ls } = useGetWorkspaceLs(selectedRoot, cwd);
  const [selectedFile, setSelectedFile] = useState<string | undefined>(
    undefined,
  );
  const { data: fileData } = useGetWorkspaceFile(selectedRoot, selectedFile);

  function handleSave() {
    const payload: Record<string, any> = {
      ai_codegen_enabled: enabled,
      ai_codegen_cli: cli,
      ai_codegen_profile: profile || null,
      ai_codegen_timeout_ms: typeof timeoutMs === "number" ? timeoutMs : 120000,
      ai_codegen_working_dir: workingDir,
      ai_codegen_api_key_env: apiKeyEnv || null,
    };
    saveSettings(payload);
  }

  if (isLoading && !settings) return <Loading />;

  function WorkspaceBrowser() {
    if (!selectedRoot) return null;
    return (
      <div className="mt-2 border rounded p-2">
        <div className="flex items-center gap-2 text-xs">
          <span className="font-semibold">Path:</span>
          <code>/{cwd}</code>
          <Button
            size="xs"
            variant="outline"
            onClick={() => {
              setCwd("");
              setSelectedFile(undefined);
            }}
          >
            Root
          </Button>
        </div>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <div className="border rounded p-2 h-64 overflow-auto text-xs">
            {(ls?.entries ?? []).map((e) => (
              <div key={e.name} className="flex items-center justify-between">
                <button
                  className="underline"
                  onClick={() => {
                    if (e.is_dir) {
                      setCwd(cwd ? `${cwd}/${e.name}` : e.name);
                      setSelectedFile(undefined);
                    } else {
                      setSelectedFile(cwd ? `${cwd}/${e.name}` : e.name);
                    }
                  }}
                >
                  {e.is_dir ? `📁 ${e.name}` : `📄 ${e.name}`}
                </button>
                {!e.is_dir && e.size != null && (
                  <span className="text-muted-foreground">{e.size} B</span>
                )}
              </div>
            ))}
          </div>
          <div className="border rounded p-2 h-64 overflow-auto text-xs whitespace-pre-wrap">
            {fileData?.content ?? "(select a file)"}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-2 space-y-4">
      <div>
        <h3 className="text-sm font-semibold">AI Codegen</h3>
        <p className="text-xs text-muted-foreground">
          Configure the external coding agent CLI used to port Python components
          to Rust. Values set via environment variables are indicated and shown
          here for visibility.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="flex items-center justify-between col-span-2">
          <div className="text-sm">
            Enable AI codegen <EnvBadge k="ai_codegen_enabled" />
          </div>
          <Switch checked={enabled} onCheckedChange={setEnabled} />
        </div>
        <div>
          <Label>
            CLI executable <EnvBadge k="ai_codegen_cli" />
          </Label>
          <Input
            value={cli}
            onChange={(e) => setCli(e.target.value)}
            placeholder="warp"
          />
          <div className="text-xs text-muted-foreground mt-1">
            Command to invoke (e.g., warp)
          </div>
        </div>
        <div>
          <Label>
            Profile ID <EnvBadge k="ai_codegen_profile" />
          </Label>
          <Input
            value={profile}
            onChange={(e) => setProfile(e.target.value)}
            placeholder="j9JE9JgmTTnox3KeKmOQCS"
          />
          <div className="text-xs text-muted-foreground mt-1">
            Passed with --profile; model choice is defined in the profile
          </div>
        </div>
        <div>
          <Label>
            Timeout (ms) <EnvBadge k="ai_codegen_timeout_ms" />
          </Label>
          <Input
            type="number"
            value={timeoutMs}
            onChange={(e) => setTimeoutMs(parseInt(e.target.value || "0", 10))}
          />
        </div>
        <div>
          <Label>
            Working directory <EnvBadge k="ai_codegen_working_dir" />
          </Label>
          <Input
            value={workingDir}
            onChange={(e) => setWorkingDir(e.target.value)}
            placeholder="repo_root | workspace"
          />
          <div className="text-xs text-muted-foreground mt-1">
            Use repo_root to give the agent full codebase context; workspace to
            limit scope
          </div>
        </div>
        <div>
          <Label>
            API key env var (optional) <EnvBadge k="ai_codegen_api_key_env" />
          </Label>
          <Input
            value={apiKeyEnv}
            onChange={(e) => setApiKeyEnv(e.target.value)}
            placeholder="WARP_API_KEY"
          />
          <div className="text-xs text-muted-foreground mt-1">
            The server never logs or reads the secret value; only the variable
            name
          </div>
        </div>
      </div>

      <div className="flex justify-end">
        <Button size="sm" onClick={handleSave} disabled={isSaving}>
          {isSaving ? "Saving…" : "Save"}
        </Button>
      </div>

      <div className="pt-4 space-y-2">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold">Temporary workspaces</h4>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={() => refetchWs()}>
              Refresh
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={async () => {
                await delAll.mutateAsync();
                refetchWs();
                setSelectedRoot(undefined);
              }}
            >
              Delete all
            </Button>
          </div>
        </div>
        <div className="border rounded p-2 text-xs">
          {(wsList?.workspaces ?? []).length === 0 && (
            <div className="text-muted-foreground">No workspaces found</div>
          )}
          {(wsList?.workspaces ?? []).map((w) => (
            <div
              key={w.root_b64}
              className="flex items-center justify-between py-1"
            >
              <div className="flex items-center gap-2">
                <span className="font-mono">{w.name}</span>
                {w.type && (
                  <span className="px-1.5 py-0.5 rounded bg-muted">
                    {w.type}
                  </span>
                )}
                {w.component_id && (
                  <span className="text-muted-foreground">
                    {w.component_id}
                  </span>
                )}
                {w.success != null && (
                  <span
                    className={w.success ? "text-green-600" : "text-red-600"}
                  >
                    {w.success ? "ok" : "failed"}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="xs"
                  variant="secondary"
                  onClick={() => {
                    setSelectedRoot(w.root_b64);
                    setCwd("");
                    setSelectedFile(undefined);
                  }}
                >
                  Open
                </Button>
                <Button
                  size="xs"
                  variant="destructive"
                  onClick={async () => {
                    await delOne.mutateAsync(w.root_b64);
                    refetchWs();
                    if (selectedRoot === w.root_b64) setSelectedRoot(undefined);
                  }}
                >
                  Delete
                </Button>
              </div>
            </div>
          ))}
        </div>
        <WorkspaceBrowser />
      </div>
    </div>
  );
}
