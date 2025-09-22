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

  const title = useMemo(
    () => `UI Builder${nodeName ? ` — ${nodeName}` : ""}`,
    [nodeName],
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <IconComponent name="Brush" className="h-5 w-5" />
            {title}
          </DialogTitle>
          <DialogDescription>
            Voice-first agent-driven UI Builder. This is a stub dialog to
            satisfy initial scaffolding; functionality will be implemented in
            follow-up issues (voice, agent orchestration, preview, Playwright
            MCP, etc.).
          </DialogDescription>
        </DialogHeader>

        <div className="mt-2 grid grid-cols-12 gap-4">
          {/* Conversation pane (placeholder) */}
          <div className="col-span-12 md:col-span-7">
            <div className="rounded-lg border p-3 h-64 flex items-center justify-center text-muted-foreground">
              Conversation pane (placeholder)
            </div>
          </div>

          {/* Controls and settings */}
          <div className="col-span-12 md:col-span-5 flex flex-col gap-3">
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

            <div className="rounded-lg border p-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <IconComponent name="Monitor" className="h-4 w-4" />
                <span>Preview</span>
              </div>
              <ShadTooltip content="Opens a preview window (stub)">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    // Stub action for now
                    console.info("Open Preview clicked for node", nodeId);
                  }}
                >
                  Open Preview
                </Button>
              </ShadTooltip>
            </div>

            <div className="rounded-lg border p-3">
              <div className="text-sm font-medium mb-2">Workspace</div>
              <div className="text-sm text-muted-foreground">
                Configure workspace path, dev server lifecycle, and agent
                permissions in follow-up issues.
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
