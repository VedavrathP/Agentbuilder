"""Build a compiled LangGraph from a user-defined workflow JSON.

Workflow JSON schema:
    {
        "entry": "node_id",
        "nodes": [
            {"id": "researcher", "type": "agent", "data": {<agent config>}},
            {"id": "router1", "type": "condition", "data": {
                "router": "keyword",
                "spec": {"branches": [...], "default": "..."}
            }}
        ],
        "edges": [
            {"source": "a", "target": "b"},
            {"source": "router1", "target": "__condition__"}   # condition edges live on the node
        ]
    }

Condition nodes do not appear directly in the compiled graph; instead, the
preceding agent's edge becomes a `add_conditional_edges` call that uses the
condition's router function.
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph

from app.engine.agents import make_agent_node
from app.engine.routers import ROUTERS


_NODE_OVERRIDE_KEYS = {
    "system_prompt",
    "model",
    "temperature",
    "max_tokens",
    "tools",
    "response_format",
    "guardrails",
    "memory_strategy",
    "interaction_rules",
    "skills",
    "handoff_targets",
    "loop_max_iterations",
}


def _resolve_agent_data(node_data: dict[str, Any]) -> dict[str, Any]:
    """If the node references a stored Agent by ``agent_id``, merge its config.

    The lookup is synchronous (uses a fresh sync session) so the factory stays
    sync-friendly. Workflow runs are short-lived, so a single SELECT per build
    is acceptable.
    """
    agent_id = node_data.get("agent_id")
    if not agent_id:
        return node_data

    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.config import get_settings
    from app.db.models import Agent

    settings = get_settings()
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg")
    engine = create_engine(sync_url, future=True)
    try:
        with Session(engine) as sess:
            row = sess.execute(select(Agent).where(Agent.id == agent_id)).scalar_one_or_none()
    finally:
        engine.dispose()
    if row is None:
        return node_data

    merged: dict[str, Any] = {
        "system_prompt": row.system_prompt,
        "model": row.model,
        "temperature": row.temperature,
        "max_tokens": row.max_tokens,
        "tools": list(row.tools or []),
        "guardrails": dict(row.guardrails or {}),
        "memory_strategy": row.memory_strategy,
        "interaction_rules": list(row.interaction_rules or []),
        "skills": list(row.skills or []),
        "role": row.role,
    }
    for k, v in node_data.items():
        if k in _NODE_OVERRIDE_KEYS or k not in merged:
            merged[k] = v
    return merged


def _terminal(name: str) -> str:
    return END if name in ("__end__", "END", "end") else name


def build_graph(
    workflow_json: dict[str, Any],
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Compile a workflow JSON into a runnable LangGraph.

    Returns the compiled graph (already calls `.compile(...)`).
    """
    builder = StateGraph(MessagesState)

    nodes_by_id: dict[str, dict[str, Any]] = {n["id"]: n for n in workflow_json["nodes"]}
    condition_nodes: dict[str, dict[str, Any]] = {
        nid: n for nid, n in nodes_by_id.items() if n["type"] == "condition"
    }

    for node in workflow_json["nodes"]:
        if node["type"] == "agent":
            data = _resolve_agent_data(node["data"])
            agent = make_agent_node({"name": node["id"], **data})
            builder.add_node(node["id"], agent)

    outgoing: dict[str, list[dict[str, Any]]] = {}
    for edge in workflow_json["edges"]:
        outgoing.setdefault(edge["source"], []).append(edge)

    for source_id, edges in outgoing.items():
        source_node = nodes_by_id.get(source_id)

        if source_node and source_node["type"] == "condition":
            continue

        cond_edges = [
            e
            for e in edges
            if (target := nodes_by_id.get(e["target"])) and target["type"] == "condition"
        ]
        if cond_edges:
            cond_edge = cond_edges[0]
            cond_node = nodes_by_id[cond_edge["target"]]
            router_name = cond_node["data"]["router"]
            spec = cond_node["data"].get("spec", {})
            router_fn = ROUTERS[router_name](spec)

            cond_outgoing = outgoing.get(cond_node["id"], [])
            target_map: dict[str, str] = {}
            for ce in cond_outgoing:
                tgt = _terminal(ce["target"])
                key = ce.get("label") or ce.get("source_handle") or ce["target"]
                target_map[key] = tgt

            normalized: dict[str, str] = {}
            for ce in cond_outgoing:
                normalized[ce["target"]] = _terminal(ce["target"])

            builder.add_conditional_edges(source_id, router_fn, normalized)
            continue

        for e in edges:
            builder.add_edge(source_id, _terminal(e["target"]))

    entry = workflow_json.get("entry")
    if entry is None:
        for n in workflow_json["nodes"]:
            if n["type"] == "agent":
                entry = n["id"]
                break
    if entry is None:
        raise ValueError("Workflow has no entry node and no agent nodes")
    builder.add_edge(START, entry)

    return builder.compile(checkpointer=checkpointer)
