"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, Power } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { TelegramLink, Workflow } from "@/lib/types";

export function TelegramLinkManager({
  workflows,
  initialLinks,
}: {
  workflows: Workflow[];
  initialLinks: TelegramLink[];
}) {
  const [links, setLinks] = useState(initialLinks);
  const [workflowId, setWorkflowId] = useState(workflows[0]?.id ?? "");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const t = setInterval(async () => {
      try {
        const next = await api.listTelegramLinks();
        setLinks(next);
      } catch {
        // ignore
      }
    }, 5000);
    return () => clearInterval(t);
  }, []);

  async function add() {
    if (!workflowId) {
      toast.error("Pick a workflow first");
      return;
    }
    if (!token.trim()) {
      toast.error("Paste a bot token");
      return;
    }
    setBusy(true);
    try {
      await api.createTelegramLink(workflowId, token.trim());
      const next = await api.listTelegramLinks();
      setLinks(next);
      setToken("");
      toast.success("Bot registered. Supervisor will start it shortly.");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function disable(id: string) {
    setBusy(true);
    try {
      await api.disableTelegramLink(id);
      const next = await api.listTelegramLinks();
      setLinks(next);
      toast.success("Disabled");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!confirm("Delete this Telegram link?")) return;
    setBusy(true);
    try {
      await api.deleteTelegramLink(id);
      setLinks((l) => l.filter((x) => x.id !== id));
      toast.success("Deleted");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Add a bot</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {workflows.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              You have no workflows yet. Create one first.
            </p>
          ) : (
            <>
              <div className="space-y-1.5">
                <Label>Workflow</Label>
                <Select value={workflowId} onValueChange={(v) => setWorkflowId(v ?? "")}>
                  <SelectTrigger>
                    <SelectValue placeholder="Pick a workflow" />
                  </SelectTrigger>
                  <SelectContent>
                    {workflows.map((w) => (
                      <SelectItem key={w.id} value={w.id}>
                        {w.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Bot token (from @BotFather)</Label>
                <Input
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="123456:ABC-DEF…"
                  className="font-mono text-sm"
                />
              </div>
              <Button onClick={add} disabled={busy}>
                <Plus className="h-4 w-4 mr-1" /> Add bot
              </Button>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Active bots</CardTitle>
        </CardHeader>
        <CardContent>
          {links.length === 0 ? (
            <p className="text-sm text-muted-foreground">No bots registered.</p>
          ) : (
            <ul className="space-y-2">
              {links.map((link) => (
                <li
                  key={link.id}
                  className="flex items-center justify-between rounded border bg-card px-3 py-2"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm">
                        @{link.bot_username ?? "pending…"}
                      </span>
                      <Badge variant={link.active ? "default" : "secondary"}>
                        {link.active ? "active" : "disabled"}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      workflow:{" "}
                      <span className="font-mono">{link.workflow_id}</span>
                    </p>
                  </div>
                  <div className="flex gap-1.5">
                    {link.active && (
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => disable(link.id)}
                        title="Disable"
                      >
                        <Power className="h-4 w-4" />
                      </Button>
                    )}
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => remove(link.id)}
                      title="Delete"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
