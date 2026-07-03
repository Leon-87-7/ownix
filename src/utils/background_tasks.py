"""Shared fire-and-forget task tracking.

asyncio.create_task(...) with no retained reference can be garbage-collected
mid-run (see the asyncio docs' "Important" note on create_task). Every
fire-and-forget call site in the codebase should go through spawn_background
instead of calling asyncio.create_task directly.
"""
from __future__ import annotations

import asyncio
from typing import Coroutine

_BACKGROUND_TASKS: set[asyncio.Task] = set()


def spawn_background(coro: Coroutine) -> asyncio.Task:
    """asyncio.create_task, but keeps a strong reference until the task finishes."""
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task
