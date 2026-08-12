# Codex prompt — implement issues #511–#514 (Telegram tagged URL submission)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/adr/0049-canonical-tag-tokens-and-telegram-tagging.md` — the accepted
   token language, cross-surface catalog invariant, Job-tag boundary, pending-state
   behavior, and tagged-force semantics. It supersedes the older punctuation-dropping
   wording and tests.
2. `CONTEXT.md` — especially **Tag token**, **Tagged URL submission**, and
   **`/taglist` command**. These glossary entries are the product contract.
3. `docs/adr/0047-intake-follow-ups-ride-the-action-envelope.md` — unknown-tag
   actions stay out of `chat_state`; do not undo that boundary.
4. `CLAUDE.md` — repository layout, architecture, and the exact test/lint commands.
5. Current tag/intake implementation: `src/intake/tag_tokens.py`,
   `src/intake/router.py`, `src/intake/actions.py`, `src/intake/commands.py`,
   `src/api/controls.py`, and the tag CRUD/attachment functions in
   `src/database.py`.
6. Current Telegram adapter and document intake: `src/telegram/webhook.py` and
   `src/telegram/sender.py`.
7. Existing regression suites: `tests/test_intake_tag_tokens.py`,
   `tests/test_intake_router.py`, `tests/test_intake_actions.py`,
   `tests/test_intake_commands_force.py`, and `tests/test_webhook.py`.
8. GitHub issues #511–#514
   (`gh issue view <n> --repo Leon-87-7/ownix`) — each issue's acceptance criteria
   are the definition of done for that slice.

## Key decisions already made (do not relitigate)

- A token is a whitespace/start-anchored `#` plus one non-whitespace payload.
  `_` encodes spaces; every other non-whitespace character is literal. Thus
  `#read_later` selects **Read Later**, `#readlater` selects **Readlater**, and
  `#c++`, `#r&d`, `#ai/ml`, `#foo#bar`, and `#design_🎨` are valid.
- Matching is case-insensitive. Display-name whitespace runs canonicalize to one
  underscore. A literal underscore in a stored name therefore shares the same
  token as a space and is a collision, not a second spelling.
- Do not add a compatibility fallback to the old punctuation-dropping normalization.
  Existing collisions remain visible and ambiguous until a human renames them;
  new/renamed collisions are rejected at a shared persistence/service boundary.
- URL fragments are preserved because only a whitespace/start-anchored hash begins
  a token. Trailing punctuation is literal: `#c++,` does not select **C++**.
- Tags attach to Jobs and are organizational metadata only. They never create or
  mutate Link tags and never affect routing, prompts, or enrichment.
- Unknown, ambiguous, invalid, or failed tag attachments never block accepted URL
  processing. Attachment is additive, idempotent, and best-effort per token.
- `/tag` and `/taglist` are Telegram-only commands over shared mechanics. Plain
  tagged intake and tagged `/force` retain cross-surface parity.
- Tag-bearing submissions preserve unrelated awaiting freestyle/PRD state. Ordinary
  untagged commands retain their existing state behavior.
- Photo/file-message tagging, Telegram tag creation, usage counts, and interactive
  `/taglist` pagination are out of scope.

## Work order

Implement in issue order. #511 is the foundation; #512 builds on it; #513 is the
Telegram submission path; #514 is independently shippable after #511. Keep every
completed slice testable and working before moving on.

### #511 — canonical token vocabulary and collision safety

- `src/intake/tag_tokens.py:17` currently accepts only `[\w-]+`; punctuation such
  as `+`, `&`, `/`, and emoji is truncated.
- `src/intake/tag_tokens.py:20` currently casefolds and drops every non-alphanumeric
  character, collapsing **Read Later**, **Read_Later**, **Read-Later**, and
  **Readlater** onto one key.
- `src/intake/router.py:119` and `src/intake/actions.py:65` each build their own
  normalized-name dictionary. Both lose duplicate rows by last-write-wins instead
  of reporting ambiguity.
- `src/api/controls.py:25` validates only shape/length; `src/database.py:2172` and
  `:2183` enforce only SQLite's exact-name uniqueness. Alternate creation paths can
  bypass canonical collision safety.

Fix direction: evolve `tag_tokens` into the one codec for parse, decode, encode,
canonical comparison, deduplication, and collision grouping. Put collision rejection
at the shared tag persistence/service boundary, with tenant scope and update-self
exclusion. Existing collisions must remain listable. Extend the structured intake
outcome so unknown, ambiguous, invalid, and internally failed tokens cannot be
mistaken for each other. The unknown-tag action must receive decoded display text
(`Read Later`, not `Read_Later`).

Existing valid dashboard/extension intake, Job-tag CRUD, Link-tag CRUD, URL fragments,
and unknown-tag offers must keep working. Update the existing tag-token/router/action/
controls/database tests rather than creating a parallel test convention.

### #512 — tagged `/force` with document-safe reprocessing

