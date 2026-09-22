"""Queue protocol tests — round-trip task envelopes through a fakeredis instance.

These tests don't require a live Redis server; they monkeypatch the module-level client.
"""

import json

import pytest

import src.job_queue as queue_module


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
    assert got["task"] == "video"
    assert got["job_id"] == "20260517_120000_ABCD"


async def test_enqueue_with_extra_fields() -> None:
    envelope = {"task": "prd_intent", "job_id": "X", "intent_text": "desktop app"}
    await queue_module.enqueue(envelope)
    got = await queue_module.dequeue()
    assert got["task"] == "prd_intent"
    assert got["job_id"] == "X"
    assert got["intent_text"] == "desktop app"


# ---------------------------------------------------------------------------
# Queue lineage (handoff §2 "Queue lineage and execution bounds")
# ---------------------------------------------------------------------------


async def test_enqueue_stamps_a_root_task_with_fresh_lineage() -> None:
    await queue_module.enqueue({"task": "video", "job_id": "A"})
    got = await queue_module.dequeue()
    assert got["depth"] == 0
    assert got["attempt"] == 1
    assert got["root_task_id"]  # a fresh id, not job_id — no parent to inherit from


async def test_enqueue_preserves_explicit_lineage() -> None:
    await queue_module.enqueue(
        {"task": "video", "job_id": "A", "root_task_id": "root-1", "depth": 2, "attempt": 3}
    )
    got = await queue_module.dequeue()
    assert got["root_task_id"] == "root-1"
    assert got["depth"] == 2
    assert got["attempt"] == 3


def test_chained_envelope_inherits_root_and_increments_depth() -> None:
    parent = {"task": "bookmarks", "job_id": "job-1", "root_task_id": "job-1", "depth": 0, "attempt": 1}
    child = queue_module.chained_envelope(parent, {"task": "bookmarks_enrich", "job_id": "job-1"})
    assert child["root_task_id"] == "job-1"
    assert child["depth"] == 1
    assert child["attempt"] == 1  # a fresh hop, not a redelivery of the parent


def test_chained_envelope_falls_back_to_parent_job_id_as_root() -> None:
    """A root task (no root_task_id of its own yet) chains onto its own job_id."""
    parent = {"task": "video", "job_id": "job-1"}
    child = queue_module.chained_envelope(parent, {"task": "enrichment", "job_id": "job-1"})
    assert child["root_task_id"] == "job-1"
    assert child["depth"] == 1


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


def test_client_socket_timeout_exceeds_dequeue_timeout(monkeypatch) -> None:  # noqa: ANN001
    """socket_timeout must stay above the blocking BRPOP window, or redis-py's
    client-side read timeout fires before the server's own timeout does."""
    monkeypatch.setattr(queue_module, "_redis", None)
    client = queue_module._client()
    try:
        assert client.get_connection_kwargs()["socket_timeout"] > queue_module._DEQUEUE_TIMEOUT_SECONDS
    finally:
        monkeypatch.setattr(queue_module, "_redis", None)
