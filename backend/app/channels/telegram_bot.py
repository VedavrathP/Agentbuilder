"""Telegram channel — a polling worker that bridges Telegram chats to LangGraph workflows.

Architecture:
    - One `Application` per (active) `TelegramLink` row.
    - The supervisor task periodically reconciles DB rows with running bots,
      starting/stopping `Application`s as links are created/disabled.
    - Each bot's message handler maps `chat_id` → `thread_id` and streams the
      workflow response back, editing one Telegram message ~every 800ms to
      respect Telegram's edit rate limits.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.db.models import (
    Message,
    MessageRole,
    Run,
    RunStatus,
    RunTrigger,
    TelegramLink,
    Workflow,
)
from app.db.session import session_scope
from app.engine.checkpointer import get_checkpointer
from app.engine.executor import run_graph
from app.engine.factory import build_graph
from app.events.bus import publish_event

logger = logging.getLogger(__name__)

RECONCILE_INTERVAL_S = 10
EDIT_THROTTLE_S = 0.8
MAX_TG_MESSAGE_LEN = 4096


@dataclass
class _RunningBot:
    link_id: uuid.UUID
    workflow_id: uuid.UUID
    app: Application
    task: asyncio.Task


_running: dict[uuid.UUID, _RunningBot] = {}
_supervisor_task: asyncio.Task | None = None


def _truncate(s: str, n: int = MAX_TG_MESSAGE_LEN) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def make_message_handler(workflow_id: uuid.UUID):
    """Build a python-telegram-bot message handler bound to a workflow id."""

    async def handle_message(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message is None or update.message.text is None:
            return
        chat_id = update.effective_chat.id
        user_text = update.message.text
        thread_id = f"telegram:{workflow_id}:{chat_id}"

        # Resolve workflow + start a Run row
        async with session_scope() as s:
            wf = await s.get(Workflow, workflow_id)
            if wf is None:
                await update.message.reply_text("This bot is not linked to a workflow.")
                return
            run = Run(
                workflow_id=wf.id,
                thread_id=thread_id,
                status=RunStatus.running,
                trigger=RunTrigger.telegram,
                input_text=user_text,
            )
            s.add(run)
            s.add(
                Message(
                    run_id=run.id,
                    thread_id=thread_id,
                    role=MessageRole.user,
                    content=user_text,
                )
            )
            await s.flush()
            run_id = run.id
            graph_json = wf.graph_json

        sent = await update.message.reply_text("…")

        cp = await get_checkpointer()
        graph = build_graph(graph_json, checkpointer=cp)

        buffer: dict[str, str] = {}
        last_edit_at = 0.0
        final_status = "succeeded"
        final_error: str | None = None
        total_usage: dict[str, Any] | None = None

        async def _flush() -> None:
            nonlocal last_edit_at
            text = "\n\n".join(
                f"*{node}*\n{txt.strip()}" for node, txt in buffer.items() if txt.strip()
            )
            if not text:
                return
            try:
                await sent.edit_text(_truncate(text), parse_mode="Markdown")
                last_edit_at = time.monotonic()
            except Exception as exc:  # noqa: BLE001
                logger.debug("telegram edit_text failed: %s", exc)

        try:
            async for event in run_graph(
                graph,
                user_input=user_text,
                thread_id=thread_id,
                run_id=str(run_id),
                workflow_id=str(workflow_id),
            ):
                await publish_event(str(run_id), event)

                et = event.get("type")
                node = event.get("node") or "agent"

                if et == "token":
                    buffer[node] = buffer.get(node, "") + event.get("text", "")
                    if time.monotonic() - last_edit_at > EDIT_THROTTLE_S:
                        await _flush()
                elif et == "agent_message":
                    buffer[node] = event.get("content", "")
                    async with session_scope() as s:
                        s.add(
                            Message(
                                run_id=run_id,
                                thread_id=thread_id,
                                source_node=node,
                                role=MessageRole.assistant,
                                content=event.get("content", ""),
                                token_usage=event.get("token_usage"),
                            )
                        )
                    await _flush()
                elif et == "tool_result":
                    async with session_scope() as s:
                        s.add(
                            Message(
                                run_id=run_id,
                                thread_id=thread_id,
                                source_node=node,
                                role=MessageRole.tool,
                                content=event.get("content", ""),
                                tool_calls=[
                                    {
                                        "name": event.get("name"),
                                        "tool_call_id": event.get("tool_call_id"),
                                    }
                                ],
                            )
                        )
                elif et == "usage":
                    total_usage = event
                elif et == "run_end":
                    final_status = event.get("status", "succeeded")
                    final_error = event.get("error")

            await _flush()
        except Exception as exc:  # noqa: BLE001
            logger.exception("telegram run failed")
            final_status = "failed"
            final_error = str(exc)
            try:
                await sent.edit_text(f"Error: {exc}")
            except Exception:
                pass

        async with session_scope() as s:
            run_obj = await s.get(Run, run_id)
            if run_obj is not None:
                run_obj.status = (
                    RunStatus(final_status)
                    if final_status in RunStatus._value2member_map_
                    else RunStatus.succeeded
                )
                run_obj.error = final_error
                run_obj.finished_at = datetime.now(UTC)
                if total_usage:
                    run_obj.total_input_tokens = int(total_usage.get("input_tokens", 0))
                    run_obj.total_output_tokens = int(total_usage.get("output_tokens", 0))
                    run_obj.total_cost_usd = float(total_usage.get("cost_usd", 0.0))

    return handle_message


async def _run_application(link: TelegramLink) -> None:
    """Start a polling bot for a TelegramLink and run until cancelled."""
    app = ApplicationBuilder().token(link.bot_token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, make_message_handler(link.workflow_id)))

    try:
        await app.initialize()
        await app.start()

        try:
            me = await app.bot.get_me()
            async with session_scope() as s:
                row = await s.get(TelegramLink, link.id)
                if row is not None:
                    row.bot_username = me.username
        except Exception as exc:  # noqa: BLE001
            logger.warning("could not fetch bot username: %s", exc)

        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("telegram bot started: link_id=%s username=@%s", link.id, link.bot_username)

        # Block until cancelled
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logger.info("telegram bot stopping: link_id=%s", link.id)
        raise
    finally:
        try:
            if app.updater and app.updater.running:
                await app.updater.stop()
            if app.running:
                await app.stop()
            await app.shutdown()
        except Exception as exc:  # noqa: BLE001
            logger.warning("error during telegram bot shutdown: %s", exc)


async def _reconcile_once() -> None:
    """One iteration of the supervisor: sync DB links to running bots."""
    async with session_scope() as s:
        result = await s.execute(select(TelegramLink).where(TelegramLink.active.is_(True)))
        active_links = list(result.scalars().all())

    by_id = {link.id: link for link in active_links}

    # Stop bots whose link is no longer active
    for link_id in list(_running.keys()):
        if link_id not in by_id:
            rb = _running.pop(link_id)
            rb.task.cancel()
            try:
                await rb.task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

    # Start bots for any new active links
    for link_id, link in by_id.items():
        if link_id in _running:
            continue
        task = asyncio.create_task(_run_application(link))
        _running[link_id] = _RunningBot(
            link_id=link_id,
            workflow_id=link.workflow_id,
            app=None,  # filled in by _run_application but unused externally
            task=task,
        )


async def supervisor_loop() -> None:
    """Periodic supervisor — reconciles active TelegramLinks with running bots."""
    logger.info("telegram supervisor started")
    try:
        while True:
            try:
                await _reconcile_once()
            except Exception:  # noqa: BLE001
                logger.exception("telegram reconcile failed")
            await asyncio.sleep(RECONCILE_INTERVAL_S)
    except asyncio.CancelledError:
        logger.info("telegram supervisor stopping")
        for link_id in list(_running.keys()):
            rb = _running.pop(link_id)
            rb.task.cancel()
            try:
                await rb.task
            except (asyncio.CancelledError, Exception):
                pass
        raise


def start_supervisor() -> asyncio.Task:
    global _supervisor_task
    if _supervisor_task is None or _supervisor_task.done():
        _supervisor_task = asyncio.create_task(supervisor_loop())
    return _supervisor_task


async def stop_supervisor() -> None:
    global _supervisor_task
    if _supervisor_task is not None:
        _supervisor_task.cancel()
        try:
            await _supervisor_task
        except (asyncio.CancelledError, Exception):
            pass
        _supervisor_task = None