- `src/intake/commands.py:122` owns the shared force behavior.
- `src/intake/commands.py:153` looks up the Markdown cache, and `:175` returns after
  deleting a cache-only row; no Job is created.
- `src/intake/commands.py:186` creates a Job directly from the detected URL. For a
  document URL that stores the remote URL where `processors.document` expects a
  content-addressed source key.
- Telegram's wrapper calls this shared command at `src/telegram/webhook.py:877`, so
  keep orchestration channel-neutral and rendering adapter-specific.
- The established document URL path is `src/telegram/webhook.py:1708` through
  `_enqueue_document_job` at `:2076`; reuse/extract that contract rather than making
  the document processor accept two incompatible source identities.

Fix direction: accept optional tag tokens in the shared force input, resolve them
through #511, and attach them additively after reset/create without deleting existing
Job tags. Carry structured attachment outcomes. A tag-bearing force preserves pending
prompt state; existing untagged force behavior stays unchanged. Cache-only cleanup must
continue to a Job. Refactor document URL storage into an appropriate shared service so
both normal Telegram intake and force use the same safe download/store/enqueue shape.

Existing valid force behavior for videos, articles, repositories, and untagged calls
must keep working. Extend `tests/test_intake_commands_force.py` and the relevant
document/webhook tests for reset/new Jobs, existing tags, cache-only state, document
URLs, pending state, and partial attachment failure.

### #513 — Telegram `/tag` and plain tagged URL intake

- `src/telegram/webhook.py:2116` routes slash commands before pending-state handling,
  and `_dispatch_slash` at `:1132` clears state for every command except `/cancel`.
- Ordinary text falls through `_route_text` to legacy `_route_url` at `:1650`, never
  through `src/intake/router.py`; this is why dashboard tag tokens work while Telegram
  tag tokens do not.
- `_invite_gate_allows` parks supported URLs with
  `create_held_job_unless_recent` at `src/telegram/webhook.py:1483`, currently without
  tag attachment.
- `_HELP_TEXT` and `_SLASH_TABLE` are at `src/telegram/webhook.py:1073` and `:1110`.

Fix direction: add a narrow Telegram adapter over the shared tagged-submission
mechanics; do not migrate the whole webhook as collateral work. Recognize explicit
`/tag` and plain tag-bearing URL messages before an awaiting prompt consumes them.
Require exactly one supported URL and at least one valid token for `/tag`, with URL
and tags allowed in either order and no other prose. Preserve every established
pipeline, including document URL intake, dedup, and held Jobs. Render one safe
acknowledgement with Job ID and separate attached/unknown/ambiguous/invalid/failed
groups. Add `/tag` to help and BotFather guidance.

Existing untagged URL routing, slash commands, prompt replies, template shortcuts,
invite behavior, and Job acknowledgements must keep working. Add webhook tests for
both orderings, plain and explicit forms, malformed grammar, dedup, held Jobs,
pending-state preservation, document URLs, and partial failures.

### #514 — Telegram `/taglist` vocabulary view

- `src/database.py:2157` already returns the caller's tag catalog alphabetically
  with name, meaning, color, and icon. Reuse it; do not create a Telegram catalog.
- `src/telegram/sender.py:130` sends one message and does not automatically chunk
  arbitrary long text.
- An existing UTF-16-aware Telegram splitter lives at
  `src/processors/enrichment.py:425`, but it is processor-private. Extract or mirror
  the established boundary-aware behavior in a shared Telegram utility; do not split
  in the middle of one tag entry or inline-code span.
- `/taglist` must be exempt from `_dispatch_slash`'s current blanket state clearing.

Fix direction: add a no-argument, read-only command that lists the complete private
catalog alphabetically. Unambiguous entries show a safely escaped inline-code
canonical token, display name, and optional meaning. Every member of an existing
canonical collision is marked ambiguous and exposes no copyable token. Omit color,
icon, and usage counts. Split long results into Telegram-safe messages by whole entry;
empty state points to dashboard Controls. Add the command to help and BotFather
guidance while preserving pending prompts.

Existing tag listing, arbitrary punctuation/emoji names, and other Telegram commands
must keep working. Add tests for normal, punctuation-heavy, ambiguous, long, empty,
invalid-argument, safe-formatting, and pending-state cases.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Do not touch unrelated processing, Link-tag behavior, photo/file-message intake, or
  unrelated webhook commands. Do not refactor a file merely because it is open.
- One canonical tag codec and one shared collision rule; do not leave adapter-specific
  normalization tables behind.
- Preserve tenant scope for tag lookup, collision checks, held Jobs, and catalog reads.
- Run `python -m pytest tests -q` and `ruff check src/` from the repo root per
  `CLAUDE.md` — never through the `rtk` hook. Focused tests during development are
  encouraged, but the final validation must include the documented commands.
- Run `git diff --check` before handoff.

## Deliverable

Uncommitted working-tree changes implementing #511–#514, regression tests satisfying
each issue's acceptance criteria, and a short summary of what changed per issue plus
any genuine blocker. Do not commit, push, create a branch, or open a PR.
