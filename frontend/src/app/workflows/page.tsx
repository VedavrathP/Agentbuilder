import Link from "next/link";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { Workflow } from "@/lib/types";

export default async function WorkflowsPage() {
  let workflows: Workflow[] = [];
  try {
    workflows = await api.listWorkflows(true);
  } catch {
    workflows = [];
  }
  const templates = workflows.filter((w) => w.is_template);
  const userWorkflows = workflows.filter((w) => !w.is_template);

  return (
    <div className="mx-auto max-w-7xl px-6 py-10 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Workflows</h1>
          <p className="text-muted-foreground">
            Visual multi-agent pipelines with branching and feedback loops.
          </p>
        </div>
        <form
          action={async () => {
            "use server";
            const { api } = await import("@/lib/api");
            const { redirect } = await import("next/navigation");
            const wf = await api.createWorkflow({
              name: "Untitled workflow",
              description: "",
              graph_json: {
                entry: undefined,
                nodes: [],
                edges: [],
              },
            });
            redirect(`/workflows/${wf.id}`);
          }}
        >
          <Button type="submit">
            <Plus className="mr-2 h-4 w-4" />
            New workflow
          </Button>
        </form>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Your workflows</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {userWorkflows.length === 0 && (
            <Card className="md:col-span-2 lg:col-span-3">
              <CardContent className="py-10 text-center text-muted-foreground">
                No workflows yet. Start from a template below or create a blank
                one.
              </CardContent>
            </Card>
          )}
          {userWorkflows.map((w) => (
            <Link key={w.id} href={`/workflows/${w.id}`}>
              <Card className="hover:bg-accent/40 transition-colors h-full">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">{w.name}</CardTitle>
                    <Badge variant="outline">v{w.version}</Badge>
                  </div>
                  <CardDescription>{w.description || "no description"}</CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">
                  {w.graph_json.nodes?.length ?? 0} nodes ·{" "}
                  {w.graph_json.edges?.length ?? 0} edges
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Templates</h2>
        <div className="grid gap-4 md:grid-cols-2">
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
    </div>
  );
}
