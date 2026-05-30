// Mirrors backend Pydantic schemas in backend/app/api/schemas.py.

export type ToolConfig = {
  type: string;
  config?: Record<string, unknown>;
};

export type ChannelConfig = {
  type: string;
  config?: Record<string, unknown>;
};

export type Agent = {
  id: string;
  name: string;
  role: string;
  system_prompt: string;
  model: string;
  temperature: number;
  max_tokens: number | null;
  tools: ToolConfig[];
  channels: ChannelConfig[];
  skills: string[];
  interaction_rules: string[];
  schedule_cron: string | null;
  default_workflow_id: string | null;
  schedule_input: string | null;
  memory_strategy: string;
  guardrails: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type AgentNodeData = {
  role?: string;
  system_prompt: string;
  model: string;
  temperature: number;
  max_tokens?: number | null;
  tools?: ToolConfig[];
  handoff_targets?: string[];
  // Optional reference to a stored Agent — when set, the agent's
  // system_prompt/model/tools/etc. are merged in at run time.
  agent_id?: string;
  loop_max_iterations?: number;
  // Force structured output, e.g. {"type": "json_object"}.
  response_format?: { type: string };
};

export type ConditionRouterSpec = {
  branches?: Array<{ keywords?: string[]; pattern?: string; target: string }>;
  default?: string;
  field?: string;
  mapping?: Record<string, string>;
};

export type ConditionNodeData = {
  router: "keyword" | "regex" | "json_field";
  spec: ConditionRouterSpec;
};

export type WorkflowNode =
  | {
      id: string;
      type: "agent";
      position: { x: number; y: number };
      data: AgentNodeData;
    }
  | {
      id: string;
      type: "condition";
      position: { x: number; y: number };
      data: ConditionNodeData;
    };

export type WorkflowEdge = {
  id: string;
  source: string;
  target: string;
  source_handle?: string;
  label?: string;
};

export type WorkflowGraph = {
  entry?: string;
  viewport?: { x: number; y: number; zoom: number };
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
};

export type Workflow = {
  id: string;
  name: string;
  description: string;
  graph_json: WorkflowGraph;
  version: number;
  is_template: boolean;
  template_key: string | null;
  created_at: string;
  updated_at: string;
};

export type Run = {
  id: string;
  workflow_id: string;
  thread_id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  trigger: "manual" | "telegram" | "schedule" | "api";
  input_text: string | null;
  error: string | null;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  started_at: string;
  finished_at: string | null;
};

export type Message = {
  id: string;
  run_id: string | null;
  thread_id: string;
  source_node: string | null;
  role: "user" | "assistant" | "tool" | "system";
  content: string;
  tool_calls: Array<Record<string, unknown>> | null;
  token_usage: Record<string, unknown> | null;
  created_at: string;
};

export type TelegramLink = {
  id: string;
  workflow_id: string;
  bot_username: string | null;
  active: boolean;
  created_at: string;
};

export type RunEvent =
  | {
      type: "run_start";
      run_id: string;
      workflow_id: string | null;
      thread_id: string;
      input: string;
    }
  | { type: "node_start"; node: string }
  | { type: "node_end"; node: string; error?: string }
  | { type: "token"; node: string; text: string }
  | {
      type: "tool_call";
      node: string;
      name: string;
      args: Record<string, unknown>;
      tool_call_id: string;
    }
  | {
      type: "tool_result";
      node: string;
      name: string;
      content: string;
      tool_call_id: string;
    }
  | {
      type: "agent_message";
      node: string;
      role: string;
      content: string;
      token_usage: Record<string, unknown> | null;
    }
  | {
      type: "usage";
      input_tokens: number;
      output_tokens: number;
      total_tokens: number;
      cost_usd: number;
      per_model: Record<string, unknown>;
    }
  | {
      type: "run_end";
      status: "succeeded" | "failed";
      error?: string;
      elapsed_ms: number;
    };
