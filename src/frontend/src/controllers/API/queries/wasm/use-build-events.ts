import { useEffect, useMemo, useRef, useState } from "react";
import { baseURL } from "@/customization/constants";

export type BuildEvent =
  | { type: "hello"; payload: any }
  | { type: "state"; payload: { status: string; step?: string } }
  | { type: "log"; payload: { level?: string; line: string } }
  | { type: "error"; payload: { message: string } }
  | {
      type: "done";
      payload: {
        success: boolean;
        digest?: string | null;
        size?: number | null;
      };
    };

export function useBuildEvents(run_id?: string) {
  const [events, setEvents] = useState<BuildEvent[]>([]);
  const [status, setStatus] = useState<string | undefined>(undefined);
  const [step, setStep] = useState<string | undefined>(undefined);
  const [success, setSuccess] = useState<boolean | undefined>(undefined);
  const esRef = useRef<EventSource | null>(null);

  const url = useMemo(() => {
    if (!run_id) return undefined;
    const base =
      (typeof window !== "undefined" && window.location?.origin) ||
      baseURL ||
      "";
    try {
      const u = new URL(`/api/v1/wasm/build/runs/${run_id}/events`, base);
      return u.toString();
    } catch {
      // Fallback to relative path if base is invalid
      return `/api/v1/wasm/build/runs/${run_id}/events`;
    }
  }, [run_id]);

  useEffect(() => {
    if (!url) return;
    const es = new EventSource(url, { withCredentials: true });
    esRef.current = es;

    const onHello = (e: MessageEvent) => {
      try {
        const payload = JSON.parse(e.data);
        setEvents((prev) => [...prev, { type: "hello", payload }]);
        setStatus(payload?.status);
        setStep(payload?.step);
      } catch {}
    };
    const onState = (e: MessageEvent) => {
      try {
        const payload = JSON.parse(e.data);
        setEvents((prev) => [...prev, { type: "state", payload }]);
        setStatus(payload?.status);
        setStep(payload?.step);
      } catch {}
    };
    const onLog = (e: MessageEvent) => {
      try {
        const payload = JSON.parse(e.data);
        setEvents((prev) => [...prev, { type: "log", payload }]);
      } catch {}
    };
    const onDone = (e: MessageEvent) => {
      try {
        const payload = JSON.parse(e.data);
        setEvents((prev) => [...prev, { type: "done", payload }]);
        setSuccess(payload?.success);
      } catch {}
    };
    const onError = (e: MessageEvent) => {
      try {
        const payload = JSON.parse(e.data);
        setEvents((prev) => [...prev, { type: "error", payload }]);
      } catch {}
    };

    es.addEventListener("hello", onHello);
    es.addEventListener("state", onState);
    es.addEventListener("log", onLog);
    es.addEventListener("done", onDone);
    es.addEventListener("error", onError);

    es.onerror = () => {
      // Close on error for now; a polling fallback could be added here
      es.close();
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [url]);

  const logs = useMemo(
    () =>
      events.filter((e) => e.type === "log") as Extract<
        BuildEvent,
        { type: "log" }
      >[],
    [events],
  );

  return { events, logs, status, step, success };
}
