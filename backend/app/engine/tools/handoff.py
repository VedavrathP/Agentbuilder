"""Agent-to-agent handoff tool returning a LangGraph `Command`.

This follows the canonical handoff pattern from the LangChain handoffs docs:
https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs

Two invariants matter for correctness with OpenAI / Anthropic chat models:

1. Every assistant ``tool_calls`` message in history MUST be immediately
   followed by a matching ``ToolMessage``. We satisfy this by returning the
   triggering ``AIMessage`` alongside the synthetic ``ToolMessage`` in the
   parent state update.
2. The source agent's ReAct loop must not bounce back to its own LLM after
   the handoff fires (otherwise the source LLM sees an unanswered tool call
   and produces an invalid follow-up). We mark the tool as ``return_direct``
   so the source subagent exits as soon as it runs.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool, InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from typing_extensions import Annotated


def make_handoff_tool(target_agent: str) -> BaseTool:
    """Create a tool the LLM can call to transfer control to ``target_agent``."""

    safe_name = target_agent.replace(" ", "_").replace("-", "_")
    tool_name = f"transfer_to_{safe_name}"

    description = (
        f"Transfer control to the '{target_agent}' agent. "
        "Use when the user's request is outside your expertise. "
        "Pass a brief 'reason' string explaining the handoff."
    )

    @tool(tool_name, description=description, return_direct=True)
    def handoff(
        reason: str,
        state: Annotated[dict[str, Any], InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        tool_msg = ToolMessage(
            content=f"Transferring to {target_agent}: {reason}",
            name=tool_name,
            tool_call_id=tool_call_id,
        )

        # Locate the AIMessage that issued this tool call so the receiving
        # agent sees a well-formed (AIMessage(tool_calls), ToolMessage) pair.
        messages = state.get("messages", []) if isinstance(state, dict) else []
        triggering_ai: AIMessage | None = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                if any(tc.get("id") == tool_call_id for tc in msg.tool_calls):
                    triggering_ai = msg
                    break

        update_messages: list[Any] = []
        if triggering_ai is not None:
            update_messages.append(triggering_ai)
        update_messages.append(tool_msg)

        return Command(
            goto=target_agent,
            graph=Command.PARENT,
            update={"messages": update_messages},
        )

    return handoff
