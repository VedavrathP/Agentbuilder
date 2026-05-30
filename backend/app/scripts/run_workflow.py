"""CLI smoke test — load a workflow template, run it end-to-end, print events.

Usage:
    python -m app.scripts.run_workflow app/templates/research_and_write.json "Research topic X"
    python -m app.scripts.run_workflow app/templates/support_triage.json "My invoice is wrong"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

from app.engine.checkpointer import close_checkpointer, get_checkpointer
from app.engine.executor import run_graph
from app.engine.factory import build_graph


def _color(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def _fmt_event(event: dict) -> str:
    et = event.get("type", "?")
    if et == "run_start":
        return _color(f"\n▶ RUN START  thread={event['thread_id']}", "1;36")
    if et == "node_start":
        return _color(f"\n┌─ node: {event['node']}", "1;33")
    if et == "node_end":
        return _color(f"└─ /{event['node']}", "33")
    if et == "token":
        return event.get("text", "")
    if et == "tool_call":
        args = json.dumps(event.get("args", {}), ensure_ascii=False)
        return _color(f"\n  ⚙ tool_call {event.get('name')}({args})", "35")
    if et == "tool_result":
        content = event.get("content", "")
        head = content[:160].replace("\n", " ")
        return _color(f"\n  ⤷ tool_result {event.get('name')}: {head}…", "35")
    if et == "agent_message":
        # Already streamed via tokens; show summary line
        return _color(
            f"\n  ✓ agent_message ({event.get('node')}, "
            f"tokens={(event.get('token_usage') or {}).get('total_tokens', '?')})",
            "32",
        )
    if et == "usage":
        return _color(
            f"\n\n📊 usage: in={event['input_tokens']} out={event['output_tokens']} "
            f"cost=${event['cost_usd']:.6f}",
            "1;34",
        )
    if et == "run_end":
        status = event.get("status", "?")
        ms = event.get("elapsed_ms", 0)
        color = "1;32" if status == "succeeded" else "1;31"
        return _color(f"\n■ RUN END status={status} elapsed_ms={ms}", color)
    return json.dumps(event)


async def main_async(workflow_path: Path, user_input: str, thread_id: str) -> int:
    workflow_json = json.loads(workflow_path.read_text())
    graph_json = workflow_json.get("graph", workflow_json)

    checkpointer = await get_checkpointer()
    try:
        graph = build_graph(graph_json, checkpointer=checkpointer)

        async for event in run_graph(
            graph,
            user_input=user_input,
            thread_id=thread_id,
            workflow_id=workflow_json.get("template_key", "ad_hoc"),
        ):
            print(_fmt_event(event), end="", flush=True)
        print()
    finally:
        await close_checkpointer()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow", type=Path, help="Path to a workflow template JSON")
    parser.add_argument("input", type=str, help="User input to send to the entry agent")
    parser.add_argument(
        "--thread",
        default=None,
        help="Thread id for persistence (defaults to a fresh UUID)",
    )
    args = parser.parse_args()
    thread = args.thread or f"cli-{uuid.uuid4()}"
    sys.exit(asyncio.run(main_async(args.workflow, args.input, thread)))


if __name__ == "__main__":
    main()
