"""APScheduler integration — fire scheduled agent runs."""

from __future__ import annotations

import logging
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.db.models import Agent, RunTrigger, Workflow
from app.db.session import session_scope
from app.engine.orchestrator import start_run

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _run_scheduled_agent(agent_id: uuid.UUID) -> None:
    async with session_scope() as s:
        agent = await s.get(Agent, agent_id)
        if agent is None or not agent.schedule_cron or not agent.default_workflow_id:
            return
        workflow = await s.get(Workflow, agent.default_workflow_id)
        if workflow is None:
            logger.warning("Agent %s scheduled workflow missing", agent_id)
            return
        user_input = agent.schedule_input or f"Scheduled run for agent {agent.name}"
        wf = workflow

    await start_run(
        workflow=wf,
        user_input=user_input,
        trigger=RunTrigger.schedule,
        thread_id=f"schedule:{agent_id}",
    )
    logger.info("Scheduled run started for agent %s", agent_id)


def _job_id(agent_id: uuid.UUID) -> str:
    return f"agent_schedule:{agent_id}"


async def reload_schedules() -> None:
    """Sync DB agent cron rows with APScheduler jobs."""
    global _scheduler
    if _scheduler is None:
        return

    async with session_scope() as s:
        result = await s.execute(
            select(Agent).where(
                Agent.schedule_cron.isnot(None),
                Agent.default_workflow_id.isnot(None),
            )
        )
        agents = list(result.scalars().all())

    active_ids = {_job_id(a.id) for a in agents}
    for job in _scheduler.get_jobs():
        if job.id.startswith("agent_schedule:") and job.id not in active_ids:
            _scheduler.remove_job(job.id)

    for agent in agents:
        jid = _job_id(agent.id)
        if _scheduler.get_job(jid):
            _scheduler.remove_job(jid)
        try:
            trigger = CronTrigger.from_crontab(agent.schedule_cron)
        except ValueError as exc:
            logger.error("Invalid cron for agent %s: %s", agent.id, exc)
            continue
        aid = agent.id
        _scheduler.add_job(
            _run_scheduled_agent,
            trigger=trigger,
            id=jid,
            args=[aid],
            replace_existing=True,
        )
        logger.info("Registered schedule %s for agent %s", agent.schedule_cron, agent.id)


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler()
    _scheduler.start()
    logger.info("APScheduler started")


async def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("APScheduler stopped")
