"""FastAPI application entry point.

Lifespan tasks:
    - Open the LangGraph Postgres checkpointer (creates checkpoint tables).
    - Seed built-in workflow templates from `app/templates/*.json`.
    - On shutdown, close pools cleanly.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api import agents as agents_router
from app.api import runs as runs_router
from app.api import telegram as telegram_router
from app.api import workflows as workflows_router
from app.channels.telegram_bot import start_supervisor, stop_supervisor
from app.config import get_settings
from app.db.models import Workflow
from app.db.session import session_scope
from app.engine.checkpointer import close_checkpointer, get_checkpointer
from app.engine.orchestrator import load_template_files
from app.events.bus import close_redis
from app.scheduler import reload_schedules, start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


def _materialize_template_graph(tpl: dict) -> dict:
    """Merge top-level fields (entry, guardrails, memory_strategy, interaction_rules)
    into the graph dict so the factory and orchestrator see them."""
    graph = dict(tpl.get("graph") or {})
    for key in ("entry", "guardrails", "memory_strategy", "interaction_rules"):
        if key in tpl and key not in graph:
            graph[key] = tpl[key]
    return graph


async def seed_templates() -> None:
    """Insert/refresh built-in templates by `template_key`."""
    templates = load_template_files()
    if not templates:
        return
    async with session_scope() as s:
        for tpl in templates:
            key = tpl.get("template_key")
            if not key:
                continue
            graph = _materialize_template_graph(tpl)
            existing = await s.execute(
                select(Workflow).where(Workflow.template_key == key, Workflow.is_template.is_(True))
            )
            row = existing.scalar_one_or_none()
            if row is None:
                s.add(
                    Workflow(
                        name=tpl["name"],
                        description=tpl.get("description", ""),
                        graph_json=graph,
                        is_template=True,
                        template_key=key,
                    )
                )
            else:
                row.name = tpl["name"]
                row.description = tpl.get("description", "")
                row.graph_json = graph
                row.version += 1


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logger.info("Starting Orchestra backend")

    await get_checkpointer()
    await seed_templates()
    start_supervisor()
    start_scheduler()
    try:
        await reload_schedules()
    except Exception:  # noqa: BLE001
        logger.exception("Failed initial schedule reload")

    yield

    logger.info("Shutting down Orchestra backend")
    await stop_supervisor()
    await stop_scheduler()
    await close_checkpointer()
    await close_redis()


app = FastAPI(
    title="Orchestra — AI Agent Orchestration Platform",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(agents_router.router)
app.include_router(workflows_router.router)
app.include_router(runs_router.router)
app.include_router(telegram_router.router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
