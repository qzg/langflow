import React, { useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  useGetComponentTwin,
  useGetWasmCapabilities,
  useGetWasmSuggestOCI,
  usePostWasmPublish,
  usePutWasmCapabilities,
} from "@/controllers/API/queries/wasm";
import { CustomLink } from "@/customization/components/custom-link";
import type { FlowType } from "@/types/flow";

function CapabilityEditor({
  initial,
  onSave,
  saving,
}: {
  initial: Record<string, any>;
  onSave: (o: Record<string, any>) => void;
  saving?: boolean;
}) {
  const [text, setText] = React.useState<string>(
    JSON.stringify(initial, null, 2),
  );
  React.useEffect(() => {
    setText(JSON.stringify(initial, null, 2));
  }, [initial]);
  return (
    <div className="space-y-2">
      <Textarea
        className="h-60"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="flex justify-end">
        <Button
          size="sm"
          onClick={() => {
            try {
              const parsed = text ? JSON.parse(text) : {};
              onSave(parsed);
            } catch (e) {
              // Silently ignore; in real UI, display validation error
              console.error("Invalid JSON", e);
            }
          }}
          disabled={saving}
        >
          {saving ? "Saving…" : "Save overrides"}
        </Button>
      </div>
    </div>
  );
}

function StructuredCapabilityEditor({
  inferred,
  overrides,
  onSave,
  saving,
}: {
  inferred: Record<string, any>;
  overrides: Record<string, any>;
  onSave: (o: Record<string, any>) => void;
  saving?: boolean;
}) {
  const [advanced, setAdvanced] = React.useState(false);
  const eff = React.useMemo(
    () => ({ ...(inferred || {}), ...(overrides || {}) }),
    [inferred, overrides],
  );
  const [domains, setDomains] = React.useState<string>("");
  const [ports, setPorts] = React.useState<string>("");
  const [kv, setKv] = React.useState<boolean>(false);
  const [blob, setBlob] = React.useState<boolean>(false);
  const [secrets, setSecrets] = React.useState<string>("");
  const [timeoutMs, setTimeoutMs] = React.useState<number>(30000);
  const [fileCsv, setFileCsv] = React.useState<boolean>(false);
  const [fileParquet, setFileParquet] = React.useState<boolean>(false);
  const [fileIceberg, setFileIceberg] = React.useState<boolean>(false);
  const [fileExcel, setFileExcel] = React.useState<boolean>(false);

  React.useEffect(() => {
    const net = eff.network || {};
    setDomains((net.domains || []).join(", "));
    setPorts((net.ports || []).join(", "));
    const stor = eff.storage || {};
    setKv(!!stor.kv);
    setBlob(!!stor.blob);
    const env = eff.env || {};
    setSecrets((env.secrets || []).join(", "));
    setTimeoutMs(eff.timeouts_ms ?? 30000);
    const files = eff?.data_sources?.files || {};
    setFileCsv(!!files.csv);
    setFileParquet(!!files.parquet);
    setFileIceberg(!!files.iceberg);
    setFileExcel(!!files.excel);
  }, [eff]);

  function saveStructured() {
    const out: Record<string, any> = {
      network: {
        domains: domains
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        ports: ports
          .split(",")
          .map((s) => parseInt(s.trim()))
          .filter((n) => !isNaN(n)),
      },
      storage: { kv, blob },
      env: {
        secrets: secrets
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      },
      timeouts_ms: timeoutMs,
      data_sources: {
        files: {
          csv: fileCsv,
          parquet: fileParquet,
          iceberg: fileIceberg,
          excel: fileExcel,
        },
      },
    };
    onSave(out);
  }

  if (advanced) {
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-sm font-semibold">Overrides (JSON)</div>
          <div className="flex items-center gap-2 text-xs">
            <span>Advanced JSON</span>
            <Switch checked={advanced} onCheckedChange={setAdvanced} />
          </div>
        </div>
        <CapabilityEditor initial={overrides} onSave={onSave} saving={saving} />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold">Overrides (structured)</div>
        <div className="flex items-center gap-2 text-xs">
          <span>Advanced JSON</span>
          <Switch checked={advanced} onCheckedChange={setAdvanced} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-xs">Allowed domains</label>
          <Input
            value={domains}
            onChange={(e) => setDomains(e.target.value)}
            placeholder="example.com, api.example.com"
          />
        </div>
        <div>
          <label className="text-xs">Allowed ports</label>
          <Input
            value={ports}
            onChange={(e) => setPorts(e.target.value)}
            placeholder="80, 443"
          />
        </div>
        <div className="flex items-center gap-2">
          <input
            id="kv"
            type="checkbox"
            checked={kv}
            onChange={(e) => setKv(e.target.checked)}
          />
          <label htmlFor="kv" className="text-xs">
            KV storage
          </label>
        </div>
        <div className="flex items-center gap-2">
          <input
            id="blob"
            type="checkbox"
            checked={blob}
            onChange={(e) => setBlob(e.target.checked)}
          />
          <label htmlFor="blob" className="text-xs">
            Blob storage
          </label>
        </div>
        <div className="col-span-2">
          <label className="text-xs">Secrets (comma-separated)</label>
          <Input
            value={secrets}
            onChange={(e) => setSecrets(e.target.value)}
            placeholder="OPENAI_API_KEY, OTHER_SECRET"
          />
        </div>
        <div>
          <label className="text-xs">Timeout (ms)</label>
          <Input
            type="number"
            value={timeoutMs}
            onChange={(e) => setTimeoutMs(parseInt(e.target.value || "0", 10))}
          />
        </div>
        <div className="col-span-2">
          <div className="text-xs mb-1">File types</div>
          <div className="flex gap-4 text-xs">
            <label className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={fileCsv}
                onChange={(e) => setFileCsv(e.target.checked)}
              />{" "}
              CSV
            </label>
            <label className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={fileParquet}
                onChange={(e) => setFileParquet(e.target.checked)}
              />{" "}
              Parquet
            </label>
            <label className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={fileIceberg}
                onChange={(e) => setFileIceberg(e.target.checked)}
              />{" "}
              Iceberg
            </label>
            <label className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={fileExcel}
                onChange={(e) => setFileExcel(e.target.checked)}
              />{" "}
              Excel
            </label>
          </div>
        </div>
      </div>
      <div className="flex justify-end">
        <Button size="sm" onClick={saveStructured} disabled={saving}>
          {saving ? "Saving…" : "Save overrides"}
        </Button>
      </div>
    </div>
  );
}

