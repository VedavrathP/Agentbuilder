"""Pydantic request/response schemas for the public API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str = "assistant"
    system_prompt: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    max_tokens: int | None = None
    tools: list[dict[str, Any]] = Field(default_factory=list)
    channels: list[dict[str, Any]] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    interaction_rules: list[str] = Field(default_factory=list)
    schedule_cron: str | None = None
    default_workflow_id: uuid.UUID | None = None
    schedule_input: str | None = None
    memory_strategy: str = "thread"
    guardrails: dict[str, Any] = Field(default_factory=dict)


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    tools: list[dict[str, Any]] | None = None
    channels: list[dict[str, Any]] | None = None
    skills: list[str] | None = None
    interaction_rules: list[str] | None = None
    schedule_cron: str | None = None
    default_workflow_id: uuid.UUID | None = None
    schedule_input: str | None = None
    memory_strategy: str | None = None
    guardrails: dict[str, Any] | None = None


class AgentOut(AgentBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class WorkflowBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    graph_json: dict[str, Any]
    is_template: bool = False
    template_key: str | None = None


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    graph_json: dict[str, Any] | None = None
    is_template: bool | None = None
    template_key: str | None = None


class WorkflowOut(WorkflowBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime


class RunCreate(BaseModel):
    workflow_id: uuid.UUID
    input: str = Field(min_length=1)
    thread_id: str | None = None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workflow_id: uuid.UUID
    thread_id: str
    status: str
    trigger: str
    input_text: str | None
    error: str | None
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    started_at: datetime
    finished_at: datetime | None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    run_id: uuid.UUID | None
    thread_id: str
    source_node: str | None
    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None
    token_usage: dict[str, Any] | None
    created_at: datetime


class TelegramLinkCreate(BaseModel):
    workflow_id: uuid.UUID
    bot_token: str = Field(min_length=10)


class TelegramLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workflow_id: uuid.UUID
    bot_username: str | None
    active: bool
    created_at: datetime
