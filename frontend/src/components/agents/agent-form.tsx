"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2, Plus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { Agent, ToolConfig, Workflow } from "@/lib/types";

const MODELS = [
  "gpt-4o-mini",
  "gpt-4o",
  "gpt-4.1",
  "gpt-4.1-mini",
  "o1-mini",
];

const TOOL_TYPES = [
  { value: "web_search", label: "Web search (DuckDuckGo)" },
  { value: "http_fetch", label: "HTTP fetch" },
];

export function AgentForm({ initial }: { initial?: Agent }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [form, setForm] = useState({
    name: initial?.name ?? "",
    role: initial?.role ?? "assistant",
    system_prompt: initial?.system_prompt ?? "",
    model: initial?.model ?? "gpt-4o-mini",
    temperature: initial?.temperature ?? 0.2,
    max_tokens: initial?.max_tokens ?? null,
    tools: initial?.tools ?? [],
    channels: initial?.channels ?? [],
    skills: initial?.skills ?? [],
    interaction_rules: initial?.interaction_rules ?? [],
    schedule_cron: initial?.schedule_cron ?? "",
    default_workflow_id: initial?.default_workflow_id ?? null,
    schedule_input: initial?.schedule_input ?? "",
    memory_strategy: initial?.memory_strategy ?? "thread",
    guardrails: initial?.guardrails ?? {},
  });

  useEffect(() => {
    let cancelled = false;
    api
      .listWorkflows(false)
      .then((rows) => {
        if (!cancelled) setWorkflows(rows);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const guardrails = form.guardrails as Record<string, unknown>;

  const update = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const addTool = (type: string) => {
    const tool: ToolConfig = { type, config: {} };
    update("tools", [...form.tools, tool]);
  };

  const removeTool = (idx: number) =>
    update(
      "tools",
      form.tools.filter((_, i) => i !== idx),
    );

  async function save() {
    if (!form.name.trim()) {
      toast.error("Name is required");
      return;
    }
    setBusy(true);
    try {
      const payload = {
        ...form,
        schedule_cron: form.schedule_cron || null,
        schedule_input: form.schedule_input || null,
        default_workflow_id: form.default_workflow_id || null,
        max_tokens: form.max_tokens || null,
      };
      const saved = initial
        ? await api.updateAgent(initial.id, payload)
        : await api.createAgent(payload);
      toast.success(initial ? "Agent updated" : "Agent created");
      router.push(`/agents/${saved.id}`);
      router.refresh();
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!initial) return;
    if (!confirm(`Delete agent “${initial.name}”?`)) return;
    setBusy(true);
    try {
      await api.deleteAgent(initial.id);
      toast.success("Agent deleted");
      router.push("/agents");
      router.refresh();
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Identity</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              value={form.name}
              onChange={(e) => update("name", e.target.value)}
              placeholder="e.g. Customer Support Bot"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="role">Role</Label>
            <Input
              id="role"
              value={form.role}
              onChange={(e) => update("role", e.target.value)}
              placeholder="e.g. support, researcher"
            />
          </div>
          <div className="md:col-span-2 space-y-2">
            <Label htmlFor="system_prompt">System prompt</Label>
            <Textarea
              id="system_prompt"
              value={form.system_prompt}
              onChange={(e) => update("system_prompt", e.target.value)}
              placeholder="You are a helpful assistant…"
              rows={6}
              className="font-mono text-sm"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Model</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Model</Label>
            <Select
              value={form.model}
              onValueChange={(v) => v && update("model", v)}
            >
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
            <Label>Max tokens (optional)</Label>
            <Input
              type="number"
              min={1}
              value={form.max_tokens ?? ""}
              onChange={(e) =>
                update(
                  "max_tokens",
                  e.target.value ? Number(e.target.value) : null,
                )
              }
              placeholder="No limit"
            />
          </div>
          <div className="md:col-span-2 space-y-2">
            <div className="flex justify-between">
              <Label>Temperature</Label>
              <span className="text-sm tabular-nums text-muted-foreground">
                {form.temperature.toFixed(2)}
              </span>
            </div>
            <Slider
              value={[form.temperature]}
              min={0}
              max={2}
              step={0.05}
              onValueChange={(v) => {
                const arr = Array.isArray(v) ? v : [v];
                update("temperature", arr[0] ?? 0);
              }}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tools</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {form.tools.length === 0 && (
            <p className="text-sm text-muted-foreground">No tools attached.</p>
          )}
          {form.tools.map((t, i) => (
            <div
              key={i}
              className="flex items-center justify-between rounded-md border px-3 py-2"
            >
              <Badge variant="secondary" className="font-mono">
                {t.type}
              </Badge>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => removeTool(i)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
          <div className="flex gap-2">
            {TOOL_TYPES.map((t) => (
              <Button
                key={t.value}
                variant="outline"
                size="sm"
                onClick={() => addTool(t.value)}
              >
                <Plus className="mr-1 h-4 w-4" />
                {t.label}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Skills & interaction rules</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="skills">Skills (comma-separated)</Label>
            <Input
              id="skills"
              value={form.skills.join(", ")}
              onChange={(e) =>
                update(
                  "skills",
                  e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                )
              }
              placeholder="e.g. summarization, sql, code review"
            />
            <p className="text-xs text-muted-foreground">
              Free-form tags shown in the UI and routed to prompts.
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="rules">Interaction rules (one per line)</Label>
            <Textarea
              id="rules"
              value={form.interaction_rules.join("\n")}
              onChange={(e) =>
                update(
                  "interaction_rules",
                  e.target.value.split("\n").map((s) => s.trim()).filter(Boolean),
                )
              }
              placeholder={"Be concise.\nNever reveal internal tools."}
              rows={4}
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              Injected as a system message at the start of every run.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Channels</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {form.channels.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No channels attached. The Telegram channel is configured per workflow
              from the <span className="font-medium">Telegram</span> tab.
            </p>
          )}
          {form.channels.map((c, i) => (
            <div
              key={i}
              className="flex items-center justify-between rounded-md border px-3 py-2"
            >
              <Badge variant="secondary" className="font-mono">{c.type}</Badge>
              <Button
                size="icon"
                variant="ghost"
                onClick={() =>
                  update(
                    "channels",
                    form.channels.filter((_, j) => j !== i),
                  )
                }
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              update("channels", [
                ...form.channels,
                { type: "telegram", config: {} },
              ])
            }
          >
            <Plus className="mr-1 h-4 w-4" /> Add Telegram tag
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Schedule, memory & guardrails</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="cron">Schedule (cron, optional)</Label>
            <Input
              id="cron"
              value={form.schedule_cron ?? ""}
              onChange={(e) => update("schedule_cron", e.target.value)}
              placeholder="e.g. 0 9 * * *"
              className="font-mono"
            />
            <p className="text-xs text-muted-foreground">
              5-field cron, server time. Requires a default workflow below.
            </p>
          </div>
          <div className="space-y-2">
            <Label>Default workflow (for scheduled runs)</Label>
            <Select
              value={form.default_workflow_id ?? "__none__"}
              onValueChange={(v) =>
                update("default_workflow_id", v === "__none__" ? null : v)
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="None" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">None</SelectItem>
                {workflows.map((w) => (
                  <SelectItem key={w.id} value={w.id}>
                    {w.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="md:col-span-2 space-y-2">
            <Label htmlFor="schedule_input">Scheduled input (optional)</Label>
            <Textarea
              id="schedule_input"
              value={form.schedule_input ?? ""}
              onChange={(e) => update("schedule_input", e.target.value)}
              placeholder="e.g. 'Summarize this morning's news on AI safety.'"
              rows={2}
            />
          </div>
          <div className="space-y-2">
            <Label>Memory strategy</Label>
            <Select
              value={form.memory_strategy}
              onValueChange={(v) => v && update("memory_strategy", v)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="thread">
                  Thread (full conversation)
                </SelectItem>
                <SelectItem value="summary">Summary (rolling)</SelectItem>
                <SelectItem value="none">None (stateless)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Max iterations (guardrail)</Label>
            <Input
              type="number"
              min={1}
              value={(guardrails.max_iterations as number) ?? ""}
              onChange={(e) =>
                update("guardrails", {
                  ...guardrails,
                  max_iterations: e.target.value
                    ? Number(e.target.value)
                    : undefined,
                })
              }
              placeholder="e.g. 10"
            />
          </div>
          <div className="space-y-2">
            <Label>Max cost per run (USD)</Label>
            <Input
              type="number"
              step="0.01"
              min={0}
              value={(guardrails.max_cost_usd as number) ?? ""}
              onChange={(e) =>
                update("guardrails", {
                  ...guardrails,
                  max_cost_usd: e.target.value
                    ? Number(e.target.value)
                    : undefined,
                })
              }
              placeholder="e.g. 0.50"
            />
          </div>
          <div className="md:col-span-2 flex items-center justify-between rounded-md border px-3 py-2">
            <div>
              <Label htmlFor="strict">Strict output validation</Label>
              <p className="text-xs text-muted-foreground">
                Reject responses that don't match the agent's declared format.
              </p>
            </div>
            <Switch
              id="strict"
              checked={Boolean(guardrails.strict_output)}
              onCheckedChange={(v) =>
                update("guardrails", { ...guardrails, strict_output: v })
              }
            />
          </div>
        </CardContent>
      </Card>

      <Separator />

      <div className="flex justify-between">
        <div>
          {initial && (
            <Button variant="destructive" onClick={remove} disabled={busy}>
              <Trash2 className="mr-2 h-4 w-4" />
              Delete
            </Button>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => router.back()}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button onClick={save} disabled={busy}>
            {initial ? "Save changes" : "Create agent"}
          </Button>
        </div>
      </div>
    </div>
  );
}
