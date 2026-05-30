"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { GitBranch } from "lucide-react";
import type { ConditionNodeData } from "@/lib/types";

export type ConditionRfNode = Node<
  ConditionNodeData & { status?: "idle" | "running" | "success" | "error" },
  "condition"
>;

export const ConditionNodeComponent = memo(function ConditionNodeComponent({
  data,
  selected,
}: NodeProps<ConditionRfNode>) {
  const ring = selected ? "ring-2 ring-primary" : "ring-1 ring-amber-500/60";

  const summary =
    data.router === "keyword"
      ? `${(data.spec.branches?.length ?? 0)} branches · default ${data.spec.default ?? "?"}`
      : data.router === "regex"
        ? `${(data.spec.branches?.length ?? 0)} regex branches`
        : `field=${data.spec.field ?? "?"} · ${Object.keys(data.spec.mapping ?? {}).length} mapping(s)`;

  return (
    <div
      className={`min-w-[220px] rounded-xl border-2 border-amber-500/50 bg-card text-card-foreground shadow-sm px-4 py-3 ${ring}`}
    >
      <Handle type="target" position={Position.Left} id="in" />
      <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-amber-600 dark:text-amber-400">
        <GitBranch className="h-3.5 w-3.5" />
        Condition
      </div>
      <div className="mt-1 text-sm font-semibold">{data.router}</div>
      <div className="mt-1 text-xs text-muted-foreground">{summary}</div>
      <Handle type="source" position={Position.Right} id="out" />
    </div>
  );
});
