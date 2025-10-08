import React from "react";
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
  useListComponentTwinsByKeys,
  usePostComponentTwin,
  usePostWasmPublish,
  usePutWasmCapabilities,
} from "@/controllers/API/queries/wasm";
import { usePostBuildStart } from "@/controllers/API/queries/wasm/use-post-build-start";
import { usePostCodegenStart } from "@/controllers/API/queries/wasm/use-post-codegen-start";
import { usePostGenerateRust } from "@/controllers/API/queries/wasm/use-post-generate-rust";
import { usePostGenerateWit } from "@/controllers/API/queries/wasm/use-post-generate-wit";
import BuildConsoleModal from "@/modals/buildConsoleModal";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";

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
  if (!ref) return false;
  if (ref !== ref.toLowerCase()) return false;
  const parts = ref.split(":");
  if (parts.length !== 2) return false;
  const [repo, tag] = parts;
  if (!tag || tag.length > 128) return false;
  if ((repo.match(/\//g) || []).length < 2) return false;
  if (!/^[a-z0-9._/-]+$/.test(repo)) return false;
  if (!/^[a-z0-9._-]+$/.test(tag)) return false;
  return true;
}

export default function ComponentDeploymentModal({
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
  const currentFlow = useFlowsManagerStore((s) => s.currentFlow);
  const flowId = currentFlow?.id;
  const { data: twins } = useListComponentTwinsByKeys(flowId, nodeId);
  const twin = twins && twins.length > 0 ? twins[0] : undefined;
  const twinId = twin?.id as string | undefined;

  const { data: caps, isLoading, isError } = useGetWasmCapabilities(twinId);
  const { data: twinData } = useGetComponentTwin(twinId);
  const getNode = useFlowStore((s) => s.getNode);
  const node = getNode(nodeId);
  // Fall back to the node's template code when the twin doesn't carry python_source yet
  const pythonFromNode = (node as any)?.data?.node?.template?.code?.value as
    | string
    | undefined;
  const pythonSource = twinData?.python_source ?? pythonFromNode;
  // Decode rust_source if it is a JSON mapping of path -> content
  const rustDisplay = React.useMemo(() => {
    const rs = twinData?.rust_source;
    if (!rs) return undefined;
    try {
      const parsed = JSON.parse(rs);
      if (parsed && typeof parsed === "object") {
        const files = Object.entries(parsed as Record<string, any>)
          .map(([p, c]) => `// ${p}\n${String(c ?? "")}`)
          .join("\n\n");
        return files;
      }
    } catch {}
    return rs;
  }, [twinData?.rust_source]);
  const { data: suggest } = useGetWasmSuggestOCI(twinId);
  const publish = usePostWasmPublish();
  const saveCaps = usePutWasmCapabilities();
  const createTwin = usePostComponentTwin();
  const genWit = usePostGenerateWit();
  const genRust = usePostGenerateRust();
  const startBuild = usePostBuildStart();
  // AI codegen SSE
  const { mutateAsync: startCodegen, isPending: isStartingCodegen } =
    usePostCodegenStart();
  const [buildRunId, setBuildRunId] = React.useState<string | undefined>(
    undefined,
  );
  const [codegenRunId, setCodegenRunId] = React.useState<string | undefined>(
    undefined,
  );
  const [openConsole, setOpenConsole] = React.useState(false);

  function buildDefaultOciRef() {
    if (suggest?.ref) return suggest.ref;
    const base = (nodeName || nodeId || "component").toLowerCase();
    return `ghcr.io/ibm/langflow/${base.replace(/[^a-z0-9._-]/g, "-")}:latest`;
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Deployment</DialogTitle>
        </DialogHeader>
        <div className="min-h-0 overflow-y-auto pr-1">
          {!twinId ? (
            <div className="space-y-3">
              <div className="text-sm text-muted-foreground">
                No component twin detected for this node. Create one to enable
                security settings, code review, parity and publishing.
              </div>
              <div className="flex justify-end">
                <Button
                  size="sm"
                  onClick={async () => {
                    if (!flowId) return;
                    // Minimal I/O schema scaffold; TODO: derive from node template
                    const io_schema = {
                      inputs: [{ name: "text", type: "string" }],
                      outputs: [{ name: "text", type: "string" }],
                    };
                    try {
                      // Generate WIT (will create or upsert the twin)
                      const witRes = await genWit.mutateAsync({
                        flow_id: flowId,
                        component_id: nodeId,
                        io_schema,
                      });
                      const newTwinId = witRes?.twin?.id;
                      if (newTwinId) {
                        // Generate Rust skeleton so code tab has content
                        const pkg = `lf_${(nodeName || nodeId).toLowerCase().replace(/[^a-z0-9_]/g, "_")}`;
                        await genRust.mutateAsync({
                          twin_id: newTwinId,
                          package_name: pkg,
                        });
                        // Optional: dry-run build to prepare workspace (kept lightweight)
                        try {
                          await startBuild.mutateAsync({
                            twin_id: newTwinId,
                            dry_run: true,
                          });
                        } catch {}
                      }
                    } catch (e) {
                      // fallback to simple record create if wit pipeline fails
                      try {
                        await createTwin.mutateAsync({
                          flow_id: flowId,
                          component_id: nodeId,
                        });
                      } catch {}
                    }
                  }}
                  disabled={
                    genWit.isPending ||
                    genRust.isPending ||
                    startBuild.isPending ||
                    createTwin.isPending
                  }
                >
                  {genWit.isPending ||
                  genRust.isPending ||
                  startBuild.isPending ||
                  createTwin.isPending
                    ? "Building…"
                    : "Build twin"}
                </Button>
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
                <div className="flex items-center justify-between">
                  <TabsList>
                    <TabsTrigger value="security">Security</TabsTrigger>
                    <TabsTrigger value="code">Code</TabsTrigger>
                    <TabsTrigger value="publish">Publish</TabsTrigger>
                  </TabsList>

                  <div className="ml-4 flex items-center gap-2">
                    {twinId && (
                      <>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={async () => {
                            if (!twinId) return;
                            // Ensure WIT exists
                            if (!twinData?.wit_source) {
                              const io_schema = {
                                inputs: [{ name: "text", type: "string" }],
                                outputs: [{ name: "text", type: "string" }],
                              };
                              await genWit.mutateAsync({
                                twin_id: twinId,
                                io_schema,
                              });
                            }
                            try {
                              const hint =
                                window.prompt(
                                  "Optional guidance for the agent (leave blank to skip):",
                                ) || undefined;
                              const res = await startCodegen({
                                twin_id: twinId,
                                use_ai: true,
                                ...(hint ? { user_hint: hint } : {}),
                              } as any);
                              setCodegenRunId(res.run_id);
                              setOpenConsole(true);
                            } catch (e) {
                              // Fallback to skeleton if AI not configured
                              await genRust.mutateAsync({
                                twin_id: twinId,
                                package_name: `lf_${(nodeName || nodeId).toLowerCase().replace(/[^a-z0-9_]/g, "_")}`,
                                use_ai: false,
                              });
                            }
                          }}
                          disabled={
                            genWit.isPending ||
                            genRust.isPending ||
                            isStartingCodegen
                          }
                        >
                          {genWit.isPending ||
                          genRust.isPending ||
                          isStartingCodegen
                            ? "Generating…"
                            : "Generate sources"}
                        </Button>
                        <Button
                          size="sm"
                          onClick={async () => {
                            if (!twinId) return;
                            const res = await startBuild.mutateAsync({
                              twin_id: twinId,
                              dry_run: false,
                            });
                            setBuildRunId(res.run_id);
                            setOpenConsole(true);
                          }}
                          disabled={startBuild.isPending}
                        >
                          {startBuild.isPending ? "Building…" : "Build"}
                        </Button>
                        {buildRunId && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setOpenConsole(true)}
                          >
                            Show details
                          </Button>
                        )}
                      </>
                    )}
                  </div>
                </div>

                <TabsContent value="security">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold">Security</h3>
                    <div className="text-xs text-muted-foreground">
                      Switch to advanced JSON if needed.
                    </div>
                  </div>
                  <StructuredCapabilityEditor
                    inferred={caps?.inferred ?? {}}
                    overrides={caps?.overrides ?? {}}
                    onSave={(overrides) => {
                      if (!twinId) return;
                      saveCaps.mutate({ twin_id: twinId, overrides });
                    }}
                    saving={saveCaps.isPending}
                  />
                  <div className="mt-4">
                    <h3 className="text-sm font-semibold mb-2">Effective</h3>
                    <pre className="bg-muted p-2 rounded text-xs overflow-auto">
                      {JSON.stringify(caps?.effective ?? {}, null, 2)}
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
                        {pythonSource ?? "(no python source)"}
                      </pre>
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold mb-2">
                        Rust (read-only)
                      </h3>
                      <pre className="bg-muted p-2 rounded text-xs overflow-auto whitespace-pre-wrap">
                        {rustDisplay ?? "(no rust source)"}
                      </pre>
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
      {buildRunId && (
        <BuildConsoleModal
          runId={buildRunId}
          open={openConsole}
          onOpenChange={setOpenConsole}
          mode="build"
        />
      )}
      {codegenRunId && (
        <BuildConsoleModal
          runId={codegenRunId}
          open={openConsole}
          onOpenChange={setOpenConsole}
          mode="codegen"
        />
      )}
    </Dialog>
  );
}
