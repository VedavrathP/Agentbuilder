"""Telegram link endpoints — register/list/disable bot tokens bound to workflows."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import TelegramLinkCreate, TelegramLinkOut
from app.db.models import TelegramLink, Workflow
from app.db.session import get_session

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.get("/links", response_model=list[TelegramLinkOut])
async def list_links(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(TelegramLink).order_by(TelegramLink.created_at.desc()))
    return result.scalars().all()


@router.post("/links", response_model=TelegramLinkOut, status_code=status.HTTP_201_CREATED)
async def create_link(payload: TelegramLinkCreate, session: AsyncSession = Depends(get_session)):
    wf = await session.get(Workflow, payload.workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="workflow not found")

    existing = await session.execute(
        select(TelegramLink).where(TelegramLink.bot_token == payload.bot_token)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="this bot token is already registered")

    link = TelegramLink(
        workflow_id=payload.workflow_id,
        bot_token=payload.bot_token,
        active=True,
    )
    session.add(link)
    await session.commit()
    await session.refresh(link)
    return link


@router.post("/links/{link_id}/disable", response_model=TelegramLinkOut)
async def disable_link(link_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    link = await session.get(TelegramLink, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="link not found")
    link.active = False
    await session.commit()
    await session.refresh(link)
    return link


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(link_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    link = await session.get(TelegramLink, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="link not found")
    await session.delete(link)
    await session.commit()
