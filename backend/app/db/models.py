"""ORM models — Agent, Workflow, Run, Message, TelegramLink."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class RunStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class RunTrigger(str, enum.Enum):
    manual = "manual"
    telegram = "telegram"
    schedule = "schedule"
    api = "api"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    tool = "tool"
    system = "system"


class Agent(Base):
    """A configurable AI agent definition."""

    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(120), nullable=False, default="assistant")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model: Mapped[str] = mapped_column(String(80), nullable=False, default="gpt-4o-mini")
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # List of {"type": "web_search", "config": {...}} entries
    tools: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)

    # List of channel descriptors, e.g. [{"type": "telegram", "config": {...}}]
    channels: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)

    # Free-form skills the agent advertises (used in prompts / discovery)
    skills: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    # Plain-language constraints injected as system message at run start
    interaction_rules: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    # Optional cron string (e.g. "0 9 * * *")
    schedule_cron: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Default workflow to invoke when the cron fires
    default_workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True
    )
    # Optional canned input for scheduled runs
    schedule_input: Mapped[str | None] = mapped_column(Text, nullable=True)

    # "none" | "thread" | "summary"
    memory_strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="thread")

    # Free-form guardrails: max_iterations, allowed_domains, max_cost_usd, etc.
    guardrails: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Workflow(Base):
    """A visual workflow connecting agents and conditions."""

    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # React Flow graph: {"nodes": [...], "edges": [...], "viewport": {...}, "entry": "node_id"}
    graph_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    template_key: Mapped[str | None] = mapped_column(String(80), nullable=True, unique=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    runs: Mapped[list[Run]] = relationship(back_populates="workflow", cascade="all, delete-orphan")


class Run(Base):
    """A single execution of a workflow."""

    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    thread_id: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status"), nullable=False, default=RunStatus.queued
    )
    trigger: Mapped[RunTrigger] = mapped_column(
        Enum(RunTrigger, name="run_trigger"), nullable=False, default=RunTrigger.manual
    )
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workflow: Mapped[Workflow] = relationship(back_populates="runs")
    messages: Mapped[list[Message]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="Message.created_at"
    )


class Message(Base):
    """A persisted message visible in the UI (separate from LangGraph internal checkpoints)."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=True
    )
    thread_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    source_node: Mapped[str | None] = mapped_column(String(120), nullable=True)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, name="message_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")

    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    run: Mapped[Run | None] = relationship(back_populates="messages")


class TelegramLink(Base):
    """Binds a Telegram bot token to a workflow (and optionally an agent)."""

    __tablename__ = "telegram_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    bot_token: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    bot_username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
