"use client";

import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api";
import { useRunStream } from "@/lib/sse";
import type { Run, RunEvent } from "@/lib/types";

function statusVariant(s: string) {
  if (s === "succeeded") return "default" as const;
  if (s === "failed") return "destructive" as const;
  return "secondary" as const;
}

export function RunMonitor({ run }: { run: Run }) {
  const { events, connected, error } = useRunStream(api.streamRunUrl(run.id));

  const finalRunEnd = events.find((e) => e.type === "run_end") as
    | Extract<RunEvent, { type: "run_end" }>
    | undefined;
  const usage = events.find((e) => e.type === "usage") as
    | Extract<RunEvent, { type: "usage" }>
    | undefined;

  const status = finalRunEnd?.status ?? run.status;

  // Tokens by node, by buffering token events
  const nodeTokens = useMemo(() => {
    const out: Record<string, string> = {};
    for (const ev of events) {
      if (ev.type === "token") {
        out[ev.node] = (out[ev.node] ?? "") + ev.text;
      }
      if (ev.type === "agent_message") {
        out[ev.node] = ev.content;
      }
    }
    return out;
  }, [events]);

  const agentMessages = useMemo(
    () =>
      events
        .filter((e): e is Extract<RunEvent, { type: "agent_message" }> =>
          e.type === "agent_message",
        )
        .map((e) => ({ ...e })),
    [events],
  );

  const toolCalls = useMemo(
    () =>
      events.filter(
        (e): e is Extract<RunEvent, { type: "tool_call" }> => e.type === "tool_call",
      ),
    [events],
  );

  return (
    <div className="mx-auto max-w-7xl px-6 py-6 space-y-4">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Run {run.id.slice(0, 8)}…
          </h1>
          <p className="text-sm text-muted-foreground">
            thread: <span className="font-mono">{run.thread_id}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={statusVariant(status)}>{status}</Badge>
          {connected && (
            <Badge variant="secondary" className="animate-pulse">
              streaming
            </Badge>
          )}
          {error && (
            <Badge variant="destructive">{error}</Badge>
          )}
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Live conversation</CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[60vh] pr-3">
              <div className="space-y-3">
                {run.input_text && (
                  <MessageBubble role="user" content={run.input_text} />
                )}
                {Object.entries(nodeTokens).map(([node, content]) => (
                  <MessageBubble
                    key={node}
                    role="assistant"
                    node={node}
                    content={content}
                    streaming={
                      connected &&
                      !agentMessages.some((m) => m.node === node)
                    }
                  />
                ))}
                {toolCalls.length > 0 && (
                  <details className="text-xs">
                    <summary className="cursor-pointer text-muted-foreground">
                      {toolCalls.length} tool call(s)
                    </summary>
                    <pre className="mt-2 rounded bg-muted p-2 font-mono overflow-x-auto">
                      {JSON.stringify(toolCalls, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Tokens & cost</CardTitle>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="total">
                <TabsList>
                  <TabsTrigger value="total">Total</TabsTrigger>
                  <TabsTrigger value="by_model">Per model</TabsTrigger>
                </TabsList>
                <TabsContent value="total" className="space-y-2">
                  <Row label="Input tokens">
                    {(usage?.input_tokens ?? run.total_input_tokens).toLocaleString()}
                  </Row>
                  <Row label="Output tokens">
                    {(usage?.output_tokens ?? run.total_output_tokens).toLocaleString()}
                  </Row>
                  <Separator />
                  <Row label="Estimated cost">
                    ${(usage?.cost_usd ?? run.total_cost_usd).toFixed(6)}
                  </Row>
                </TabsContent>
                <TabsContent value="by_model">
                  <pre className="text-xs font-mono overflow-x-auto">
                    {JSON.stringify(usage?.per_model ?? {}, null, 2)}
                  </pre>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Event log</CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[28vh]">
                <ul className="space-y-1 text-xs font-mono">
                  {events.map((ev, i) => (
                    <li key={i} className="text-muted-foreground">
                      <span className="font-semibold text-foreground">
                        {ev.type}
                      </span>
                      {"node" in ev && ` · ${ev.node}`}
                      {ev.type === "token" && ` "${ev.text.slice(0, 20)}…"`}
                      {ev.type === "tool_call" && ` ${ev.name}(${JSON.stringify(ev.args)})`}
                    </li>
                  ))}
                </ul>
              </ScrollArea>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium tabular-nums">{children}</span>
    </div>
  );
}

function MessageBubble({
  role,
  node,
  content,
  streaming,
}: {
  role: "user" | "assistant" | "tool";
  node?: string;
  content: string;
  streaming?: boolean;
}) {
  const isUser = role === "user";
  return (
    <div
      className={`rounded-lg px-3 py-2 max-w-[90%] whitespace-pre-wrap ${
        isUser
          ? "ml-auto bg-primary text-primary-foreground"
          : "mr-auto bg-muted text-foreground"
      }`}
    >
      {!isUser && (
        <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
          <span className="font-semibold">{node ?? role}</span>
          {streaming && (
            <span className="inline-block h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
          )}
        </div>
      )}
      {content || (streaming ? <span className="opacity-50">…</span> : null)}
    </div>
  );
}
