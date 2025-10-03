import { useMemo, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select-custom";
import { useDevtoolsNavigate } from "@/controllers/API/queries/devtools/use-devtools-navigate";
import { useDevtoolsPages } from "@/controllers/API/queries/devtools/use-devtools-pages";
import { useDevtoolsScreenshot } from "@/controllers/API/queries/devtools/use-devtools-screenshot";
import { useWorkspaceScaffold } from "@/controllers/API/queries/workspace/use-workspace-scaffold";
import { useWorkspaceStart } from "@/controllers/API/queries/workspace/use-workspace-start";
import { useWorkspaceStop } from "@/controllers/API/queries/workspace/use-workspace-stop";
import { useDevSettingsStore } from "@/stores/devSettingsStore";
import { useUiBuilderStore } from "@/stores/uiBuilderStore";

export default function UiBuilderModal({
  open,
  setOpen,
  nodeId,
  nodeName,
}: {
  open: boolean;
  setOpen: (open: boolean) => void;
  nodeId: string;
  nodeName?: string;
}) {
  const [voiceEnabled, setVoiceEnabled] = useState(true);

  const {
    getSession,
    setAgent,
    setWorkspacePath,
    setDevServerStatus,
    setPreflight,
  } = useUiBuilderStore();
  const session = getSession(nodeId);

  // DevTools MCP browser state
  const defaultDevUrl = useDevSettingsStore((s) => s.defaultDevUrl);
  const [browserUrl, setBrowserUrl] = useState(defaultDevUrl);
  const [lastScreenshotPath, setLastScreenshotPath] = useState<string | null>(
    null,
  );
  const pagesQuery = useDevtoolsPages({ server_name: "chrome-devtools" });
  const { mutate: navigateMut, isPending: navPending } = useDevtoolsNavigate();
  const { mutate: screenshotMut, isPending: shotPending } =
    useDevtoolsScreenshot();

  // Workspace lifecycle hooks
  const workspaceName = useMemo(() => {
    // Convert path-like input to a safe name (last segment)
    const raw = (session.workspacePath || "").trim();
    const seg = raw.split("/").filter(Boolean).pop() || "";
    return seg;
  }, [session.workspacePath]);

  const statusQuery = useWorkspaceStatus(
    { name: workspaceName },
    { enabled: Boolean(workspaceName) },
  );

  const { mutate: startDev, isPending: startPending } = useWorkspaceStart({
    onSuccess: (res) => {
      setDevServerStatus(nodeId, { running: !!res.started });
      statusQuery.refetch();
    },
  });
  const { mutate: stopDev, isPending: stopPending } = useWorkspaceStop({
    onSuccess: (res) => {
      setDevServerStatus(nodeId, { running: false });
      statusQuery.refetch();
    },
  });

  const {
    mutate: scaffold,
    mutateAsync: scaffoldAsync,
    isPending: scaffoldPending,
  } = useWorkspaceScaffold({
    onSuccess: (_res) => {
      // after scaffold, attempt to start dev automatically when using Start Building
      if (workspaceName) {
        startDev({ name: workspaceName });
      }
    },
  });

  const { mutateAsync: startDevAsync } = useWorkspaceStart();

  // Build & Preview flow
  const [buildBusy, setBuildBusy] = useState(false);
  const [buildStage, setBuildStage] = useState<string | null>(null);
  const [buildError, setBuildError] = useState<string | null>(null);

  async function waitForUrl(url: string, timeoutMs = 30000, intervalMs = 1000) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      try {
        // no-cors to avoid CORS errors; resolve means server reachable
        await fetch(url, { mode: "no-cors" });
        return true;
      } catch (_) {
        // ignore and retry
      }
      await new Promise((r) => setTimeout(r, intervalMs));
    }
    return false;
  }

  async function handleBuildAndPreview() {
    if (!workspaceName) return;
    setBuildError(null);
    setBuildBusy(true);
    try {
      setBuildStage("Scaffolding project");
      await scaffoldAsync({ name: workspaceName });

      setBuildStage("Starting dev server");
      const url = session.devServerUrl || defaultDevUrl;
      await startDevAsync({ name: workspaceName });
      setDevServerStatus(nodeId, { running: true, url });
      statusQuery.refetch();

      setBuildStage("Waiting for dev server");
      const ready = await waitForUrl(url, 30000, 1000);

      setBuildStage("Opening preview");
      await new Promise<void>((resolve, reject) =>
        navigateMut(
          { url },
          {
            onSuccess: () => resolve(),
            onError: (e: any) => reject(e),
          },
        ),
      );

      if (!ready) {
        // Even if wait failed, we attempted to open. Surface soft warning.
        setBuildError("Dev server readiness not confirmed; preview attempted.");
      }
    } catch (e: any) {
      setBuildError(e?.message || "Build & Preview failed");
    } finally {
      setBuildStage(null);
      setBuildBusy(false);
    }
  }

  const title = useMemo(
    () => `UI Builder${nodeName ? ` — ${nodeName}` : ""}`,
    [nodeName],
  );

  const handleOpenPreview = () => {
    if (session.devServerRunning && session.devServerUrl) {
      window.open(session.devServerUrl, "_blank", "noopener,noreferrer");
    } else {
      console.info(
        "Preview not available: dev server is not running or URL not set",
      );
    }
  };

  const handleRunPreflight = () => {
    // Placeholder: integrate with backend/system checks in follow-up issue #49
    setPreflight(nodeId, {
      node: "unknown",
      npm: "unknown",
      playwright: "unknown",
      claude: "unknown",
      warp: "unknown",
      timestamp: new Date().toISOString(),
    });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-5xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <IconComponent name="Brush" className="h-5 w-5" />
            {title}
          </DialogTitle>
          <DialogDescription>
            Voice-first agent-driven UI Builder. Shell structure with
            placeholders for voice, preview, preflight, agent orchestration, and
            workspace lifecycle.
          </DialogDescription>
        </DialogHeader>

        <div className="mt-2 grid grid-cols-12 gap-4">
          {/* Conversation pane (placeholder) */}
          <div className="col-span-12 md:col-span-7">
            <div className="rounded-lg border p-3 h-72 flex items-center justify-center text-muted-foreground">
              Conversation pane (placeholder)
            </div>
          </div>

          {/* Controls and settings */}
          <div className="col-span-12 md:col-span-5 flex flex-col gap-3">
            {/* Browser (MCP) */}
            <div className="rounded-lg border p-3 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <IconComponent name="Globe" className="h-4 w-4" />
                  <span>Browser (MCP)</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span>Server:</span>
                  <code>chrome-devtools</code>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Input
                  value={browserUrl}
                  onChange={(e) => setBrowserUrl(e.target.value)}
                  placeholder="Enter URL"
                />
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={navPending}
                  onClick={() => navigateMut({ url: browserUrl })}
                >
                  {navPending ? "Navigating..." : "Navigate"}
                </Button>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => pagesQuery.refetch()}
                  disabled={pagesQuery.isLoading}
                >
                  {pagesQuery.isLoading ? "Listing..." : "List Pages"}
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={shotPending}
                  onClick={() =>
                    screenshotMut(
                      {
                        fullPage: true,
                        workspace: session.workspacePath || undefined,
                      },
                      {
                        onSuccess: (res) => {
                          if (res.saved && res.path)
                            setLastScreenshotPath(res.path);
                        },
                      },
                    )
                  }
                >
                  {shotPending ? "Capturing..." : "Full Screenshot"}
                </Button>
                {lastScreenshotPath && (
                  <a
                    className="text-xs underline"
                    href={`file://${lastScreenshotPath}`}
                    target="_blank"
                    rel="noreferrer"
                    title={lastScreenshotPath}
                  >
                    Open last screenshot
                  </a>
                )}
              </div>
              {pagesQuery.data?.pages?.length ? (
                <div className="rounded-md bg-muted/40 p-2 text-xs">
                  <div className="mb-1 font-medium">Pages</div>
                  <ul className="list-disc space-y-1 pl-4">
                    {pagesQuery.data.pages.map((p, i) => (
                      <li key={i} className="truncate">
                        {p}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
            {/* Voice toggle */}
            <div className="rounded-lg border p-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <IconComponent name="Mic" className="h-4 w-4" />
                <span>Voice</span>
              </div>
              <Button
                size="sm"
                variant={voiceEnabled ? "default" : "secondary"}
                onClick={() => setVoiceEnabled((v) => !v)}
              >
                {voiceEnabled ? "On" : "Off"}
              </Button>
            </div>

            {/* Chat fallback info */}
            <div className="rounded-lg border p-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <IconComponent
                  name="MousePointerSquareDashed"
                  className="h-4 w-4"
                />
                <span>Chat</span>
              </div>
              <span className="text-sm text-muted-foreground">
                Hidden by default
              </span>
            </div>

            {/* Agent selection and preview */}
            <div className="rounded-lg border p-3 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <IconComponent name="Settings2" className="h-4 w-4" />
                  <span>Agent</span>
                </div>
                <Select
                  onValueChange={(value) => setAgent(nodeId, value as any)}
                  value={session.agent}
                >
                  <SelectTrigger className="w-40" />
                  <SelectContent>
                    <SelectItem value="warp">warp</SelectItem>
                    <SelectItem value="claude">claude</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <IconComponent name="Monitor" className="h-4 w-4" />
                  <span>Preview</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">
                    {statusQuery.data?.running || session.devServerRunning
                      ? "Running"
                      : "Stopped"}
                  </span>
                  <ShadTooltip
                    content={
                      statusQuery.data?.running || session.devServerRunning
                        ? "Open Workspace Preview via MCP"
                        : "Dev server not running"
                    }
                  >
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={
                        !(statusQuery.data?.running || session.devServerRunning)
                      }
                      onClick={() => {
                        const url =
                          session.devServerUrl || browserUrl || defaultDevUrl;
                        setBrowserUrl(url);
                        navigateMut({ url });
                      }}
                    >
                      Open Workspace Preview
                    </Button>
                  </ShadTooltip>
                </div>
              </div>
            </div>

            {/* Workspace */}
            <div className="rounded-lg border p-3 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <IconComponent name="Folder" className="h-4 w-4" />
                  <span className="font-medium">Workspace</span>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="primary"
                    disabled={!workspaceName || scaffoldPending || buildBusy}
                    onClick={() => scaffold({ name: workspaceName })}
                  >
                    {scaffoldPending ? "Scaffolding..." : "Start Building"}
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={!workspaceName || buildBusy}
                    onClick={handleBuildAndPreview}
                  >
                    {buildBusy
                      ? buildStage
                        ? buildStage
                        : "Working..."
                      : "Build & Preview"}
                  </Button>
                </div>
              </div>
              {(buildBusy || buildError) && (
                <div className="rounded-md bg-muted/40 p-2 text-xs">
                  {buildBusy && (
                    <div className="mb-1">{buildStage || "Working..."}</div>
                  )}
                  {buildError && (
                    <div className="text-accent-red-foreground">
                      {buildError}
                    </div>
                  )}
                </div>
              )}
              <div className="flex items-center gap-2">
                <IconComponent name="Folder" className="h-4 w-4" />
                <span className="font-medium">Workspace</span>
              </div>
              <input
                className="w-full rounded-md border bg-background px-2 py-1 text-sm"
                placeholder="e.g. apps/my-ui"
                value={session.workspacePath}
                onChange={(e) => setWorkspacePath(nodeId, e.target.value)}
              />
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">
                  Configure the project path (name). Dev controls require a
                  valid name.
                </span>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={!workspaceName || startPending || buildBusy}
                    onClick={() => startDev({ name: workspaceName })}
                  >
                    {startPending ? "Starting..." : "Start Dev"}
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={!workspaceName || stopPending || buildBusy}
                    onClick={() => stopDev({ name: workspaceName })}
                  >
                    {stopPending ? "Stopping..." : "Stop Dev"}
                  </Button>
                </div>
              </div>
            </div>

            {/* Dependency Preflight */}
            <div className="rounded-lg border p-3 flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <IconComponent name="ClipboardCheck" className="h-4 w-4" />
                <span className="font-medium">Dependency Preflight</span>
              </div>
              <ul className="text-sm text-muted-foreground grid grid-cols-2 gap-1">
                <li>Node.js: {session.preflight?.node ?? "unknown"}</li>
                <li>npm: {session.preflight?.npm ?? "unknown"}</li>
                <li>
                  Playwright: {session.preflight?.playwright ?? "unknown"}
                </li>
                <li>claude CLI: {session.preflight?.claude ?? "unknown"}</li>
                <li>warp CLI: {session.preflight?.warp ?? "unknown"}</li>
              </ul>
              <div className="flex justify-end">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={handleRunPreflight}
                >
                  Run Checks
                </Button>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setOpen(false)}>
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