function PublishPanel({
  twinId,
  defaultRef,
  onPublish,
  isPublishing,
}: {
  twinId: string;
  defaultRef: string;
  onPublish: (ref: string) => void;
  isPublishing?: boolean;
}) {
  const [ref, setRef] = React.useState(defaultRef);
  React.useEffect(() => {
    setRef(defaultRef);
  }, [defaultRef]);
  const isValid = validateOCIRef(ref);
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium">OCI reference</label>
      <Input value={ref} onChange={(e) => setRef(e.target.value)} />
      {!isValid && (
        <div className="text-xs text-destructive">
          Invalid reference. Use lowercase and include a tag (e.g.,
          ghcr.io/ibm/langflow/my-component:deadbeefcaf0).
        </div>
      )}
      <div className="flex justify-end">
        <Button
          size="sm"
          onClick={() => onPublish(ref)}
          disabled={isPublishing || !isValid}
        >
          {isPublishing ? "Publishing…" : "Publish"}
        </Button>
      </div>
    </div>
  );
}

function StatusStrip({ twin }: { twin: any }) {
  const [label, variant] = React.useMemo(() => {
    const now = Date.now();
    const last = twin?.last_verified_at
      ? new Date(twin.last_verified_at).getTime()
      : 0;
    const ageHrs = last ? (now - last) / (1000 * 60 * 60) : Infinity;
    const passed = !!twin?.parity_metrics?.text?.passed;

    if (passed && ageHrs <= 24) return ["In parity", "ok"] as const;
    if (passed && ageHrs > 24) return ["Parity stale", "warn"] as const;
    return [
      "Parity unknown or failed",
      twin?.parity_metrics ? "error" : "warn",
    ] as const;
  }, [twin]);

  const cls =
    variant === "ok"
      ? "text-emerald-600"
      : variant === "warn"
        ? "text-amber-600"
        : "text-destructive";
  return (
    <div className="text-sm">
      Status: <span className={`font-medium ${cls}`}>{label}</span>
    </div>
  );
}

