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
  const [browserUrl, setBrowserUrl] = useState("http://localhost:5173/");
  const [lastScreenshotPath, setLastScreenshotPath] = useState<string | null>(
    null,
  );
  const pagesQuery = useDevtoolsPages({ server_name: "chrome-devtools" });
  const { mutate: navigateMut, isPending: navPending } = useDevtoolsNavigate();
  const { mutate: screenshotMut, isPending: shotPending } =
    useDevtoolsScreenshot();

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
                    {session.devServerRunning ? "Running" : "Stopped"}
                  </span>
                  <ShadTooltip
                    content={
                      session.devServerRunning
                        ? "Open preview"
                        : "Dev server not running"
                    }
                  >
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={handleOpenPreview}
                    >
                      Open Preview
                    </Button>
                  </ShadTooltip>
                </div>
              </div>
            </div>

            {/* Workspace */}
            <div className="rounded-lg border p-3 flex flex-col gap-2">
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
                  Configure the project path where the agent will generate your
                  UI.
                </span>
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" disabled>
                    Start Dev
                  </Button>
                  <Button size="sm" variant="secondary" disabled>
                    Stop Dev
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
