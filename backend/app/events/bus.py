"""Redis pub/sub event bus.

Each run publishes events to channel `run:{run_id}`. SSE consumers subscribe
to that channel. A short Redis Stream is also written (`run:{run_id}:history`)
so late subscribers can replay the run from the beginning.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import redis.asyncio as redis

from app.config import get_settings

_client: redis.Redis | None = None

HISTORY_MAX_LEN = 5_000  # cap to avoid unbounded growth


def channel_for(run_id: str) -> str:
    return f"run:{run_id}"


def history_key_for(run_id: str) -> str:
    return f"run:{run_id}:history"


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        settings = get_settings()
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def publish_event(run_id: str, event: dict[str, Any]) -> None:
    """Publish an event to subscribers AND append to the history stream."""
    r = get_redis()
    payload = json.dumps(event, ensure_ascii=False, default=str)
    pipe = r.pipeline()
    pipe.publish(channel_for(run_id), payload)
    pipe.xadd(history_key_for(run_id), {"e": payload}, maxlen=HISTORY_MAX_LEN, approximate=True)
    await pipe.execute()


async def replay_history(run_id: str) -> list[dict[str, Any]]:
    """Return the full event history for a run (empty if none)."""
    r = get_redis()
    raw = await r.xrange(history_key_for(run_id), min="-", max="+")
    out: list[dict[str, Any]] = []
    for _id, fields in raw:
        e = fields.get("e")
        if e:
            try:
                out.append(json.loads(e))
            except json.JSONDecodeError:
                continue
    return out


async def subscribe(run_id: str, *, include_history: bool = True) -> AsyncIterator[dict[str, Any]]:
    """Async iterator over events for a run.

    If `include_history` is True, all already-published events are replayed
    first, then live events are streamed until a `run_end` event is observed.
    """
    if include_history:
        history = await replay_history(run_id)
        terminal = False
        for ev in history:
            yield ev
            if ev.get("type") == "run_end":
                terminal = True
        if terminal:
            return

    r = get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(channel_for(run_id))
    try:
        async for message in pubsub.listen():
            if message is None:
                continue
            if message.get("type") != "message":
                continue
            data = message.get("data")
            if not data:
                continue
            try:
                ev = json.loads(data)
            except json.JSONDecodeError:
                continue
            yield ev
            if ev.get("type") == "run_end":
                return
    finally:
        await pubsub.unsubscribe(channel_for(run_id))
        await pubsub.aclose()
