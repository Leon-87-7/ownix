---
adr: "0051"
title: Automatic bookmark capture rejected — deliberate triggers keep the link-pipeline fallback instead
status: accepted
date: 2026-08-18
---

## Context

A feature request explored automating step 0-1 of intake: the user bookmarks a URL in
the browser, the Chrome extension listens for `chrome.bookmarks.onCreated`, and sends it
straight into Ownix's existing triage (`detect_pipeline()`, `src/utils/validators.py` →
`src/intake/router.py`) with no further action from the user. Three implementation shapes
were compared (direct listener, a scoped "Ownix Inbox" bookmark folder, a buffered queue
via `chrome.alarms`) — all reusing the same `buildIntakePayload()` / `sendToOwnix()` /
`create_and_enqueue_job()` path every existing capture surface already shares.

Separately, a real gap surfaced in that same triage: `detect_pipeline()` returns
`"rejected"` for any URL that doesn't match a specific pipeline (short/long/unsized/repo/
document/article), and `_route()` (`src/intake/router.py:98-120`) only rescues that with
a generic Link job when the caller passed an explicit `intent` of `article`/`link`/
`document`. A bookmark — or the extension's existing `Ctrl+Shift+1` "Capture automatically"
command — sends no such narrower intent, so an ordinary bookmark (a personal blog post, a
recipe, anything outside the specific pipelines) would silently vanish today: no job, no
feedback, nothing. This was validated against a throwaway prototype
(`extension/chrome/prototype-bookmark-triage.html`, a 1:1 JS port of `detect_pipeline()`
plus the fallback) before either change landed here.

Not in scope: [[Bookmark import]] (ADR-0048) — uploading a bookmark-export HTML file is
an explicit, one-time, user-initiated action (the person picks the file and hits upload)
and is unaffected by this decision. This ADR is only about *passively listening* for new
bookmarks as they're created.

## Decision

**Reject automatic bookmark capture in every shape considered.** No `chrome.bookmarks.*`
permission, no `onCreated` listener, no bookmark-folder inbox.

**Keep and upgrade the existing `Ctrl+Shift+1` / "Capture automatically" trigger
instead.** The extension already has a deliberate, per-item, one-keypress capture command
(`captureCommand`, `extension/chrome/src/background.ts`) that goes through the identical
downstream pipeline a bookmark listener would have used. The only real fix needed is the
triage gap above: give it the link-pipeline fallback validated in the prototype.

Implementation: a new `ProcessingIntent` value, `"capture"` (`src/intake/models.py`),
distinct from the contract's existing default, `"automatic"`. `_route()` extends its
existing `"link"`-intent fallback branch to also cover `"capture"` — both already do the
same thing (validate the candidate is a structurally sound `http(s)` URL with a hostname,
then set `pipeline = "link"`), so the two conditions are merged rather than duplicated.
The extension's `capture-automatic` command now sends `intent: "capture"` instead of
`intent: "automatic"` in its `COMMAND_INTENTS` map.

**Deliberately not implemented as `msg.intent == "automatic"`.** `automatic` is the
contract's own default (`IntakeMessage.intent: ProcessingIntent = "automatic"`,
`src/intake/models.py:69`) — it's what every plain Telegram paste and every dashboard
submission already carries when no narrower intent is set. Gating the fallback on it
would have silently widened triage for the Telegram bot and the dashboard too, changing
established behavior (today's "Unsupported URL..." message, which tells the user what
*is* supported) for every channel at once — a materially bigger, unreviewed change than
what was scoped and validated. A distinct `"capture"` intent keeps the blast radius to
exactly the one trigger this decision is about.

## Rationale

`docs/brand/CONSTITUTION.md`'s Second Law: *"Never automate away the actions that create
understanding... The operative question for any new AI feature is never 'can AI automate
this?' It's 'what cognitive value would the user lose if we automated this?'"* Sending
something to Ownix today is a second, deliberate decision layered on top of bookmarking —
"this specific thing is worth cultivating," not just "save for later." An automatic
listener collapses those into one reflexive action and removes exactly the judgment the
Second Law protects; that's not automating friction (retrieval, transcription — which the
Law explicitly permits), it's automating the one piece of cognition it exists to keep
human.

