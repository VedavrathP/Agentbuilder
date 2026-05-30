"use client";

import { useCallback, useMemo, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  Background,
  Controls,
  MiniMap,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
  type OnConnect,
  type ReactFlowInstance,
} from "@xyflow/react";
import { Bot, GitBranch, Play, Save, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";

import { AgentNodeComponent } from "./nodes/agent-node";
import { ConditionNodeComponent } from "./nodes/condition-node";
import { NodePropertiesPanel } from "./properties-panel";

import { api } from "@/lib/api";
import type { Workflow, WorkflowGraph } from "@/lib/types";

const nodeTypes = {
  agent: AgentNodeComponent,
  condition: ConditionNodeComponent,
};

type RfNode = Node;

function makeAgentNode(id: string, position: { x: number; y: number }): RfNode {
  return {
    id,
    type: "agent",
    position,
    data: {
      role: "agent",
      system_prompt: "You are a helpful assistant.",
      model: "gpt-4o-mini",
      temperature: 0.2,
      tools: [],
    } as unknown as Record<string, unknown>,
  };
}

function makeConditionNode(id: string, position: { x: number; y: number }): RfNode {
  return {
    id,
    type: "condition",
    position,
    data: {
      router: "keyword",
      spec: {
        branches: [{ keywords: [""], target: "" }],
        default: "__end__",
      },
    } as unknown as Record<string, unknown>,
  };
}

function newId(prefix: string, existing: string[]): string {
  let i = 1;
  while (existing.includes(`${prefix}_${i}`)) i += 1;
  return `${prefix}_${i}`;
}

function graphFromWorkflow(wf: Workflow): { nodes: RfNode[]; edges: Edge[]; entry?: string } {
  const g = wf.graph_json;
  const nodes: RfNode[] = (g.nodes ?? []).map((n) => ({
    id: n.id,
    type: n.type,
    position: n.position ?? { x: 100, y: 100 },
    data: n.data as unknown as Record<string, unknown>,
  }));
  const edges: Edge[] = (g.edges ?? []).map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.source_handle,
    label: e.label,
    type: "smoothstep",
  }));
  return { nodes, edges, entry: g.entry };
}

export function WorkflowEditor({ workflow }: { workflow: Workflow }) {
  return (
    <ReactFlowProvider>
      <Inner workflow={workflow} />
    </ReactFlowProvider>
  );
}

