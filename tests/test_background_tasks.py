"""Unit tests for src/utils/background_tasks.py."""
from __future__ import annotations

import asyncio

from src.utils.background_tasks import _BACKGROUND_TASKS, spawn_background


def test_spawn_background_retains_reference_until_done() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        finished = asyncio.Event()

        async def work() -> None:
            started.set()
            await asyncio.sleep(0.01)
            finished.set()

        task = spawn_background(work())
        assert task in _BACKGROUND_TASKS

        await started.wait()
        assert task in _BACKGROUND_TASKS  # still tracked while running

        await finished.wait()
        await asyncio.sleep(0)  # let the done_callback fire
        assert task not in _BACKGROUND_TASKS  # discarded once complete

    asyncio.run(scenario())


def test_spawn_background_runs_the_coroutine() -> None:
    async def scenario() -> None:
        result = {}

        async def work() -> None:
            result["ran"] = True

        task = spawn_background(work())
        await task

        assert result == {"ran": True}

    asyncio.run(scenario())
