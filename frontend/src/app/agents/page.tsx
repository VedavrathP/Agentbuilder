import Link from "next/link";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { Agent } from "@/lib/types";

export default async function AgentsPage() {
  let agents: Agent[] = [];
  try {
    agents = await api.listAgents();
  } catch {
    agents = [];
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-10 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Agents</h1>
          <p className="text-muted-foreground">
            Configure name, role, prompt, model, tools, schedules, memory and
            guardrails.
          </p>
        </div>
        <Link href="/agents/new">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            New agent
          </Button>
        </Link>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {agents.length === 0 && (
          <Card className="md:col-span-2 lg:col-span-3">
            <CardContent className="py-12 text-center text-muted-foreground">
              No agents yet. Create your first one to get started.
            </CardContent>
          </Card>
        )}
        {agents.map((a) => (
          <Link key={a.id} href={`/agents/${a.id}`}>
            <Card className="hover:bg-accent/40 transition-colors h-full">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{a.name}</CardTitle>
                  <Badge variant="outline" className="font-mono text-xs">
                    {a.model}
                  </Badge>
                </div>
                <CardDescription>{a.role}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p className="text-muted-foreground line-clamp-3 whitespace-pre-wrap">
                  {a.system_prompt || "(no system prompt)"}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {a.tools.map((t, i) => (
                    <Badge key={i} variant="secondary" className="text-xs">
                      {t.type}
                    </Badge>
                  ))}
                  {a.tools.length === 0 && (
                    <span className="text-xs text-muted-foreground">
                      no tools
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
