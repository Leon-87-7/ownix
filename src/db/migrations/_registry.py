"""Migration registry — a step's version is declared, never inferred from position.

Every step registers itself under an explicit target version: ``@migration(44)``
is the v43 → v44 step no matter where in the file it sits, and ``sql(45, [...])``
likewise. Registration rejects a duplicate version on import, and :func:`ordered`
rejects a gap, so a mis-numbered or missing step fails startup loudly instead of
being skipped.

This replaces a ``_MIGRATIONS.append(...)`` list whose runtime order *was* file
position. That cost a production outage (commit 0415dfa): a step appended next
to related code landed at index 46 while production had already reached
user_version 48, so ``_MIGRATIONS[48:]`` silently skipped it on every startup,
and the ``v44 -> v45`` comments above neighbouring steps had drifted out of sync
with their real indices. Declaring the number makes both failures impossible.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import aiosqlite

#: A step is either a list of idempotent SQL statements or an async callable.
Step = list[str] | Callable[[aiosqlite.Connection], Awaitable[None]]

_REGISTRY: dict[int, Step] = {}


def _register(version: int, step: Step) -> None:
    if version < 1:
        raise RuntimeError(f"migration versions start at 1, got {version}")
    if version in _REGISTRY:
        raise RuntimeError(f"duplicate migration version {version}")
    _REGISTRY[version] = step


def migration(version: int) -> Callable[[Step], Step]:
    """Register an async callable as the v(*version*-1) → v(*version*) step."""

    def register(step: Step) -> Step:
        _register(version, step)
        return step

    return register


def sql(version: int, statements: list[str]) -> list[str]:
    """Register *statements* as the v(*version*-1) → v(*version*) step.

    Returns the same list object, so a step that also needs a module-level name
    (one a test pins by identity) can be written as a plain assignment first and
    registered by that name.
    """
    _register(version, statements)
    return statements


def ordered() -> list[Step]:
    """Registered steps as a 0-indexed list: index N holds the vN → v(N+1) step.

    Raises if any version between 1 and the highest registered one is missing —
    a gap means a step was deleted or mis-numbered, and running the rest would
    stamp a user_version the schema hasn't actually reached.
    """
    if not _REGISTRY:
        return []
    highest = max(_REGISTRY)
    missing = sorted(set(range(1, highest + 1)) - set(_REGISTRY))
    if missing:
        raise RuntimeError(f"migration version gap: {missing}")
    return [_REGISTRY[version] for version in range(1, highest + 1)]
