"""Run endpoints — start a run, stream events via SSE, list messages."""

from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.schemas import MessageOut, RunCreate, RunOut
from app.db.models import Message, Run, Workflow
from app.db.session import get_session
from app.engine.orchestrator import start_run
from app.events.bus import subscribe

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("", response_model=list[RunOut])
async def list_runs(
    workflow_id: uuid.UUID | None = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Run).order_by(Run.started_at.desc()).limit(limit)
    if workflow_id is not None:
        stmt = stmt.where(Run.workflow_id == workflow_id)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=RunOut, status_code=201)
async def create_run(payload: RunCreate, session: AsyncSession = Depends(get_session)):
    wf = await session.get(Workflow, payload.workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    run = await start_run(
        workflow=wf,
        user_input=payload.input,
        thread_id=payload.thread_id,
    )
    return run


@router.get("/{run_id}", response_model=RunOut)
async def get_run(run_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.get("/{run_id}/messages", response_model=list[MessageOut])
async def list_run_messages(run_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Message).where(Message.run_id == run_id).order_by(Message.created_at.asc())
    )
    return result.scalars().all()


@router.get("/{run_id}/stream")
async def stream_run(run_id: uuid.UUID, request: Request):
    """Server-Sent Events stream of run events. Replays history + tails live."""

    async def event_generator():
        try:
            async for event in subscribe(str(run_id), include_history=True):
                if await request.is_disconnected():
                    break
                yield {"event": event.get("type", "message"), "data": json.dumps(event)}
                if event.get("type") == "run_end":
                    break
        except asyncio.CancelledError:
            raise

    return EventSourceResponse(event_generator())
