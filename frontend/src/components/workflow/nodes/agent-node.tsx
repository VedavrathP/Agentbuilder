"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { Bot } from "lucide-react";
import type { AgentNodeData } from "@/lib/types";

export type AgentRfNode = Node<
  AgentNodeData & { status?: "idle" | "running" | "success" | "error" },
  "agent"
>;

export const AgentNodeComponent = memo(function AgentNodeComponent({
  data,
  selected,
}: NodeProps<AgentRfNode>) {
  const status = data.status ?? "idle";
  const ring =
    status === "running"
      ? "ring-2 ring-blue-500 animate-pulse"
      : status === "success"
        ? "ring-2 ring-green-500/60"
        : status === "error"
          ? "ring-2 ring-red-500"
          : selected
            ? "ring-2 ring-primary"
            : "";

  return (
    <div
      className={`min-w-[240px] rounded-xl border bg-card text-card-foreground shadow-sm px-4 py-3 ${ring}`}
    >
      <Handle type="target" position={Position.Left} id="in" />
      <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted-foreground">
        <Bot className="h-3.5 w-3.5" />
        Agent
      </div>
      <div className="mt-1 text-sm font-semibold truncate">
        {data.role || "agent"}
      </div>
      <div className="mt-1 inline-flex rounded bg-muted px-2 py-0.5 font-mono text-[11px]">
        {data.model}
      </div>
      {data.tools && data.tools.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {data.tools.map((t, i) => (
            <span
              key={i}
              className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-mono"
            >
              {t.type}
            </span>
          ))}
        </div>
      )}
      <Handle type="source" position={Position.Right} id="out" />
    </div>
  );
});
