# Article Auto-Allowlist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A URL that `detect_pipeline()` rejects, pasted with the default `intent="automatic"` on any channel (Telegram, Discord, dashboard), gets one live content check — if it reads as a real article, its domain is auto-added to the chat's allowlist, the user is told so in the same reply, and the URL is routed to the article pipeline. Otherwise the user sees the same "Unsupported URL" outcome as today.

**Architecture:** Two new small, dependency-free helpers (`is_known_platform_host` in `validators.py`, `looks_like_article` in `jina.py`) feed a single new branch in `src/intake/router.py`'s existing `_route()` rejected-handling. Telegram's two entrypoints that currently bypass the shared router (`_route_url`, `_route_tagged_submission` in `src/telegram/routing.py`) are changed to call `intake_router.handle()` on rejection instead of their own hardcoded messages, so the fix lands once and applies to all three channels. `_reject_url` becomes dead code and is deleted.

**Tech Stack:** Python 3.11, FastAPI/asyncio backend, `httpx` for the Jina fetch, `pytest` + `pytest-asyncio` (run via PowerShell per this repo's convention — pytest under Bash silently hangs, see project memory).

**Spec:** `docs/superpowers/specs/2026-09-21-article-auto-allowlist-design.md`

## Global Constraints

- No new dependency — reuse `src/services/jina.py`'s existing `fetch_markdown`/`fetch_raw` machinery.
- The probe must never raise and never hang the caller: any Jina error, oversize, or timeout resolves to `False` (fail closed to "Unsupported URL").
- The probe only ever runs for `msg.intent == "automatic"` and only for hosts `is_known_platform_host()` returns `False` for.
- `add_allowed_domain` is `INSERT OR IGNORE` (confirmed) — safe to call more than once for the same chat/domain.
- Every existing test that currently asserts `"Unsupported"` text for a rejected URL must keep passing unchanged, or be updated deliberately with a stated reason (never silently).
- Run tests via PowerShell (`python -m pytest ...`), never the Bash tool — see project memory `feedback_pytest_via_powershell`.

---

### Task 1: `is_known_platform_host()` in `src/utils/validators.py`

**Files:**
- Modify: `src/utils/validators.py` (add near `_match_github`, after the `ARTICLE_DEFAULT_DOMAINS`/`_match_article` block, i.e. after line 213 in the current file)
- Test: `tests/test_validators.py`

**Interfaces:**
- Produces: `is_known_platform_host(host: str) -> bool` — `host` is a lowercased hostname (as `urlparse(...).hostname` gives, `www.` stripped by the caller the same way `detect_pipeline` already does). Used by Task 3.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_validators.py`:

```python
@pytest.mark.parametrize(
    "host",
    [
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
        "instagram.com",
        "www.instagram.com",
        "tiktok.com",
        "www.tiktok.com",
        "vt.tiktok.com",
        "facebook.com",
        "x.com",
        "twitter.com",
        "github.com",
        "gist.github.com",
        "enterprise.github.com",
    ],
)
def test_is_known_platform_host_true_for_recognized_platforms(host: str) -> None:
    from src.utils.validators import is_known_platform_host

    assert is_known_platform_host(host) is True


@pytest.mark.parametrize(
    "host",
    [
        "example.com",
        "news.example.com",
        "medium.com",
        "github.blog",
        "some-random-blog.dev",
    ],
)
def test_is_known_platform_host_false_for_unrecognized_hosts(host: str) -> None:
    from src.utils.validators import is_known_platform_host

    assert is_known_platform_host(host) is False
```

Note: `github.blog` must be `False` — it's already a default article domain (`ARTICLE_DEFAULT_DOMAINS`), so a URL on that host is never `"rejected"` in the first place; it's included here to pin that `is_known_platform_host` doesn't over-match on `github.` prefixes.

- [ ] **Step 2: Run tests to verify they fail**

Run (PowerShell): `python -m pytest tests/test_validators.py -k is_known_platform_host -v`
Expected: FAIL with `ImportError: cannot import name 'is_known_platform_host'`

- [ ] **Step 3: Implement `is_known_platform_host`**

In `src/utils/validators.py`, add after `_match_article` (after line 213):

```python
_KNOWN_PLATFORM_HOSTS: frozenset[str] = frozenset(
    {
        "youtube.com",
        "youtu.be",
        "instagram.com",
        "tiktok.com",
        "vt.tiktok.com",
        "facebook.com",
        "x.com",
        "twitter.com",
        "github.com",
        "gist.github.com",
    }
)


def is_known_platform_host(host: str) -> bool:
    """True when *host* belongs to a platform `detect_pipeline` already has
    dedicated handling for — matched or not.

    Used to keep the auto-article-probe fallback (router.py) scoped to hosts
    `detect_pipeline` has no opinion about at all. Without this, a YouTube
    channel page or a GitHub gist — rejected for a URL-*shape* reason, not a
    domain reason — could read as a long article and get wrongly
    auto-allowlisted as an article domain.
    """
    normalized = host.lower().removeprefix("www.")
    if any(_host_matches(normalized, h) for h in _KNOWN_PLATFORM_HOSTS):
        return True
    # Enterprise/subdomain GitHub hosts (matches _match_github's own rule),
    # excluding github.blog which is a legitimate article domain.
    return normalized.startswith("github.") and normalized != "github.blog"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_validators.py -k is_known_platform_host -v`
Expected: PASS (both parametrized tests, all cases)

- [ ] **Step 5: Commit**

```bash
git add src/utils/validators.py tests/test_validators.py
git commit -m "feat(validators): add is_known_platform_host for article-probe scoping"
```

---

### Task 2: `looks_like_article()` in `src/services/jina.py`

**Files:**
- Modify: `src/services/jina.py` (add after `fetch_markdown`, i.e. after the current line 169)
- Test: `tests/test_jina.py`

**Interfaces:**
- Consumes: `fetch_markdown(url, client=...)` (existing, `src/services/jina.py:153`), `JinaFetchError`, `JinaOversizeError` (existing, `src/services/jina.py:32,40`).
- Produces: `looks_like_article(url: str, *, timeout: float = 8.0, client: httpx.AsyncClient | None = None) -> bool` and module constant `MIN_ARTICLE_CHARS = 500`. Used by Task 3.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_jina.py`:

```python
@pytest.mark.asyncio
async def test_looks_like_article_true_for_long_body():
    from src.services import jina

    long_body = "Markdown Content:\n" + ("Real article content. " * 40)
    async with _mock_client(_text_responder(200, long_body)) as client:
        result = await jina.looks_like_article("https://example.com/post", client=client)

    assert result is True


@pytest.mark.asyncio
async def test_looks_like_article_false_for_short_body():
    from src.services import jina

    short_body = "Markdown Content:\nTiny page."
    async with _mock_client(_text_responder(200, short_body)) as client:
        result = await jina.looks_like_article("https://example.com/stub", client=client)

    assert result is False


@pytest.mark.asyncio
async def test_looks_like_article_false_on_non_200():
    from src.services import jina

    async with _mock_client(_text_responder(404, "")) as client:
        result = await jina.looks_like_article("https://example.com/missing", client=client)

    assert result is False


@pytest.mark.asyncio
async def test_looks_like_article_false_on_timeout():
    from src.services import jina

    def _raise_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    async with _mock_client(_raise_timeout) as client:
        result = await jina.looks_like_article("https://example.com/slow", client=client)

    assert result is False


@pytest.mark.asyncio
async def test_looks_like_article_false_on_oversize():
    from src.services import jina

    def _oversize_responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            content=b"x" * (jina._MAX_JINA_BYTES + 1),
            request=request,
        )

    async with _mock_client(_oversize_responder) as client:
        result = await jina.looks_like_article("https://example.com/huge", client=client)

    assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_jina.py -k looks_like_article -v`
Expected: FAIL with `AttributeError: module 'src.services.jina' has no attribute 'looks_like_article'`

- [ ] **Step 3: Implement `looks_like_article`**

In `src/services/jina.py`, add after `fetch_markdown` (after the current line 169):

```python
MIN_ARTICLE_CHARS = 500  # mirrors src/processors/article.py's _PAYWALL_MIN_CHARS


async def looks_like_article(
    url: str, *, timeout: float = 8.0, client: httpx.AsyncClient | None = None
) -> bool:
    """Best-effort "does this read like a real article" probe.

    Used by the intake router's auto-allowlist fallback to decide whether an
    unrecognized URL is worth adding to a chat's article allowlist. Never
    raises: any fetch error, oversize response, or timeout resolves to
    ``False`` so a slow or broken site just falls through to "Unsupported
    URL" instead of hanging the caller.
    """
    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=timeout)
    try:
        _, body = await fetch_markdown(url, client=active_client)
        return len(body.strip()) >= MIN_ARTICLE_CHARS
    except (JinaFetchError, JinaOversizeError, httpx.HTTPError):
        return False
    finally:
        if owns_client:
            await active_client.aclose()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_jina.py -k looks_like_article -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Run the full jina test file to check for regressions**

Run: `python -m pytest tests/test_jina.py -v`
Expected: PASS (every test, old and new)

- [ ] **Step 6: Commit**

```bash
git add src/services/jina.py tests/test_jina.py
git commit -m "feat(jina): add looks_like_article probe for the auto-allowlist fallback"
```

---

### Task 3: Extend the rejected branch in `src/intake/router.py`

**Files:**
- Modify: `src/intake/router.py:57-133` (the `_route` function)
- Test: `tests/test_intake_router.py`

**Interfaces:**
- Consumes: `is_known_platform_host(host: str) -> bool` (Task 1), `looks_like_article(url, *, timeout=8.0, client=None) -> bool` (Task 2), `database.add_allowed_domain(chat_id, domain) -> bool` (existing, `src/db/users.py:185`), `_ARTICLE_HINT` and `_REPO_HINT` (existing string constants, `src/utils/validators.py:73,49-51` — already imported cross-module by `src/telegram/routing.py`, same pattern reused here).
- Produces: no new public symbols — behavior change only. `router.handle()`'s existing signature and `IntakeResponse` shape are unchanged; the `"unsupported"` response's `text` now includes the ported hint copy, and a `"job_created"`/`"job_deduped"` response's `text` is prefixed with an allowlist note when this fallback fired. Both are read by Task 4/5's callers via `resp.text` / `resp.job_id`, already-existing fields.

- [ ] **Step 1: Add an autouse fixture so existing "unsupported" tests stay green**

In `tests/test_intake_router.py`, add near the top (after the existing `_memory_idempotency` fixture, before the `db` fixture):

```python
@pytest.fixture(autouse=True)
def _no_article_probe(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Default every test to a probe that finds nothing article-like.

    Every existing "unsupported" test in this file uses an example.com-style
    host that isn't a known platform, so without this default they'd each
    trigger a real network fetch. Tests that want the auto-allow path
    override the return value explicitly.
    """
    probe = AsyncMock(return_value=False)
    monkeypatch.setattr("src.services.jina.looks_like_article", probe)
    return probe
```

- [ ] **Step 2: Run the existing suite to confirm nothing broke yet**

Run: `python -m pytest tests/test_intake_router.py -v`
Expected: PASS (fixture is a no-op until Task 3's router.py change calls the probe at all — confirms the fixture itself is wired correctly with no import errors)

- [ ] **Step 3: Write the failing tests for the new behavior**

Append to `tests/test_intake_router.py`, inside `class TestUrlIntake` (or as a new `class TestArticleAutoAllowlist` in the same file — match whichever style reads more naturally next to the existing class; either is fine, keep one class per file for this feature):

```python
class TestArticleAutoAllowlist:
    def test_unrecognized_host_probed_and_allowlisted_when_article_like(
        self, db, monkeypatch: pytest.MonkeyPatch, _no_article_probe: AsyncMock
    ) -> None:
        _enqueue_noop(monkeypatch)
        _no_article_probe.return_value = True

        resp = asyncio.run(router.handle(_msg(url="https://news.example.com/a-real-post")))

        assert resp.kind == "job_created"
        _no_article_probe.assert_awaited_once_with("https://news.example.com/a-real-post")
        assert asyncio.run(db.list_allowed_domains(CHAT_ID)) == {"news.example.com"}
        job = asyncio.run(db.get_job(resp.job_id))
        assert job["content_type"] == "article"
        assert "Added news.example.com to your article allowlist" in resp.text

    def test_unrecognized_host_stays_unsupported_when_probe_says_no(
        self, db, monkeypatch: pytest.MonkeyPatch, _no_article_probe: AsyncMock
    ) -> None:
        _enqueue_noop(monkeypatch)
        # _no_article_probe already defaults to False

        resp = asyncio.run(router.handle(_msg(url="https://news.example.com/not-an-article")))

        assert resp.kind == "unsupported"
        assert asyncio.run(db.list_allowed_domains(CHAT_ID)) == set()
        assert "Unsupported URL" in resp.text

    def test_known_platform_host_never_probed(
        self, db, monkeypatch: pytest.MonkeyPatch, _no_article_probe: AsyncMock
    ) -> None:
        _enqueue_noop(monkeypatch)
        # A GitHub gist: rejected for a URL-shape reason, not a domain reason.
        resp = asyncio.run(router.handle(_msg(url="https://gist.github.com/someone/abc123")))

        assert resp.kind == "unsupported"
        _no_article_probe.assert_not_awaited()
        assert asyncio.run(db.list_allowed_domains(CHAT_ID)) == set()

    def test_non_automatic_intent_never_probed(
        self, db, monkeypatch: pytest.MonkeyPatch, _no_article_probe: AsyncMock
    ) -> None:
        _enqueue_noop(monkeypatch)
        # intent="link" already has its own fallback (router.py:106) — the
        # probe must not fire and steal it.
        resp = asyncio.run(
            router.handle(_msg(url="https://news.example.com/thing", intent="link"))
        )

        assert resp.kind == "job_created"
        _no_article_probe.assert_not_awaited()
        job = asyncio.run(db.get_job(resp.job_id))
        assert job["content_type"] == "link"
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python -m pytest tests/test_intake_router.py -k TestArticleAutoAllowlist -v`
Expected: FAIL — `test_unrecognized_host_probed_and_allowlisted_when_article_like` gets `resp.kind == "unsupported"` instead of `"job_created"`; `test_known_platform_host_never_probed` currently passes already (no probe exists yet to call) but re-verify after Step 6 that it's for the right reason.

- [ ] **Step 5: Implement the router.py change**

In `src/intake/router.py`, update the imports (top of file, currently lines 14-25):

```python
from __future__ import annotations

from urllib.parse import urlparse

from src import database
from src.intake import commands, idempotency, responses, tag_tokens
from src.intake.models import SCHEMA_VERSION, IntakeAction, IntakeMessage, IntakeResponse
from src.services import jina
from src.services.jobs import create_and_enqueue_job
from src.utils.logger import get_logger
from src.utils.validators import (
    _ARTICLE_HINT,
    _REPO_HINT,
    detect_pipeline,
    is_known_platform_host,
    normalize_repo_url,
)

log = get_logger(__name__)
```

Replace the pipeline-dispatch block (currently lines 95-133) with:

```python
    pipeline = detect_pipeline(candidate, frozenset(await database.list_allowed_domains(chat_id)))
    auto_allowed_host: str | None = None
    if pipeline == "document":
        return await _create_remote_document(chat_id, candidate)
    if pipeline == "rejected" and msg.intent == "article":
        parsed_candidate = urlparse(candidate)
        hostname = (parsed_candidate.hostname or "").lower()
        if parsed_candidate.scheme not in {"http", "https"} or not hostname:
            return responses.unsupported("Article capture needs a valid HTTP(S) URL.")
        # Consent is deliberately durable even when job creation/enqueue fails.
        await database.add_allowed_domain(chat_id, hostname)
        pipeline = "article"
    elif pipeline == "rejected" and msg.intent in ("link", "capture"):
        # "capture" (ADR-0051) is the Chrome extension's deliberate one-shot
        # trigger (Ctrl+Shift+1 etc.) — same fallback as an explicit "link"
        # intent, so nothing valid the user chose to send silently vanishes.
        # Deliberately not gated on the contract's default "automatic" intent,
        # which every plain Telegram/dashboard paste also carries — that would
        # have widened this fallback to every channel, not just this trigger.
        parsed_candidate = urlparse(candidate)
        if (
            parsed_candidate.scheme not in {"http", "https"}
            or not parsed_candidate.hostname
        ):
            return responses.unsupported("Link capture needs a valid HTTP(S) URL.")
        pipeline = "link"
    elif pipeline == "rejected" and msg.intent == "document":
        return await _create_remote_document(chat_id, candidate, require_document_path=False)
    elif pipeline == "rejected" and msg.intent == "automatic":
        parsed_candidate = urlparse(candidate)
        hostname = (parsed_candidate.hostname or "").lower()
        if (
            parsed_candidate.scheme in {"http", "https"}
            and hostname
            and not is_known_platform_host(hostname)
            and await jina.looks_like_article(candidate)
        ):
            await database.add_allowed_domain(chat_id, hostname)
            pipeline = "article"
            auto_allowed_host = hostname
        if pipeline == "rejected":
            github_hint = (
                f"\n{_REPO_HINT}"
                if hostname == "github.com" or hostname.endswith(".github.com")
                else ""
            )
            return responses.unsupported(
                "Unsupported URL. Ownix accepts YouTube/Shorts, Reels, TikTok, "
                "Facebook/X video, allowlisted article domains, and GitHub repos.\n"
                + _ARTICLE_HINT
                + github_hint
            )

    url_for_job = normalize_repo_url(candidate) if pipeline == "repo" else candidate
    job = await create_and_enqueue_job(chat_id, url_for_job, pipeline)
    result = responses.job_created(job, deduped=bool(job.get("_deduped")))
    if auto_allowed_host:
        result = result.model_copy(
            update={
                "text": f"Added {auto_allowed_host} to your article allowlist. {result.text}"
            }
        )
    if tag_names:
        result = await apply_tag_tokens(chat_id, job["id"], tag_names, result)
    return result
```

Note: the original code had a trailing bare `elif pipeline == "rejected":`
catch-all after the four named-intent branches — that's now unreachable and
removed. `ProcessingIntent` (`src/intake/models.py:26`) is a closed
`Literal["automatic", "article", "link", "document", "capture"]`; the
`"article"`, `"link"`/`"capture"`, `"document"`, and now `"automatic"`
branches together already cover every possible value, so nothing could ever
reach a fifth catch-all. The one remaining `pipeline == "rejected"` reply
site (inside the `"automatic"` branch, on a probe miss) is written inline
rather than factored into a helper — with a single call site, a function
would just be indirection. It reuses the `hostname` already computed a few
lines above for the probe check, and carries Telegram's richer hint copy
(`_ARTICLE_HINT`, conditional `_REPO_HINT`) so Discord and the dashboard
gain it too.

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_intake_router.py -v`
Expected: PASS — every existing test (protected by the Step 1 fixture) plus all four new `TestArticleAutoAllowlist` tests.

- [ ] **Step 7: Commit**

```bash
git add src/intake/router.py tests/test_intake_router.py
git commit -m "feat(intake): auto-allowlist and route article-like rejected URLs"
```

---

### Task 4: Migrate `_route_url`'s rejected branch onto `intake_router.handle()`

**Files:**
- Modify: `src/telegram/routing.py:40-46` (imports), `:513-527` (delete `_reject_url`), `:593-613` (`_route_url`)
- Test: `tests/test_webhook.py`

**Interfaces:**
- Consumes: `router.handle(IntakeMessage) -> IntakeResponse` (existing, `src/intake/router.py:35`; already imported elsewhere in this file as `from src.intake.router import apply_tag_tokens` inside `_route_tagged_submission` — this task adds a module-level import instead), `IntakeActor`, `IntakeMessage` (existing, `src/intake/models.py`).
- Produces: no new public symbols. `_route_url`'s external behavior on the rejected path changes from always "Unsupported URL" to the Task 3 fallback; every other branch of `_route_url` is untouched.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_webhook.py` (near `test_webhook_rejects_unsupported_url`, ~line 195):

```python
async def test_webhook_auto_allowlists_article_like_rejected_url(client, monkeypatch) -> None:
    c, fake_redis, fake_http = client
    monkeypatch.setattr(
        "src.services.jina.looks_like_article", AsyncMock(return_value=True)
    )

    response = c.post(
        "/webhook",
        json=_telegram_update("https://news.example.com/a-real-post"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )

    assert response.status_code == 200
    queued = fake_redis._lists.get("video_jobs", [])
    assert len(queued) == 1
    sent = fake_http.calls[0]["json"]["text"]
    assert "Added news.example.com to your article allowlist" in sent
    assert await database.list_allowed_domains(12345) == {"news.example.com"}


async def test_webhook_still_unsupported_when_probe_says_no(client, monkeypatch) -> None:
    c, fake_redis, fake_http = client
    monkeypatch.setattr(
        "src.services.jina.looks_like_article", AsyncMock(return_value=False)
    )

    response = c.post(
        "/webhook",
        json=_telegram_update("https://news.example.com/stub"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )

    assert response.status_code == 200
    assert fake_redis._lists.get("video_jobs", []) == []
    assert "Unsupported" in fake_http.calls[0]["json"]["text"]
    assert await database.list_allowed_domains(12345) == set()
```

Add `from unittest.mock import AsyncMock` to `tests/test_webhook.py`'s imports if not already present (check the existing import block first — `test_pending_user_unsupported_url_still_gets_the_url_error` already uses `AsyncMock`, so it should already be imported).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_webhook.py -k "auto_allowlists or still_unsupported_when_probe" -v`
Expected: FAIL — `test_webhook_auto_allowlists_article_like_rejected_url` gets `"Unsupported"` in the reply instead of the allowlist note (the mock is set but `_route_url` never calls into anything that uses it yet).

- [ ] **Step 3: Update imports in routing.py**

In `src/telegram/routing.py`, replace the import block at lines 40-46:

```python
from src.utils.validators import (
    detect_pipeline,
    normalize_email,
    normalize_repo_url,
)
```

(`_ARTICLE_HINT` and `_REPO_HINT` are removed — their only use was inside `_reject_url`, which Step 4 deletes; they're now used from `src/intake/router.py` instead, per Task 3.)

Add a new import near the other `src.intake` usage (this file already does `from src.intake.router import apply_tag_tokens` *inside* `_route_tagged_submission` — add a module-level equivalent instead, next to the `from src import database, job_queue as queue` line at the top):

```python
from src.intake import router as intake_router
from src.intake.models import IntakeActor, IntakeMessage
```

- [ ] **Step 4: Delete `_reject_url`**

Remove the entire function at `src/telegram/routing.py:513-527`:

```python
async def _reject_url(chat_id: int, text: str) -> None:
    try:
        _host = (urlparse(text).hostname or "").lower().removeprefix("www.")
    except Exception:
        _host = ""
    _github_hint = (
        f"\n{_REPO_HINT}" if _host == "github.com" or _host.endswith(".github.com") else ""
    )
    await sender.send_message(
        chat_id,
        "❌ Unsupported URL. I accept YouTube videos, YouTube Shorts, "
        "Instagram Reels (not /p/ carousels), TikTok videos, Facebook videos, "
        "and X/Twitter videos.\n" + _ARTICLE_HINT + _github_hint,
    )
    log.info("url_rejected", chat_id=chat_id, url=text)
```

- [ ] **Step 5: Rewrite `_route_url`'s rejected branch**

In `src/telegram/routing.py:593-613`, replace:

```python
async def _route_url(chat_id: int, text: str, message_id: int | None) -> None:
    client = queue._client()
    pending_template: str | None = await client.get(f"pending_template:{chat_id}")
    if pending_template:
        await client.delete(f"pending_template:{chat_id}")

    extra_domains = await database.list_allowed_domains(chat_id)
    pipeline = detect_pipeline(text, frozenset(extra_domains))
    if pipeline == "rejected":
        await _reject_url(chat_id, text)
        return
    if pipeline == "document":
        await _route_document_url(chat_id, text, message_id)
        return
    if pipeline == "article":
        await _route_article(chat_id, text, message_id, pending_template)
        return
    if pipeline == "repo":
        await _route_repo(chat_id, text, message_id, pending_template, client)
        return
    await _route_video(chat_id, text, pipeline, message_id, pending_template)
```

with:

```python
async def _route_url(chat_id: int, text: str, message_id: int | None) -> None:
    client = queue._client()
    pending_template: str | None = await client.get(f"pending_template:{chat_id}")
    if pending_template:
        await client.delete(f"pending_template:{chat_id}")

    extra_domains = await database.list_allowed_domains(chat_id)
    pipeline = detect_pipeline(text, frozenset(extra_domains))
    if pipeline == "rejected":
        await _route_rejected_url(chat_id, text, message_id)
        return
    if pipeline == "document":
        await _route_document_url(chat_id, text, message_id)
        return
    if pipeline == "article":
        await _route_article(chat_id, text, message_id, pending_template)
        return
    if pipeline == "repo":
        await _route_repo(chat_id, text, message_id, pending_template, client)
        return
    await _route_video(chat_id, text, pipeline, message_id, pending_template)


async def _route_rejected_url(chat_id: int, text: str, message_id: int | None) -> None:
    """A URL `detect_pipeline` rejected: give the shared intake router (and its
    article-auto-allowlist fallback) the one chance `_reject_url` never gave it.

    Any pending_template was already popped and discarded above in
    `_route_url`, unchanged from before this fallback existed — there is no
    resolved pipeline yet on a rejected URL for a template to apply to.
    """
    actor = IntakeActor(
        user_id=chat_id, channel_id=str(chat_id), channel_type="telegram", legacy_chat_id=chat_id
    )
    resp = await intake_router.handle(
        IntakeMessage(actor=actor, url=text, source_message_id=message_id)
    )
    await sender.send_message(chat_id, resp.text)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_webhook.py -v`
Expected: PASS — every existing test in the file (`test_webhook_rejects_unsupported_url` and `test_template_pending_not_applied_to_rejected_url` both use `instagram.com/p/...`, a known-platform host per Task 1, so the probe never fires and their asserted `"Unsupported"` text is unchanged) plus the two new tests from Step 1.

- [ ] **Step 7: Run ruff to catch the now-unused imports**

Run: `ruff check src/telegram/routing.py`
Expected: no unused-import warnings for `_ARTICLE_HINT`/`_REPO_HINT` (removed in Step 3) or `urlparse` (still used elsewhere in the file by `_safe_get_pdf` — verify it's still imported; it is, at line 17, untouched by this task).

- [ ] **Step 8: Commit**

```bash
git add src/telegram/routing.py tests/test_webhook.py
git commit -m "refactor(telegram): route rejected URLs through the shared intake router"
```

---

### Task 5: Remove `_route_tagged_submission`'s early rejection

**Files:**
- Modify: `src/telegram/routing.py:823-854`
- Test: `tests/test_webhook.py`

**Interfaces:**
- Consumes: nothing new — `_route_tagged_submission` already imports `router as intake_router` and `IntakeActor`/`IntakeMessage` locally (`from src.intake import router as intake_router, tag_tokens` and `from src.intake.models import IntakeActor, IntakeMessage`, lines 827-828); Task 4's module-level `intake_router`/`IntakeActor`/`IntakeMessage` imports make these local ones redundant.
- Produces: no new symbols — a rejected `#tag` submission now falls through to the same `intake_router.handle()` call this function already makes for every other pipeline outcome.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_webhook.py`, near the other tag tests (~line 2300):

```python
@pytest.mark.asyncio
async def test_tagged_rejected_url_gets_auto_allowlist_fallback(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """A #tag alongside an article-like unknown-domain URL is no longer a dead end."""
    from src import database as db

    await db.create_tag(chat_id=100, name="Read Later", meaning="", color="#8b5cf6")
    monkeypatch.setattr(
        "src.services.jina.looks_like_article", AsyncMock(return_value=True)
    )
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.sender.send_message", sent)
    monkeypatch.setattr("src.job_queue.enqueue", AsyncMock())

    url = "https://news.example.com/tagged-post"
    await _post_webhook(f"{url} #read_later")

    job = await db.find_recent_job_by_url(100, url)
    assert job is not None
    assert job["content_type"] == "article"
    sent.assert_awaited_once()
    assert "Added news.example.com to your article allowlist" in sent.await_args.args[1]
    assert await db.list_allowed_domains(100) == {"news.example.com"}
```

Matches the exact grammar and fixture pattern of the neighboring
`test_plain_url_with_hashtag_attaches_tag` (`tests/test_webhook.py:2228-2244`,
same file, same section): create the tag first via `db.create_tag`, paste
`f"{url} #read_later"` (space-separated, url first, tag second, underscored
name), assert via `db.find_recent_job_by_url`. `_post_webhook`'s default
`chat_id=100` (confirmed at `tests/test_webhook.py:446`) matches the
`chat_id` used in this test's assertions.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_webhook.py -k tagged_rejected_url -v`
Expected: FAIL — reply is `"❌ Unsupported URL."` instead of carrying the allowlist note.

- [ ] **Step 3: Remove the early rejection**

In `src/telegram/routing.py`, inside `_route_tagged_submission` (currently lines 836-839):

```python
    pipeline = detect_pipeline(parts[0], frozenset(await database.list_allowed_domains(chat_id)))
    if pipeline == "rejected":
        await sender.send_message(chat_id, "❌ Unsupported URL.")
        return
    if pipeline == "document":
```

becomes:

```python
    pipeline = detect_pipeline(parts[0], frozenset(await database.list_allowed_domains(chat_id)))
    if pipeline == "document":
```

(The `pipeline` variable is still needed for the `document` check immediately below, so it stays computed — only the `rejected` early-return is deleted.)

- [ ] **Step 3b: Deduplicate the now-redundant local imports**

Task 4 added module-level `from src.intake import router as intake_router`
and `from src.intake.models import IntakeActor, IntakeMessage` to this file.
`_route_tagged_submission`'s existing local imports partially duplicate
those. In `src/telegram/routing.py`, inside `_route_tagged_submission`,
replace:

```python
    from src.intake import router as intake_router, tag_tokens
    from src.intake.models import IntakeActor, IntakeMessage
```

with:

```python
    from src.intake import tag_tokens
```

(`tag_tokens` isn't imported at module level, so it stays a local import;
`intake_router`, `IntakeActor`, and `IntakeMessage` are now module-level from
Task 4, so re-importing them locally would just be dead weight.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_webhook.py -v`
Expected: PASS — full file, including the new tagged test and every pre-existing one (no test in this file asserted the literal `"❌ Unsupported URL."` tagged-rejection string — confirmed by grep before writing this plan).

- [ ] **Step 5: Commit**

```bash
git add src/telegram/routing.py tests/test_webhook.py
git commit -m "refactor(telegram): let tagged rejected URLs reach the intake auto-allowlist fallback"
```

---

### Task 6: Full regression pass

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend suite**

Run (PowerShell, per project convention — never Bash): `python -m pytest tests -q`
Expected: PASS, 0 failures. If anything outside the files touched above fails, stop and investigate before continuing — it means a test elsewhere asserted on `_reject_url`, the old tagged-rejection string, or a probe call the earlier tasks didn't anticipate.

- [ ] **Step 2: Run ruff across the full src tree**

Run: `ruff check src/`
Expected: no new warnings (line-length 100, py311 per repo convention).

- [ ] **Step 3: Confirm no remaining references to deleted/removed symbols**

Run: `python -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in pathlib.Path('src').rglob('*.py')]"`
(Cheap syntax-validity sweep — the earlier `ruff check` already covers unused-import detection for `_reject_url`'s removed imports; this step is a fast sanity net, not a substitute.)

Expected: no output, no exception (every file still parses).

- [ ] **Step 4: Commit if anything was fixed in Steps 1-3**

Only if a fix was needed:

```bash
git add -A
git commit -m "fix: address regressions found in full-suite verification pass"
```

If nothing needed fixing, no commit — Task 6 is a verification gate, not a deliverable.