function validateOCIRef(ref: string): boolean {
  // Minimal validation: must be lowercase, have at least two '/', and have a ':tag'
  if (!ref) return false;
  if (ref !== ref.toLowerCase()) return false;
  const parts = ref.split(":");
  if (parts.length !== 2) return false;
  const [repo, tag] = parts;
  if (!tag || tag.length > 128) return false;
  if ((repo.match(/\//g) || []).length < 2) return false;
  // allowed chars check
  if (!/^[a-z0-9._/-]+$/.test(repo)) return false;
  if (!/^[a-z0-9._-]+$/.test(tag)) return false;
  return true;
}

function RustSourceView({ source }: { source?: string | null }) {
  const display = React.useMemo(() => {
    if (!source) return undefined;
    try {
      const parsed = JSON.parse(source);
      if (parsed && typeof parsed === "object") {
        return Object.entries(parsed as Record<string, any>)
          .map(([p, c]) => `// ${p}\n${String(c ?? "")}`)
          .join("\n\n");
      }
    } catch {}
    return source ?? undefined;
  }, [source]);
  return (
    <pre className="bg-muted p-2 rounded text-xs overflow-auto whitespace-pre-wrap">
      {display ?? "(no rust source)"}
    </pre>
  );
}

export default function DeploymentModal({
  open,
  setOpen,
  flowData,
}: {
  open: boolean;
  setOpen: (open: boolean) => void;
  flowData: FlowType;
}) {
  // NOTE: FlowType does not expose twin_id; we attempt to load if present on custom field
  const twinId = (flowData as any)?.twin_id as string | undefined;
  const { data, isLoading, isError } = useGetWasmCapabilities(twinId);
  const { data: twin } = useGetComponentTwin(twinId);
  const { data: suggest } = useGetWasmSuggestOCI(twinId);
  const publish = usePostWasmPublish();
  const saveCaps = usePutWasmCapabilities();

  function buildDefaultOciRef() {
    if (suggest?.ref) return suggest.ref;
    // Fallback default: derive from flow name/id
    const base = (
      flowData?.name ||
      flowData?.id ||
      twinId ||
      "component"
    ).toLowerCase();
    return `ghcr.io/ibm/langflow/${base.replace(/[^a-z0-9._-]/g, "-")}:latest`;
  }

  useEffect(() => {
    // close on route change? leave noop
  }, []);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Deployment</DialogTitle>
        </DialogHeader>
        <div className="min-h-0 overflow-y-auto pr-1">
          {!twinId ? (
            <div className="space-y-3 text-sm text-muted-foreground">
              <p>No twin is associated with this item yet.</p>
              <p>
                To deploy, first create a component twin from the flow editor:
              </p>
              <ol className="list-decimal pl-5 space-y-1">
                <li>Open this flow in the editor.</li>
                <li>From a node's menu, choose "Deployment".</li>
                <li>
                  Click "Build twin", then return here to configure Security and
                  Publish.
                </li>
              </ol>
              <div className="pt-2">
                <CustomLink to={`/flow/${flowData.id}`}>
                  <Button size="sm">Open flow editor</Button>
                </CustomLink>
              </div>
            </div>
          ) : isLoading ? (
            <div className="text-sm">Loading capabilities…</div>
          ) : isError ? (
            <div className="text-sm text-destructive">
              Failed to load capabilities.
            </div>
          ) : (
            <div className="space-y-4">
              <StatusStrip twin={twin} />
              <Tabs defaultValue="security">
                <TabsList>
                  <TabsTrigger value="security">Security</TabsTrigger>
                  <TabsTrigger value="code">Code</TabsTrigger>
                  <TabsTrigger value="publish">Publish</TabsTrigger>
                </TabsList>

                <TabsContent value="security">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold">Security</h3>
                    <div className="text-xs text-muted-foreground">
                      Switch to advanced JSON if needed.
                    </div>
                  </div>
                  <StructuredCapabilityEditor
                    inferred={data?.inferred ?? {}}
                    overrides={data?.overrides ?? {}}
                    onSave={(overrides) => {
                      if (!twinId) return;
                      saveCaps.mutate({ twin_id: twinId, overrides });
                    }}
                    saving={saveCaps.isPending}
                  />
                  <div className="mt-4">
                    <h3 className="text-sm font-semibold mb-2">Effective</h3>
                    <pre className="bg-muted p-2 rounded text-xs overflow-auto">
                      {JSON.stringify(data?.effective ?? {}, null, 2)}
                    </pre>
                  </div>
                </TabsContent>

                <TabsContent value="code">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <h3 className="text-sm font-semibold mb-2">
                        Python (read-only)
                      </h3>
                      <pre className="bg-muted p-2 rounded text-xs overflow-auto whitespace-pre-wrap">
                        {twin?.python_source ?? "(no python source)"}
                      </pre>
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold mb-2">
                        Rust (read-only)
                      </h3>
                      <RustSourceView source={twin?.rust_source} />
                    </div>
                  </div>
                </TabsContent>

                <TabsContent value="publish">
                  <PublishPanel
                    twinId={twinId!}
                    defaultRef={buildDefaultOciRef()}
                    onPublish={(oci_ref) =>
                      publish.mutate({ twin_id: twinId!, oci_ref })
                    }
                    isPublishing={publish.isPending}
                  />
                </TabsContent>
              </Tabs>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
