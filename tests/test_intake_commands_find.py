"""Tests for the shared `/find` command (issue #485).

`find_command` is the channel-agnostic half migrated out of
`src/telegram/webhook.py:_cmd_find` — search, score-filter, GitHub enrichment.
Message formatting stays per-channel; this covers only the shared behavior,
via `SHARED_COMMANDS` the same way the dashboard reaches it.
"""

from __future__ import annotations

import asyncio

import pytest

from src.intake import commands

CHAT_ID = 42


def _candidate(url: str, title: str, score: float, topic: str = "") -> dict:
    return {"url": url, "title": title, "topic": topic, "score": score}


class TestFindCommand:
    def test_usage_message_with_no_query(self, monkeypatch: pytest.MonkeyPatch) -> None:
        resp = asyncio.run(commands.SHARED_COMMANDS["/find"].handler(CHAT_ID, ["/find"]))
        assert resp.kind == "command_result"
        assert "usage" in resp.text.lower()

    def test_no_results_below_threshold(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_search(query: str, top_k: int = 10) -> list[dict]:
            return [_candidate("https://example.com/a", "A", 0.3)]

        monkeypatch.setattr("src.brain.search_links", _fake_search)
        resp = asyncio.run(commands.SHARED_COMMANDS["/find"].handler(CHAT_ID, ["/find", "svg"]))
        assert resp.artifacts == []
        assert "nothing found" in resp.text.lower()

    def test_results_ride_artifacts_not_flattened_text(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_search(query: str, top_k: int = 10) -> list[dict]:
            return [
                _candidate("https://example.com/a", "Result A", 0.9, "topic a"),
                _candidate("https://example.com/b", "Result B", 0.7, "topic b"),
            ]

        async def _fake_enrich(links: list[dict]) -> list[dict]:
            return links

        monkeypatch.setattr("src.brain.search_links", _fake_search)
        monkeypatch.setattr("src.services.github.enrich_github_links", _fake_enrich)

        resp = asyncio.run(commands.SHARED_COMMANDS["/find"].handler(CHAT_ID, ["/find", "svg"]))

        assert len(resp.artifacts) == 2
        assert resp.artifacts[0]["url"] == "https://example.com/a"
        assert resp.artifacts[0]["title"] == "Result A"
        # The old Telegram-only threshold (0.58) and cap (5) are preserved.
        assert "2 result" in resp.text

    def test_caps_at_five_and_filters_below_0_58(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_search(query: str, top_k: int = 10) -> list[dict]:
            return [_candidate(f"https://example.com/{i}", f"R{i}", 0.6) for i in range(8)] + [
                _candidate("https://example.com/low", "Low", 0.5),
            ]

        async def _fake_enrich(links: list[dict]) -> list[dict]:
            return links

        monkeypatch.setattr("src.brain.search_links", _fake_search)
        monkeypatch.setattr("src.services.github.enrich_github_links", _fake_enrich)

        resp = asyncio.run(commands.SHARED_COMMANDS["/find"].handler(CHAT_ID, ["/find", "x"]))
        assert len(resp.artifacts) == 5
        assert all(a["url"] != "https://example.com/low" for a in resp.artifacts)

    def test_multi_word_query_is_joined(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: dict[str, str] = {}

        async def _fake_search(query: str, top_k: int = 10) -> list[dict]:
            seen["query"] = query
            return []

        monkeypatch.setattr("src.brain.search_links", _fake_search)
        asyncio.run(commands.SHARED_COMMANDS["/find"].handler(CHAT_ID, ["/find", "react", "hooks"]))
        assert seen["query"] == "react hooks"

    def test_dashboard_reaches_it_through_the_router(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Same entry point the palette advertises actually works end to end."""
        db_file = tmp_path / "find_router_test.db"
        monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
        monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
        monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")

        from src import database
        from src.intake import idempotency, router
        from src.intake.models import IntakeActor, IntakeMessage

        asyncio.run(database.init_db())
        idempotency._memory.clear()

        async def _fake_search(query: str, top_k: int = 10) -> list[dict]:
            return [_candidate("https://example.com/a", "A", 0.9)]

        async def _fake_enrich(links: list[dict]) -> list[dict]:
            return links

        monkeypatch.setattr("src.brain.search_links", _fake_search)
        monkeypatch.setattr("src.services.github.enrich_github_links", _fake_enrich)

        actor = IntakeActor(
            user_id=CHAT_ID, channel_id="dashboard", channel_type="dashboard", legacy_chat_id=CHAT_ID
        )
        resp = asyncio.run(router.handle(IntakeMessage(actor=actor, text="/find svg")))
        assert resp.kind == "command_result"
        assert len(resp.artifacts) == 1
