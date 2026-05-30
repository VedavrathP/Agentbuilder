"use client";

import { useEffect, useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Plus, Trash2 } from "lucide-react";
import type { Node } from "@xyflow/react";
import { api } from "@/lib/api";
import type { Agent, AgentNodeData, ConditionNodeData, ToolConfig } from "@/lib/types";

const MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-4.1-mini", "o1-mini"];
const TOOLS = [
  { value: "web_search", label: "Web search" },
  { value: "http_fetch", label: "HTTP fetch" },
];

type AnyNode = Node<Record<string, unknown>, string>;

export function NodePropertiesPanel({
  node,
  onClose,
  onUpdate,
  onDelete,
  allNodeIds,
}: {
  node: AnyNode | null;
  onClose: () => void;
  onUpdate: (id: string, data: Record<string, unknown>) => void;
  onDelete: (id: string) => void;
  allNodeIds: string[];
}) {
  const [local, setLocal] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    setLocal(node ? { ...node.data } : null);
  }, [node?.id]);

  if (!node || !local) return null;

  const set = (k: string, v: unknown) => {
    const next = { ...local, [k]: v };
    setLocal(next);
    onUpdate(node.id, next);
  };

  const isAgent = node.type === "agent";

  return (
    <Sheet open={true} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="w-[460px] sm:max-w-[460px] overflow-y-auto p-4">
        <SheetHeader>
          <SheetTitle>
            {isAgent ? "Agent node" : "Condition node"}
          </SheetTitle>
          <SheetDescription>id: {node.id}</SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-4">
          {isAgent ? (
            <AgentEditor
              data={local as AgentNodeData}
              set={set}
              otherAgentIds={allNodeIds.filter((id) => id !== node.id)}
            />
          ) : (
            <ConditionEditor data={local as ConditionNodeData} set={set} />
          )}
        </div>

        <div className="mt-8 pt-4 border-t flex justify-between">
          <Button variant="destructive" onClick={() => onDelete(node.id)}>
            <Trash2 className="h-4 w-4 mr-1" />
            Delete node
          </Button>
          <Button variant="outline" onClick={onClose}>
            Done
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function AgentEditor({
  data,
  set,
  otherAgentIds,
}: {
  data: AgentNodeData;
  set: (k: string, v: unknown) => void;
  otherAgentIds: string[];
}) {
  const tools = data.tools ?? [];
  const targets = data.handoff_targets ?? [];
  const [agents, setAgents] = useState<Agent[]>([]);

  useEffect(() => {
    let cancelled = false;
    api
      .listAgents()
      .then((rows) => {
        if (!cancelled) setAgents(rows);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const wantJson = data.response_format?.type === "json_object";

  return (
    <>
      <div className="space-y-2">
        <Label>Linked agent (optional)</Label>
        <Select
          value={data.agent_id ?? "__none__"}
          onValueChange={(v) =>
            set("agent_id", v === "__none__" ? undefined : v)
          }
        >
          <SelectTrigger>
            <SelectValue placeholder="None" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__none__">Inline (no link)</SelectItem>
            {agents.map((a) => (
              <SelectItem key={a.id} value={a.id}>
                {a.name} — <span className="text-muted-foreground">{a.role}</span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          When set, this node inherits prompt/model/tools from the stored agent.
          Fields below override the linked agent's values.
        </p>
      </div>

      <div className="space-y-2">
        <Label>Role</Label>
        <Input
          value={data.role ?? ""}
          onChange={(e) => set("role", e.target.value)}
          placeholder="researcher, writer, support…"
        />
      </div>

      <div className="space-y-2">
        <Label>System prompt</Label>
        <Textarea
          rows={6}
          className="font-mono text-xs"
          value={data.system_prompt ?? ""}
          onChange={(e) => set("system_prompt", e.target.value)}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label>Model</Label>
          <Select value={data.model} onValueChange={(v) => v && set("model", v)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MODELS.map((m) => (
                <SelectItem key={m} value={m}>
                  {m}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <div className="flex justify-between">
            <Label>Temp</Label>
            <span className="text-xs text-muted-foreground">
              {(data.temperature ?? 0.2).toFixed(2)}
            </span>
          </div>
          <Slider
            min={0}
            max={2}
            step={0.05}
            value={[data.temperature ?? 0.2]}
            onValueChange={(v) => {
              const arr = Array.isArray(v) ? v : [v];
              set("temperature", arr[0] ?? 0);
            }}
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label>Tools</Label>
        <div className="space-y-1.5">
          {tools.map((t, i) => (
            <div
              key={i}
              className="flex items-center justify-between rounded border px-2 py-1"
            >
              <Badge variant="secondary" className="font-mono text-xs">
                {t.type}
              </Badge>
              <Button
                size="icon"
                variant="ghost"
                onClick={() =>
                  set(
                    "tools",
                    tools.filter((_, ix) => ix !== i),
                  )
                }
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {TOOLS.map((t) => (
            <Button
              key={t.value}
              variant="outline"
              size="sm"
              onClick={() => {
                const next: ToolConfig = { type: t.value, config: {} };
                set("tools", [...tools, next]);
              }}
            >
              <Plus className="h-3.5 w-3.5 mr-1" />
              {t.label}
            </Button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <Label>Handoff targets</Label>
        <p className="text-xs text-muted-foreground">
          Other agents this agent can transfer control to via a tool call.
        </p>
        <div className="space-y-1.5">
          {otherAgentIds.length === 0 && (
            <p className="text-xs text-muted-foreground">
              No other agents in the workflow.
            </p>
          )}
          {otherAgentIds.map((id) => (
            <label
              key={id}
              className="flex items-center justify-between rounded border px-2 py-1.5 text-sm cursor-pointer"
            >
              <span className="font-mono">{id}</span>
              <input
                type="checkbox"
                checked={targets.includes(id)}
                onChange={(e) => {
                  const next = e.target.checked
                    ? [...targets, id]
                    : targets.filter((t) => t !== id);
                  set("handoff_targets", next);
                }}
              />
            </label>
          ))}
        </div>
      </div>

      <div className="space-y-2 rounded border p-3">
        <div className="flex items-center justify-between">
          <div>
            <Label>Force JSON output</Label>
            <p className="text-xs text-muted-foreground">
              Sets response_format = {"{"}"type": "json_object"{"}"}. Required when a
              downstream condition uses the JSON-field router.
            </p>
          </div>
          <Switch
            checked={wantJson}
            onCheckedChange={(v) =>
              set("response_format", v ? { type: "json_object" } : undefined)
            }
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label>Loop iteration cap</Label>
        <Input
          type="number"
          min={1}
          value={data.loop_max_iterations ?? ""}
          placeholder="e.g. 4"
          onChange={(e) =>
            set(
              "loop_max_iterations",
              e.target.value ? Number(e.target.value) : undefined,
            )
          }
        />
        <p className="text-xs text-muted-foreground">
          Maximum number of times this node may execute in a single run. If
          exceeded, the run fails with a guardrail violation — protects against
          runaway critic/writer loops.
        </p>
      </div>
    </>
  );
}

const ROUTER_TEMPLATES: Record<string, Record<string, unknown>> = {
  keyword: {
    branches: [
      { keywords: ["billing", "invoice", "refund"], target: "billing_agent" },
      { keywords: ["bug", "error", "crash"], target: "tech_agent" },
    ],
    default: "__end__",
  },
  regex: {
    branches: [
      { pattern: "\\b(refund|invoice|charge)\\b", target: "billing_agent" },
      { pattern: "\\b(error|crash|bug)\\b", target: "tech_agent" },
    ],
    default: "__end__",
  },
  json_field: {
    field: "intent",
    mapping: {
      billing: "billing_agent",
      technical: "tech_agent",
    },
    default: "__end__",
  },
};

const ROUTER_HINTS: Record<string, string> = {
  keyword:
    'Each branch: {"keywords": ["..."], "target": "node_id"}. First branch whose keyword appears in the upstream agent\'s last message wins (case-insensitive substring match).',
  regex:
    'Each branch: {"pattern": "regex", "target": "node_id"}. First pattern matched by re.search(..., IGNORECASE) wins.',
  json_field:
    'The upstream agent must return a JSON object (set its response_format to {"type":"json_object"}). The router reads obj[field] and looks it up in mapping. Unmatched values fall to default.',
};

function isSpecShapedFor(router: string, spec: Record<string, unknown>): boolean {
  switch (router) {
    case "keyword":
    case "regex":
      return Array.isArray((spec as { branches?: unknown }).branches);
    case "json_field":
      return (
        typeof (spec as { field?: unknown }).field === "string" &&
        typeof (spec as { mapping?: unknown }).mapping === "object" &&
        (spec as { mapping?: unknown }).mapping !== null
      );
    default:
      return false;
  }
}

function ConditionEditor(props: {
  data: ConditionNodeData;
  set: (k: string, v: unknown) => void;
}) {
  const key = `${props.data.router}:${JSON.stringify(props.data.spec)}`;
  return <ConditionEditorInner key={key} {...props} />;
}

function ConditionEditorInner({
  data,
  set,
}: {
  data: ConditionNodeData;
  set: (k: string, v: unknown) => void;
}) {
  const [specText, setSpecText] = useState(() =>
    JSON.stringify(data.spec, null, 2),
  );
  const [parseError, setParseError] = useState<string | null>(null);

  const onRouterChange = (next: string | null) => {
    if (!next) return;
    set("router", next);
    if (!isSpecShapedFor(next, data.spec as Record<string, unknown>)) {
      set("spec", ROUTER_TEMPLATES[next]);
    }
  };

  return (
    <>
      <div className="space-y-2">
        <Label>Router type</Label>
        <Select value={data.router} onValueChange={onRouterChange}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="keyword">Keyword match</SelectItem>
            <SelectItem value="regex">Regex match</SelectItem>
            <SelectItem value="json_field">JSON field (recommended)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Default branch (target node id)</Label>
        <Input
          value={(data.spec as { default?: string }).default ?? ""}
          onChange={(e) =>
            set("spec", { ...data.spec, default: e.target.value })
          }
          placeholder="e.g. tech_agent or __end__"
          className="font-mono"
        />
        <p className="text-xs text-muted-foreground">
          Used when no branch matches.
        </p>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Spec (JSON)</Label>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => set("spec", ROUTER_TEMPLATES[data.router] ?? {})}
          >
            Reset to example
          </Button>
        </div>
        <Textarea
          rows={12}
          className="font-mono text-xs"
          value={specText}
          onChange={(e) => {
            const text = e.target.value;
            setSpecText(text);
            try {
              const parsed = JSON.parse(text);
              setParseError(null);
              set("spec", parsed);
            } catch (err) {
              setParseError(err instanceof Error ? err.message : "invalid JSON");
            }
          }}
        />
        {parseError ? (
          <p className="text-xs text-destructive">{parseError}</p>
        ) : (
          <p className="text-xs text-muted-foreground">
            {ROUTER_HINTS[data.router]}
          </p>
        )}
      </div>
    </>
  );
}
