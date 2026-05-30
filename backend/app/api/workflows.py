"""Workflow CRUD + template instantiation."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import WorkflowCreate, WorkflowOut, WorkflowUpdate
from app.db.models import Workflow
from app.db.session import get_session
from app.engine.orchestrator import invalidate_graph_cache

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("", response_model=list[WorkflowOut])
async def list_workflows(
    include_templates: bool = True,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Workflow).order_by(Workflow.created_at.desc())
    if not include_templates:
        stmt = stmt.where(Workflow.is_template.is_(False))
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=WorkflowOut, status_code=status.HTTP_201_CREATED)
async def create_workflow(payload: WorkflowCreate, session: AsyncSession = Depends(get_session)):
    wf = Workflow(**payload.model_dump())
    session.add(wf)
    await session.commit()
    await session.refresh(wf)
    return wf


@router.get("/{workflow_id}", response_model=WorkflowOut)
async def get_workflow(workflow_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    wf = await session.get(Workflow, workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return wf


@router.patch("/{workflow_id}", response_model=WorkflowOut)
async def update_workflow(
    workflow_id: uuid.UUID,
    payload: WorkflowUpdate,
    session: AsyncSession = Depends(get_session),
):
    wf = await session.get(Workflow, workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    data = payload.model_dump(exclude_unset=True)
    if "graph_json" in data and data["graph_json"] is not None:
        wf.version += 1
    for k, v in data.items():
        setattr(wf, k, v)
    await session.commit()
    await session.refresh(wf)
    invalidate_graph_cache(str(wf.id))
    return wf


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(workflow_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    wf = await session.get(Workflow, workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    await session.delete(wf)
    await session.commit()
    invalidate_graph_cache(str(workflow_id))


@router.post("/from-template/{template_key}", response_model=WorkflowOut, status_code=201)
async def instantiate_template(
    template_key: str,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Workflow).where(Workflow.template_key == template_key, Workflow.is_template.is_(True))
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail=f"template {template_key!r} not found")

    clone = Workflow(
        name=f"{template.name} (copy)",
        description=template.description,
        graph_json=template.graph_json,
        is_template=False,
        template_key=None,
    )
    session.add(clone)
    await session.commit()
    await session.refresh(clone)
    return clone
