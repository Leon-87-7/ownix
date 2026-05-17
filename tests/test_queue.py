"""Queue protocol tests — round-trip task envelopes through a fakeredis instance.

These tests don't require a live Redis server; they monkeypatch the module-level client.
"""

import json

import pytest

import src.queue as queue_module


class FakeRedis:
    """Minimal async-compatible double for redis.asyncio.Redis."""

    def __init__(self) -> None:
        self._lists: dict[str, list[str]] = {}

    async def lpush(self, key: str, value: str) -> int:
        self._lists.setdefault(key, []).insert(0, value)
        return len(self._lists[key])

    async def brpop(self, keys, timeout=0):  # noqa: ANN001 — match redis-py loose signature
        key = keys[0] if isinstance(keys, list) else keys
        items = self._lists.get(key, [])
        if not items:
            return None
        return (key, items.pop())

    async def close(self) -> None:
        pass


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):  # noqa: ANN001
    """Replace the module-level client with a FakeRedis for every test in this file."""
    fake = FakeRedis()
    monkeypatch.setattr(queue_module, "_redis", fake)
    yield fake
    monkeypatch.setattr(queue_module, "_redis", None)


async def test_enqueue_dequeue_roundtrip() -> None:
    envelope = {"task": "video", "job_id": "20260517_120000_ABCD"}
    await queue_module.enqueue(envelope)
    got = await queue_module.dequeue()
    assert got == envelope


async def test_enqueue_with_extra_fields() -> None:
    envelope = {"task": "prd_intent", "job_id": "X", "intent_text": "desktop app"}
    await queue_module.enqueue(envelope)
    got = await queue_module.dequeue()
    assert got == envelope


async def test_dequeue_empty_returns_none() -> None:
    assert await queue_module.dequeue() is None


async def test_enqueue_rejects_missing_task() -> None:
    with pytest.raises(ValueError):
        await queue_module.enqueue({"job_id": "X"})


async def test_enqueue_rejects_missing_job_id() -> None:
    with pytest.raises(ValueError):
        await queue_module.enqueue({"task": "video"})


async def test_dequeue_rejects_non_dict_payload(fake_redis: FakeRedis) -> None:
    # Manually push a bad payload (bypasses the enqueue() validation).
    fake_redis._lists.setdefault("video_jobs", []).insert(0, json.dumps(["not", "a", "dict"]))
    assert await queue_module.dequeue() is None


async def test_dequeue_rejects_envelope_missing_keys(fake_redis: FakeRedis) -> None:
    fake_redis._lists.setdefault("video_jobs", []).insert(0, json.dumps({"task": "video"}))
    assert await queue_module.dequeue() is None


async def test_dequeue_rejects_malformed_json(fake_redis: FakeRedis) -> None:
    fake_redis._lists.setdefault("video_jobs", []).insert(0, "{not json")
    assert await queue_module.dequeue() is None


async def test_fifo_order() -> None:
    await queue_module.enqueue({"task": "video", "job_id": "A"})
    await queue_module.enqueue({"task": "video", "job_id": "B"})
    first = await queue_module.dequeue()
    second = await queue_module.dequeue()
    assert first["job_id"] == "A"
    assert second["job_id"] == "B"
