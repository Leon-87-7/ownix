# Article auto-allowlist on unrecognized URLs

## Problem

Pasting an article/blog URL whose domain isn't already allowlisted currently
dead-ends: `detect_pipeline()` returns `"rejected"`, and the user must run
`/allowlist <domain>` separately, then resend the same URL. Two steps to do
one thing.

`src/intake/router.py`'s `_route()` already has a live auto-allow branch
(`pipeline == "rejected" and msg.intent == "article"`), but nothing ever sets
`intent="article"` from a plain paste — every channel's default is
`"automatic"`. Separately, Telegram's actual plain-paste entrypoint,
`_route_url()` in `src/telegram/routing.py`, doesn't even go through
`router.py` — it calls `detect_pipeline()` directly and replies via a
Telegram-only `_reject_url()`. `_route_tagged_submission()` (the `#tag` path)
has the same kind of short-circuit.

## Goal

A rejected URL, on any channel's default (`intent="automatic"`) plain paste,
gets one shot at a live content check: if it reads as a real article, the
domain is auto-added to the chat's allowlist, the user is told so, and the
URL is routed to the article pipeline in the same turn. If not, the user
sees the same "Unsupported URL" outcome as today. No new ML model — this
reuses the same fetch-and-check shape `article.py`'s existing paywall gate
already does.

## Non-goals

- Not migrating `_route_url`'s resolved-pipeline branches (article/repo/video
  happy paths) onto `router.py`. Those thread `pending_template`, a
  Telegram-only Redis flag with no place in the channel-neutral
  `IntakeMessage` contract (whose own docstring forbids branching on
  channel-private state for core decisions). The reject branch already
  discards `pending_template` unconditionally before `detect_pipeline` even
  runs (routing.py:594-598), so there's nothing to preserve there — this is
  the one branch that's safe to unify without touching the contract.
- Not touching the Chrome extension's `capture`/`link` intent fallback
  (router.py:106-119) — out of scope, untouched.
- Not adding a local/cloud classifier model (Laya/JEV). The existing Jina
  fetch + minimum-content-length check already answers "does this look like
  an article" — evaluated and rejected as unnecessary complexity for what
  the codebase already does.

## Components

### 1. `src/utils/validators.py` — `is_known_platform_host(host: str) -> bool`

New public helper. Returns `True` when `host` belongs to a platform
`detect_pipeline` already has dedicated handling for, matched or not —
YouTube/youtu.be, Instagram, TikTok/vt.tiktok.com, Facebook/X/Twitter,
github.com/gist.github.com/enterprise github hosts. Mirrors the exact host
sets `_match_short`/`_match_long`/`_match_github`/`_UNSIZED_VIDEO_HOSTS`
already use.

Purpose: keeps the new auto-probe scoped to hosts `detect_pipeline` has *no*
opinion about. Without this, a YouTube channel page or a GitHub gist —
rejected for a URL-shape reason, not a domain reason — could render >500
chars of Jina markdown and get wrongly auto-allowlisted as an "article
domain," creating a confusing dual-behavior host (sometimes video/repo,
sometimes article) depending on which URL shape was pasted.

### 2. `src/services/jina.py` — `looks_like_article(url: str, *, timeout: float = 8.0) -> bool`

New function. Fetches via `fetch_markdown` using a client built with the
given timeout; returns `True` if the body is ≥500 chars (`MIN_ARTICLE_CHARS`,
a new module constant — mirrors `article.py`'s private `_PAYWALL_MIN_CHARS`;
not unified into one shared constant, two files owning the same literal is
cheaper than the coupling). Returns `False` — never raises — on
`JinaFetchError`, `JinaOversizeError`, `httpx.TimeoutException`, or any
`httpx` transport error. Fails closed: a slow or broken site just falls
through to "Unsupported URL," never hangs the caller.

### 3. `src/intake/router.py` — extend the `elif pipeline == "rejected":` branch

```python
elif pipeline == "rejected":
    auto_allowed_host: str | None = None
    if msg.intent == "automatic":
        parsed_candidate = urlparse(candidate)
        hostname = (parsed_candidate.hostname or "").lower()
        if (
            parsed_candidate.scheme in {"http", "https"}
            and hostname
            and not is_known_platform_host(hostname)
            and await looks_like_article(candidate)
        ):
            await database.add_allowed_domain(chat_id, hostname)
            pipeline = "article"
            auto_allowed_host = hostname
    if pipeline == "rejected":
        return responses.unsupported(...)  # message text ported from _reject_url, see Component 4
```

