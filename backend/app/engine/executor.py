"""Executor — runs a compiled graph and yields structured execution events.

Event types (dict with `type` discriminator):
    run_start    {run_id, workflow_id, thread_id}
    node_start   {node}
    token        {node, text}
    tool_call    {node, name, args, tool_call_id}
    tool_result  {node, name, content, tool_call_id}
    agent_message{node, role, content, token_usage}
    node_end     {node}
    usage        {input_tokens, output_tokens, cost_usd, per_model}
    run_end      {status, error?}
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from app.engine.guardrails import GuardrailViolation, WorkflowGuardrails
from app.engine.usage import aggregate_usage


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for p in content:
            if isinstance(p, dict):
                if p.get("type") == "text":
                    parts.append(p.get("text", ""))
                elif "text" in p:
                    parts.append(p["text"])
            else:
                parts.append(str(p))
        return "".join(parts)
    return str(content)


async def run_graph(
    graph,
    *,
    user_input: str,
    thread_id: str,
    run_id: str | None = None,
    workflow_id: str | None = None,
    guardrails: WorkflowGuardrails | None = None,
    seed_messages: list[Any] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Run `graph.astream` against `user_input` and yield structured events.

    The graph is expected to be compiled with a checkpointer; `thread_id` is
    threaded through `configurable`. ``guardrails`` enforces per-node visit
    caps and rolling cost limits while the stream is consumed.
    """
    run_id = run_id or str(uuid.uuid4())
    guardrails = guardrails or WorkflowGuardrails()
    usage_cb = UsageMetadataCallbackHandler()
    config = {
        "configurable": {"thread_id": thread_id},
        "callbacks": [usage_cb],
        "recursion_limit": (guardrails.max_iterations or 25) * 4,
    }

    started = time.monotonic()
    yield {
        "type": "run_start",
        "run_id": run_id,
        "workflow_id": workflow_id,
        "thread_id": thread_id,
        "input": user_input,
    }

    try:
        guardrails.check_input(user_input)
    except GuardrailViolation as exc:
        yield {"type": "usage", **aggregate_usage(usage_cb.usage_metadata)}
        yield {
            "type": "run_end",
            "status": "failed",
            "error": str(exc),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }
        return

    if seed_messages:
        inputs = {"messages": seed_messages}
    else:
        inputs = {"messages": [HumanMessage(content=user_input)]}

    current_node: str | None = None
    seen_tool_call_ids: set[str] = set()
    seen_ai_msg_ids: set[str] = set()

    try:
        async for stream_mode, chunk in graph.astream(
            inputs,
            config=config,
            stream_mode=["messages", "updates"],
            subgraphs=True,
        ) if False else _astream_compat(graph, inputs, config):
            mode = stream_mode
            payload = chunk

            if mode == "messages":
                msg, meta = payload
                node = meta.get("langgraph_node") or current_node
                if node and node != current_node:
                    if current_node is not None:
                        yield {"type": "node_end", "node": current_node}
                    yield {"type": "node_start", "node": node}
                    current_node = node

                if isinstance(msg, AIMessageChunk):
                    text = _content_to_text(msg.content)
                    if text:
                        yield {"type": "token", "node": node, "text": text}
                elif isinstance(msg, AIMessage):
                    text = _content_to_text(msg.content)
                    for tc in msg.tool_calls or []:
                        tc_id = tc.get("id") or ""
                        if tc_id and tc_id not in seen_tool_call_ids:
                            seen_tool_call_ids.add(tc_id)
                            yield {
                                "type": "tool_call",
                                "node": node,
                                "name": tc.get("name", ""),
                                "args": tc.get("args", {}),
                                "tool_call_id": tc_id,
                            }
                    if msg.id and msg.id not in seen_ai_msg_ids and text:
                        seen_ai_msg_ids.add(msg.id)
                        yield {
                            "type": "agent_message",
                            "node": node,
                            "role": "assistant",
                            "content": text,
                            "token_usage": getattr(msg, "usage_metadata", None),
                        }
                elif isinstance(msg, ToolMessage):
                    yield {
                        "type": "tool_result",
                        "node": node,
                        "name": msg.name or "",
                        "content": _content_to_text(msg.content),
                        "tool_call_id": msg.tool_call_id,
                    }

            elif mode == "updates":
                for node_name, delta in payload.items():
                    if node_name in ("__start__", "__end__"):
                        continue
                    guardrails.record_node_visit(node_name)
                    guardrails.check_cost(
                        aggregate_usage(usage_cb.usage_metadata)["cost_usd"]
                    )
                    if current_node != node_name:
                        if current_node is not None:
                            yield {"type": "node_end", "node": current_node}
                        yield {"type": "node_start", "node": node_name}
                        current_node = node_name

                    delta_messages = (
                        delta.get("messages", []) if isinstance(delta, dict) else []
                    )
                    for m in delta_messages:
                        if isinstance(m, AIMessage):
                            text = _content_to_text(m.content)
                            if m.id and m.id in seen_ai_msg_ids:
                                continue
                            if m.id:
                                seen_ai_msg_ids.add(m.id)
                            if text:
                                yield {
                                    "type": "agent_message",
                                    "node": node_name,
                                    "role": "assistant",
                                    "content": text,
                                    "token_usage": getattr(m, "usage_metadata", None),
                                }
                            for tc in m.tool_calls or []:
                                tc_id = tc.get("id") or ""
                                if tc_id and tc_id not in seen_tool_call_ids:
                                    seen_tool_call_ids.add(tc_id)
                                    yield {
                                        "type": "tool_call",
                                        "node": node_name,
                                        "name": tc.get("name", ""),
                                        "args": tc.get("args", {}),
                                        "tool_call_id": tc_id,
                                    }
                        elif isinstance(m, ToolMessage):
                            yield {
                                "type": "tool_result",
                                "node": node_name,
                                "name": m.name or "",
                                "content": _content_to_text(m.content),
                                "tool_call_id": m.tool_call_id,
                            }

        if current_node is not None:
            yield {"type": "node_end", "node": current_node}

        usage = aggregate_usage(usage_cb.usage_metadata)
        yield {"type": "usage", **usage}
        yield {
            "type": "run_end",
            "status": "succeeded",
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }
    except GuardrailViolation as exc:
        if current_node is not None:
            yield {"type": "node_end", "node": current_node, "error": str(exc)}
        usage = aggregate_usage(usage_cb.usage_metadata)
        yield {"type": "usage", **usage}
        yield {
            "type": "run_end",
            "status": "failed",
            "error": f"guardrail: {exc}",
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }
    except Exception as exc:  # noqa: BLE001
        if current_node is not None:
            yield {"type": "node_end", "node": current_node, "error": str(exc)}
        usage = aggregate_usage(usage_cb.usage_metadata)
        yield {"type": "usage", **usage}
        yield {
            "type": "run_end",
            "status": "failed",
            "error": str(exc),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }


async def _astream_compat(graph, inputs, config) -> AsyncIterator[tuple[str, Any]]:
    """Adapter that yields `(stream_mode, payload)` tuples regardless of the
    LangGraph version's tuple ordering when `stream_mode=[...]` is a list."""
    async for chunk in graph.astream(
        inputs,
        config=config,
        stream_mode=["messages", "updates"],
    ):
        # When stream_mode is a list, langgraph yields (mode, data)
        if isinstance(chunk, tuple) and len(chunk) == 2 and isinstance(chunk[0], str):
            yield chunk
        else:
            # Defensive: single-mode dict shape
            yield ("updates", chunk)
