"""Agent CRUD endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import AgentCreate, AgentOut, AgentUpdate
from app.db.models import Agent
from app.db.session import get_session
from app.scheduler import reload_schedules

router = APIRouter(prefix="/api/agents", tags=["agents"])


async def _safe_reload_schedules() -> None:
    try:
        await reload_schedules()
    except Exception:  # noqa: BLE001
        pass


@router.get("", response_model=list[AgentOut])
async def list_agents(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Agent).order_by(Agent.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(payload: AgentCreate, session: AsyncSession = Depends(get_session)):
    agent = Agent(**payload.model_dump())
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    await _safe_reload_schedules()
    return agent


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return agent


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: uuid.UUID,
    payload: AgentUpdate,
    session: AsyncSession = Depends(get_session),
):
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(agent, k, v)
    await session.commit()
    await session.refresh(agent)
    await _safe_reload_schedules()
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    await session.delete(agent)
    await session.commit()
    await _safe_reload_schedules()
