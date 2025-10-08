import React from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useBuildEvents } from "@/controllers/API/queries/wasm/use-build-events";
import { useCodegenEvents } from "@/controllers/API/queries/wasm/use-codegen-events";

export default function BuildConsoleModal({
  runId,
  open,
  onOpenChange,
  mode = "build" as "build" | "codegen",
}: {
  runId?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode?: "build" | "codegen";
}) {
  const { logs, status, step, success } =
    mode === "build" ? useBuildEvents(runId) : useCodegenEvents(runId);
  const titleBase = mode === "build" ? "Build" : "Codegen";
  const title =
    success === undefined
      ? `${titleBase} in progress`
      : success
        ? `${titleBase} succeeded`
        : `${titleBase} failed`;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>
            {title}
            {status ? ` • ${status}` : ""}
            {step ? ` • ${step}` : ""}
          </DialogTitle>
        </DialogHeader>
        <div className="min-h-0 overflow-y-auto pr-1">
          <div className="text-xs font-mono whitespace-pre-wrap bg-muted rounded p-2">
            {logs.length === 0
              ? "(waiting for logs...)"
              : logs.map((e, i) => <div key={i}>{e.payload.line}</div>)}
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button
            size="sm"
            variant="secondary"
            onClick={() => onOpenChange(false)}
          >
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
