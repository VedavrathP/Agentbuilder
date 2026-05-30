// Typed fetch client for the Orchestra backend.

import type {
  Agent,
  Message,
  Run,
  TelegramLink,
  Workflow,
  WorkflowGraph,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(
      `${init?.method ?? "GET"} ${path} → ${res.status}: ${text || res.statusText}`,
    );
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  // Agents
  listAgents: () => request<Agent[]>("/api/agents"),
  getAgent: (id: string) => request<Agent>(`/api/agents/${id}`),
  createAgent: (payload: Partial<Agent>) =>
    request<Agent>("/api/agents", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateAgent: (id: string, payload: Partial<Agent>) =>
    request<Agent>(`/api/agents/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteAgent: (id: string) =>
    request<void>(`/api/agents/${id}`, { method: "DELETE" }),

  // Workflows
  listWorkflows: (includeTemplates = true) =>
    request<Workflow[]>(
      `/api/workflows?include_templates=${includeTemplates}`,
    ),
  getWorkflow: (id: string) => request<Workflow>(`/api/workflows/${id}`),
  createWorkflow: (payload: {
    name: string;
    description?: string;
    graph_json: WorkflowGraph;
    is_template?: boolean;
    template_key?: string | null;
  }) =>
    request<Workflow>("/api/workflows", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateWorkflow: (
    id: string,
    payload: Partial<{
      name: string;
      description: string;
      graph_json: WorkflowGraph;
    }>,
  ) =>
    request<Workflow>(`/api/workflows/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteWorkflow: (id: string) =>
    request<void>(`/api/workflows/${id}`, { method: "DELETE" }),
  instantiateTemplate: (templateKey: string) =>
    request<Workflow>(`/api/workflows/from-template/${templateKey}`, {
      method: "POST",
    }),

  // Runs
  listRuns: (workflowId?: string, limit = 50) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (workflowId) params.set("workflow_id", workflowId);
    return request<Run[]>(`/api/runs?${params.toString()}`);
  },
  createRun: (workflow_id: string, input: string, thread_id?: string) =>
    request<Run>("/api/runs", {
      method: "POST",
      body: JSON.stringify({ workflow_id, input, thread_id }),
    }),
  getRun: (id: string) => request<Run>(`/api/runs/${id}`),
  listRunMessages: (id: string) =>
    request<Message[]>(`/api/runs/${id}/messages`),
  streamRunUrl: (id: string) => `${API_BASE}/api/runs/${id}/stream`,

  // Telegram
  listTelegramLinks: () =>
    request<TelegramLink[]>("/api/telegram/links"),
  createTelegramLink: (workflow_id: string, bot_token: string) =>
    request<TelegramLink>("/api/telegram/links", {
      method: "POST",
      body: JSON.stringify({ workflow_id, bot_token }),
    }),
  disableTelegramLink: (id: string) =>
    request<TelegramLink>(`/api/telegram/links/${id}/disable`, {
      method: "POST",
    }),
  deleteTelegramLink: (id: string) =>
    request<void>(`/api/telegram/links/${id}`, { method: "DELETE" }),
};