The Purpose statement is more direct still: *"Ownix must not passively build a model of
the user behind the scenes and call that personal context. The person has to participate
in creating it."* A passive bookmark-sync listener is the literal shape that sentence
rules out.

`docs/brand/ICP.md` sharpens the practical failure mode: its own landing-page symptom
copy is *"40 saved links you forgot you saved"* — a browser's bookmarks folder is already
exactly that graveyard for most people. Auto-vacuuming it into Ownix doesn't solve the
hoarding problem the ICP already senses; it relocates the pile into Ownix's own database,
fully enriched and embedded, but still never chosen. The doc's own "automation line" says
it plainly: Ownix kills friction, never *"deciding what applies"* — and a reflexive
bookmark click contains no such decision.

`Ctrl+Shift+1` (and the context-menu / popup captures alongside it) keep the one thing
the brand needs preserved: a human choosing, per item, that this belongs in their
context. Fixing its triage gap gets the practical win the bookmark proposal was chasing
(nothing valid silently vanishes) without giving up that choice.

## Considered options

- **Direct `chrome.bookmarks.onCreated` listener, same capture pipeline.** Reused the most
  code, shipped fastest. Rejected: Chrome fires `onCreated` in bulk for Chrome Sync's
  initial pull on a new profile/device and for browser import, so pairing on a synced
  account could silently fire dozens-to-hundreds of jobs at once — independent of, and in
  addition to, the Second Law problem above.
- **Scoped "Ownix Inbox" bookmark folder.** Turns bookmarking into an intentional,
  folder-scoped act, closer to a deliberate trigger than approach one. Still rejected:
  it's still bookmarking (a browser-native, low-cognition habit) standing in for the
  distinct "send this to Ownix" decision, and still needs the `bookmarks` permission with
  its Chrome Web Store review overhead for a win the fallback fix mostly already captures.
- **Buffered queue via `chrome.alarms`, burst-threshold dropped.** Defends against the
  sync-storm risk of approach one without approach two's setup step. Rejected: most new
  code for a problem approach two avoids by construction, and it delays capture past the
  "star it, watch it land" moment that was the whole pitch — while doing nothing to
  address the underlying Second Law objection, which no batching strategy fixes.
- **Gate the new fallback on `msg.intent == "automatic"` instead of a new `"capture"`
  value.** Smaller diff — no new intent, no extension change beyond the router. Rejected
  per Decision above: `"automatic"` is the universal default, so this would have widened
  triage for Telegram and the dashboard as a side effect of fixing one keyboard shortcut.

## Consequences

- No new `bookmarks` permission is requested in `manifest.json`, and no Chrome Web Store
  review overhead beyond what pairing already required (`extension/chrome/README.md`
  "Chrome Web Store reviewer access").
- `ProcessingIntent` gains a fifth value, `"capture"` (`src/intake/models.py`), carried
  only by the extension's `capture-automatic` command
  (`extension/chrome/src/background.ts`'s `COMMAND_INTENTS`). Telegram and the dashboard
  are untouched — a plain paste with no explicit intent still defaults to `"automatic"`
  and still gets today's `"Unsupported URL..."` message when nothing matches.
- The extension's badge/notification text now derives its human-readable label from the
  command name (`command.replace(/^capture-/, '')`) rather than the wire `intent` value,
  so `Ctrl+Shift+1` still reads "automatic" in notifications even though it now sends
  `intent: "capture"` on the wire — display text and routing intent were previously the
  same string by coincidence, not by design, and diverge here.
- `extension/chrome/prototype-bookmark-triage.html` is retained as historical context
  for the fallback decision, updated to mirror the final `link`/`capture`-only router
  contract rather than being folded into the extension build (it's a throwaway HTML file,
  not wired into `manifest.json`).
- If a genuine cross-device capture need shows up later (bookmark on phone, land in
  Ownix on desktop via sync) — the one benefit of the bookmark approach this ADR doesn't
  address — it should be re-opened as its own decision against this one's reasoning, not
  quietly re-added as a "just in case" listener.
