# Launch-to-friends — implementation order

Sequenced plan across two tracks: **export isolation** (epic #201) and the
**invite gate** (epic #253). Goal: open VIG to a handful of LinkedIn friends who
sign in and use it, then reach full per-user export parity.

Decisions are pinned in **ADR-0030** (export gate + OAuth credential model) and
**ADR-0031** (invite-only gate + onboarding).

## At a glance (2026-06-30)

| #           | What                                        | Status            | When                                   |
| ----------- | ------------------------------------------- | ----------------- | -------------------------------------- |
| #207        | export-isolation docs / ADR-0030            | ✅ merged          | done                                   |
| #208        | `OPERATOR_CHAT_ID` export gate (closed #202) | ✅ merged          | done — keystone                        |
| #258        | ADR-0031 invite-gate docs                   | open              | next on path                           |
| #259        | stored XSS in `brain-graph.tsx`             | open, **new**     | **before first invite** (independent)  |
| #254        | `users.email`/`status` schema + cutover     | open              | Phase 1, after #208                    |
| #255        | bot email capture + pending gate            | open              | after #254                             |
| #256        | web email modal + `/api/*` gate             | open              | after #254 → 🚀 launchable             |
| #203        | Google Cloud OAuth app verification         | open              | **start now, in parallel** (external)  |
| #204        | web "Connect Google" → per-user export      | open              | Phase 2, after #203                    |
| #205 / #206 | Mini App surface · connection lifecycle     | open              | parallel, after #204                   |

---

## Phase 0 — land the foundation (you merge)

1. ~~**#207**~~ — ✅ **merged** (PR #207, squash → `main`). Docs only;
   established ADR-0030, the `Operator` glossary term, and the issue breakdown.
2. ~~**#208**~~ — ✅ **merged** (squash → `main`, auto-closed spec #202).
   **Keystone:** `OPERATOR_CHAT_ID` is the admin identity everything below keys
   on; gate enforced at the API layer and the Drive/Sheets service boundary.
3. **#258** — rebase on `main` (resolve glossary overlap with #207's `Operator`
   row) → merge ADR-0031 + this doc.
4. **#259** — stored XSS via `nodeLabel` in `web/components/brain-graph.tsx`
   (external video titles → `innerHTML`). **Independent, no deps — fix before
   inviting anyone**, since friends will load the dashboard. Small, slot it
   anywhere in Phase 0.

## Phase 1 — invite gate (the actual launch gate; depends on #208)

4. **#254** — schema + cutover: `users.email`/`status`, `awaiting_email` CHECK
   migration, operator auto-approve, grandfather existing rows. *Gates 5 & 6.*
5. **#255** — bot onboarding + gate: first-contact email capture, pending gate,
   push one-tap approve. *Before #256 — the bot is the primary ingestion door.*
6. **#256** — web onboarding + gate: email modal, `/api/*` status gate, pending
   screen.

> **🚀 Launchable after #256.** Invite friends: they sign in, give an email
> once, you tap Approve, they use VIG (Telegram + dashboard). No personal Google
> exports yet — that is Phase 2.

## Phase 2 — export parity ("use VIG exactly as I do"; post-launch, slow lane)

7. **#203** — Google Cloud OAuth app + sensitive-scope verification.
   **Start in parallel with Phase 0** — it is external (Google review,
   days–weeks) and no code, so kicking it off early means it is ready when you
   reach #204. Must not block the launch.
8. **#204** — web "Connect Google" → encrypted per-`chat_id` token → exports to
   their `/vig` folder. First real per-user export.
9. **#205** — Telegram Mini App surface · **#206** — connection lifecycle
   (`invalid_grant`, `/disconnect`, notify-once). Parallel after #204.

## Phase 3 — open decision still owed

10. **Global Brain.** Friends' extracted *links* still flow into the
    operator-owned brain (the Obsidian sync — ungated by design). Not covered by
    epic #201. Decide the "Brain tiers" (private / community / group) track when
    it matters; independent of everything above.

---

**Critical path to launch:** ~~#207~~ ✅ → ~~#208~~ ✅ → **#258** → #254 → #255 → #256.
**Start #203 in parallel immediately** so parity is not gated on Google later.
**Land #259 (XSS) before the first invite** — independent of the path, but a
launch blocker on its own.
