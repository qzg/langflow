import { useEffect, useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Loading from "@/components/ui/loading";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useGetWasmCloudSettings } from "@/controllers/API/queries/wasmcloud/use-get-wasmcloud-settings";
import { useGetWasmCloudTestConnection } from "@/controllers/API/queries/wasmcloud/use-get-wasmcloud-test-connection";
import { usePostWasmCloudInvoke } from "@/controllers/API/queries/wasmcloud/use-post-wasmcloud-invoke";
import { usePutWasmCloudSettings } from "@/controllers/API/queries/wasmcloud/use-put-wasmcloud-settings";
import useAlertStore from "@/stores/alertStore";

function isValidNatsUrl(url?: string | null) {
  if (!url) return true; // optional validation
  try {
    const u = new URL(url);
    return u.protocol === "nats:" && !!u.hostname;
  } catch (_e) {
    return false;
  }
}

export default function RuntimePage() {
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  const { data: settings, isLoading } = useGetWasmCloudSettings();
  const { mutate: saveSettings, isPending: isSaving } = usePutWasmCloudSettings(
    {
      onSuccess: () => setSuccessData({ title: "Settings saved" }),
      onError: (e: any) =>
        setErrorData({ title: "Error saving settings", list: [e?.message] }),
    },
  );
  const {
    mutate: testConnection,
    mutateAsync: testConnectionAsync,
    isPending: isTesting,
  } = useGetWasmCloudTestConnection({
    onError: (e: any) =>
      setErrorData({ title: "Test connection failed", list: [e?.message] }),
  });

  const { mutate: invoke, isPending: isInvoking } = usePostWasmCloudInvoke({
    onError: (e: any) =>
      setErrorData({ title: "Invoke failed", list: [e?.message] }),
  });

  const [enabled, setEnabled] = useState<boolean>(false);
  const [natsUrl, setNatsUrl] = useState<string>("");
  const [lattice, setLattice] = useState<string>("");
  const [timeoutMs, setTimeoutMs] = useState<number | "">("");
  const [credsPath, setCredsPath] = useState<string>("");
  const [credsStored, setCredsStored] = useState<boolean>(false);

  // Observe last test connection result
  const [lastTest, setLastTest] = useState<{
    timestamp: string;
    configured: boolean;
    available?: boolean | null;
    connected?: boolean | null;
    latency_ms?: number | null;
    error?: string | null;
  } | null>(null);

  // Invoke state
  const [componentId, setComponentId] = useState<string>("");
  const [operation, setOperation] = useState<string>("");
  const [payloadMode, setPayloadMode] = useState<
    "none" | "text" | "json" | "base64"
  >("none");
  const [latticeOverride, setLatticeOverride] = useState<string>("");
  const [payloadText, setPayloadText] = useState<string>("");
  const [payloadJson, setPayloadJson] = useState<string>("");
  const [payloadB64, setPayloadB64] = useState<string>("");
  const [invokeTimeout, setInvokeTimeout] = useState<number | "">("");
  const [invokeResult, setInvokeResult] = useState<{
    success: boolean;
    latency_ms?: number | null;
    data_text?: string | null;
    data_b64?: string | null;
    error?: string | null;
  } | null>(null);

  useEffect(() => {
    if (!settings) return;
    setEnabled(Boolean(settings.wasmcloud_enabled));
    setNatsUrl(settings.wasmcloud_nats_url ?? "");
    setLattice(settings.wasmcloud_lattice ?? "");
    setTimeoutMs(settings.wasmcloud_timeout_ms ?? "");
    setCredsStored(Boolean(settings.wasmcloud_creds_present));
    setCredsPath(""); // never expose stored path; set empty for overwrite
  }, [settings]);

  const isConfigured = useMemo(() => {
    // Minimal criteria: enabled and NATS url provided
    return Boolean(enabled && natsUrl);
  }, [enabled, natsUrl]);

  const natsUrlValid = isValidNatsUrl(natsUrl);

  function handleSave() {
    if (!natsUrlValid) {
      setErrorData({
        title: "Invalid NATS URL",
        list: ["Use nats://host:port"],
      });
      return;
    }
    const updates: Record<string, any> = {
      wasmcloud_enabled: enabled,
      wasmcloud_nats_url: natsUrl || null,
      wasmcloud_lattice: lattice || null,
      wasmcloud_timeout_ms: typeof timeoutMs === "number" ? timeoutMs : null,
    };
    if (credsPath && credsPath.trim() !== "") {
      updates.wasmcloud_creds_path = credsPath.trim();
    }
    saveSettings(updates);
  }

  async function handleTest() {
    testConnection(undefined, {
      onSuccess: (data) => {
        const details = [
          `Configured: ${Boolean(data.configured)}`,
          `Available: ${data.available ?? "unknown"}`,
          `Connected: ${data.connected ?? "unknown"}`,
          data.message ? `Message: ${data.message}` : undefined,
        ].filter(Boolean) as string[];

        setLastTest({
          timestamp: new Date().toLocaleString(),
          configured: Boolean(data.configured),
          available: data.available ?? undefined,
          connected: data.connected ?? undefined,
          latency_ms: (data as any).latency_ms ?? undefined,
          error: (data as any).message ?? undefined,
        });

        if (data.connected === true) {
          setSuccessData({ title: "wasmCloud connection OK" });
        } else {
          setErrorData({ title: "wasmCloud connection failed", list: details });
        }
      },
      onError: (_e) => {
        setLastTest({
          timestamp: new Date().toLocaleString(),
          configured: true,
          available: true,
          connected: false,
          latency_ms: undefined,
          error: "Request failed",
        });
      },
    });
  }

  function latencyClass(ms?: number | null) {
    if (ms == null) return "text-muted-foreground";
    if (ms < 200) return "text-green-600";
    if (ms < 1000) return "text-yellow-600";
    return "text-red-600";
  }

  function buildInvokePayload() {
    const body: any = {
      component_id: componentId.trim(),
      operation: operation.trim(),
    };
    if (invokeTimeout !== "" && typeof invokeTimeout === "number") {
      body.timeout_ms = invokeTimeout;
    }
    if (latticeOverride && latticeOverride.trim() !== "") {
      body.lattice = latticeOverride.trim();
    }
    if (payloadMode === "text") {
      body.payload_text = payloadText;
    } else if (payloadMode === "json") {
      try {
        body.payload_json = payloadJson ? JSON.parse(payloadJson) : {};
      } catch (e: any) {
        setErrorData({ title: "Invalid JSON payload", list: [e.message] });
        return null;
      }
    } else if (payloadMode === "base64") {
      body.payload_b64 = payloadB64;
    }
    return body;
  }

  async function handleInvoke() {
    if (!componentId || !operation) {
      setErrorData({ title: "Component ID and operation are required" });
      return;
    }
    // Client-side preflight: ensure connected or give quick feedback
    try {
      const pre = await testConnectionAsync(undefined);
      if (!pre?.connected) {
        const details = [
          `Configured: ${Boolean(pre?.configured)}`,
          `Available: ${pre?.available ?? "unknown"}`,
          `Connected: ${pre?.connected ?? "unknown"}`,
          (pre as any)?.message
            ? `Message: ${(pre as any).message}`
            : undefined,
        ].filter(Boolean) as string[];
        setErrorData({ title: "wasmCloud not connected", list: details });
        return;
      }
    } catch (_e) {
      setErrorData({
        title: "Preflight failed",
        list: ["Could not verify connection"],
      });
      return;
    }

    const body = buildInvokePayload();
    if (!body) return;
    setInvokeResult(null);
    invoke(body, {
      onSuccess: (res) => {
        setInvokeResult(res);
        if (res.success) {
          setSuccessData({ title: `Invoke OK (${res.latency_ms ?? "-"} ms)` });
        } else {
          const list = res.error ? [res.error] : undefined;
          setErrorData({ title: "Invoke failed", list });
        }
      },
    });
  }

  function copy(text?: string | null) {
    if (!text) return;
    navigator.clipboard?.writeText(text).then(() => {
      setSuccessData({ title: "Copied to clipboard" });
    });
  }

  return (
    <div className="flex h-full w-full flex-col gap-6">
      <div className="flex w-full items-start justify-between gap-6">
        <div className="flex w-full flex-col">
          <h2 className="flex items-center text-lg font-semibold tracking-tight">
            Runtime
            <ForwardedIconComponent
              name="Cpu"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            Configure wasmCloud runtime connectivity.
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="flex h-full w-full items-center justify-center">
          <Loading />
        </div>
      ) : (
        <div className="flex max-w-3xl flex-col gap-6">
          <div className="grid grid-cols-1 gap-4 rounded-lg border p-4">
            <div className="flex items-center justify-between">
              <div className="flex flex-col">
                <Label htmlFor="wasmcloud_enabled">Enable wasmCloud</Label>
                <p className="text-xs text-muted-foreground">
                  Toggle runtime integration on this instance.
                </p>
              </div>
              <Switch
                id="wasmcloud_enabled"
                checked={enabled}
                onCheckedChange={setEnabled}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="wasmcloud_nats_url">NATS URL</Label>
              <Input
                id="wasmcloud_nats_url"
                placeholder="nats://localhost:4222"
                value={natsUrl}
                onChange={(e) => setNatsUrl(e.target.value)}
                className={!natsUrlValid ? "border-destructive" : undefined}
              />
              {!natsUrlValid && (
                <span className="text-xs text-destructive">
                  Use nats://host:port
                </span>
              )}
            </div>

            <div className="grid gap-2">
              <Label htmlFor="wasmcloud_lattice">Lattice (optional)</Label>
              <Input
                id="wasmcloud_lattice"
                placeholder="default"
                value={lattice}
                onChange={(e) => setLattice(e.target.value)}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="wasmcloud_timeout_ms">
                Timeout (ms, optional)
              </Label>
              <Input
                id="wasmcloud_timeout_ms"
                type="number"
                min={0}
                placeholder="30000"
                value={timeoutMs}
                onChange={(e) => {
                  const v = e.target.value;
                  setTimeoutMs(v === "" ? "" : Number(v));
                }}
              />
            </div>

            <div className="grid gap-1">
              <Label htmlFor="wasmcloud_creds_path">Credentials (.creds)</Label>
              <Input
                id="wasmcloud_creds_path"
                placeholder={
                  credsStored
                    ? "Stored (enter a new path to replace)"
                    : ".creds file path"
                }
                value={credsPath}
                onChange={(e) => setCredsPath(e.target.value)}
              />
              {credsStored && (
                <span className="text-xs text-muted-foreground">
                  Credentials are stored. They won't be shown here. Provide a
                  new path to overwrite.
                </span>
              )}
            </div>
          </div>

          <div className="flex gap-2 items-center">
            <Button variant="primary" onClick={handleSave} disabled={isSaving}>
              {isSaving ? "Saving..." : "Save"}
            </Button>
            <Button
              variant="secondary"
              onClick={handleTest}
              disabled={!isConfigured || isSaving || isTesting}
            >
              {isTesting ? "Testing..." : "Test Connection"}
            </Button>
            {lastTest && (
              <div className="ml-4 text-xs text-muted-foreground">
                <span className="mr-2">Last test:</span>
                <span>{lastTest.timestamp}</span>
                {" · "}
                <span className={latencyClass(lastTest.latency_ms)}>
                  {lastTest.latency_ms != null
                    ? `${Math.round(lastTest.latency_ms)} ms`
                    : "-"}
                </span>
                {lastTest.connected ? (
                  <span className="ml-2 text-green-600">connected</span>
                ) : (
                  <span className="ml-2 text-red-600">not connected</span>
                )}
              </div>
            )}
          </div>

          {/* Invoke test panel */}
          <div className="mt-6 grid grid-cols-1 gap-4 rounded-lg border p-4">
            <div className="flex items-center justify-between">
              <div className="flex flex-col">
                <Label>Invoke component (wRPC)</Label>
                <p className="text-xs text-muted-foreground">
                  Send a test request to a component/operation.
                </p>
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="invoke_component_id">Component ID</Label>
              <Input
                id="invoke_component_id"
                placeholder="example.component"
                value={componentId}
                onChange={(e) => setComponentId(e.target.value)}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="invoke_operation">Operation</Label>
              <Input
                id="invoke_operation"
                placeholder="process"
                value={operation}
                onChange={(e) => setOperation(e.target.value)}
              />
            </div>

            <div className="grid gap-2">
              <div className="flex items-center justify-between">
                <Label>Payload</Label>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setComponentId("acme.greeter");
                    setOperation("process");
                    setPayloadMode("json");
                    setPayloadJson(
                      JSON.stringify({ name: "LangFlow" }, null, 2),
                    );
                    setPayloadText("");
                    setLatticeOverride("");
                  }}
                >
                  Use Greeter Example
                </Button>
              </div>
              <div className="flex gap-2 text-xs">
                <Button
                  variant={payloadMode === "none" ? "default" : "secondary"}
                  onClick={() => setPayloadMode("none")}
                >
                  None
                </Button>
                <Button
                  variant={payloadMode === "text" ? "default" : "secondary"}
                  onClick={() => setPayloadMode("text")}
                >
                  Text
                </Button>
                <Button
                  variant={payloadMode === "json" ? "default" : "secondary"}
                  onClick={() => setPayloadMode("json")}
                >
                  JSON
                </Button>
                <Button
                  variant={payloadMode === "base64" ? "default" : "secondary"}
                  onClick={() => setPayloadMode("base64")}
                >
                  Base64
                </Button>
              </div>
              {payloadMode === "text" && (
                <Textarea
                  placeholder="Hello"
                  value={payloadText}
                  onChange={(e) => setPayloadText(e.target.value)}
                />
              )}
              {payloadMode === "json" && (
                <Textarea
                  placeholder={`{\n  "key": "value"\n}`}
                  value={payloadJson}
                  onChange={(e) => setPayloadJson(e.target.value)}
                />
              )}
              {payloadMode === "base64" && (
                <Input
                  placeholder="SGVsbG8="
                  value={payloadB64}
                  onChange={(e) => setPayloadB64(e.target.value)}
                />
              )}
            </div>

            <div className="grid gap-2">
              <Label htmlFor="invoke_lattice">
                Lattice (optional override)
              </Label>
              <Input
                id="invoke_lattice"
                placeholder="default"
                value={latticeOverride}
                onChange={(e) => setLatticeOverride(e.target.value)}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="invoke_timeout">Timeout (ms, optional)</Label>
              <Input
                id="invoke_timeout"
                type="number"
                min={0}
                placeholder="30000"
                value={invokeTimeout}
                onChange={(e) => {
                  const v = e.target.value;
                  setInvokeTimeout(v === "" ? "" : Number(v));
                }}
              />
            </div>

            <div className="flex gap-2">
              <Button
                variant="secondary"
                onClick={handleInvoke}
                disabled={isInvoking}
              >
                {isInvoking ? "Invoking..." : "Invoke"}
              </Button>
            </div>

            {invokeResult && (
              <div className="rounded-md bg-muted p-3 text-xs">
                <div className="flex items-center gap-3">
                  <span>
                    Status:{" "}
                    {invokeResult.success ? (
                      <span className="text-green-600">success</span>
                    ) : (
                      <span className="text-red-600">failed</span>
                    )}
                  </span>
                  <span className={latencyClass(invokeResult.latency_ms)}>
                    Latency: {invokeResult.latency_ms ?? "-"} ms
                  </span>
                </div>
                {invokeResult.error && (
                  <div className="mt-2 text-red-600">
                    Error: {invokeResult.error}
                  </div>
                )}
                {invokeResult.data_text && (
                  <div className="mt-2">
                    <div className="mb-1 flex items-center justify-between">
                      <span className="font-medium">Text output</span>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => copy(invokeResult.data_text!)}
                      >
                        Copy
                      </Button>
                    </div>
                    <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words rounded bg-background p-2">
                      {invokeResult.data_text}
                    </pre>
                  </div>
                )}
                {!invokeResult.data_text && invokeResult.data_b64 && (
                  <div className="mt-2">
                    <div className="mb-1 flex items-center justify-between">
                      <span className="font-medium">Base64 output</span>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => copy(invokeResult.data_b64!)}
                      >
                        Copy
                      </Button>
                    </div>
                    <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words rounded bg-background p-2">
                      {invokeResult.data_b64}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
