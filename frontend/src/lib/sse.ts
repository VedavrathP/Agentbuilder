// EventSource hook for run events.

"use client";

import { useEffect, useRef, useState } from "react";
import type { RunEvent } from "./types";

export type RunStream = {
  events: RunEvent[];
  connected: boolean;
  error: string | null;
  ended: boolean;
};

export function useRunStream(url: string | null): RunStream {
  const [state, setState] = useState<RunStream>({
    events: [],
    connected: false,
    error: null,
    ended: false,
  });
  const accRef = useRef<RunEvent[]>([]);
  const endedRef = useRef(false);

  useEffect(() => {
    if (!url) return;
    accRef.current = [];
    endedRef.current = false;
    setState({ events: [], connected: false, error: null, ended: false });

    const es = new EventSource(url);
    const onOpen = () => {
      setState((s) => ({ ...s, connected: true }));
    };
    // EventSource fires `error` both for transport failures AND when the
    // server cleanly closes the stream (e.g., after `run_end`). We only
    // surface it as an error when the run hasn't ended yet.
    const onError = () => {
      if (endedRef.current) {
        setState((s) => ({ ...s, connected: false }));
        return;
      }
      setState((s) => ({ ...s, connected: false, error: "stream error" }));
    };

    const knownTypes = [
      "run_start",
      "node_start",
      "node_end",
      "token",
      "tool_call",
      "tool_result",
      "agent_message",
      "usage",
      "run_end",
      "message",
    ];

    const handlers: Record<string, (ev: MessageEvent) => void> = {};
    for (const t of knownTypes) {
      handlers[t] = (ev) => {
        try {
          const parsed = JSON.parse(ev.data) as RunEvent;
          accRef.current = [...accRef.current, parsed];
          setState((s) => ({ ...s, events: accRef.current }));
          if ((parsed as { type: string }).type === "run_end") {
            endedRef.current = true;
            es.close();
            setState((s) => ({ ...s, connected: false, ended: true }));
          }
        } catch {
          // ignore parse errors
        }
      };
      es.addEventListener(t, handlers[t]);
    }

    es.addEventListener("open", onOpen);
    es.addEventListener("error", onError);

    return () => {
      for (const t of knownTypes) {
        es.removeEventListener(t, handlers[t]);
      }
      es.close();
    };
  }, [url]);

  return state;
}
