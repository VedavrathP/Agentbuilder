import { TelegramLinkManager } from "./telegram-link-manager";
import { api } from "@/lib/api";
import type { TelegramLink, Workflow } from "@/lib/types";

export default async function TelegramPage() {
  let workflows: Workflow[] = [];
  let links: TelegramLink[] = [];
  try {
    [workflows, links] = await Promise.all([
      api.listWorkflows(false),
      api.listTelegramLinks(),
    ]);
  } catch {
    workflows = [];
    links = [];
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-10 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Telegram bots</h1>
        <p className="text-muted-foreground">
          Bind a Telegram bot token to a workflow. The supervisor will start a
          polling worker within ~10 seconds; users can then chat with the
          workflow entry agent.
        </p>
      </div>
      <TelegramLinkManager workflows={workflows} initialLinks={links} />
    </div>
  );
}
