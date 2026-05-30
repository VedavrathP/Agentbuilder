import { AgentForm } from "@/components/agents/agent-form";

export default function NewAgentPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-10 space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">New agent</h1>
      <AgentForm />
    </div>
  );
}
