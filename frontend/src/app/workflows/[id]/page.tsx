import { notFound } from "next/navigation";
import { WorkflowCanvas } from "./workflow-canvas";
import { api } from "@/lib/api";

export default async function WorkflowPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let workflow;
  try {
    workflow = await api.getWorkflow(id);
  } catch {
    notFound();
  }
  return <WorkflowCanvas workflow={workflow} />;
}
