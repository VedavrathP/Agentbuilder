import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

async function safeFetch<T>(fn: () => Promise<T>, fallback: T): Promise<T> {
  try {
    return await fn();
  } catch {
    return fallback;
  }
}

export default async function HomePage() {
  const [agents, workflows, runs, telegram] = await Promise.all([
    safeFetch(() => api.listAgents(), []),
    safeFetch(() => api.listWorkflows(true), []),
    safeFetch(() => api.listRuns(undefined, 10), []),
    safeFetch(() => api.listTelegramLinks(), []),
  ]);

  const templates = workflows.filter((w) => w.is_template);
  const userWorkflows = workflows.filter((w) => !w.is_template);

  return (
    <div className="mx-auto max-w-7xl px-6 py-10 space-y-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          {agents.length} agents · {userWorkflows.length} workflows ·{" "}
          {runs.length} recent runs · {telegram.filter((l) => l.active).length} active
          Telegram bot{telegram.filter((l) => l.active).length === 1 ? "" : "s"}
        </p>
      </header>

      <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Agents</CardTitle>
            <CardDescription>
              Build configurable AI workers with prompts, tools, and guardrails.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex justify-between items-center">
            <span className="text-2xl font-semibold">{agents.length}</span>
            <Link href="/agents">
              <Button variant="outline">Manage</Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Workflows</CardTitle>
            <CardDescription>
              Connect agents into branching, multi-step collaborations.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex justify-between items-center">
            <span className="text-2xl font-semibold">{userWorkflows.length}</span>
            <Link href="/workflows">
              <Button variant="outline">Manage</Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Telegram</CardTitle>
            <CardDescription>
              Expose a workflow to humans through a real Telegram bot.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex justify-between items-center">
            <span className="text-2xl font-semibold">
              {telegram.filter((l) => l.active).length}
            </span>
            <Link href="/telegram">
              <Button variant="outline">Configure</Button>
            </Link>
          </CardContent>
        </Card>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Templates</h2>
        <div className="grid gap-4 md:grid-cols-2">
          {templates.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No templates seeded. The backend should seed templates on first
              startup.
            </p>
          )}
          {templates.map((t) => (
            <Card key={t.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{t.name}</CardTitle>
                  <Badge variant="secondary">template</Badge>
                </div>
                <CardDescription>{t.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <form
                  action={async () => {
                    "use server";
                    const { api } = await import("@/lib/api");
                    const { redirect } = await import("next/navigation");
                    const created = await api.instantiateTemplate(
                      t.template_key!,
                    );
                    redirect(`/workflows/${created.id}`);
                  }}
                >
                  <Button type="submit" size="sm">
                    Use template
                  </Button>
                </form>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Recent runs</h2>
        <div className="space-y-2">
          {runs.length === 0 && (
            <p className="text-sm text-muted-foreground">No runs yet.</p>
          )}
          {runs.map((r) => (
            <Link
              key={r.id}
              href={`/runs/${r.id}`}
              className="flex items-center justify-between rounded-lg border bg-card px-4 py-3 hover:bg-accent/40 transition-colors"
            >
              <div className="flex items-center gap-3">
                <Badge
                  variant={
                    r.status === "succeeded"
                      ? "default"
                      : r.status === "failed"
                        ? "destructive"
                        : "secondary"
                  }
                >
                  {r.status}
                </Badge>
                <span className="text-sm font-medium">
                  {r.input_text?.slice(0, 64) ?? "(no input)"}
                </span>
              </div>
              <div className="text-xs text-muted-foreground">
                {r.trigger} · {r.total_input_tokens + r.total_output_tokens} tok ·
                ${r.total_cost_usd.toFixed(4)}
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
