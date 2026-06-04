# Issue Kanban

> Read-only snapshot — authoritative state lives on [GitHub Issues](https://github.com/Leon-87-7/vig/issues).  
> Update this file whenever an issue moves columns.

---

## Done

|                                                 # | Title                                                                                                   | Area                    | Notes                                                                                     |
| ------------------------------------------------: | ------------------------------------------------------------------------------------------------------- | ----------------------- | ----------------------------------------------------------------------------------------- |
|   [#1](https://github.com/Leon-87-7/vig/issues/1) | Scaffold + URL echo — FastAPI + worker + Redis + SQLite + task-envelope queue                           | Infra                   | Closed on GH                                                                              |
|   [#2](https://github.com/Leon-87-7/vig/issues/2) | Short video pipeline (Frames → Gemini Vision → Drive → Sheets → Telegram)                               | Short Video             | Merged; closed on GH                                                                      |
|   [#3](https://github.com/Leon-87-7/vig/issues/3) | Long video Phase 1 — transcript + metadata + description links + buttons                                | Long Video              | Merged; closed on GH                                                                      |
|   [#4](https://github.com/Leon-87-7/vig/issues/4) | Long video Phase 2 — Gemini enrichment + URL-resolution prompt                                          | Long Video              | Merged; closed on GH                                                                      |
|   [#5](https://github.com/Leon-87-7/vig/issues/5) | Second Brain — brain.py module (ingest, search, rebuild, refresh worker)                                | Brain                   | Merged; closed on GH                                                                      |
|   [#8](https://github.com/Leon-87-7/vig/issues/8) | Short Sheet brain backfill — one-off script to seed brain corpus                                        | Brain / Short           | Merged; closed on GH                                                                      |
|   [#9](https://github.com/Leon-87-7/vig/issues/9) | Long Sheet brain backfill + resolve_tool_urls helper + URL Resolution Prompt                            | Brain / Long            | Merged; closed on GH                                                                      |
| [#10](https://github.com/Leon-87-7/vig/issues/10) | BotFather command registration + ops runbook updates                                                    | Ops                     | Closed on GH                                                                              |
| [#11](https://github.com/Leon-87-7/vig/issues/11) | Photo link extraction — Gemini Vision OCR on uploaded screenshots                                       | Photo / Brain           | Merged; closed on GH                                                                      |
|   [#6](https://github.com/Leon-87-7/vig/issues/6) | Mini-PRD auto slot — tail-call enqueue, Flash, JSON schema, Drive + Sheets + brain                      | Mini-PRD                | Merged; closed on GH                                                                      |
|   [#7](https://github.com/Leon-87-7/vig/issues/7) | Mini-PRD intent slot + /spec command + chat_state routing                                               | Mini-PRD                | Merged; closed on GH                                                                      |
| [#13](https://github.com/Leon-87-7/vig/issues/13) | Add retry button on Gemini enrichment failures                                                          | Long Video              | Merged; closed on GH                                                                      |
| [#15](https://github.com/Leon-87-7/vig/issues/15) | feat: extend transcript sidecar to support TikTok/Instagram via yt-dlp                                  | Short Video             | Merged; closed on GH                                                                      |
| [#16](https://github.com/Leon-87-7/vig/issues/16) | feat: template + transcript enhancement system                                                          | Templates               | Parent issue; closed on GH                                                                |
| [#17](https://github.com/Leon-87-7/vig/issues/17) | feat: template system — data layer (Phases 1–4)                                                         | Templates               | Merged; closed on GH                                                                      |
| [#18](https://github.com/Leon-87-7/vig/issues/18) | feat: template system — handler layer (Phases 5–8)                                                      | Templates               | Merged; closed on GH                                                                      |
| [#21](https://github.com/Leon-87-7/vig/issues/21) | feat: GitHub service + Redis cache for repo enrichment                                                  | Photo / GitHub          | Merged; PR #28                                                                            |
| [#23](https://github.com/Leon-87-7/vig/issues/23) | refactor: GeminiClient core module                                                                      | Refactor                | Merged; PR #29                                                                            |
| [#24](https://github.com/Leon-87-7/vig/issues/24) | refactor: PRD skeleton unification                                                                      | Refactor                | Merged; PR #30                                                                            |
| [#25](https://github.com/Leon-87-7/vig/issues/25) | refactor: webhook callback dispatch table                                                               | Refactor                | Merged; PR #31                                                                            |
| [#22](https://github.com/Leon-87-7/vig/issues/22) | feat: wire repo enrichment into photo pipeline                                                          | Photo / GitHub          | Merged; closed on GH                                                                      |
| [#26](https://github.com/Leon-87-7/vig/issues/26) | refactor: GeminiClient — migrate remaining callers                                                      | Refactor                | Merged; closed on GH                                                                      |
| [#27](https://github.com/Leon-87-7/vig/issues/27) | refactor: webhook slash dispatch table                                                                  | Refactor                | Merged; closed on GH                                                                      |
| [#32](https://github.com/Leon-87-7/vig/issues/32) | feat: audio fallback for caption-less Reels (transcript service + audio enrichment)                     | Short Video / Templates | Committed to main (add56a6); not pushed; closed on GH                                     |
| [#33](https://github.com/Leon-87-7/vig/issues/33) | feat: promise-gap extraction — schema + prompt + parse + persist                                        | Enrichment              | Committed to main (51803cd); closed on GH                                                 |
| [#34](https://github.com/Leon-87-7/vig/issues/34) | feat: promise-gap Telegram render                                                                       | Enrichment              | Committed to main (22c7de2); closed on GH                                                 |
| [#35](https://github.com/Leon-87-7/vig/issues/35) | Recover orphaned jobs at worker startup (ADR-0010)                                                      | Infra / Worker          | Committed to main (7ba1a95); closed on GH; 43 tests green                                 |
| [#37](https://github.com/Leon-87-7/vig/issues/37) | Slimming sweep: dedup trivial helpers (ID gen, links formatter, EMBEDDING_DIM)                          | Refactor                | Closed on GH; changes local (uncommitted); 49 touched-module tests green                  |
| [#38](https://github.com/Leon-87-7/vig/issues/38) | Unify the two template-matching tables into the Template module                                         | Refactor                | Closed on GH                                                                              |
| [#41](https://github.com/Leon-87-7/vig/issues/41) | refactor(database): add set_prd_slot_status — narrow the update_job_status escape hatch                 | DB / PRD                | Merged; PR #44; closed on GH                                                              |
| [#43](https://github.com/Leon-87-7/vig/issues/43) | refactor(database): replace silent ALTER TABLE blocks with PRAGMA user_version migration tracking       | DB                      | Merged; PR #45; closed on GH; 17 db tests green                                           |
|                                                 — | fix(database): phantom status filter in find_recent_job_by_url ('failed'/'stale')                       | DB / Dedup              | No issue; fixed directly; committed to main                                               |
| [#36](https://github.com/Leon-87-7/vig/issues/36) | fix: photo pipeline missing ADR-0005 UI-chrome filter (3 red tests)                                     | Photo                   | Merged; PR #48; commit 2df529e; closed on GH                                              |
| [#46](https://github.com/Leon-87-7/vig/issues/46) | bug(gemini_photo): \_filter_grounded_links not dropping 'followed by' UI-chrome links                   | Photo                   | Closed as dup of #36; fixed by PR #48                                                     |
| [#39](https://github.com/Leon-87-7/vig/issues/39) | Collapse the Gemini service triplet into one module (ADR-0011)                                          | Refactor                | Merged; PR #49; commit bd4d949; closed on GH                                              |
| [#42](https://github.com/Leon-87-7/vig/issues/42) | refactor(database): move links table DDL from brain.py into database.py                                 | DB / Brain              | Completed; links DDL in database.py SCHEMA_SQL; brain.py SCHEMA_SQL removed; closed on GH |
| [#47](https://github.com/Leon-87-7/vig/issues/47) | bug(test_short_video): short_video.run() hits no such table: ignored_domains                            | Test / DB               | Merged; PR #50; commit 5dbdd2b; closed on GH                                              |
| [#51](https://github.com/Leon-87-7/vig/issues/51) | feat(db): add jobs.freestyle_prompt column                                                              | DB                      | Merged; PR #55; commit 004d6ab; closed on GH                                              |
| [#52](https://github.com/Leon-87-7/vig/issues/52) | feat(enrichment): substitute freestyle_prompt in place of template extra_instructions                   | Enrichment              | Merged; PR #56; commit c8e52ce; closed on GH                                              |
| [#53](https://github.com/Leon-87-7/vig/issues/53) | feat(webhook): template picker keyboard replaces direct gemini_yes enqueue (ADR-0012)                   | Webhook / Long Video    | Merged; PR #57; commit 3092399; closed on GH                                              |
| [#54](https://github.com/Leon-87-7/vig/issues/54) | feat(webhook): /freestyle slash command for both short and long pipelines                               | Webhook / Templates     | Merged; PR #58; commit 128f9fb; closed on GH                                              |
|                                                 — | feat(webhook): /find UX — GitHub enrichment, full URL path, score floor 0.58                            | Brain / Webhook         | No issue; committed directly (feat/find-ux session)                                       |
|                                                 — | feat(webhook): plain-text command shortcut — first word matched against \_SLASH_TABLE                   | Webhook                 | No issue; committed directly (same session)                                               |
| [#59](https://github.com/Leon-87-7/vig/issues/59) | refactor(sheets): consolidate three GOOGLE*SHEETS_ID*\* env vars into one with named tabs (ADR-0013)    | Refactor / Sheets       | Committed to main; closed on GH                                                           |
| [#60](https://github.com/Leon-87-7/vig/issues/60) | feat(jina): markdown_cache + /download_md utility + /force cache invalidation                           | Article / Utility       | Committed to main; closed on GH                                                           |
| [#61](https://github.com/Leon-87-7/vig/issues/61) | feat(allowlist): /allowlist family + allowed_domains table + ARTICLE_DEFAULT_DOMAINS + rejection hint   | Article / Webhook       | Committed to main; closed on GH                                                           |
| [#62](https://github.com/Leon-87-7/vig/issues/62) | feat(article): end-to-end article URL pipeline — Jina → cache → doc → paywall → Gemini → sheets → brain | Article                 | Committed to main; closed on GH; 159/160 tests green                                      |
| [#66](https://github.com/Leon-87-7/vig/issues/66) | Repo pipeline #1: URL routing + stub processor (tracer bullet)                                          | Repo Pipeline           | —                                                                                         |
| [#67](https://github.com/Leon-87-7/vig/issues/67) | Repo pipeline #2: GitHub bundle fetch + Redis cache + README preprocessing + /force                     | Repo Pipeline           | Merged; PR #80; closed on GH                                                              |
| [#68](https://github.com/Leon-87-7/vig/issues/68) | Repo pipeline #3: Gemini analysis + structured JSON + summary message                                   | Repo Pipeline           | Merged; PR #80; closed on GH                                                              |
| [#69](https://github.com/Leon-87-7/vig/issues/69) | Repo pipeline #4: Telegram document delivery (`<owner>-<repo>.md`)                                      | Repo Pipeline           | Merged; PR #80; closed on GH                                                              |
| [#70](https://github.com/Leon-87-7/vig/issues/70) | Repo pipeline #5: Sheets persistence (Repo Analysis tab + append/update)                                | Repo Pipeline           | Merged; PR #80; closed on GH                                                              |
| [#71](https://github.com/Leon-87-7/vig/issues/71) | Repo pipeline #6: Second Brain ingest (repo URL only)                                                   | Repo Pipeline           | Merged; PR #80; closed on GH                                                              |
| [#72](https://github.com/Leon-87-7/vig/issues/72) | Repo pipeline #7: Edge cases (archived + no-README + distinct API errors)                               | Repo Pipeline           | Merged; PR #80; closed on GH                                                              |
| [#73](https://github.com/Leon-87-7/vig/issues/73) | Repo pipeline #8: Freestyle re-run end-to-end (same job_id, cache hit, Sheets in-place update)          | Repo Pipeline           | Merged; PR #80; closed on GH                                                              |
| [#81](https://github.com/Leon-87-7/vig/issues/81) | bug(database): add chat_id to ignored_domains — per-chat tenancy (drift fix)                            | DB / Tenancy            | Committed to main (45edd0d); closed on GH                                                 |
| [#83](https://github.com/Leon-87-7/vig/issues/83) | web(S0): API package split + FK enforcement                                                             | Web / Infra             | Closed on GH                                                                              |
| [#84](https://github.com/Leon-87-7/vig/issues/84) | web(S1): Auth spine — Telegram Login Widget → Redis session → guarded Next.js shell                     | Web / Auth              | Closed on GH; dev branch; 18 tests green; end-to-end login verified on app.leondev.xyz    |
| [#85](https://github.com/Leon-87-7/vig/issues/85) | web(S2): Feed — hero stats + fuse.js search + filters + Scope-A polling                                 | Web / Feed              | —                                                                                         |
| [#86](https://github.com/Leon-87-7/vig/issues/86) | web(S3): Job detail — full enrichment view + per-field copy buttons                                     | Web / Jobs              | —                                                                                         |
| [#87](https://github.com/Leon-87-7/vig/issues/87) | web(S4): Controls Tags tab — tag CRUD with name + meaning + color                                       | Web / Controls          | —                                                                                         |
| [#89](https://github.com/Leon-87-7/vig/issues/89) | web(S6): Spaces — CRUD + URLs tab                                                                       | Web / Spaces            | Merged to dev; commits 1bd879b + 894c43c; closed on GH                                     |
| [#101](https://github.com/Leon-87-7/vig/issues/101) | feat(enrichment): transcribe_audio + enrich_audio returns transcript text (ADR-0020 foundation)       | Short Video / Enrichment | Committed (dbdcd40); closed on GH; 57 tests green                                          |
| [#102](https://github.com/Leon-87-7/vig/issues/102) | feat(short-pipeline): guaranteed transcript acquisition on every short job (ADR-0020)                | Short Video             | Committed (dbdcd40); closed on GH; 57 tests green                                          |
| [#103](https://github.com/Leon-87-7/vig/issues/103) | feat(short-pipeline): transcript Drive upload + Telegram document delivery tail (ADR-0020)           | Short Video             | Committed (dbdcd40); closed on GH; 57 tests green                                          |

---

## Needs Triage

|   # | Title | Area | Depends On |
| --: | ----- | ---- | ---------- |
| [#88](https://github.com/Leon-87-7/vig/issues/88) | web(S5): Job annotation + tagging (Milkdown) | Web / Jobs | #86, #87 |
| [#90](https://github.com/Leon-87-7/vig/issues/90) | web(S9): User templates + -name branch | Web / Templates | #83, #84 |
| [#91](https://github.com/Leon-87-7/vig/issues/91) | web(S10): Controls Allowed/Ignored domains | Web / Controls | #84, #81 |
| [#92](https://github.com/Leon-87-7/vig/issues/92) | web(S11): Brain search page | Web / Brain | #83, #84 |
| [#94](https://github.com/Leon-87-7/vig/issues/94) | web(S12): Deploy — compose web + subdomains [HITL] | Web / Ops | #84 |

---

## Ready for Agent

Ordered by unblocked-first, then dependency chain.

|                                                 # | Title                                                                                                       | Area                | Depends On    |
| ------------------------------------------------: | ----------------------------------------------------------------------------------------------------------- | ------------------- | ------------- |
| [#75](https://github.com/Leon-87-7/vig/issues/75) | refactor(telegram): extract dispatch.py — CallbackCtx/SlashCtx contract module (ADR-0015)                   | Refactor / Telegram | —             |
| [#76](https://github.com/Leon-87-7/vig/issues/76) | refactor(telegram): extract callbacks.py — _cb_\* + \_CALLBACK_TABLE + handle_callback()                    | Refactor / Telegram | #75           |
| [#77](https://github.com/Leon-87-7/vig/issues/77) | refactor(telegram): extract domain_cmds.py — /ignore·/allowlist family + DOMAIN_COMMANDS                    | Refactor / Telegram | #75           |
| [#78](https://github.com/Leon-87-7/vig/issues/78) | refactor(telegram): extract photo.py — batch state machine + handle_photo_message() + PHOTO_COMMANDS        | Refactor / Telegram | #75           |
| [#79](https://github.com/Leon-87-7/vig/issues/79) | refactor(telegram): finalize sender.\* seam in webhook + line-count/glossary verification (ADR-0015)        | Refactor / Telegram | #76, #77, #78 |
| [#82](https://github.com/Leon-87-7/vig/issues/82) | bug(test_long_video): under-mocked send_message → coroutine reaches editMessageText JSON encode (test-only) | Test / Long Video   | —             |
| [#93](https://github.com/Leon-87-7/vig/issues/93) | web(S7): Space context blobs — Context tab (Milkdown, ordered)                                              | Web / Spaces        | #89, #88      |
| [#95](https://github.com/Leon-87-7/vig/issues/95) | web(S8): Space export — composer + gdoc + md/txt/pdf modal                                                  | Web / Spaces        | #89, #93, #87, #88 |

---

## Ready for Human

|   # | Title   | Area | Notes |
| --: | ------- | ---- | ----- |
|   — | (empty) |      |       |

---

## Dependency Map

```
#1 Scaffold ✓
├── #2 Short pipeline ✓
│   └── #8 Short brain backfill ✓
├── #3 Long Phase 1 ✓
│   ├── #4 Long Phase 2 ✓
│   └── #9 Long brain backfill ✓
└── #5 Second Brain ✓
    ├── #8 ✓
    ├── #9 ✓
    ├── #11 Photo link extraction ✓
    │   ├── #21 GitHub service + cache ✓
    │   │   └── #22 Photo pipeline wiring (repo enrichment) ✓
    ├── #6 Mini-PRD auto ✓
    │   └── #7 Mini-PRD intent ✓
    │       └── #13 Enrichment retry button ✓
    └── (feeds #4 via URL-resolution)

#10 BotFather ✓
#15 Transcript sidecar TikTok/Instagram ✓
#16 Template system parent ✓
    ├── #17 Template data layer ✓
    └── #18 Template handler layer ✓
        └── #32 Audio fallback for caption-less Reels (ADR-0009) ✓

#23 GeminiClient core ✓
└── #26 GeminiClient migrate remaining callers ✓

#24 PRD skeleton unification ✓

#25 Webhook callback dispatch table ✓
└── #27 Webhook slash dispatch table ✓

#37 Slimming sweep — dedup ID gen / links formatter / EMBEDDING_DIM ✓ (slimming-doc #3/#4/#5)
#38 Unify template-matching tables ✓
#39 Collapse Gemini service triplet → ADR-0011 ✓ (PR #49)

#33 Promise-gap extraction ✓
└── #34 Promise-gap Telegram render ✓ (needs #33)

#35 Orphaned-job reaper (ADR-0010) ✓
#36 Photo UI-chrome filter (ADR-0005) ✓ (PR #48)
└── #46 _filter_grounded_links UI-chrome dup ✓ (closed as dup of #36)

— fix: phantom status filter (find_recent_job_by_url) ✓ (no issue; committed directly)

#41 add set_prd_slot_status ✓
#42 move links DDL into database.py ✓
#43 PRAGMA user_version migrations ✓ (best after #42)
#47 short_video ignored_domains missing in tests ✓ (PR #50)

#51 jobs.freestyle_prompt column ✓
└── #52 enrichment freestyle substitution ✓
    └── #53 template picker keyboard (ADR-0012) ✓
        └── #54 /freestyle slash command ✓

— /find UX (GitHub enrichment, full URL path, score floor) ✓
— plain-text command shortcut (first word → _SLASH_TABLE) ✓

Article URL feature (postgrill: docs/features/postgrill/article-url-feature.md)
#59 Sheets consolidation (ADR-0013) ─────────┐
                                             │
#60 Jina + markdown_cache + /download_md ────┼──► #62 Article pipeline end-to-end ✓
                                             │
#61 Article allowlist CRUD ──────────────────┘
(all four closed)

Repo URL feature (postgrill: docs/features/postgrill/repo-url-feature.md + ADR-0014)
#66 URL routing + stub ✓
└── #67 bundle + cache + README preprocessing + /force ✓ (PR #80)
    └── #68 Gemini analysis + summary ✓ ──┬── #69 document delivery ✓
                                          ├── #70 Sheets persistence ✓ ──┐
                                          ├── #71 brain ingest ✓         │
                                          ├── #72 edge cases ✓           │
                                          └── #73 freestyle re-run ✓ ◄───┘
                                                (also depends on #70)

webhook.py split (CONTEXT.md: Dispatch contract module / Telegram sender seam + ADR-0015)
#75 extract dispatch.py (CallbackCtx/SlashCtx contract)
├── #76 extract callbacks.py (_cb_* + _CALLBACK_TABLE + handle_callback) ──┐
├── #77 extract domain_cmds.py (/ignore·/allowlist + DOMAIN_COMMANDS) ─────┤
└── #78 extract photo.py (batch + handle_photo_message + PHOTO_COMMANDS) ──┴── #79 finalize sender.* seam in webhook + verify

Web dashboard feature (postgrill: docs/features/postgrill/web-plan.md + ADR-0016..0019)
#81 ignored_domains per-chat migration (tenancy drift) ✓
└── (45edd0d; prerequisite for /controls Ignored tab)

Web dashboard slices (WEB-PRD: docs/seed/WEB-PRD.md)
Critical path: #83 → #84 → {#85, #86, #87} → #88/#89 → #93 → #95

#83 S0 — API package split + FK enforcement ✓
└── #84 S1 — Auth spine [HITL] ✓
    ├── #85 S2 — Feed ✓
    │   └── #89 S6 — Spaces CRUD + URLs tab ✓ ◄── also #84
    │       └── #93 S7 — Context blobs ◄── also #88
    │           └── #95 S8 — Space export ◄── also #87, #88
    ├── #86 S3 — Job detail ✓
    │   └── #88 S5 — Job annotation ◄── also #87
    ├── #87 S4 — Controls Tags tab ✓
    ├── #90 S9 — User templates ◄── also #83
    ├── #91 S10 — Controls Allowed/Ignored ◄── also #81
    ├── #92 S11 — Brain search page ◄── also #83
    └── #94 S12 — Deploy [HITL]

#82 test(long_video) under-mocked send_message → coroutine in editMessageText (standalone test-hygiene; no deps)

ADR-0020: Guaranteed transcript on every short job (docs/adr/0020-always-transcript-short-pipeline.md)
#32 Audio fallback for caption-less Reels ✓ ◄── pre-existing foundation
└── #101 transcribe_audio + enrich_audio returns transcript text ✓ (dbdcd40)
    └── #102 guaranteed transcript acquisition on all short jobs ✓ ◄── also #32
        └── #103 transcript Drive upload + Telegram document delivery tail ✓
Critical path: #101 → #102 → #103 (all ✓)
```
