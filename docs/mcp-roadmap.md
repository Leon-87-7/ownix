# Ownix MCP Roadmap

Ownix as an MCP server: exposes the user's indexed content ("the brain") to AI agents. User-initiated only — no background or autonomous execution. Nothing runs unless the user opens a session and asks for it.

Four planned functions: **Gardener** (cleanup), **Connection-finding**, **Scouting**, **Space curation**. They are not parallel workstreams — later phases are gated on things earlier ones haven't yet produced, so treat this as sequential, not a fixed track plan. The first three operate on the Brain (Links); Space curation is the first phase over a different object (Spaces, the named collections built on top of the Brain).

---

## Phase 1 — Gardener (MVP)

**Goal:** flag dead/broken/not-worth-keeping **Brain links** (not Jobs — a Job is a work record, not something a user "gardens") for the user to review and act on. Suggest-only — the agent never deletes without explicit per-batch or per-item user approval.

**MCP tools needed:**
- `list_items` — paginated, with metadata
- `get_item_detail` — full content/metadata for one item
- a confirm-gated delete tool, only callable after user approval — calls the existing `delete_link` primitive as-is (hard delete, no new soft-delete tier — see ADR-0062)

No separate `flag_item` tool. Flagging is the agent narrating its reasoning in conversation, not a tool call — nothing about a flag needs to survive past the turn where the user approves or rejects it (grilled 2026-09-14).

**Session flow:**
1. User: "garden my saved links"
2. Agent pulls items via `list_items`
3. Classifies each as dead / broken / not worth keeping, checking URL status live in-session (no cron, no persisted health column — matches the "no background execution" principle above)
4. Proposes a batch to the user in conversation, each with its reasoning stated, not just a bare verdict
5. User approves/rejects per item or in bulk
6. Approved items are deleted (permanently — see Decisions below) via the confirm-gated tool

**UX requirements (brand-lens pass, 2026-09-14):**
- The agent's reasoning is shown at approval time, not just a verdict — a flag without its reasoning is a black box the user rubber-stamps instead of evaluates.
- Copy never frames flagged items as "garbage" or "junk" — use "not worth keeping." The verdict is about the item's utility, not a judgment on the user for having saved it.
- Dead/broken are mechanical calls (live URL status) — safe to auto-flag confidently. "Not worth keeping" is a judgment call about relevance, not a status check — it should read as a question the user is settling, not a verdict already reached.

**Decisions (grilled 2026-09-14, see `CONTEXT.md` → Gardener, ADR-0062):**
- **Scope: links only**, not Jobs.
- **Delete is hard, via the existing `delete_link` endpoint** — no new soft-delete/archive column, no undo window. The codebase already rejected a trash tier for this exact shape of endpoint (ADR-0042); the safeguard here is the approval step + shown reasoning, not a recovery path after the fact.
- **"Duplicate" is dropped from Phase 1's classifier.** `links` already has a unique `(chat_id, url)` index, so no literal same-URL duplicate can exist — a real duplicate flag means near-duplicate/similar content, which needs embedding-similarity infra. That's Phase 2's `find_related`, not Phase 1.

**Known limitation — deletions are permanent, including for Phase 3:** once a link is Gardener-deleted, its content, embedding, and Drive copy are gone — a future Phase 3 "scout the brain" session can never resurface it, even if it would have been genuinely useful in a context nobody could predict at delete time. This is a real tradeoff, not an oversight: building retention infrastructure now to hedge against an unscoped future phase would violate this roadmap's own sequencing discipline (below). If real Phase 1/3 usage later shows this is a recurring regret, revisit then — hard-delete-today is not a one-way door; a retention window can be added later without rearchitecting.

**Success metric / exit criteria for this phase:** what fraction of the agent's flags does the user actually agree with? Target ~80%+ agreement before considering Phase 1 validated and moving on. Below that, the classifier/prompt needs iteration — don't expand scope on a weak foundation.

---

## Phase 2 — Connection-finding

**Status: shipped (2026-09-17).** The infra blocker below turned out to already be resolved — `src/brain.py` already carries Gemini embeddings + cosine similarity, used since Phase 1 to compute each link's top-3 related items at ingest time (the Obsidian `.md` "Related" section) and for `/find` semantic search. No new similarity layer was needed.

**Infra check (resolved):** confirming whether the current index supports embeddings/vector similarity, or only structured metadata search — it supports embeddings/vector similarity.

**MCP tool:** `find_related(link_id)` in `src/mcp_server.py`, backed by `brain.find_related_links()` — same owner-scoping as Phase 1's `get_item_detail`, returns up to 3 nearest neighbors gated by `settings.BRAIN_MIN_SCORE`; agent narrates why they're related from the returned `{id, url, title, topic, score}` data, no reasoning baked into the tool itself.

**Risk to design against:** raw embedding similarity often produces shallow connections (same domain, same tags) rather than genuinely useful ones. Define upfront what counts as a good connection vs. noise — otherwise this looks impressive in a demo and gets ignored in daily use.

