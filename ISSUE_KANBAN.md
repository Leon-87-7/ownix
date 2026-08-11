# Issue Kanban

> Read-only snapshot — authoritative state lives on [GitHub Issues](https://github.com/Leon-87-7/vig/issues).\
> Update this file whenever an issue moves columns.

---

## Done

|                                                    # | Title                                                              | Area              | Notes                          |
| ----------------------------------------------------: | ------------------------------------------------------------------- | ------------------ | ------------------------------- |
| [#436](https://github.com/Leon-87-7/ownix/issues/436) | fix(api): cache job thumbnail responses (ETag + Cache-Control)      | API                | Merged; PR #437; closed on GH  |
| [#441](https://github.com/Leon-87-7/ownix/issues/441) | feat(web): eager-load the first 10 feed preview cards               | Web / Feed         | Merged; PR #447; closed on GH  |
| [#442](https://github.com/Leon-87-7/ownix/issues/442) | feat(web): thumbnail preload SSR head start for the Feed            | Web / Feed         | Merged; PR #447; closed on GH  |
| [#443](https://github.com/Leon-87-7/ownix/issues/443) | fix(api): extend stored thumbnail cache to 30 days                  | API / Thumbnails   | Merged; PR #447; closed on GH  |
| [#449](https://github.com/Leon-87-7/ownix/issues/449) | feat(jobs): hold a pending user's links as un-enqueued 'held' jobs  | Jobs / Invite      | Merged; PR #453; closed on GH  |
| [#450](https://github.com/Leon-87-7/ownix/issues/450) | feat(web): pending sessions get the preview dashboard + queue banner | Web / Auth        | Merged; PR #453; closed on GH  |
| [#451](https://github.com/Leon-87-7/ownix/issues/451) | feat(jobs): flush held jobs to the queue on invite approval         | Jobs / Ops         | Merged; PR #453; closed on GH  |
| [#452](https://github.com/Leon-87-7/ownix/issues/452) | fix(telegram): invite waiting copy says links sent now are saved    | Telegram / Copy    | Merged; PR #453; closed on GH  |

---

## Needs Triage

|                                                   # | Title                                                                                       | Area             | Depends On |
| --------------------------------------------------: | ------------------------------------------------------------------------------------------- | ---------------- | ---------- |
| [#275](https://github.com/Leon-87-7/vig/issues/275) | tests/test_sheets.py: 6 tests fail on main — mocks predate _append_sync chat_id signature change (#264) | Tests / Sheets | —  |
| [#339](https://github.com/Leon-87-7/vig/issues/339) | Use Docker-internal ntfy URL for app publishing                                             | Ops / ntfy       | —          |
| [#340](https://github.com/Leon-87-7/vig/issues/340) | Expose ntfy configuration status at startup and in health output                            | Ops / ntfy       | —          |
| [#341](https://github.com/Leon-87-7/vig/issues/341) | Only throttle ntfy alerts after a confirmed publish                                         | Ops / ntfy       | —          |
| [#342](https://github.com/Leon-87-7/vig/issues/342) | Make worker heartbeat semantics explicit for single-worker topology                         | Ops / Worker     | —          |
| [#343](https://github.com/Leon-87-7/vig/issues/343) | Fix ntfy docs table duplication and URL terminology drift                                    | Docs / ntfy      | —          |
| [#344](https://github.com/Leon-87-7/vig/issues/344) | Make health degradation visible outside ntfy                                                | Ops / Health     | —          |
| [#345](https://github.com/Leon-87-7/vig/issues/345) | Add a manual ntfy smoke-test command or endpoint                                            | Ops / ntfy       | —          |
| [#346](https://github.com/Leon-87-7/vig/issues/346) | Send recovery notifications after degraded health returns to healthy                         | Ops / Health     | —          |
| [#347](https://github.com/Leon-87-7/vig/issues/347) | Harden startup alert ordering around ntfy readiness                                          | Ops / ntfy       | —          |
| [#348](https://github.com/Leon-87-7/vig/issues/348) | Add deployment-level ntfy verification docs                                                  | Docs / ntfy      | —          |
| [#366](https://github.com/Leon-87-7/vig/issues/366) | Next 16: replace removed next lint with ESLint flat config | Web / Next16 | — |
| [#367](https://github.com/Leon-87-7/vig/issues/367) | Next 16: rename middleware.ts -> proxy.ts | Web / Next16 | — |
| [#368](https://github.com/Leon-87-7/vig/issues/368) | Next 16: end-to-end verification + deploy check | Web / Next16 | — |
| [#352](https://github.com/Leon-87-7/vig/issues/352) | Auto-approve new users while keeping operator block controls | Auth / Access | — |
| [#398](https://github.com/Leon-87-7/ownix/issues/398) | feat: Freestyle button on job detail — run a custom prompt against any job | Web / Jobs | — |
| [#444](https://github.com/Leon-87-7/ownix/issues/444) | feat(web): permanent delete on the job details page | Web / Jobs | — |
| [#445](https://github.com/Leon-87-7/ownix/issues/445) | fix(worker): drop task envelopes whose job row is gone | Worker / Queue | #444 |
| [#446](https://github.com/Leon-87-7/ownix/issues/446) | feat(worker): job_purge — delete the job's Drive, GCS and Sheets artifacts | Purge / Cloud | #444 |
| [#457](https://github.com/Leon-87-7/ownix/issues/457) | refactor(brain): links.chat_id + backfill + owner-scoped ingest (per-tenant Second Brain) | Brain / Schema | — |
| [#458](https://github.com/Leon-87-7/ownix/issues/458) | feat(api): viewer-scoped Second Brain reads on the dashboard | API / Brain | #457 |
| [#459](https://github.com/Leon-87-7/ownix/issues/459) | feat(telegram): scope /find and /rebuild-graph to the sender's own Brain | Telegram / Brain | #457 |
| [#460](https://github.com/Leon-87-7/ownix/issues/460) | fix(brain): Brain Drive writes bypass the ADR-0030 Operator export gate | Brain / Drive | #457 |
| [#461](https://github.com/Leon-87-7/ownix/issues/461) | feat(web): restricted-mode Brain reads the Operator graph | Web / Restricted | #458 |
| [#481](https://github.com/Leon-87-7/ownix/issues/481) | Live intake card — poll job state and render it walking the FSM | Intake / Console | — |
| [#482](https://github.com/Leon-87-7/ownix/issues/482) | Parse #tag tokens in the intake router and attach existing tags | Intake / Router | — |
| [#483](https://github.com/Leon-87-7/ownix/issues/483) | Render the retry action on retryable intake errors | Intake / Console | — |
| [#484](https://github.com/Leon-87-7/ownix/issues/484) | Slash-command palette with argument hints | Intake / Commands | — |
| [#485](https://github.com/Leon-87-7/ownix/issues/485) | Migrate /find to shared intake commands | Intake / Commands | — |
| [#486](https://github.com/Leon-87-7/ownix/issues/486) | Migrate /force to shared intake commands | Intake / Commands | — |
| [#487](https://github.com/Leon-87-7/ownix/issues/487) | Migrate /freestyle to shared intake commands | Intake / Commands | — |
| [#488](https://github.com/Leon-87-7/ownix/issues/488) | Persist the intake thread in sessionStorage | Intake / Console | #481 |
| [#489](https://github.com/Leon-87-7/ownix/issues/489) | Offer inline tag creation when a #tag token is unknown | Intake / Tags | #482 |
| [#490](https://github.com/Leon-87-7/ownix/issues/490) | Tighten is_fetchable_url and add coerce_url | Links / Validators | — |
| [#491](https://github.com/Leon-87-7/ownix/issues/491) | Links outlive jobs — drop delete cascade, add ?with_links=1 | Links / Delete | — |
| [#492](https://github.com/Leon-87-7/ownix/issues/492) | Accept Netscape bookmark HTML end-to-end (empty import) | Bookmarks / Intake | — |
| [#493](https://github.com/Leon-87-7/ownix/issues/493) | _rewrite_existing_md must update_file, not upload_file | Brain / Drive | — |
| [#494](https://github.com/Leon-87-7/ownix/issues/494) | Batch link paste — textarea, client loop, progress | Links / Console | #490 |
| [#495](https://github.com/Leon-87-7/ownix/issues/495) | Parse and insert links, skip existing (snapshot ingest) | Bookmarks / Parser | #490, #492 |
| [#496](https://github.com/Leon-87-7/ownix/issues/496) | Deferred import-scoped enrichment pass | Bookmarks / Brain | #495 |
| [#497](https://github.com/Leon-87-7/ownix/issues/497) | Folder-to-tag opt-in form | Bookmarks / Tags | #495 |
| [#505](https://github.com/Leon-87-7/ownix/issues/505) | Extract shared CopyButton component | Web / Jobs | — |
| [#506](https://github.com/Leon-87-7/ownix/issues/506) | Telegram /checklists command delivery | Telegram | — |
| [#507](https://github.com/Leon-87-7/ownix/issues/507) | Dashboard job detail: generate & display checklists | Web / Jobs | #505 |
| [#508](https://github.com/Leon-87-7/ownix/issues/508) | Intake response card: copy button for checklists results | Web / Intake | #505 |

---

## Ready for Agent

Ordered by unblocked-first, then dependency chain.

|                                                   # | Title                                                                                            | Area                     | Depends On       |
| --------------------------------------------------: | ------------------------------------------------------------------------------------------------ | ------------------------ | ---------------- |
| [#317](https://github.com/Leon-87-7/vig/issues/317) | fix(telegram): .md documents preview as mojibake (â€”) — UTF-8 BOM + strip Gemini em-dashes       | Telegram / Gemini        | —                |
| [#414](https://github.com/Leon-87-7/ownix/issues/414) | test_sheets_append_short_row fails: export_blocked() not mocked | Tests / Sheets | — |
| [#466](https://github.com/Leon-87-7/ownix/issues/466) | Sidecar: /metadata exposes duration; _detect_platform reports real extractor keys | Sidecar / Transcript | — |
| [#467](https://github.com/Leon-87-7/ownix/issues/467) | Route Facebook + X as `unsized`, resolve short/long by duration in the worker | Worker / Validators | #466 |
| [#468](https://github.com/Leon-87-7/ownix/issues/468) | Feed thumbnails for Facebook and X jobs | Feed / Thumbnails | #466 |
| [#469](https://github.com/Leon-87-7/ownix/issues/469) | Update bot help copy to advertise Facebook + X support | Telegram / Copy | #467 |
| [#472](https://github.com/Leon-87-7/ownix/issues/472) | Dashboard Intake MVP — /intake URL submit through create_and_enqueue_job() | Web / Intake | — |
| [#473](https://github.com/Leon-87-7/ownix/issues/473) | Shared channel-neutral intake router + versioned contract | Intake / Router | #472 |
| [#474](https://github.com/Leon-87-7/ownix/issues/474) | Dashboard conversational intake state (intent / freestyle) with expiry sweeper | Intake / State | #473 |
| [#475](https://github.com/Leon-87-7/ownix/issues/475) | Dashboard intake files + inline actions (upload caps, idempotent actions) | Intake / Uploads | #473 |
| [#476](https://github.com/Leon-87-7/ownix/issues/476) | Move PWA share target from Feed prefill to /intake/share | Web / PWA | #472 |
| [#477](https://github.com/Leon-87-7/ownix/issues/477) | Refactor Telegram webhook into an intake-router adapter | Telegram / Intake | #473 |
| [#478](https://github.com/Leon-87-7/ownix/issues/478) | Chrome extension MVP — capture current tab / context-menu links into Ownix Intake | Extension | #472 |
| [#479](https://github.com/Leon-87-7/ownix/issues/479) | Production-safe Chrome extension auth via one-time pairing tokens | Extension / Auth | #478 |

---

## Ready for Human

|                                                   # | Title                                                                                     | Area               | Notes                                                  |
| --------------------------------------------------: | ------------------------------------------------------------------------------------------ | ------------------ | ------------------------------------------------------ |
| [#413](https://github.com/Leon-87-7/ownix/issues/413) | SSRF: pin resolved IP / validate redirects for transcript_server.py fetch path | Security / Transcript | Agent brief posted; needs a human tradeoff call (disable redirects vs re-validate each hop) across yt-dlp + youtube-transcript-api before an agent implements |

---

## Dependency Map

```
#1 Scaffold ✅-Done
├── #2 Short pipeline ✅-Done
│   └── #8 Short brain backfill ✅-Done
├── #3 Long Phase 1 ✅-Done
│   ├── #4 Long Phase 2 ✅-Done
│   └── #9 Long brain backfill ✅-Done
└── #5 Second Brain ✅-Done
    ├── #8 ✅-Done
    ├── #9 ✅-Done
    ├── #11 Photo link extraction ✅-Done
    │   ├── #21 GitHub service + cache ✅-Done
    │   │   └── #22 Photo pipeline wiring (repo enrichment) ✅-Done
    ├── #6 Mini-PRD auto ✅-Done
    │   └── #7 Mini-PRD intent ✅-Done
    │       └── #13 Enrichment retry button ✅-Done
    └── (feeds #4 via URL-resolution)

#10 BotFather ✅-Done
#15 Transcript sidecar TikTok/Instagram ✅-Done
#16 Template system parent ✅-Done
    ├── #17 Template data layer ✅-Done
    └── #18 Template handler layer ✅-Done
        └── #32 Audio fallback for caption-less Reels (ADR-0009) ✅-Done

#23 GeminiClient core ✅-Done
└── #26 GeminiClient migrate remaining callers ✅-Done

#24 PRD skeleton unification ✅-Done

#25 Webhook callback dispatch table ✅-Done
└── #27 Webhook slash dispatch table ✅-Done

#37 Slimming sweep — dedup ID gen / links formatter / EMBEDDING_DIM ✅-Done (slimming-doc #3/#4/#5)
#38 Unify template-matching tables ✅-Done
#39 Collapse Gemini service triplet → ADR-0011 ✅-Done (PR #49)

#33 Promise-gap extraction ✅-Done
└── #34 Promise-gap Telegram render ✅-Done (needs #33)

#35 Orphaned-job reaper (ADR-0010) ✅-Done
#36 Photo UI-chrome filter (ADR-0005) ✅-Done (PR #48)
└── #46 _filter_grounded_links UI-chrome dup ✅-Done (closed as dup of #36)

— fix: phantom status filter (find_recent_job_by_url) ✅-Done (no issue; committed directly)

#41 add set_prd_slot_status ✅-Done
#42 move links DDL into database.py ✅-Done
#43 PRAGMA user_version migrations ✅-Done (best after #42)
#47 short_video ignored_domains missing in tests ✅-Done (PR #50)

#51 jobs.freestyle_prompt column ✅-Done
└── #52 enrichment freestyle substitution ✅-Done
    └── #53 template picker keyboard (ADR-0012) ✅-Done
        └── #54 /freestyle slash command ✅-Done

— /find UX (GitHub enrichment, full URL path, score floor) ✅-Done
— plain-text command shortcut (first word → _SLASH_TABLE) ✅-Done

Article URL feature (postgrill: docs/features/postgrill/article-url-feature.md)
#59 Sheets consolidation (ADR-0013) ─────────┐
                                             │
#60 Jina + markdown_cache + /download_md ────┼──► #62 Article pipeline end-to-end ✅-Done
                                             │
#61 Article allowlist CRUD ──────────────────┘
(all four closed)

Repo URL feature (postgrill: docs/features/postgrill/repo-url-feature.md + ADR-0014)
#66 URL routing + stub ✅-Done
└── #67 bundle + cache + README preprocessing + /force ✅-Done (PR #80)
    └── #68 Gemini analysis + summary ✅-Done ──┬── #69 document delivery ✅-Done
                                          ├── #70 Sheets persistence ✅-Done ──┐
                                          ├── #71 brain ingest ✅-Done         │
                                          ├── #72 edge cases ✅-Done           │
                                          └── #73 freestyle re-run ✅-Done ◄───┘
                                                (also depends on #70)

#118 feat(github+repo): topics field, v2 cache key, _prioritize_tree helper ✅-Done (PR #120)
#119 feat(repo): improve _build_repo_prompt ✅-Done (PR #120)

webhook.py split (ADR-0015) — ✗ WONTFIX 2026-06-07 (#75–#79 closed not-planned; superseded by #130 CC-reduction on single-file webhook.py)

Web dashboard feature (postgrill: docs/features/postgrill/web-plan.md + ADR-0016..0019)
#81 ignored_domains per-chat migration (tenancy drift) ✅-Done
└── (45edd0d; prerequisite for /controls Ignored tab)

Web dashboard slices (WEB-PRD: docs/seed/WEB-PRD.md)
Critical path: #83 → #84 → {#85, #86, #87} → #88/#89 → #93 → #95

#83 S0 — API package split + FK enforcement ✅-Done
└── #84 S1 — Auth spine [HITL] ✅-Done
    ├── #85 S2 — Feed ✅-Done
    │   └── #89 S6 — Spaces CRUD + URLs tab ✅-Done ◄── also #84
    │       └── #93 S7 — Context blobs ✅-Done ◄── also #88
    │           └── #95 S8 — Space export ✅-Done ◄── also #87, #88
    ├── #86 S3 — Job detail ✅-Done
    │   └── #88 S5 — Job annotation ✅-Done ◄── also #87
    ├── #87 S4 — Controls Tags tab ✅-Done
    ├── #90 S9 — User templates ✅-Done ◄── also #83
    ├── #91 S10 — Controls Allowed/Ignored ✅-Done ◄── also #81
    ├── #92 S11 — Brain search page ✅-Done ◄── also #83
    └── #94 S12 — Deploy [HITL] ✅-Done

#96 Templates IDOR fix (tenant-scope templates table) ✅-Done (commit 93ad9f0)

#82 test(long_video) under-mocked send_message → coroutine in editMessageText — ✅-Done (closed COMPLETED on GH; superseded earlier ✗ WONTFIX 2026-06-07; still carries wontfix label)

Web complexity reduction (fallow health — CRAP scores; all independent, no blockers)
#129 refactor(fetch-utils) — flatten mapFetchState + shared fetchJson<T> ✅-Done (PR #134)
#121 refactor(feed) — useFeedData + useFuseSearch + polling hook ✅-Done (PR #134)        (CRAP 506 → ~30)
#122 refactor(spaces/detail) — 4 hooks + UrlsTab + ContextTab split ✅-Done (PR #134)     (CRAP 420 → ~60)
#123 refactor(job/detail) — useJobDetail + useJobAnnotation + useJobTags ✅-Done (PR #134) (CRAP 272 → ~40)
#124 refactor(controls) — useTagList + useDomainList ✅-Done (PR #134)                     (CRAP 110 → ~30)
#125 refactor(spaces/list) — useSpaceList + useCreateSpace ✅-Done (PR #134)               (CRAP 110 → ~30)
#126 refactor(export-modal) — useGdocExport + flatten handleGdoc ✅-Done (PR #134)         (CRAP 110 → ~25)
#127 refactor(prompts) — useTemplateList + slim UserTemplateRow ✅-Done (PR #134)          (CRAP 72 → ~25)
#128 refactor(brain) — useSemanticSearch ✅-Done (PR #134)                                 (CRAP 72 → ~25)
Note: #129 synergizes with #121–#128 (fetchJson<T> replaces repeated fetch boilerplate)

ADR-0020: Guaranteed transcript on every short job (docs/adr/0020-always-transcript-short-pipeline.md)
#32 Audio fallback for caption-less Reels ✅-Done ◄── pre-existing foundation
└── #101 transcribe_audio + enrich_audio returns transcript text ✅-Done (dbdcd40)
    └── #102 guaranteed transcript acquisition on all short jobs ✅-Done ◄── also #32
        └── #103 transcript Drive upload + Telegram document delivery tail ✅-Done
Critical path: #101 → #102 → #103 (all ✅-Done)

Short pipeline transcript series (PR #113)
#97 caption-based job always produces a transcript ✅-Done
#98 caption-less plain job transcribes via Gemini ✅-Done
#99 caption-less template job persists transcript from fused enrich_audio ✅-Done
#100 explicit transcript-failure taxonomy ✅-Done

Photo batch feature (ADR-0024: docs/adr/0024-photo-batch-media-group-debounce.md)
#136 Remove Quick Links section from build_enriched_links_message (independent) ✅-Done
#137 media_group_id debounce — replace /photoBatch-start /photoBatch-end (independent) ✅-Done
Critical path: #136 and #137 are parallel — no dependency between them

pyscn health refactors (.pyscn report 2026-06-07 — Health 47/100; Duplication 0, Complexity 45)
All independent — no blockers, all AFK, behavior-preserving (existing suite stays green).
#130 refactor(webhook) — extract _route_url + _handle_user_template_shortcut + chat-state helper (CC 32 → <12) ✅-Done
     (replaces the parked #75–#79 webhook split; works on current single-file webhook.py)
#132 refactor(database) — _execute/_execute_rowcount/_fetch_one/_fetch_all; collapse clone Group 38 (13 clones) ✅-Done
#131 refactor(short_video) — extract _acquire_transcript; flatten run() (CC 27, depth 6) ✅-Done
#133 refactor(brain) — extract _select_refresh_batch + _refresh_one_link; flatten refresh_stale_links (CC 24) ✅-Done

Feed tab redesign + server-resolved thumbnails (ADR-0025 — grill session 2026-06-13)
Phase 1 (frontend + thin backend resolver, no migration):
#142 content-type tabs replace feed filter bar ✅-Done (PR #149)
#143 server-resolved thumbnail_url on /api/jobs ✅-Done (PR #149)
└── #144 preview-card grid for typed feed tabs ✅-Done (PR #149) ◄── #142, #143
    ├── #146 persist short best frame as job thumbnail (Phase 2) ✅-Done (PR #149)
    └── #147 scrape article og:image as job thumbnail (Phase 2) ✅-Done (PR #149)
        └── #148 one-shot og:image backfill script ✅-Done (PR #149)
#145 brand-icon badges in All-tab feed rows ✅-Done (PR #149) ◄── #142
Critical path: #142/#143 → #144 → #146/#147 → #148 (all ✅-Done)

Document pipeline (ADR-0023: docs/adr/0023-liteparse-document-pipeline.md + docs/roadmap.md)
#150 GCS content-addressed storage seam (root) ✅-Done (PR #182)
├── #151 Telegram file upload ingestion ✅-Done (PR #182)
├── #152 Direct document URL routing ✅-Done (PR #182)
└── #153 vig-document liteparse sidecar ✅-Done (PR #182)
    └── #154 parse cache + automatic Gemini enrichment ◄── also #151, #152 ✅-Done (PR #182)
        ├── #155 plain text + enrichment Telegram delivery ✅-Done (PR #182)
        │   ├── #156 on-demand Markdown rendering ✅-Done (PR #200) ◄── also #154
        │   └── #157 Freestyle re-runs from cached parse ✅-Done (PR #200) ◄── also #154
        └── #158 opt-in Document Analysis export hook ✅-Done (PR #200)
Critical path: #150 → {#151, #152, #153} → #154 → #155 → {#156, #157}; #158 can follow #154 in parallel
(#150–#158 ✅-Done; #150–#155 via PR #182, #156/#157/#158 via PR #200)

Short-thumbnail backfill (docs/backfill_agreed_plan.md — ADR-0025 Phase-2 follow-up)
#159 core script (happy path) ✅-Done (PR #149)
├── #161 frame-selection strategies (rerun-vision, fallbacks) ✅-Done
└── #162 --overwrite-existing clobber-safety flag ✅-Done
#160 ADR-0025 follow-up note (independent — doc only) ✅-Done
Critical path: #159 → {#161, #162}; #160 parallel (all ✅-Done)

Feed/detail bug fixes (docs/bugs/2026-06-15-*.md)
#164 short-pipeline detail pages populate (independent) ✅-Done (PR #172)
#165 feed fetch-race guard (independent) ✅-Done (PR #173)
└── #166 tab-scoped Overview stat cards ◄── #165 ✅-Done (PR #173)
Critical path: #165 → #166; #164 parallel (all ✅-Done)

Dashboard recovery panel (ADR-0026)
#167 recovery summary + panel shell ✅-Done (PR #174)
├── #168 retry stale pending jobs ✅-Done
├── #169 retry failed jobs + tenant-scoped stale reaping ✅-Done
│   └── #171 Controls opt-out for recovery Telegram notifications ✅-Done
└── #170 clear failed jobs as cancelled ✅-Done
Critical path: #167 → {#168, #169, #170}; #171 follows #169 (all ✅-Done)

Feed freshness + keep-warm (PR #178)
#175 client-side feed filtering (preload + instant filters) ✅-Done
#176 keep-warm ping — eliminate API cold-start spike ✅-Done
#177 silent background freshness (focus-refetch + backstop poll) ✅-Done
Critical path: #175, #176, #177 are independent — no dependency between them (all ✅-Done)

UI/UX makeover (source: docs/todo-notes.md — impeccable shape briefs 2026-06-20)
#185 mobile inline stats row (T/D/P/E) — independent ✅-Done (PR #193)
#186 wrap content-type tabs — independent ✅-Done (PR #193)
#187 collapse recovery + status filters on mobile — independent ✅-Done (PR #193)
#188 scroll-to-top button — independent ✅-Done (PR #193)
#189 add icon column to spaces table — independent (root) ✅-Done (PR #193)
├── #190 redesign space cards with icon + color wash + inline delete ✅-Done (PR #193)
└── #191 icon picker on space create/edit ✅-Done (PR #193)
#192 enlarge mobile back-link on job detail — independent ✅-Done (PR #193)
Critical path: #189 → {#190, #191}; all others independent (all ✅-Done)

Brain graph map (grill 2026-06-21 — ADR-0027, ADR-0028; CONTEXT.md Brain graph)
— ✗ WONTFIX 2026-06-25: implementation set shelved after the plan (PR #199 merged). #194–#198 closed not-planned.
#194 graph endpoint + desktop 2D render (root) — ✗ WONTFIX
#196 graph search highlight ◄── #194 — ✗ WONTFIX
#197 mobile ego-network view — ✗ WONTFIX 2026-06-21
#198 repo-node metadata refresh (stars/pushed_at) ◄── #194 — ✗ WONTFIX
#195 normalized-URL dedup (independent) — ✗ WONTFIX

Short titles + Links Found (grill 2026-06-23)
#211 vision-harvested short titles (independent) — title field on existing vision pass, no 2nd Gemini call ✅-Done (PR #215)
#212 remove key_phrases end-to-end (independent) — template enrichment untouched ✅-Done (PR #215)
└── #213 Links Found detail section (clickable) ◄── #212 (takes over the detail-section slot key_phrases vacates) ✅-Done (PR #215)
Critical path: #211 parallel; #212 → #213 (all ✅-Done)

Doc Parser dashboard page (ADR-0029: docs/adr/0029-doc-parser-dashboard-page.md) — all ✅-Done (PR #227; #231 via PR #232; #228 via PR #229; #240 via PR #242)
#217 upload API + telegram_delivery column (root) ✅-Done
├── #219 Gemini structured summary + enriched GCS storage ✅-Done
│   └── #221 on-demand clean + freestyle endpoints ✅-Done
│       └── #225 detail page + output cards ◄── also #223, #224 ✅-Done
│           └── #226 freestyle modal with random + saved prompts ✅-Done
├── #220 SSE endpoint for document job status ✅-Done
│   └── #223 job list + SSE real-time updates ◄── also #218 ✅-Done
├── #222 upload zone — URL input + file dropzone ◄── also #218 ✅-Done
└── #224 three-state Telegram toggle component ✅-Done
#218 page shell + sidebar entry (root, independent of #217) ✅-Done
Critical path: #217 → #219 → #221 → #225 → #226 (all ✅-Done)

Tooltip system (spec: docs/superpowers/specs/2026-06-28-tooltips-design.md) — Radix Tooltip primitive, replace all native title= + extend coverage
#243 Tooltip primitive + first adoption (foundation, root) ✅-Done (PR #248)
├── #244 migrate explanatory title= ◄── #243 ✅-Done (PR #248)
├── #245 migrate overflow-reveal title= (mono) ◄── #243 ✅-Done (PR #248)
├── #246 add tooltips to icon-only controls ◄── #243 ✅-Done (PR #248)
└── #247 add tooltips to metric labels (stats-overview) ◄── #243 ✅-Done (PR #248)
Critical path: #243 → {#244, #245, #246, #247} (all ✅-Done)

Brain Links nav + graph controls (grill 2026-06-29 — tasks #7/#8 from docs/TASK.md)
#238 Extracted-links table on the Brain page ✅-Done (PR #239) — foundation the nav builds on
#251 Links table — server-side sort params + per-tenant user_settings view + jump-to-page/page-size ✅-Done (PR #257)
#252 Brain graph on-canvas controls — zoom/fit/recenter + focus-on-match + topic legend/filter (desktop-only) ✅-Done (PR #260)
Critical path: #251 and #252 are independent — no dependency between them

Per-user export isolation (epic #201; ADR-0030 + ADR-0022; CONTEXT.md `Operator`)
#202 operator-only export gate (the "now" fix — root, unblocked) ✅-Done (PR #208) ◄── also gates #158
└── #204 per-user "Connect Google" (web): encrypted token store → /vig ✅-Done (PR #264) ◄── also #203
    ├── #205 Telegram Mini App surface (initData → shared OAuth backend) ✅-Done (PR #264)
    └── #206 connection lifecycle (invalid_grant / /disconnect / notify-once) ✅-Done (PR #264)
#203 Google Cloud OAuth app: prod publish + sensitive-scope verification (HITL/external — gates #204 for production) ✅-Done
Critical path: #202 → #204 → {#205, #206}; #203 (external review) gates #204 production readiness

Council fixes chunk 2 — event loop + shim deletion + React race/cleanup batch (docs/superpowers/council/sub-plans/main-council-fixes-chunk2-backend-and-react.md)
#276 export_blocked async (event-loop fix) ✅-Done (PR #282)
#277 delete GeminiClient passthrough shim ✅-Done (PR #282)
#278 CopyButton reset-timer cleanup (jobs detail) ✅-Done (PR #282)
#279 space-delete failure surfacing ✅-Done (PR #282)
#280 Connect Google button-signal spec alignment ✅-Done (PR #282)
#281 Doc Parser loading skeleton + empty state ✅-Done (PR #282)
Critical path: #276, #277, #278, #279, #280, #281 are all independent — no dependency between them

Council fixes chunk 3 — admin-contact copy, decorative-signal removal, timeouts, dead code (docs/superpowers/council/sub-plans/main-council-fixes-chunk3-copy-and-hygiene.md)
#283 configurable ADMIN_CONTACT_NAME replaces hardcoded 'Leon' (webhook + invite-gate) ✅-Done (PR #298)
#284 drop decorative signal-orange accents (logout glow, doc-parser Sparkles) ✅-Done (PR #298)
#285 Jina fetch_markdown — explicit 30s httpx timeout ✅-Done (PR #298)
#286 delete unused _DETAIL_FIELDS tuple ✅-Done (PR #298)
#287 normalize_repo_url — explicit ValueError guard instead of unguarded IndexError ✅-Done (PR #298)
Critical path: #283, #284, #285, #286, #287 are all independent — no dependency between them
(Task 21/APScheduler→asyncio sleep-loop skipped per user decision — kept APScheduler, no issue filed)

Council fixes chunk 4 — eyebrow sweep, tabs hoisting, background-task tracking, scoping docs (docs/superpowers/council/sub-plans/main-council-fixes-chunk4-design-and-tasks.md)
#288 drop banned uppercase-tracked eyebrow labels per DESIGN.md ✅-Done (PR #299)
#289 hoist SegmentedTabs/FilterBar tab definitions to stable references ✅-Done (PR #299)
#290 retain strong references to fire-and-forget asyncio tasks ✅-Done (PR #299)
#291 document context-blob + brain-endpoint ownership-scoping decisions (confirmed: single shared graph, not per-user — future marketing point for Brain page + public home page, docs/TASK.md §14) ✅-Done (PR #299)
Critical path: #288, #289, #290, #291 are all independent — no dependency between them
(Task 27/HKDF key derivation skipped per user decision — not an active vulnerability, no issue filed)

Council fixes chunk 5 — spinner→skeleton conversion, webhook callback gate + copy sweep (docs/superpowers/council/sub-plans/main-council-fixes-chunk5-skeletons-and-webhook.md)
#300 replace in-content spinners with content-shaped skeletons (web — independent) ✅-Done (PR #304)
#301 skip invite-gate email-parsing branch on callback button presses (via_callback) ✅-Done (PR #304)
└── #302 message-copy hygiene sweep ◄── #301 (same-file ordering, not a logical dependency — one agent does 23→24 on webhook.py) ✅-Done (PR #304)
Critical path: #301 → #302; #300 parallel (all ✅-Done)

Account affordance — Google connection + Telegram identity (grill 2026-07-02 — task #17 from docs/TASK.md; CONTEXT.md `Account affordance`)
#292 session-user context + sidebar identity row (root) ✅-Done ──┐
                                                                 ├──► #295 sidebar Google-connection state ✅-Done
#293 Google-status provider + Feed disconnected-only nudge ✅-Done ┘
#294 OAuth-return one-time banner (independent) ✅-Done
Critical path: {#292, #293} → #295; #294 parallel (all ✅-Done via PR #296)

Sidebar footer + Brain Links + job navigation (grill 2026-07-03 — tasks #7/#10/#15/#18/#20 from docs/TASK.md)
#305 Links table — truncate & expand title · topic description (root) ✅-Done (PR #316)
└── #306 Links table — mobile TableCard stacked layout ◄── #305 ✅-Done (PR #316)
#307 Sidebar Terms/Privacy links + Sign out icon (independent) ✅-Done (PR #316)
#308 Sidebar Google-connect row redesign (independent) ✅-Done (PR #316)
#309 Job details previous/next navigation (independent) ✅-Done (PR #316)
#310 Feed Docs tab → Doc Parser (independent) ✅-Done (PR #316)
Critical path: #305 → #306; #307, #308, #309, #310 are independent — no dependency between them (all ✅-Done via PR #316)

Repo analysis "more informational" (job 20260703_211658 review 2026-07-04 — prompt tweaks driven from GoogleCloudPlatform/knowledge-catalog output)
#311 sub-project READMEs into repo bundle (independent) ✅-Done (PR #315) ◄── extends #67 bundle ✅
#312 key_components schema field + rendering (root) ✅-Done (PR #315)
└── #314 prompt field-guidance tightening ◄── #312 (same region of repo.py — conflict-avoidance ordering, not logical) ✅-Done (PR #315)
#313 job detail raw-JSON render fix (web — independent) ✅-Done (PR #315)
Critical path: #312 → #314; #311, #313 parallel (all ✅-Done via PR #315)

Dashboard job submission + repo follow-up (grill 2026-07-04 — tasks #4/#9 from docs/TASK.md; ADR-0032, ADR-0033)
#318 Shared job-creation core (root, unblocked) ✅-Done
├── #319 POST /api/jobs endpoint ◄── #318 ✅-Done
│   └── #320 Feed page submit UI ◄── #319 ✅-Done
└── #321 Repo follow-up: short pipeline ◄── #318 ✅-Done
    ├── #322 Repo follow-up: article pipeline ◄── #321 ✅-Done
    └── #323 Repo follow-up: long-video pipeline ◄── #321 ✅-Done
Critical path: #318 → {#319, #321}; #319 → #320; #321 → {#322, #323} (all ✅-Done via PR #324)

Public landing page (grill 2026-07-06 — task #14 from docs/TASK.md)
#329 Routing cutover — Feed→/feed, / public + auth-redirect (root, unblocked) ✅-Done
└── #331 BrandBackground extraction + full marketing landing + /login back-link ◄── #329 ✅-Done
    └── #332 staged dashboard screenshots ◄── #331
#330 Limited Use disclosure on /privacy (independent) ✅-Done
Critical path: #329 → #331 → #332; #330 parallel

Feed inventory IA — Links view, Docs ingest action, command launcher (task #24 from docs/TASK.md)
#333 Feed tabs: rename Feed and move Links into Feed (root, unblocked) ✅-Done (PR #337)
#334 Docs ingest modal from Feed actions (independent) ✅-Done (PR #337)
├── #335 Desktop Commands launcher for Feed actions ◄── also #333 ✅-Done (PR #337)
│   └── #336 Move Links inventory API to Feed namespace last ◄── also #333 ✅-Done (PR #337)
Critical path: {#333, #334} → #335 → #336 (all ✅-Done via PR #337)

Restricted mode preview (source: docs/handoff/restricted-mode-preview.md — ADR-0035; CONTEXT.md Restricted mode)
#353 preview data plane — read-only preview endpoints + diversified corpus (root, backend) ✅-Done
└── #354 entry — session-aware landing + ownix_preview cookie + read-only Feed ◄── also #329 (routing cutover, merged) ✅-Done
    ├── #355 chrome — shared state + AppHeader banner + global toast + blocked actions ✅-Done
    │   ├── #356 Feed intro modal (once per browser session) ✅-Done
    │   └── #357 sidebar persistence + read-only page facades (Docs/Collections/Recipes/Settings) ✅-Done
    └── #358 login access sequence + locked Connect Google ✅-Done
Critical path: #353 → #354 → #355 → {#356, #357}; #358 follows #354 in parallel
Follow-up (out of scope): #352 auto-approve new users — separate access-policy change, not part of this preview

Ops bot + dev-login e2e (source: grill 2026-07-16; CONTEXT.md `Ops bot`, `Dev login`)
#374 Ops bot foundation: settings, allowlists, sender, startup webhook registration ✅-Done
├── #375 Invite approvals move to Ops bot with admin-only callbacks ✅-Done
│   └── #378 Dev login stays quiet by default, with explicit Ops bot e2e mode ✅-Done
│       └── #379 Ngrok-assisted local Ops e2e helper ◄── also #374 ✅-Done
└── #376 Ops bot read-only user queue commands ✅-Done
    └── #377 Domain-scoped batch approval with confirmation ◄── also #374 ✅-Done
Critical path: #374 → #375 → #378 → #379; #374 → #376 → #377 parallel

Standalone link identity + link tags (source: docs/TASK.md tasks 30 & 32 — grill 2026-07-17; CONTEXT.md `Standalone link identity`, `Link tag`)
#381 links.description via tiered resolver (GitHub svc → meta parse → Jina) ✅-Done
└── #384 search + embedding cutover to url/title/description ✅-Done
    └── #385 backfill via refresh-loop repair (re-resolve + re-embed) ✅-Done
#382 link_tags schema + attach/detach API + dot-cluster TagMenu trigger ✅-Done
├── #386 optional tag icons (tags.icon + Lucide picker) ✅-Done
└── #387 Links search box matches tag names exactly ✅-Done
#383 global tag palette redesign — parallel, no dependency ✅-Done
Critical path: #381 → #384 → #385; #382 → {#386, #387} independent chain; #383 parallel

Ownix mobile onboarding hero (source: docs/plans/2026-07-17-ownix-mobile-onboarding-hero.md — ADR-0037) — ✗ WONTFIX 2026-08-01: Rive storyboard/mini-game approach abandoned; superseded by ADR-0044's scroll-driven onboarding stepper (already shipped). #391–#395 closed not-planned.
#391 landing restructure: storyboard shell replaces demo video in place; recording → later #demo — ✗ WONTFIX
└── #392 storyboard orchestration with placeholder scenes + Vitest coverage — ✗ WONTFIX
    └── #393 Rive runtime integration with one test scene — ✗ WONTFIX
        └── #394 author the seven onboarding Rive scenes (HITL) — ✗ WONTFIX
            └── #395 copy, timing polish, and verification pass (HITL) — ✗ WONTFIX
Critical path: n/a — shelved

Security review — input validation & authz findings (source: pasted findings table, 2026-07-21)
#402 validators: http/https scheme + exact host match + domain normalization — independent ✅-Done
#403 telegram: chat_id ownership check on job callbacks (IDOR) — independent ✅-Done
#404 transcript-service: SSRF guards + auth + parameter bounds — independent ✅-Done
#405 api: length/size bounds on unbounded text fields — independent ✅-Done
#406 telegram: /download_md URL validation — independent ✅-Done
#407 api: reject whitespace-only names — independent ✅-Done
#408 api: sort_order bounds on reorder — independent ✅-Done
#409 api: constrain tag icon to fixed set — independent ✅-Done
#410 ops-bot: escape SQL LIKE wildcards in /users email — independent ✅-Done
Critical path: none — all nine are independent, no dependency between them

Link pipeline — direct-add URLs to the Second Brain (grill 2026-07-22 — ADR-0039; CONTEXT.md `Link pipeline`, `Essential OG collection`)
#415 link pipeline core + /addlink command (root, unblocked) ✅-Done
├── #416 Add Link modal (U shortcut) ◄── #415 ✅-Done
└── #417 Feed content-type support for link jobs ◄── #415 ✅-Done
Critical path: #415 → {#416, #417}

Mobile Feed intake sheet — BadgePlus launcher for the three ingests (grill 2026-07-23 — ADR-0040; CONTEXT.md `Link pipeline`)
#419 shared INTAKE_ACTIONS + "Ingest Link" rename + bottom-sheet launcher replacing the mobile Submit/Docs chips (independent) ◄── relates to #416 Ingest Link modal ✅-Done
Critical path: none — single independent slice

Installable PWA (grill 2026-07-23 — task #6 from docs/TASK.md)
#421 PWA installability — manifest start_url /feed + id (root, unblocked) ✅-Done
└── #423 share-target intake — manifest share_target → Submit URL dialog prefill ◄── #421 (share sheet lists installed PWAs only) ✅-Done
#422 offline fallback — /offline page + hand-rolled sw.js (independent) ✅-Done
Critical path: #421 → #423; #422 parallel

Thumbnail cache-header fix (ADR-0025 follow-up — /grill-with-docs session 2026-07-26)
#436 fix(api): cache job thumbnail responses (ETag + Cache-Control) — independent, no blockers ✅-Done

Feed thumbnail preload — <300ms first thumbnails (grill-with-docs 2026-07-27 — ADR-0041; CONTEXT.md `Feed thumbnail preload`)
#441 eager-load the first 10 preview cards (root, unblocked) ✅-Done
└── #442 thumbnail preload SSR head start ◄── #441 (preloads consumed only once the first-10 imgs are eager) ✅-Done
#443 extend stored thumbnail cache to 30 days (independent) ◄── also #436 (builds on the merged cache helper) ✅-Done
Critical path: #441 → #442; #443 parallel

Job delete + cloud purge (docs/TASK.md task 33 — grill-with-docs 2026-07-27; ADR-0042; CONTEXT.md `Job delete` / `Job purge`, invariants 14–15)
#444 permanent delete on the job details page (root, unblocked — owns DELETE /api/jobs/{id}, the links de-index, and ui/confirm-dialog.tsx)
├── #445 drop task envelopes whose job row is gone (needs a delete to race against)
└── #446 job_purge — Drive, GCS and Sheets artifacts (extends the same endpoint with the async half)
Critical path: #444 → {#445, #446}
Note: task 19 (full delete surface — cards, swipe, Telegram message deletion) builds on #444's endpoint and confirm dialog; not yet broken into issues.

Streamline new-user signup — pending is a preview, not a wall (docs/TASK.md task 29 — grilled 2026-07-23, re-grounded 2026-07-28)
#449 hold a pending user's links as un-enqueued 'held' jobs (root, unblocked — owns the jobs.status CHECK rebuild and the FSM note) ✅-Done
├── #451 flush held jobs to the queue on invite approval (both approve paths share one helper) ✅-Done
└── #452 invite waiting copy says links sent now are saved (only true once #449 lands) ✅-Done
#450 pending sessions get the preview dashboard + queue banner (independent — reuses the ADR-0035 restricted plane) ✅-Done
Critical path: #449 → {#451, #452}; #450 parallel
Note: web-side submission for pending users and the INVITE_AUTO_APPROVE flag are deliberately out of scope; #352 (auto-approve) is the related open idea.

Per-tenant Second Brain (docs/TASK.md task 11 session 2 — grill-with-docs 2026-07-31; ADR-0043; CONTEXT.md `Second Brain`)
#457 links.chat_id + backfill + owner-scoped ingest (root, unblocked — owns the migration, the COALESCE backfill, and the ingest reuse SELECT) [HITL]
├── #458 viewer-scoped Brain reads on the dashboard (list/search/graph/preview + the get_link_preview IDOR)
│   └── #461 restricted-mode Brain reads the Operator graph (needs scoped reads to exist before it can name an owner; supersedes ADR-0035 line 81)
├── #459 scope /find and /rebuild-graph to the sender (Telegram half of #458, ships independently)
└── #460 Brain Drive writes obey the ADR-0030 export gate (needs per-row chat_id so aggregates stop relying on export_blocked(None))
Critical path: #457 → #458 → #461; {#459, #460} parallel off #457
Note: #457 is HITL — the backfill runs against live data and aborts if OPERATOR_CHAT_ID is unset while the 137 orphan rows exist. Community Brain + Sharer window are deliberately split out of task 11 and not yet broken into issues.

Unsized video hosts (docs/TASK.md task 34 — grill-with-search-docs 2026-08-01; ADR-0045; CONTEXT.md `Unsized video` + invariant 17)
#466 Sidecar /metadata exposes duration + _detect_platform returns real extractor keys (root, unblocked)
├── #467 Route facebook.com + x.com/twitter.com as `unsized`; worker resolves short/long on the 180s boundary
│   └── #469 Help-copy sweep — advertise the new hosts (must not ship before support exists)
└── #468 Feed thumbnails for FB/X (allowlist 2→4 entries; needs real platform strings from #466)
Critical path: #466 → #467 → #469; #468 parallel off #466
Note: the #466 dependency is on DEPLOYMENT, not merge — transcript_server.py ships in its own image (Dockerfile.transcript) as the transcript-service container. Against a stale sidecar #467 fails silently into the default-to-short path. Vimeo is deliberately excluded (every anonymous yt-dlp route is auth-walled — Vimeo revoked the app credential yt-dlp impersonates, error_code 8001) and Twitch was dropped as not relevant; both live in docs/TASK.md Inbox.

Ownix Intake channels — dashboard, extension, share sheet (docs/plans/2026-08-03-ownix-intake-channels-extension-share.md — spec-to-kanban 2026-08-03)
#472 Dashboard Intake MVP — /intake URL submit (root, unblocked)
├── #473 Shared intake router + versioned contract ◄── #472
│   ├── #474 Dashboard conversational state (intent/freestyle) + expiry sweeper
│   ├── #475 Dashboard files + idempotent actions
│   └── #477 Telegram webhook → intake-router adapter
├── #476 PWA share target → /intake/share
└── #478 Chrome extension MVP (current tab + context menu)
    └── #479 Extension pairing auth (one-time token, hash-only)
Critical path: #472 → #473 → {#474, #475, #477}; #476 parallel off #472; #478 → #479 parallel off #472
Note: Phase 9 user_id identity migration and Phase 10 Discord adapter deferred per the plan's Non-Goals — not yet broken into issues.

Batch link intake — paste a list, import a bookmark file (grill-with-docs 2026-08-06/07; ADR-0046, ADR-0048; CONTEXT.md `Batch link paste` / `Paste parsing` / `URL coercion` / `Bookmark import` / `Snapshot ingest` / `Deferred link enrichment` / `Job card` / `Job delete`)
#490 Tighten is_fetchable_url + add coerce_url (root, unblocked — the whitespace-blob bug; one validator for every intake surface)
├── #494 Batch link paste — textarea, client loop, progress (zero backend diff; loops the endpoint #490 fixed)
└── #495 Parse and insert links, skip existing ◄── also #492 (needs both the validator and the accepted upload)
    ├── #496 Deferred import-scoped enrichment pass (embeds once, after descriptions land)
    └── #497 Folder-to-tag opt-in form (HITL-ish UI; reuses the shared OKLCH tag palette / TAG_ICONS / IconPicker)
#492 Accept Netscape bookmark HTML end-to-end (root, unblocked — deliberately hollow: card in, zero links)
#491 Links outlive jobs — drop delete cascade, add ?with_links=1 (root, unblocked — ADR-0046, all seven pipelines)
#493 _rewrite_existing_md must update_file, not upload_file (root, unblocked — pre-existing Drive-duplication bug)
Critical path: #490 → #495 → {#496, #497}; #492 joins #495; #491 and #493 fully parallel
Note: #492 is split from #495 on purpose — it proves the sniff → router → worker → job-card path with an empty payload, so parser surprises land in isolation. #491 and #493 are prerequisites for *safety* rather than *function*: without #491 one misclick on the import card destroys all 318 links, and without #493 every re-import duplicates its Drive .md files. Deliberately excluded: fixing the global refresh cron (Drive-gated, 449 descriptions unresolved since May 2026) — ADR-0048 decoupled bookmark import from it; needs its own diagnosis issue.

Intake console makeover — conversational + informing (grill 2026-08-06; CONTEXT.md "Intake console" / "Tag token", ADR-0047)
#481 Live intake card — poll job state, shimmer + status badge, PreviewCard at done (root, unblocked)
└── #488 Persist the intake thread in sessionStorage (restore path needs #481's polling to resolve real status)
#482 Parse #tag tokens in the intake router; attach existing tags (root, unblocked)
└── #489 Offer inline tag creation when a #tag token is unknown (ADR-0047 — action envelope, not chat_state)
#483 Render the retry action on retryable intake errors (root, unblocked — retry_job already exists in actions.py)
#484 Slash-command palette with argument hints (root, unblocked — derives its list from SHARED_COMMANDS)
├── #485 Migrate /find to shared intake commands
├── #486 Migrate /force to shared intake commands
└── #487 Migrate /freestyle to shared intake commands
Critical path: none — four independent roots (#481, #482, #483, #484). #488 off #481; #489 off #482.
Note: #485/#486/#487 are drawn under #484 as *content*, not as blockers — the palette derives its list from SHARED_COMMANDS, so each migration lights up its own entry on landing and all four can proceed in parallel. Builds on the shipped intake-channels batch (#472–#479). Deliberately excluded: the other eleven Telegram commands, SSE, /undo, per-flow pending state, and ?tag= feed filtering (the last is in docs/TASK.md Inbox — #489's bare-token warning links nowhere until it exists).

/checklists command — engineering-recommendation checklist from short/long video transcripts, pasteable straight into a coding agent (docs/superpowers/plans/2026-08-11-checklists-command.md)
#505 Extract shared CopyButton component (root, unblocked — needed by both #507 and #508)
├── #507 Dashboard job detail: generate & display checklists (API endpoint + hook + UI; needs the shared CopyButton)
└── #508 Intake response card: copy button for checklists results (small UI addition; needs the shared CopyButton)
#506 Telegram /checklists command delivery (root, unblocked — thin adapter over the already-shipped shared checklists_command core)
Critical path: #505 → {#507, #508}; #506 fully parallel
Note: the shared checklists_command core (SHARED_COMMANDS handler, DB columns, Gemini prompt/schema, run_checklists) already shipped directly on branch worktree-checklists-command (plan Tasks 1-5) — these four issues cover only the remaining Telegram and dashboard delivery surfaces.
```

---

## Open PRs

| # | Title | Branch→Base | Linked Issue | Status |
| --: | ----- | ----------- | ------------ | ------ |
| [#349](https://github.com/Leon-87-7/ownix/pull/349) | Add and harden ntfy operator alerts | claude/ntfy-vig-integration-7y8dw6→main | #339–#348 | 🔄 Open |

## Closed PRs

| # | Title | Branch→Base | Linked Issue | Status |
| --: | ----- | ----------- | ------------ | ------ |
| [#465](https://github.com/Leon-87-7/ownix/pull/465) | feat(web): robots.txt, sitemap, JSON-LD schema, noindex login | feat/seo-audit-fixes-robots-sitemap-schema→main | — | ✅ Merged |
| [#464](https://github.com/Leon-87-7/ownix/pull/464) | feat(brain): tenant-scoped link deletion | feat/brain-links-tenant-scoped-delete→main | — | ✅ Merged |
| [#463](https://github.com/Leon-87-7/ownix/pull/463) | feat(web): upgrade to Next.js 16, React 19 (#365-368) | feat/next16-upgrade-365-368→main | #365 | ✅ Merged |
| [#462](https://github.com/Leon-87-7/ownix/pull/462) | Short pipeline: extract on-screen code snippets | short-code-snippets→main | — | ✅ Merged |
