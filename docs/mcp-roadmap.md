# Ownix MCP Roadmap

Ownix as an MCP server: exposes the user's indexed content ("the brain") to AI agents. User-initiated only — no background or autonomous execution. Nothing runs unless the user opens a session and asks for it.

Three planned functions: **Gardener** (cleanup), **Connection-finding**, **Scouting**. They are not parallel workstreams — Phase 2 and 3 are gated on things Phase 1 hasn't yet produced, so treat this as sequential, not a fixed three-track plan.

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

**Status:** intentionally unscoped for now. This is the vaguest of the three and the most likely to produce generic, low-value output if defined too early.

**Do not scope until:** Phase 1 and 2 are live and there's real usage data on how people actually use an agent-connected brain. What "scout" should mean will likely change once real usage patterns are visible.

**Rough shape (subject to revision):** during a work session, the agent searches the *existing* brain — not external search — and surfaces already-saved items (tools, references, prior notes) relevant to what the user is currently building. This is reuse, not accumulation: nothing new enters the brain, the agent pulls from what's already there. The pitch isn't "AI knows a good tool," it's "you already saved this three months ago and forgot." Will need tight scoping rules to avoid generic, low-signal suggestions.

---

## Sequencing note

This is not "ship all three, see what sticks." Phase 2 is complete — its infra blocker was already resolved by Phase 1's embeddings work, so it shipped without waiting on usage data. Phase 3 is still blocked on usage data that doesn't exist yet: don't scope or commit to a Phase 3 timeline until Phase 1 and 2 have been used by real people.
