"""Agent CRUD tests via FastAPI against the live (docker-compose) Postgres.

Tests truncate the app tables before each run for hermetic state. They
monkeypatch out the LangGraph + Redis startup hooks so the lifespan doesn't
require those services to be available.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient

from app.db.session import get_sessionmaker, reset_engine
from app.engine import checkpointer as checkpointer_module
from app.events import bus as bus_module
from app.main import app


async def _truncate_app_tables() -> None:
    """Reset transient state to give each test a clean slate, but preserve
    any seeded ``is_template=true`` workflow rows so we don't clobber the
    templates that a co-running dev backend has installed.
    """
    sm = get_sessionmaker()
    async with sm() as s:
        # Order matters: child tables before parents (CASCADE handles the rest).
        await s.execute(sa.text("TRUNCATE messages, runs, telegram_links RESTART IDENTITY"))
        await s.execute(sa.text("DELETE FROM agents"))
        # Keep built-in template rows so a co-running dev backend keeps working,
        # but drop test-only templates so re-running the suite is idempotent.
        await s.execute(
            sa.text(
                "DELETE FROM workflows "
                "WHERE is_template = FALSE OR template_key NOT IN ("
                "'research_and_write', 'support_triage', 'draft_and_critic')"
            )
        )
        await s.commit()


@pytest_asyncio.fixture
async def client(monkeypatch) -> AsyncIterator[AsyncClient]:
    # Fresh engine per test (pytest-asyncio uses a new loop per test).
    await reset_engine()
    await _truncate_app_tables()

    async def _noop():
        return None

    monkeypatch.setattr(checkpointer_module, "get_checkpointer", _noop)
    monkeypatch.setattr(checkpointer_module, "close_checkpointer", _noop)
    monkeypatch.setattr(bus_module, "close_redis", _noop)

    async def _noop_seed():
        return None

    monkeypatch.setattr("app.main.seed_templates", _noop_seed)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        async with app.router.lifespan_context(app):
            yield ac

    await reset_engine()


@pytest.mark.asyncio
async def test_agent_crud_roundtrip(client: AsyncClient):
    payload = {
        "name": "Test Agent",
        "role": "tester",
        "system_prompt": "You are a tester.",
        "model": "gpt-4o-mini",
        "temperature": 0.5,
        "tools": [{"type": "web_search", "config": {"max_results": 3}}],
    }
    r = await client.post("/api/agents", json=payload)
    assert r.status_code == 201, r.text
    agent = r.json()
    agent_id = agent["id"]
    assert agent["name"] == "Test Agent"

    r = await client.get(f"/api/agents/{agent_id}")
    assert r.status_code == 200
    assert r.json()["temperature"] == 0.5

    r = await client.patch(f"/api/agents/{agent_id}", json={"temperature": 0.9})
    assert r.status_code == 200
    assert r.json()["temperature"] == 0.9

    r = await client.get("/api/agents")
    assert r.status_code == 200
    assert any(a["id"] == agent_id for a in r.json())

    r = await client.delete(f"/api/agents/{agent_id}")
    assert r.status_code == 204

    r = await client.get(f"/api/agents/{agent_id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_workflow_template_instantiate(client: AsyncClient):
    # Seed one template directly via the API
    template_payload = {
        "name": "Demo Template",
        "description": "demo",
        "graph_json": {
            "entry": "a",
            "nodes": [
                {"id": "a", "type": "agent", "data": {"system_prompt": "hi", "model": "gpt-4o-mini"}}
            ],
            "edges": [{"id": "e", "source": "a", "target": "__end__"}],
        },
        "is_template": True,
        "template_key": "demo_template",
    }
    r = await client.post("/api/workflows", json=template_payload)
    assert r.status_code == 201, r.text

    r = await client.post("/api/workflows/from-template/demo_template")
    assert r.status_code == 201
    clone = r.json()
    assert clone["is_template"] is False
    assert clone["name"].endswith("(copy)")
