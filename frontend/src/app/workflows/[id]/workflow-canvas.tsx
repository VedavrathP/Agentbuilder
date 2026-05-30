"use client";

import dynamic from "next/dynamic";
import type { Workflow } from "@/lib/types";

const WorkflowEditor = dynamic(
  () =>
    import("@/components/workflow/workflow-editor").then(
      (m) => m.WorkflowEditor,
    ),
  {
    ssr: false,
    loading: () => (
      <div className="p-10 text-center text-muted-foreground">
        Loading canvas…
      </div>
    ),
  },
);

export function WorkflowCanvas({ workflow }: { workflow: Workflow }) {
  return <WorkflowEditor workflow={workflow} />;
}
