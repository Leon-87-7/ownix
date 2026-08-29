# Handoff: Ownix Agents (wayfinder map)

Focus of the next session: continuing the "Ownix Agents" initiative — picking
up the wayfinder map, working the frontier, or starting the foundational
implementation slice once ready.

## Where things live

- **Repo**: `Leon-87-7/ownix` on GitHub, working copy at
  `C:\Users\leone\Desktop\codeKitchen\ownix` (this session worked from the
  `web\` subdirectory). Issue tracker is GitHub via the `gh` CLI — see
  `docs/agents/issue-tracker.md`.
- **The map**: [Ownix Agents — map (#574)](https://github.com/Leon-87-7/ownix/issues/574)
  — read this issue first, it's the low-res index (Destination, Notes,
  Decisions so far, Not yet specified / fog, Out of scope). Do not
  re-summarize its content here — it's the source of truth and will keep
  changing as tickets resolve.
- **Closed decision tickets** (detail lives on the issues, not duplicated
  here): [#575 — agent identity, credentials, dashboard architecture](https://github.com/Leon-87-7/ownix/issues/575),
  [#576 — what an Ownix Agent should accomplish](https://github.com/Leon-87-7/ownix/issues/576).
- **Open frontier tickets** (unblocked, unclaimed, takeable next):
  [#577 — design the passive-capture mechanism](https://github.com/Leon-87-7/ownix/issues/577),
  [#578 — Second Brain scope: separate agent graph or cross-linked?](https://github.com/Leon-87-7/ownix/issues/578).

## State of the map's fog

Still un-ticketed on the map (see #574's "Not yet specified"): the MCP server's
tool surface and the Telegram chat-handler design (both wait on #577
resolving first), and cross-dashboard permission wiring (best specified once
the #575 dashboard scaffold actually exists).

## A parallel, non-wayfinder track: building the foundational slice

Everything decided in #575 (new `agents` table, `owner_user_id` FK,
token-based credentials extending `src/auth/extension_tokens.py`'s
pairing/bearer pattern, multiple agents per human, agent dashboard v1 reusing
the human dashboard's route shell scoped to empty agent data, new "Agents" nav
section on the human dashboard) is **fully specified with nothing left to
decide**. Wayfinder is planning-only by default, so it will not build this.
When ready, this is a standalone implementation effort — a new git branch off
`main`, driven by `superpowers:writing-plans` then `superpowers:executing-plans`
— independent of continuing to work the map's frontier tickets.

## Tracker mechanics learned this session (useful if creating more tickets)

- Wayfinder labels now exist in this repo: `wayfinder:map`, `wayfinder:research`,
  `wayfinder:prototype`, `wayfinder:grilling`, `wayfinder:task`.
- GitHub's native sub-issues REST API works here for parent/child wiring:
  `gh api repos/Leon-87-7/ownix/issues/<parent>/sub_issues -F sub_issue_id=<child_numeric_id>`
  — the `sub_issue_id` is the issue's internal numeric `id` (from
  `gh api repos/OWNER/REPO/issues/<number> -q .id`), **not** the issue number,
  and must be passed with `-F` (typed) not `-f` (string) or the API rejects it.
  No native "blocked by" relationship was tested/used yet — if a future ticket
  needs one, check `gh api ... /issues/<n>/dependencies` conventions before
  falling back to a body-text convention.

## Suggested skills for the next session

- **`mattpocock-skills:wayfinder`** — the default next step. Invoke with the
  map's URL/number (#574) to load the low-res view and claim the next frontier
  ticket (#577 or #578). It will call `grilling` and `domain-modeling` itself
  while resolving whichever ticket is picked.
- **`superpowers:writing-plans`** then **`superpowers:executing-plans`** —
  only if the session's actual goal is to start building the #575 foundational
  slice rather than continuing to chart/resolve the map.

## Notes / gotchas

- No secrets, keys, or credentials were generated or handled this session —
  nothing to redact.
- The existing human-side Second Brain (`src/brain.py`, the `links` table)
  deliberately demotes provenance (`source_job` is documented as "provenance,
  not ownership"; `topic` was stripped from search in a 2026-07-17 decision).
  Keep this in mind on #578 — agent memory is being treated as a genuinely
  separate concern, not an extension of that existing table/decision history.
