import { notFound } from "next/navigation";
import { AgentForm } from "@/components/agents/agent-form";
import { api } from "@/lib/api";

export default async function EditAgentPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let agent;
  try {
    agent = await api.getAgent(id);
  } catch {
    notFound();
  }
  return (
    <div className="mx-auto max-w-3xl px-6 py-10 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{agent.name}</h1>
        <p className="text-muted-foreground">Edit agent configuration</p>
      </div>
      <AgentForm initial={agent} />
    </div>
  );
}
