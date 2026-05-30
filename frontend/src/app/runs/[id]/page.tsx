import { notFound } from "next/navigation";
import { RunMonitor } from "./run-monitor";
import { api } from "@/lib/api";

export default async function RunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let run;
  try {
    run = await api.getRun(id);
  } catch {
    notFound();
  }
  return <RunMonitor run={run} />;
}