**UX requirement:** the agent narrates *why* two items connect rather than just asserting the pairing — same principle as Phase 1's reason field. Deciding a connection is actually relevant to the current project stays the user's call.

---

## Phase 3 — Scouting: brain-as-source for current work

**Status: shipped (2026-09-18).** Scoped ahead of the usage-data gate this roadmap originally set (see Sequencing note) at explicit user request, not because Phase 1/2 usage data materialized.

**MCP tools:** `scout(query, top_k=5)` in `src/mcp_server.py`, backed by `brain.search_links_scoped()` — owner-scoped semantic search over the caller's own links, reusing `/find`'s tuned `0.58` relevance bar (`_SCOUT_MIN_SCORE`) instead of the looser `BRAIN_MIN_SCORE` to keep noise down. `get_scout_settings()` returns the caller's autonomy toggle so the agent knows whether it may search unprompted.

**Autonomy toggle:** off by default, opt-in via the dashboard Controls page ("MCP clients" section, alongside the existing pairing/token UI → `ScoutSettingsPanel`, `GET/PUT /api/controls/scout-settings`), stored as `mcp_scout_autonomous` in the existing `user_settings` table. This is advisory, not enforced server-side — MCP has no mechanism to compel the calling agent's behavior, only to tell it the account's preference via `get_scout_settings`'s docstring instruction.

**UX principle (kept from the rough shape):** this is reuse, not accumulation — nothing new enters the brain, the agent pulls from what's already there. The pitch isn't "AI knows a good tool," it's "you already saved this three months ago and forgot."

---

## Phase 4 — Space curation

**Goal:** let an agent manage a user's Spaces (`src/db/spaces.py`) — the named collections of jobs plus editorial context blobs described in `docs/seed/WEB-PRD.md` §4 — with the same human-in-the-loop shape as Gardener: the agent proposes a change in conversation, the user approves, then a dedicated tool executes it. Full editing surface, not just curation-lite: create/rename/delete a Space; add/remove/reorder its jobs; create/edit/delete/reorder its context blobs.

**MCP tools needed (one per mutation, mirroring `delete_item`'s shape):**
- `create_space(name, color, icon, confirm)`
- `update_space(space_id, name, color=None, icon=None, confirm)` — omitting color/icon leaves them unchanged
- `delete_space(space_id, confirm)`
- `add_space_url(space_id, job_id, confirm)` — pins an existing job only, see Decisions below
- `remove_space_url(space_id, job_id, confirm)`
- `reorder_space_url(space_id, job_id, new_sort_order)` — **not** confirm-gated, see Decisions below
- `create_context_blob(space_id, name, content, confirm)`
- `update_context_blob(blob_id, name, content, confirm)`
- `delete_context_blob(blob_id, confirm)`
- `reorder_context_blob(blob_id, new_sort_order)` — **not** confirm-gated

Plus the existing read tools (`list_items`-shaped listing of the caller's Spaces, and detail fetches) needed to give the agent something to act on.

**Session flow:** same shape as Gardener — agent proposes a change with its reasoning stated, user approves per-item or in bulk, approved change executes via the matching confirm-gated tool. As with Phase 1's flagging, there's no separate "propose" tool call; the proposal is conversational.

**Decisions (grilled 2026-09-19, see ADR-0063):**
- **Approval granularity:** reordering (a job within a Space, or a context blob) executes immediately, no gate — it's low-stakes and trivially reversible. Every other mutation (create/rename/delete Space; add/remove URL; create/edit/delete blob) is confirm-gated, same bar as Gardener's delete.
- **Tool shape:** one dedicated tool per mutation, not a single generic `apply_space_change(op, payload)` tool — consistent with `delete_item`'s existing shape, and keeps per-field schema validation instead of a loose payload dict.
- **Scope: pin existing jobs only.** `add_space_url` never enqueues a new job — see ADR-0063.
- **No optimistic-concurrency guard on context blobs** — MCP writes inherit the dashboard's existing last-write-wins semantics rather than getting bespoke protection the dashboard itself doesn't have. See ADR-0063.
- **Ownership scoping** follows the same pattern as every existing tool: resolved from the MCP session's `_chat_id()`, not a caller-supplied parameter; a Space owned by another tenant reads as not-found, same as `_get_owned_space`'s 404 in the REST API.

---

## Sequencing note

This is not "ship all four, see what sticks." Phase 2 is complete — its infra blocker was already resolved by Phase 1's embeddings work, so it shipped without waiting on usage data. Phase 3 shipped without the usage-data validation this roadmap called for — a deliberate deviation, not evidence the gate was wrong for the next roadmap that follows this shape. Phase 4 is a different object (Spaces, not Links) rather than a continuation of the Brain-cleanup lineage, but follows the same phase discipline: propose-then-approve for anything destructive or judgment-based, narrow tool surface per operation, no scope creep into adjacent concerns (job ingestion) without its own grilling session.