function Inner({ workflow }: { workflow: Workflow }) {
  const router = useRouter();
  const initial = useMemo(() => graphFromWorkflow(workflow), [workflow]);
  const [nodes, setNodes, onNodesChange] = useNodesState<RfNode>(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(initial.edges);
  const [entry, setEntry] = useState<string | undefined>(
    initial.entry ?? initial.nodes[0]?.id,
  );
  const [name, setName] = useState(workflow.name);
  const [description, setDescription] = useState(workflow.description);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [rfInstance, setRfInstance] = useState<ReactFlowInstance | null>(null);
  const [runOpen, setRunOpen] = useState(false);
  const [runInput, setRunInput] = useState("Hello!");
  const [busy, setBusy] = useState(false);

  const allNodeIds = nodes.map((n) => n.id);

  const onConnect: OnConnect = useCallback(
    (params: Connection) =>
      setEdges((eds) =>
        addEdge({ ...params, type: "smoothstep" }, eds),
      ),
    [setEdges],
  );

  const selected = nodes.find((n) => n.id === selectedId) ?? null;

  const updateNodeData = useCallback(
    (id: string, data: Record<string, unknown>) => {
      setNodes((ns) =>
        ns.map((n) =>
          n.id === id ? { ...n, data: { ...n.data, ...data } } : n,
        ),
      );
    },
    [setNodes],
  );

  const deleteNode = useCallback(
    (id: string) => {
      setNodes((ns) => ns.filter((n) => n.id !== id));
      setEdges((es) => es.filter((e) => e.source !== id && e.target !== id));
      setSelectedId(null);
    },
    [setNodes, setEdges],
  );

  const addAgent = useCallback(() => {
    const id = newId("agent", allNodeIds);
    setNodes((ns) => [
      ...ns,
      makeAgentNode(id, {
        x: 150 + Math.random() * 200,
        y: 150 + Math.random() * 200,
      }),
    ]);
    if (!entry) setEntry(id);
  }, [allNodeIds, entry, setNodes]);

  const addCondition = useCallback(() => {
    const id = newId("condition", allNodeIds);
    setNodes((ns) => [
      ...ns,
      makeConditionNode(id, {
        x: 350 + Math.random() * 200,
        y: 150 + Math.random() * 200,
      }),
    ]);
  }, [allNodeIds, setNodes]);

  const serialize = useCallback((): WorkflowGraph => {
    return {
      entry,
      viewport: rfInstance?.getViewport(),
      nodes: nodes.map((n) => ({
        id: n.id,
        type: n.type as "agent" | "condition",
        position: n.position,
        data: n.data,
      })) as WorkflowGraph["nodes"],
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        source_handle: (e.sourceHandle as string) ?? undefined,
        label: typeof e.label === "string" ? e.label : undefined,
      })),
    };
  }, [nodes, edges, entry, rfInstance]);

  const save = useCallback(async () => {
    setBusy(true);
    try {
      await api.updateWorkflow(workflow.id, {
        name,
        description,
        graph_json: serialize(),
      });
      toast.success("Workflow saved");
      router.refresh();
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(false);
    }
  }, [workflow.id, name, description, serialize, router]);

  const run = useCallback(async () => {
    setBusy(true);
    try {
      await api.updateWorkflow(workflow.id, {
        graph_json: serialize(),
      });
      const created = await api.createRun(workflow.id, runInput);
      toast.success("Run started");
      router.push(`/runs/${created.id}`);
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(false);
      setRunOpen(false);
    }
  }, [workflow.id, runInput, serialize, router]);

  // Keep selected node id valid
  useEffect(() => {
    if (selectedId && !nodes.some((n) => n.id === selectedId)) {
      setSelectedId(null);
    }
  }, [nodes, selectedId]);

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col">
      <div className="border-b px-4 py-2 flex items-center gap-3 bg-card">
        <Input
          className="max-w-xs font-semibold"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Input
          className="max-w-md text-sm"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Description"
        />
        <div className="flex-1" />
        <Button variant="outline" size="sm" onClick={addAgent}>
          <Bot className="h-4 w-4 mr-1" /> Agent
        </Button>
        <Button variant="outline" size="sm" onClick={addCondition}>
          <GitBranch className="h-4 w-4 mr-1" /> Condition
        </Button>
        <Button size="sm" onClick={save} disabled={busy}>
          <Save className="h-4 w-4 mr-1" /> Save
        </Button>
        <Button
          size="sm"
          variant="default"
          disabled={busy}
          onClick={() => setRunOpen(true)}
        >
          <Play className="h-4 w-4 mr-1" /> Run
        </Button>
        <Dialog open={runOpen} onOpenChange={setRunOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Run workflow</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label>Input</Label>
                <Textarea
                  rows={4}
                  value={runInput}
                  onChange={(e) => setRunInput(e.target.value)}
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setRunOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={run} disabled={busy || !runInput.trim()}>
                  Start run
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="flex-1 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onInit={setRfInstance}
          nodeTypes={nodeTypes}
          onNodeClick={(_, n) => setSelectedId(n.id)}
          onPaneClick={() => setSelectedId(null)}
          fitView
          defaultEdgeOptions={{ type: "smoothstep" }}
        >
          <Background />
          <MiniMap pannable zoomable />
          <Controls />
          <Panel position="top-left">
            <div className="rounded bg-card text-xs px-2 py-1 border shadow-sm">
              Entry: <span className="font-mono">{entry ?? "(none)"}</span>
              {nodes.length > 0 && (
                <select
                  className="ml-2 bg-transparent text-xs font-mono"
                  value={entry}
                  onChange={(e) => setEntry(e.target.value)}
                >
                  {nodes
                    .filter((n) => n.type === "agent")
                    .map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.id}
                      </option>
                    ))}
                </select>
              )}
            </div>
          </Panel>
        </ReactFlow>
      </div>

      <NodePropertiesPanel
        node={selected as Node<Record<string, unknown>, string> | null}
        allNodeIds={allNodeIds}
        onClose={() => setSelectedId(null)}
        onUpdate={updateNodeData}
        onDelete={deleteNode}
      />
    </div>
  );
}
