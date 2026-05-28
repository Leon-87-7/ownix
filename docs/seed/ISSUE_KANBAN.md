# Issue Kanban

> Read-only snapshot — authoritative state lives on [GitHub Issues](https://github.com/Leon-87-7/vig/issues).  
> Update this file whenever an issue moves columns.

---

## Done

|                                                 # | Title                                                                               | Area                    | Notes                                                                    |
| ------------------------------------------------: | ----------------------------------------------------------------------------------- | ----------------------- | ------------------------------------------------------------------------ |
|   [#1](https://github.com/Leon-87-7/vig/issues/1) | Scaffold + URL echo — FastAPI + worker + Redis + SQLite + task-envelope queue       | Infra                   | Closed on GH                                                             |
|   [#2](https://github.com/Leon-87-7/vig/issues/2) | Short video pipeline (Frames → Gemini Vision → Drive → Sheets → Telegram)           | Short Video             | Merged; closed on GH                                                     |
|   [#3](https://github.com/Leon-87-7/vig/issues/3) | Long video Phase 1 — transcript + metadata + description links + buttons            | Long Video              | Merged; closed on GH                                                     |
|   [#4](https://github.com/Leon-87-7/vig/issues/4) | Long video Phase 2 — Gemini enrichment + URL-resolution prompt                      | Long Video              | Merged; closed on GH                                                     |
|   [#5](https://github.com/Leon-87-7/vig/issues/5) | Second Brain — brain.py module (ingest, search, rebuild, refresh worker)            | Brain                   | Merged; closed on GH                                                     |
|   [#8](https://github.com/Leon-87-7/vig/issues/8) | Short Sheet brain backfill — one-off script to seed brain corpus                    | Brain / Short           | Merged; closed on GH                                                     |
|   [#9](https://github.com/Leon-87-7/vig/issues/9) | Long Sheet brain backfill + resolve_tool_urls helper + URL Resolution Prompt        | Brain / Long            | Merged; closed on GH                                                     |
| [#10](https://github.com/Leon-87-7/vig/issues/10) | BotFather command registration + ops runbook updates                                | Ops                     | Closed on GH                                                             |
| [#11](https://github.com/Leon-87-7/vig/issues/11) | Photo link extraction — Gemini Vision OCR on uploaded screenshots                   | Photo / Brain           | Merged; closed on GH                                                     |
|   [#6](https://github.com/Leon-87-7/vig/issues/6) | Mini-PRD auto slot — tail-call enqueue, Flash, JSON schema, Drive + Sheets + brain  | Mini-PRD                | Merged; closed on GH                                                     |
|   [#7](https://github.com/Leon-87-7/vig/issues/7) | Mini-PRD intent slot + /spec command + chat_state routing                           | Mini-PRD                | Merged; closed on GH                                                     |
| [#13](https://github.com/Leon-87-7/vig/issues/13) | Add retry button on Gemini enrichment failures                                      | Long Video              | Merged; closed on GH                                                     |
| [#15](https://github.com/Leon-87-7/vig/issues/15) | feat: extend transcript sidecar to support TikTok/Instagram via yt-dlp              | Short Video             | Merged; closed on GH                                                     |
| [#16](https://github.com/Leon-87-7/vig/issues/16) | feat: template + transcript enhancement system                                      | Templates               | Parent issue; closed on GH                                               |
| [#17](https://github.com/Leon-87-7/vig/issues/17) | feat: template system — data layer (Phases 1–4)                                     | Templates               | Merged; closed on GH                                                     |
| [#18](https://github.com/Leon-87-7/vig/issues/18) | feat: template system — handler layer (Phases 5–8)                                  | Templates               | Merged; closed on GH                                                     |
| [#21](https://github.com/Leon-87-7/vig/issues/21) | feat: GitHub service + Redis cache for repo enrichment                              | Photo / GitHub          | Merged; PR #28                                                           |
| [#23](https://github.com/Leon-87-7/vig/issues/23) | refactor: GeminiClient core module                                                  | Refactor                | Merged; PR #29                                                           |
| [#24](https://github.com/Leon-87-7/vig/issues/24) | refactor: PRD skeleton unification                                                  | Refactor                | Merged; PR #30                                                           |
| [#25](https://github.com/Leon-87-7/vig/issues/25) | refactor: webhook callback dispatch table                                           | Refactor                | Merged; PR #31                                                           |
| [#22](https://github.com/Leon-87-7/vig/issues/22) | feat: wire repo enrichment into photo pipeline                                      | Photo / GitHub          | Merged; closed on GH                                                     |
| [#26](https://github.com/Leon-87-7/vig/issues/26) | refactor: GeminiClient — migrate remaining callers                                  | Refactor                | Merged; closed on GH                                                     |
| [#27](https://github.com/Leon-87-7/vig/issues/27) | refactor: webhook slash dispatch table                                              | Refactor                | Merged; closed on GH                                                     |
| [#32](https://github.com/Leon-87-7/vig/issues/32) | feat: audio fallback for caption-less Reels (transcript service + audio enrichment) | Short Video / Templates | Committed to main (add56a6); not pushed; closed on GH                    |
| [#33](https://github.com/Leon-87-7/vig/issues/33) | feat: promise-gap extraction — schema + prompt + parse + persist                    | Enrichment              | Committed to main (51803cd); closed on GH                                |
| [#34](https://github.com/Leon-87-7/vig/issues/34) | feat: promise-gap Telegram render                                                   | Enrichment              | Committed to main (22c7de2); closed on GH                                |
| [#35](https://github.com/Leon-87-7/vig/issues/35) | Recover orphaned jobs at worker startup (ADR-0010)                                  | Infra / Worker          | Committed to main (7ba1a95); closed on GH; 43 tests green                |
| [#37](https://github.com/Leon-87-7/vig/issues/37) | Slimming sweep: dedup trivial helpers (ID gen, links formatter, EMBEDDING_DIM)      | Refactor                | Closed on GH; changes local (uncommitted); 49 touched-module tests green |
| [#38](https://github.com/Leon-87-7/vig/issues/38) | Unify the two template-matching tables into the Template module                     | Refactor                | Closed on GH                                                             |
| [#41](https://github.com/Leon-87-7/vig/issues/41) | refactor(database): add set_prd_slot_status — narrow the update_job_status escape hatch | DB / PRD           | Merged; PR #44; closed on GH                                             |
| [#43](https://github.com/Leon-87-7/vig/issues/43) | refactor(database): replace silent ALTER TABLE blocks with PRAGMA user_version migration tracking | DB    | Merged; PR #45; closed on GH; 17 db tests green                         |
| —                                                  | fix(database): phantom status filter in find_recent_job_by_url ('failed'/'stale')   | DB / Dedup              | No issue; fixed directly; committed to main                              |
| [#36](https://github.com/Leon-87-7/vig/issues/36) | fix: photo pipeline missing ADR-0005 UI-chrome filter (3 red tests)                 | Photo                   | Merged; PR #48; commit 2df529e; closed on GH                            |
| [#46](https://github.com/Leon-87-7/vig/issues/46) | bug(gemini_photo): _filter_grounded_links not dropping 'followed by' UI-chrome links | Photo                  | Closed as dup of #36; fixed by PR #48                                   |
| [#39](https://github.com/Leon-87-7/vig/issues/39) | Collapse the Gemini service triplet into one module (ADR-0011)                      | Refactor                | Merged; PR #49; commit bd4d949; closed on GH                            |
| [#42](https://github.com/Leon-87-7/vig/issues/42) | refactor(database): move links table DDL from brain.py into database.py             | DB / Brain              | Completed; links DDL in database.py SCHEMA_SQL; brain.py SCHEMA_SQL removed; closed on GH |
| [#47](https://github.com/Leon-87-7/vig/issues/47) | bug(test_short_video): short_video.run() hits no such table: ignored_domains        | Test / DB               | Merged; PR #50; commit 5dbdd2b; closed on GH                            |
| [#51](https://github.com/Leon-87-7/vig/issues/51) | feat(db): add jobs.freestyle_prompt column                                          | DB                      | Merged; PR #55; commit 004d6ab; closed on GH                            |
| [#52](https://github.com/Leon-87-7/vig/issues/52) | feat(enrichment): substitute freestyle_prompt in place of template extra_instructions | Enrichment            | Merged; PR #56; commit c8e52ce; closed on GH                            |
| [#53](https://github.com/Leon-87-7/vig/issues/53) | feat(webhook): template picker keyboard replaces direct gemini_yes enqueue (ADR-0012) | Webhook / Long Video  | Merged; PR #57; commit 3092399; closed on GH                            |
| [#54](https://github.com/Leon-87-7/vig/issues/54) | feat(webhook): /freestyle slash command for both short and long pipelines           | Webhook / Templates     | Merged; PR #58; commit 128f9fb; closed on GH                            |
| —                                                  | feat(webhook): /find UX — GitHub enrichment, full URL path, score floor 0.58       | Brain / Webhook         | No issue; committed directly (feat/find-ux session)                     |
| —                                                  | feat(webhook): plain-text command shortcut — first word matched against _SLASH_TABLE | Webhook               | No issue; committed directly (same session)                             |
| [#59](https://github.com/Leon-87-7/vig/issues/59) | refactor(sheets): consolidate three GOOGLE_SHEETS_ID_* env vars into one with named tabs (ADR-0013) | Refactor / Sheets | Committed to main; closed on GH |
| [#60](https://github.com/Leon-87-7/vig/issues/60) | feat(jina): markdown_cache + /download_md utility + /force cache invalidation | Article / Utility | Committed to main; closed on GH |
| [#61](https://github.com/Leon-87-7/vig/issues/61) | feat(allowlist): /allowlist family + allowed_domains table + ARTICLE_DEFAULT_DOMAINS + rejection hint | Article / Webhook | Committed to main; closed on GH |
| [#62](https://github.com/Leon-87-7/vig/issues/62) | feat(article): end-to-end article URL pipeline — Jina → cache → doc → paywall → Gemini → sheets → brain | Article | Committed to main; closed on GH; 159/160 tests green |

---

## Needs Triage

|      # | Title | Area | Depends On |
| -----: | ----- | ---- | ---------- |
| (none) |       |      |            |

---

## Ready for Agent

Ordered by unblocked-first, then dependency chain.

|      # | Title | Area | Depends On |
| -----: | ----- | ---- | ---------- |
| (none) |       |      |            |

---

## Ready for Human

|      # | Title | Area | Notes |
| -----: | ----- | ---- | ----- |
| (none) |       |      |       |

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
```