Falls through into the existing job-creation code below (same as the
`intent == "article"` branch already does). After `responses.job_created(...)`
is built, if `auto_allowed_host` is set, prepend a note — mirrors the
pattern `apply_tag_tokens` already uses (`result.model_copy(update=...)`):

> "Added {auto_allowed_host} to your article allowlist. " + existing job-created text

This is the **always-inform** requirement — today's `intent == "article"`
branch doesn't message this at all; this is new behavior for both paths,
sharing the same code.

### 4. `src/intake/router.py` — port Telegram's richer unsupported-URL copy

`_reject_url`'s current message (GitHub-repo hint when the host looks like a
GitHub variant, plus the "try /allowlist" article hint) is richer than
`router.py`'s generic unsupported text. Port both conditional hints into
`responses.unsupported()`'s call site in `router.py` so Discord and the
dashboard gain the same guidance Telegram users get today, instead of losing
it in the migration.

### 5. `src/telegram/routing.py` — `_route_url`

Replace:
```python
if pipeline == "rejected":
    await _reject_url(chat_id, text)
    return
```
with constructing an `IntakeMessage` (`actor.channel_type="telegram"`,
`intent="automatic"`, `text=text`, `source_message_id=message_id`) and
calling `intake_router.handle()`, then rendering the response exactly as
`_route_tagged_submission` already does: `resp.job_id` set → an ack message
built the same way `_enqueue_simple_job` acks today (`📥 Received!\njob_XXXX`,
or the deduped-cached-job message); else → `sender.send_message(chat_id, resp.text)`.

`_reject_url` becomes unreachable (its one caller, confirmed via
`codegraph_callers`) — delete it.

### 6. `src/telegram/routing.py` — `_route_tagged_submission`

Delete the early-out:
```python
if pipeline == "rejected":
    await sender.send_message(chat_id, "❌ Unsupported URL.")
    return
```
It already falls through to `intake_router.handle()` for every other
pipeline outcome; removing this lets the same fallback apply here for free.

## Data flow (rejected → auto-allowed case)

```
Telegram plain paste (or dashboard / Discord)
  → _route_url / router.py._route (intent="automatic")
  → detect_pipeline() → "rejected"
  → is_known_platform_host(host)? no
  → looks_like_article(url) → Jina fetch (≤8s) → body ≥500 chars? yes
  → database.add_allowed_domain(chat_id, host)
  → pipeline = "article"
  → create_and_enqueue_job(...)
  → responses.job_created(...), text prefixed with the auto-allow note
  → channel adapter renders it (Telegram: sender.send_message; Discord/dashboard: existing rendering)
```

## Error handling

- Malformed/non-http(s) candidate: unchanged, still short-circuits to
  `responses.unsupported()` before any fetch (existing guard at the top of
  the `intent == "article"` branch, reused).
- Jina fetch failure/timeout/oversize: `looks_like_article` returns `False`,
  falls through to today's unsupported message. No exception ever escapes
  the probe.
- `add_allowed_domain` is `INSERT OR IGNORE` (confirmed) — safe if this path
  is hit twice for the same chat/domain (e.g. a duplicate webhook delivery).
- Known open question, not blocking: no per-chat rate limit was found
  wrapping the plain-message path before this reject fallback, so every
  rejected garbage URL a user pastes now costs one bounded Jina call instead
  of zero. Flagged for the user to decide whether to add one; not addressed
  in this change.

## Testing

- `looks_like_article`: returns `True` on a long-body fetch, `False` on
  `JinaFetchError`, `JinaOversizeError`, and a short body.
- `is_known_platform_host`: true/false table across the platform host list
  and a handful of genuine unknown hosts.
- `router.py._route`: rejected + `intent="automatic"` + unknown host →
  probe called; probe `True` → domain added, job created, text carries the
  note; probe `False` → unchanged unsupported response; known-platform host
  → probe never called (mock asserts no call).
- `_route_url`: rejected path now delegates to `intake_router.handle` — one
  test asserting the call and response rendering, replacing whatever covered
  `_reject_url` today.
- `_route_tagged_submission`: rejected tagged URL now reaches
  `intake_router.handle` instead of the hardcoded message.
