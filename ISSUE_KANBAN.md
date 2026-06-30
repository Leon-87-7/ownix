# Issue Kanban

> Read-only snapshot — authoritative state lives on [GitHub Issues](https://github.com/Leon-87-7/vig/issues).\
> Update this file whenever an issue moves columns.

---

## Done

|                                                   # | Title                                                                                                      | Area                     | Notes                                                                                     |
| --------------------------------------------------: | ---------------------------------------------------------------------------------------------------------- | ------------------------ | ----------------------------------------------------------------------------------------- |
|     [#1](https://github.com/Leon-87-7/vig/issues/1) | Scaffold + URL echo — FastAPI + worker + Redis + SQLite + task-envelope queue                              | Infra                    | Closed on GH                                                                              |
|     [#2](https://github.com/Leon-87-7/vig/issues/2) | Short video pipeline (Frames → Gemini Vision → Drive → Sheets → Telegram)                                  | Short Video              | Merged; closed on GH                                                                      |
|     [#3](https://github.com/Leon-87-7/vig/issues/3) | Long video Phase 1 — transcript + metadata + description links + buttons                                   | Long Video               | Merged; closed on GH                                                                      |
|     [#4](https://github.com/Leon-87-7/vig/issues/4) | Long video Phase 2 — Gemini enrichment + URL-resolution prompt                                             | Long Video               | Merged; closed on GH                                                                      |
|     [#5](https://github.com/Leon-87-7/vig/issues/5) | Second Brain — brain.py module (ingest, search, rebuild, refresh worker)                                   | Brain                    | Merged; closed on GH                                                                      |
|     [#8](https://github.com/Leon-87-7/vig/issues/8) | Short Sheet brain backfill — one-off script to seed brain corpus                                           | Brain / Short            | Merged; closed on GH                                                                      |
|     [#9](https://github.com/Leon-87-7/vig/issues/9) | Long Sheet brain backfill + resolve_tool_urls helper + URL Resolution Prompt                               | Brain / Long             | Merged; closed on GH                                                                      |
|   [#10](https://github.com/Leon-87-7/vig/issues/10) | BotFather command registration + ops runbook updates                                                       | Ops                      | Closed on GH                                                                              |
|   [#11](https://github.com/Leon-87-7/vig/issues/11) | Photo link extraction — Gemini Vision OCR on uploaded screenshots                                          | Photo / Brain            | Merged; closed on GH                                                                      |
|     [#6](https://github.com/Leon-87-7/vig/issues/6) | Mini-PRD auto slot — tail-call enqueue, Flash, JSON schema, Drive + Sheets + brain                         | Mini-PRD                 | Merged; closed on GH                                                                      |
|     [#7](https://github.com/Leon-87-7/vig/issues/7) | Mini-PRD intent slot + /spec command + chat_state routing                                                  | Mini-PRD                 | Merged; closed on GH                                                                      |
|   [#13](https://github.com/Leon-87-7/vig/issues/13) | Add retry button on Gemini enrichment failures                                                             | Long Video               | Merged; closed on GH                                                                      |
|   [#15](https://github.com/Leon-87-7/vig/issues/15) | feat: extend transcript sidecar to support TikTok/Instagram via yt-dlp                                     | Short Video              | Merged; closed on GH                                                                      |
|   [#16](https://github.com/Leon-87-7/vig/issues/16) | feat: template + transcript enhancement system                                                             | Templates                | Parent issue; closed on GH                                                                |
|   [#17](https://github.com/Leon-87-7/vig/issues/17) | feat: template system — data layer (Phases 1–4)                                                            | Templates                | Merged; closed on GH                                                                      |
|   [#18](https://github.com/Leon-87-7/vig/issues/18) | feat: template system — handler layer (Phases 5–8)                                                         | Templates                | Merged; closed on GH                                                                      |
|   [#21](https://github.com/Leon-87-7/vig/issues/21) | feat: GitHub service + Redis cache for repo enrichment                                                     | Photo / GitHub           | Merged; PR #28                                                                            |
|   [#23](https://github.com/Leon-87-7/vig/issues/23) | refactor: GeminiClient core module                                                                         | Refactor                 | Merged; PR #29                                                                            |
|   [#24](https://github.com/Leon-87-7/vig/issues/24) | refactor: PRD skeleton unification                                                                         | Refactor                 | Merged; PR #30                                                                            |
|   [#25](https://github.com/Leon-87-7/vig/issues/25) | refactor: webhook callback dispatch table                                                                  | Refactor                 | Merged; PR #31                                                                            |
|   [#22](https://github.com/Leon-87-7/vig/issues/22) | feat: wire repo enrichment into photo pipeline                                                             | Photo / GitHub           | Merged; closed on GH                                                                      |
|   [#26](https://github.com/Leon-87-7/vig/issues/26) | refactor: GeminiClient — migrate remaining callers                                                         | Refactor                 | Merged; closed on GH                                                                      |
|   [#27](https://github.com/Leon-87-7/vig/issues/27) | refactor: webhook slash dispatch table                                                                     | Refactor                 | Merged; closed on GH                                                                      |
|   [#32](https://github.com/Leon-87-7/vig/issues/32) | feat: audio fallback for caption-less Reels (transcript service + audio enrichment)                        | Short Video / Templates  | Committed to main (add56a6); not pushed; closed on GH                                     |
|   [#33](https://github.com/Leon-87-7/vig/issues/33) | feat: promise-gap extraction — schema + prompt + parse + persist                                           | Enrichment               | Committed to main (51803cd); closed on GH                                                 |
|   [#34](https://github.com/Leon-87-7/vig/issues/34) | feat: promise-gap Telegram render                                                                          | Enrichment               | Committed to main (22c7de2); closed on GH                                                 |
|   [#35](https://github.com/Leon-87-7/vig/issues/35) | Recover orphaned jobs at worker startup (ADR-0010)                                                         | Infra / Worker           | Committed to main (7ba1a95); closed on GH; 43 tests green                                 |
|   [#37](https://github.com/Leon-87-7/vig/issues/37) | Slimming sweep: dedup trivial helpers (ID gen, links formatter, EMBEDDING_DIM)                             | Refactor                 | Closed on GH; changes local (uncommitted); 49 touched-module tests green                  |
|   [#38](https://github.com/Leon-87-7/vig/issues/38) | Unify the two template-matching tables into the Template module                                            | Refactor                 | Closed on GH                                                                              |
|   [#41](https://github.com/Leon-87-7/vig/issues/41) | refactor(database): add set_prd_slot_status — narrow the update_job_status escape hatch                    | DB / PRD                 | Merged; PR #44; closed on GH                                                              |
|   [#43](https://github.com/Leon-87-7/vig/issues/43) | refactor(database): replace silent ALTER TABLE blocks with PRAGMA user_version migration tracking          | DB                       | Merged; PR #45; closed on GH; 17 db tests green                                           |
|                                                   — | fix(database): phantom status filter in find_recent_job_by_url ('failed'/'stale')                          | DB / Dedup               | No issue; fixed directly; committed to main                                               |
|   [#36](https://github.com/Leon-87-7/vig/issues/36) | fix: photo pipeline missing ADR-0005 UI-chrome filter (3 red tests)                                        | Photo                    | Merged; PR #48; commit 2df529e; closed on GH                                              |
|   [#46](https://github.com/Leon-87-7/vig/issues/46) | bug(gemini_photo): \_filter_grounded_links not dropping 'followed by' UI-chrome links                      | Photo                    | Closed as dup of #36; fixed by PR #48                                                     |
|   [#39](https://github.com/Leon-87-7/vig/issues/39) | Collapse the Gemini service triplet into one module (ADR-0011)                                             | Refactor                 | Merged; PR #49; commit bd4d949; closed on GH                                              |
|   [#42](https://github.com/Leon-87-7/vig/issues/42) | refactor(database): move links table DDL from brain.py into database.py                                    | DB / Brain               | Completed; links DDL in database.py SCHEMA_SQL; brain.py SCHEMA_SQL removed; closed on GH |
|   [#47](https://github.com/Leon-87-7/vig/issues/47) | bug(test_short_video): short_video.run() hits no such table: ignored_domains                               | Test / DB                | Merged; PR #50; commit 5dbdd2b; closed on GH                                              |
|   [#51](https://github.com/Leon-87-7/vig/issues/51) | feat(db): add jobs.freestyle_prompt column                                                                 | DB                       | Merged; PR #55; commit 004d6ab; closed on GH                                              |
|   [#52](https://github.com/Leon-87-7/vig/issues/52) | feat(enrichment): substitute freestyle_prompt in place of template extra_instructions                      | Enrichment               | Merged; PR #56; commit c8e52ce; closed on GH                                              |
|   [#53](https://github.com/Leon-87-7/vig/issues/53) | feat(webhook): template picker keyboard replaces direct gemini_yes enqueue (ADR-0012)                      | Webhook / Long Video     | Merged; PR #57; commit 3092399; closed on GH                                              |
|   [#54](https://github.com/Leon-87-7/vig/issues/54) | feat(webhook): /freestyle slash command for both short and long pipelines                                  | Webhook / Templates      | Merged; PR #58; commit 128f9fb; closed on GH                                              |
|                                                   — | feat(webhook): /find UX — GitHub enrichment, full URL path, score floor 0.58                               | Brain / Webhook          | No issue; committed directly (feat/find-ux session)                                       |
|                                                   — | feat(webhook): plain-text command shortcut — first word matched against \_SLASH_TABLE                      | Webhook                  | No issue; committed directly (same session)                                               |
|   [#59](https://github.com/Leon-87-7/vig/issues/59) | refactor(sheets): consolidate three GOOGLE*SHEETS_ID*\* env vars into one with named tabs (ADR-0013)       | Refactor / Sheets        | Committed to main; closed on GH                                                           |
|   [#60](https://github.com/Leon-87-7/vig/issues/60) | feat(jina): markdown_cache + /download_md utility + /force cache invalidation                              | Article / Utility        | Committed to main; closed on GH                                                           |
|   [#61](https://github.com/Leon-87-7/vig/issues/61) | feat(allowlist): /allowlist family + allowed_domains table + ARTICLE_DEFAULT_DOMAINS + rejection hint      | Article / Webhook        | Committed to main; closed on GH                                                           |
|   [#62](https://github.com/Leon-87-7/vig/issues/62) | feat(article): end-to-end article URL pipeline — Jina → cache → doc → paywall → Gemini → sheets → brain    | Article                  | Committed to main; closed on GH; 159/160 tests green                                      |
|   [#66](https://github.com/Leon-87-7/vig/issues/66) | Repo pipeline #1: URL routing + stub processor (tracer bullet)                                             | Repo Pipeline            | —                                                                                         |
|   [#67](https://github.com/Leon-87-7/vig/issues/67) | Repo pipeline #2: GitHub bundle fetch + Redis cache + README preprocessing + /force                        | Repo Pipeline            | Merged; PR #80; closed on GH                                                              |
|   [#68](https://github.com/Leon-87-7/vig/issues/68) | Repo pipeline #3: Gemini analysis + structured JSON + summary message                                      | Repo Pipeline            | Merged; PR #80; closed on GH                                                              |
|   [#69](https://github.com/Leon-87-7/vig/issues/69) | Repo pipeline #4: Telegram document delivery (`<owner>-<repo>.md`)                                         | Repo Pipeline            | Merged; PR #80; closed on GH                                                              |
|   [#70](https://github.com/Leon-87-7/vig/issues/70) | Repo pipeline #5: Sheets persistence (Repo Analysis tab + append/update)                                   | Repo Pipeline            | Merged; PR #80; closed on GH                                                              |
|   [#71](https://github.com/Leon-87-7/vig/issues/71) | Repo pipeline #6: Second Brain ingest (repo URL only)                                                      | Repo Pipeline            | Merged; PR #80; closed on GH                                                              |
|   [#72](https://github.com/Leon-87-7/vig/issues/72) | Repo pipeline #7: Edge cases (archived + no-README + distinct API errors)                                  | Repo Pipeline            | Merged; PR #80; closed on GH                                                              |
|   [#73](https://github.com/Leon-87-7/vig/issues/73) | Repo pipeline #8: Freestyle re-run end-to-end (same job_id, cache hit, Sheets in-place update)             | Repo Pipeline            | Merged; PR #80; closed on GH                                                              |
|   [#81](https://github.com/Leon-87-7/vig/issues/81) | bug(database): add chat_id to ignored_domains — per-chat tenancy (drift fix)                               | DB / Tenancy             | Committed to main (45edd0d); closed on GH                                                 |
|   [#83](https://github.com/Leon-87-7/vig/issues/83) | web(S0): API package split + FK enforcement                                                                | Web / Infra              | Closed on GH                                                                              |
|   [#84](https://github.com/Leon-87-7/vig/issues/84) | web(S1): Auth spine — Telegram Login Widget → Redis session → guarded Next.js shell                        | Web / Auth               | Closed on GH; dev branch; 18 tests green; end-to-end login verified on app.leondev.xyz    |
|   [#85](https://github.com/Leon-87-7/vig/issues/85) | web(S2): Feed — hero stats + fuse.js search + filters + Scope-A polling                                    | Web / Feed               | —                                                                                         |
|   [#86](https://github.com/Leon-87-7/vig/issues/86) | web(S3): Job detail — full enrichment view + per-field copy buttons                                        | Web / Jobs               | —                                                                                         |
|   [#87](https://github.com/Leon-87-7/vig/issues/87) | web(S4): Controls Tags tab — tag CRUD with name + meaning + color                                          | Web / Controls           | —                                                                                         |
|   [#89](https://github.com/Leon-87-7/vig/issues/89) | web(S6): Spaces — CRUD + URLs tab                                                                          | Web / Spaces             | Merged to dev; commits 1bd879b + 894c43c; closed on GH                                    |
|   [#93](https://github.com/Leon-87-7/vig/issues/93) | web(S7): Space context blobs — Context tab (Milkdown, ordered)                                             | Web / Spaces             | Committed to dev; closed on GH                                                            |
|   [#95](https://github.com/Leon-87-7/vig/issues/95) | web(S8): Space export — composer + gdoc + md/txt/pdf modal                                                 | Web / Spaces             | Committed to dev; closed on GH                                                            |
| [#101](https://github.com/Leon-87-7/vig/issues/101) | feat(enrichment): transcribe_audio + enrich_audio returns transcript text (ADR-0020 foundation)            | Short Video / Enrichment | Committed (dbdcd40); closed on GH; 57 tests green                                         |
| [#102](https://github.com/Leon-87-7/vig/issues/102) | feat(short-pipeline): guaranteed transcript acquisition on every short job (ADR-0020)                      | Short Video              | Committed (dbdcd40); closed on GH; 57 tests green                                         |
| [#103](https://github.com/Leon-87-7/vig/issues/103) | feat(short-pipeline): transcript Drive upload + Telegram document delivery tail (ADR-0020)                 | Short Video              | Committed (dbdcd40); closed on GH; 57 tests green                                         |
|   [#90](https://github.com/Leon-87-7/vig/issues/90) | web(S9): User templates + -name branch (ADR-0019)                                                          | Web / Templates          | Closed on GH (completed)                                                                  |
|   [#91](https://github.com/Leon-87-7/vig/issues/91) | web(S10): Controls — Allowed + Ignored domain tabs                                                         | Web / Controls           | Closed on GH (completed)                                                                  |
|   [#92](https://github.com/Leon-87-7/vig/issues/92) | web(S11): Brain semantic-search page                                                                       | Web / Brain              | Closed on GH (completed)                                                                  |
|   [#96](https://github.com/Leon-87-7/vig/issues/96) | Templates API is not tenant-scoped (IDOR / cross-user read+write+delete)                                   | Bug / Templates          | Fixed; commit 93ad9f0; closed on GH                                                       |
|   [#97](https://github.com/Leon-87-7/vig/issues/97) | Short pipeline: caption-based job always produces a transcript                                             | Short Video              | Merged; PR #113; closed on GH                                                             |
|   [#98](https://github.com/Leon-87-7/vig/issues/98) | Short pipeline: caption-less plain job transcribes via Gemini                                              | Short Video              | Merged; PR #113; closed on GH                                                             |
|   [#99](https://github.com/Leon-87-7/vig/issues/99) | Short pipeline: caption-less template job persists transcript from the fused enrich_audio call             | Short Video              | Merged; PR #113; closed on GH                                                             |
| [#100](https://github.com/Leon-87-7/vig/issues/100) | Short pipeline: explicit transcript-failure taxonomy                                                       | Short Video              | Merged; PR #113; closed on GH                                                             |
| [#118](https://github.com/Leon-87-7/vig/issues/118) | feat(github+repo): topics field, v2 cache key, and \_prioritize_tree helper                                | Repo Pipeline            | Merged; PR #120; closed on GH                                                             |
| [#119](https://github.com/Leon-87-7/vig/issues/119) | feat(repo): improve \_build_repo_prompt — constraints, topics, field guidance, caps, star calibration      | Repo Pipeline            | Merged; PR #120; closed on GH                                                             |
| [#121](https://github.com/Leon-87-7/vig/issues/121) | refactor(feed): extract useFeedData + useFuseSearch + polling hook                                         | Web / Refactor           | Merged; PR #134; closed on GH                                                             |
| [#122](https://github.com/Leon-87-7/vig/issues/122) | refactor(spaces/detail): extract data hooks + split UrlsTab / ContextTab components                        | Web / Refactor           | Merged; PR #134; closed on GH                                                             |
| [#123](https://github.com/Leon-87-7/vig/issues/123) | refactor(job/detail): extract useJobDetail + useJobAnnotation + useJobTags hooks                           | Web / Refactor           | Merged; PR #134; closed on GH                                                             |
| [#124](https://github.com/Leon-87-7/vig/issues/124) | refactor(controls): extract useTagList + useDomainList; slim DomainTab                                     | Web / Refactor           | Merged; PR #134; closed on GH                                                             |
| [#125](https://github.com/Leon-87-7/vig/issues/125) | refactor(spaces/list): extract useSpaceList + useCreateSpace hooks                                         | Web / Refactor           | Merged; PR #134; closed on GH                                                             |
| [#126](https://github.com/Leon-87-7/vig/issues/126) | refactor(export-modal): extract useGdocExport; flatten handleGdoc branches                                 | Web / Refactor           | Merged; PR #134; closed on GH                                                             |
| [#127](https://github.com/Leon-87-7/vig/issues/127) | refactor(prompts): extract useTemplateList; slim UserTemplateRow                                           | Web / Refactor           | Merged; PR #134; closed on GH                                                             |
| [#128](https://github.com/Leon-87-7/vig/issues/128) | refactor(brain): extract useSemanticSearch hook                                                            | Web / Refactor           | Merged; PR #134; closed on GH                                                             |
| [#129](https://github.com/Leon-87-7/vig/issues/129) | refactor(fetch-utils): reduce mapFetchState complexity; consolidate shared fetch patterns                  | Web / Refactor           | Merged; PR #134; closed on GH                                                             |
|   [#88](https://github.com/Leon-87-7/vig/issues/88) | web(S5): Job annotation + tagging — Milkdown notes (debounced) + TagPicker                                 | Web / Jobs               | Committed to main (7e37bd4); closed on GH                                                 |
| [#130](https://github.com/Leon-87-7/vig/issues/130) | refactor(webhook): extract URL-routing + template-shortcut helpers — cut webhook() CC 32→<12               | Refactor / Telegram      | Committed to main (057a28d); closed on GH                                                 |
| [#131](https://github.com/Leon-87-7/vig/issues/131) | refactor(short_video): extract \_acquire_transcript — flatten run() nesting (CC 27, depth 6)               | Refactor / Short Video   | Committed to main; closed on GH                                                           |
| [#132](https://github.com/Leon-87-7/vig/issues/132) | refactor(database): add \_execute/\_fetch_one/\_fetch_all helpers — collapse clone Group 38 (13 clones)    | Refactor / DB            | Committed to main (7038a5d); closed on GH                                                 |
| [#133](https://github.com/Leon-87-7/vig/issues/133) | refactor(brain): extract \_select_refresh_batch + \_refresh_one_link — flatten refresh_stale_links (CC 24) | Refactor / Brain         | Committed to main; closed on GH                                                           |
| [#136](https://github.com/Leon-87-7/vig/issues/136) | feat(photo): remove redundant Quick Links section from build_enriched_links_message                        | Photo / Webhook          | Merged; PR #138; closed on GH                                                             |
| [#137](https://github.com/Leon-87-7/vig/issues/137) | feat(photo): replace explicit batch commands with media_group_id debounce (ADR-0024)                       | Photo / Telegram         | Merged; PR #138; closed on GH                                                             |
| [#159](https://github.com/Leon-87-7/vig/issues/159) | Backfill short thumbnails: core script (happy path)                                                        | Pipeline / Short         | Merged; PR #149; closed on GH                                                             |
| [#142](https://github.com/Leon-87-7/vig/issues/142) | feat(web): content-type tabs replace feed filter bar                                                       | Web / Feed               | Merged; PR #149; closed on GH                                                             |
| [#143](https://github.com/Leon-87-7/vig/issues/143) | feat(api): server-resolved thumbnail_url on /api/jobs                                                      | API / Jobs               | Merged; PR #149; closed on GH                                                             |
| [#144](https://github.com/Leon-87-7/vig/issues/144) | feat(web): preview-card grid for typed feed tabs                                                           | Web / Feed               | Merged; PR #149; closed on GH                                                             |
| [#145](https://github.com/Leon-87-7/vig/issues/145) | feat(web): brand-icon badges in All-tab feed rows                                                          | Web / Feed               | Merged; PR #149; closed on GH                                                             |
| [#146](https://github.com/Leon-87-7/vig/issues/146) | feat(short): persist best frame as job thumbnail (Phase 2)                                                 | Pipeline / Short         | Merged; PR #149; closed on GH                                                             |
| [#147](https://github.com/Leon-87-7/vig/issues/147) | feat(article): scrape og:image as job thumbnail (Phase 2)                                                  | Pipeline / Article       | Merged; PR #149; closed on GH                                                             |
| [#148](https://github.com/Leon-87-7/vig/issues/148) | chore(article): one-shot og:image backfill script                                                          | Pipeline / Article       | Merged; PR #149; closed on GH                                                             |
| [#160](https://github.com/Leon-87-7/vig/issues/160) | ADR-0025 follow-up note: historical short thumbnails are re-derivable                                      | Docs / ADR               | Closed on GH                                                                              |
| [#161](https://github.com/Leon-87-7/vig/issues/161) | Backfill short thumbnails: frame-selection strategies (rerun-vision, fallbacks)                            | Pipeline / Short         | Closed on GH                                                                              |
| [#162](https://github.com/Leon-87-7/vig/issues/162) | Backfill short thumbnails: --overwrite-existing clobber-safety flag                                        | Pipeline / Short         | Closed on GH                                                                              |
| [#117](https://github.com/Leon-87-7/vig/issues/117) | ExportModal: restore PDF fallback when Google Drive is not configured                                      | Web / Exports            | Committed to main (e3dcdd2); closed on GH                                                 |
| [#164](https://github.com/Leon-87-7/vig/issues/164) | fix(web/jobs): populate short-pipeline job detail pages                                                    | Web / Jobs Detail        | Merged; PR #172; closed on GH                                                             |
| [#165](https://github.com/Leon-87-7/vig/issues/165) | fix(web/feed): guard feed fetch race so tabs only show their content type                                  | Web / Feed               | Merged; PR #173; closed on GH                                                             |
| [#166](https://github.com/Leon-87-7/vig/issues/166) | fix(web/feed): scope Overview stat cards to the active content-type tab                                    | Web / Feed               | Merged; PR #173; closed on GH                                                             |
|   [#94](https://github.com/Leon-87-7/vig/issues/94) | web(S12): Deploy — docker-compose 'web' service + Dockerfile + app./api. subdomains \[HITL]                | Web / Ops                | HITL deploy; closed on GH                                                                 |
| [#167](https://github.com/Leon-87-7/vig/issues/167) | web(jobs): recovery panel summary by active feed tab                                                       | Web / Jobs               | Merged; PR #174; closed on GH                                                             |
| [#168](https://github.com/Leon-87-7/vig/issues/168) | web(jobs): retry stale pending jobs from recovery panel                                                    | Web / Jobs               | Merged; PR #174; closed on GH                                                             |
| [#169](https://github.com/Leon-87-7/vig/issues/169) | web(jobs): retry failed jobs with tenant-scoped stale reaping                                              | Web / Jobs               | Merged; PR #174; closed on GH                                                             |
| [#170](https://github.com/Leon-87-7/vig/issues/170) | web(jobs): clear failed jobs as cancelled from recovery panel                                              | Web / Jobs               | Merged; PR #174; closed on GH                                                             |
| [#171](https://github.com/Leon-87-7/vig/issues/171) | web(controls): opt out of dashboard recovery Telegram notifications                                        | Web / Controls           | Merged; PR #174; closed on GH                                                             |
| [#175](https://github.com/Leon-87-7/vig/issues/175) | feat(web): client-side feed filtering (preload + instant filters)                                          | Web / Feed               | Merged; PR #178; closed on GH                                                             |
| [#176](https://github.com/Leon-87-7/vig/issues/176) | feat(ops): keep-warm ping to eliminate API cold-start spike                                                | Ops                      | Merged; PR #178; closed on GH                                                             |
| [#177](https://github.com/Leon-87-7/vig/issues/177) | feat(web): silent background freshness (focus-refetch + backstop poll)                                     | Web / Feed               | Merged; PR #178; closed on GH                                                             |
| [#185](https://github.com/Leon-87-7/vig/issues/185) | feat(web/feed): mobile inline stats row (T/D/P/E)                                                          | Web / Feed               | Merged; PR #193; closed on GH                                                             |
| [#186](https://github.com/Leon-87-7/vig/issues/186) | feat(web/feed): wrap content-type tabs instead of horizontal scroll                                        | Web / Feed               | Merged; PR #193; closed on GH                                                             |
| [#187](https://github.com/Leon-87-7/vig/issues/187) | feat(web/feed): collapse recovery + status filters on mobile                                               | Web / Feed               | Merged; PR #193; closed on GH                                                             |
| [#188](https://github.com/Leon-87-7/vig/issues/188) | feat(web): scroll-to-top button in dashboard layout                                                        | Web / Layout             | Merged; PR #193; closed on GH                                                             |
| [#189](https://github.com/Leon-87-7/vig/issues/189) | feat(db): add icon column to spaces table                                                                  | DB / Spaces              | Merged; PR #193; closed on GH                                                             |
| [#190](https://github.com/Leon-87-7/vig/issues/190) | feat(web/spaces): redesign space cards with icon + color wash + inline delete                              | Web / Spaces             | Merged; PR #193; closed on GH                                                             |
| [#191](https://github.com/Leon-87-7/vig/issues/191) | feat(web/spaces): icon picker on space create/edit                                                         | Web / Spaces             | Merged; PR #193; closed on GH                                                             |
| [#192](https://github.com/Leon-87-7/vig/issues/192) | feat(web/jobs): enlarge mobile back-link on job detail                                                     | Web / Jobs               | Merged; PR #193; closed on GH                                                             |
| [#150](https://github.com/Leon-87-7/vig/issues/150) | feat(storage): add GCS-backed content-addressed storage seam                                               | Platform / Storage       | Merged; PR #182; closed on GH                                                             |
| [#151](https://github.com/Leon-87-7/vig/issues/151) | feat(document): ingest Telegram file uploads into document jobs                                            | Telegram / Document      | Merged; PR #182; closed on GH                                                             |
| [#152](https://github.com/Leon-87-7/vig/issues/152) | feat(document): route direct document URLs before article allowlist                                        | Routing / Document       | Merged; PR #182; closed on GH                                                             |
| [#153](https://github.com/Leon-87-7/vig/issues/153) | feat(document): add vig-document liteparse sidecar                                                         | Document / Sidecar       | Merged; PR #182; closed on GH                                                             |
| [#154](https://github.com/Leon-87-7/vig/issues/154) | feat(document): parse cache and automatic Gemini enrichment                                                | Document Pipeline        | Merged; PR #182; closed on GH                                                             |
| [#155](https://github.com/Leon-87-7/vig/issues/155) | feat(document): deliver plain text and enrichment summary in Telegram                                      | Telegram / Document      | Merged; PR #182; closed on GH                                                             |
| [#156](https://github.com/Leon-87-7/vig/issues/156) | feat(document): render Markdown on demand from cached plain text                                           | Document / Markdown      | Merged; PR #200; closed on GH                                                             |
| [#157](https://github.com/Leon-87-7/vig/issues/157) | feat(document): support Freestyle re-runs from cached parse                                                | Document / Templates     | Merged; PR #200; closed on GH                                                             |
| [#158](https://github.com/Leon-87-7/vig/issues/158) | feat(exports): add opt-in Document Analysis export hook                                                    | Exports / Sheets         | Merged; PR #200; closed on GH                                                             |
| [#211](https://github.com/Leon-87-7/vig/issues/211) | Vision-harvested short titles                                                                              | Short Video              | Merged; PR #215; closed on GH                                                             |
| [#212](https://github.com/Leon-87-7/vig/issues/212) | Remove key_phrases end-to-end                                                                             | Short Video / Enrichment | Merged; PR #215; closed on GH                                                             |
| [#213](https://github.com/Leon-87-7/vig/issues/213) | Links Found detail section (clickable)                                                                     | Web / Jobs               | Merged; PR #215; closed on GH                                                             |
| [#217](https://github.com/Leon-87-7/vig/issues/217) | feat(api): document upload REST endpoints + telegram_delivery column                                       | API                      | Merged; PR #227; closed on GH                                                             |
| [#218](https://github.com/Leon-87-7/vig/issues/218) | feat(web): Doc Parser page shell + sidebar entry                                                           | Web                      | Merged; PR #227; closed on GH                                                             |
| [#219](https://github.com/Leon-87-7/vig/issues/219) | feat(processor): Gemini structured summary + enriched GCS storage                                          | Processor                | Merged; PR #227; closed on GH                                                             |
| [#220](https://github.com/Leon-87-7/vig/issues/220) | feat(api): SSE endpoint for document job status                                                            | API                      | Merged; PR #227; closed on GH                                                             |
| [#221](https://github.com/Leon-87-7/vig/issues/221) | feat(api): on-demand clean + freestyle document endpoints                                                  | API                      | Merged; PR #227; closed on GH                                                             |
| [#222](https://github.com/Leon-87-7/vig/issues/222) | feat(web): upload zone — URL input + file dropzone                                                         | Web                      | Merged; PR #227; closed on GH                                                             |
| [#223](https://github.com/Leon-87-7/vig/issues/223) | feat(web): document job list + SSE real-time updates                                                       | Web                      | Merged; PR #227; closed on GH                                                             |
| [#224](https://github.com/Leon-87-7/vig/issues/224) | feat(web): three-state Telegram toggle component                                                           | Web / API                | Merged; PR #227; closed on GH                                                             |
| [#225](https://github.com/Leon-87-7/vig/issues/225) | feat(web): Doc Parser detail page with output cards                                                        | Web                      | Merged; PR #227; closed on GH                                                             |
| [#226](https://github.com/Leon-87-7/vig/issues/226) | feat(web): freestyle modal with random + saved prompts                                                     | Web                      | Merged; PR #227; closed on GH                                                             |
| [#231](https://github.com/Leon-87-7/vig/issues/231) | Latent: 'retroactive' storable as a persistent telegram_delivery state                                     | DB / Document            | Merged; PR #232; closed on GH                                                             |
| [#228](https://github.com/Leon-87-7/vig/issues/228) | Refactor: extract parsed.py trust-boundary PDF intake into a deep module (post-#227)                       | Refactor / Document      | Merged; PR #229; closed on GH                                                             |
| [#240](https://github.com/Leon-87-7/vig/issues/240) | Doc detail page: move Telegram toggle next to Clean + add download/copy buttons to output cards            | Web / Doc Parser         | Merged; PR #242; closed on GH                                                             |
| [#238](https://github.com/Leon-87-7/vig/issues/238) | Extracted-links table on the Brain page (deduplicated, paginated)                                          | Web / Brain              | Merged; PR #239; closed on GH                                                             |
| [#82](https://github.com/Leon-87-7/vig/issues/82)   | bug(test_long_video): under-mocked send_message → coroutine reaches editMessageText JSON encode            | Test / Long Video        | ⚠ Closed on GH as COMPLETED despite `wontfix` label (dep-map marked WONTFIX 2026-06-07)   |

---

## Needs Triage

|                                                   # | Title                                                                                       | Area             | Depends On |
| --------------------------------------------------: | ------------------------------------------------------------------------------------------- | ---------------- | ---------- |
| [#201](https://github.com/Leon-87-7/vig/issues/201) | epic(multi-tenancy): per-user export isolation                                              | Multi-tenancy    | —          |
| [#202](https://github.com/Leon-87-7/vig/issues/202) | feat(config): operator-only export gate (per-user isolation, the #201 'now' fix)            | Multi-tenancy    | —          |
| [#203](https://github.com/Leon-87-7/vig/issues/203) | chore(ops): Google Cloud OAuth app — production publishing + sensitive-scope verification   | Ops / Google Cloud | —        |
| [#204](https://github.com/Leon-87-7/vig/issues/204) | feat(oauth): per-user 'Connect Google' (web) — encrypted token store → exports to /vig      | OAuth / Export   | #202, #203 |
| [#205](https://github.com/Leon-87-7/vig/issues/205) | feat(telegram): Mini App 'Connect Google' surface — initData identity, shared OAuth backend | OAuth / Telegram | #204       |
| [#206](https://github.com/Leon-87-7/vig/issues/206) | feat(oauth): connection lifecycle — invalid_grant handling, /disconnect, notify-once        | OAuth / Export   | #204       |
| [#234](https://github.com/Leon-87-7/vig/issues/234) | Replace raw logout API response with dedicated logout page                                   | Web / Auth       | —          |

---

## Ready for Agent

Ordered by unblocked-first, then dependency chain.

|                                                   # | Title                                                                | Area                     | Depends On       |
| --------------------------------------------------: | -------------------------------------------------------------------- | ------------------------ | ---------------- |
| [#251](https://github.com/Leon-87-7/vig/issues/251) | Brain Links table: richer navigation + persisted per-tenant view     | Web / Brain              | —                |
| [#252](https://github.com/Leon-87-7/vig/issues/252) | Brain graph on-canvas controls overlay (zoom/fit/recenter + filter)  | Web / Brain              | —                |
| [#243](https://github.com/Leon-87-7/vig/issues/243) | Tooltip primitive + first adoption (foundation)                      | Web / Tooltips           | —                |
| [#244](https://github.com/Leon-87-7/vig/issues/244) | Migrate explanatory title= tooltips to Tooltip primitive             | Web / Tooltips           | #243             |
| [#245](https://github.com/Leon-87-7/vig/issues/245) | Migrate overflow-reveal title= tooltips (mono variant)               | Web / Tooltips           | #243             |
| [#246](https://github.com/Leon-87-7/vig/issues/246) | Add tooltips to icon-only controls                                   | Web / Tooltips           | #243             |
| [#247](https://github.com/Leon-87-7/vig/issues/247) | Add tooltips to metric labels in stats-overview                      | Web / Tooltips           | #243             |

---

## Ready for Human

|   # | Title | Area | Notes |
| --: | ----- | ---- | ----- |

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
#243 Tooltip primitive + first adoption (foundation, root) — Ready for Agent
├── #244 migrate explanatory title= ◄── #243 — Ready for Agent
├── #245 migrate overflow-reveal title= (mono) ◄── #243 — Ready for Agent
├── #246 add tooltips to icon-only controls ◄── #243 — Ready for Agent
└── #247 add tooltips to metric labels (stats-overview) ◄── #243 — Ready for Agent
Critical path: #243 → {#244, #245, #246, #247} (all parallel once #243 lands)

Brain Links nav + graph controls (grill 2026-06-29 — tasks #7/#8 from docs/TASK.md)
#238 Extracted-links table on the Brain page ✅-Done (PR #239) — foundation the nav builds on
#251 Links table — server-side sort params + per-tenant user_settings view + jump-to-page/page-size — Ready for Agent (independent; LinksTable already shipped via #238)
#252 Brain graph on-canvas controls — zoom/fit/recenter + focus-on-match + topic legend/filter (desktop-only) — Ready for Agent (independent)
Critical path: #251 and #252 are independent — no dependency between them

Per-user export isolation (epic #201; ADR-0030 + ADR-0022; CONTEXT.md `Operator`)
#202 operator-only export gate (the "now" fix — root, unblocked) ◄── also gates #158 (open: opt-in Document Analysis export hook)
└── #204 per-user "Connect Google" (web): encrypted token store → /vig ◄── also #203
    ├── #205 Telegram Mini App surface (initData → shared OAuth backend)
    └── #206 connection lifecycle (invalid_grant / /disconnect / notify-once)
#203 Google Cloud OAuth app: prod publish + sensitive-scope verification (HITL/external — gates #204 for production)
Critical path: #202 → #204 → {#205, #206}; #203 (external review) gates #204 production readiness
```

---

## Open PRs

| # | Title | Branch→Base | Linked Issue | Status |
| --: | ----- | ----------- | ------------ | ------ |
| [#208](https://github.com/Leon-87-7/vig/pull/208) | feat(config): operator-only export gate — per-user isolation (#202) | feat/operator-export-gate→main | #202 | Open |
| [#207](https://github.com/Leon-87-7/vig/pull/207) | docs(multi-tenancy): export-isolation design — ADR-0027, Operator term, issue breakdown | docs/multi-tenancy-export-isolation→main | — | Open |

## Closed PRs

| # | Title | Branch→Base | Linked Issue | Status |
| --: | ----- | ----------- | ------------ | ------ |
| [#250](https://github.com/Leon-87-7/vig/pull/250) | feat(skills): /pre-grill + TASK.md ideation workflow | feat/pre-grill-skill→main | — | ✅ Merged |
| [#249](https://github.com/Leon-87-7/vig/pull/249) | feat(skills): /pre-grill — fatten one-line ideas into grill-ready briefs | feat/pre-grill-skill→main | — | ✅ Merged |
| [#248](https://github.com/Leon-87-7/vig/pull/248) | Add Tooltip component (Radix) and integrate across UI | codex/resolve-issues-#243-to-#247→main | — | ✅ Merged |
| [#242](https://github.com/Leon-87-7/vig/pull/242) | feat(doc-parser): relocate Telegram toggle + copy/download on output cards (#240) | 240-doc-detail-page-move-telegram-toggle-next-to-clean-add-downloadcopy-buttons-to-output-cards→main | #240 | ✅ Merged |
| [#241](https://github.com/Leon-87-7/vig/pull/241) | fix(brain): sort extracted links by latest sighting | codex/resolve-issue-240→main | — | ✅ Merged |
| [#239](https://github.com/Leon-87-7/vig/pull/239) | feat: Brain Links tab (+ search) and feed dashboard redesign | feat(brain)--link-table→main | — | ✅ Merged |
| [#237](https://github.com/Leon-87-7/vig/pull/237) | fix(webhook): add /start + /help handlers, harden webhook against unhandled errors | claude/telegram-bot-diagnose-9d41p6→main | — | ✅ Merged |
| [#236](https://github.com/Leon-87-7/vig/pull/236) | Consistent mobile page layout + doc-parser fixes | mobile-consistent-page-shell→main | — | ✅ Merged |
| [#235](https://github.com/Leon-87-7/vig/pull/235) | feat(auth): add logout confirmation page | ui/logout-frontend→main | — | ✅ Merged |
| [#233](https://github.com/Leon-87-7/vig/pull/233) | feat(web): redesign Telegram delivery toggle | feat/telegram-toggle-redesign→main | — | ✅ Merged |
| [#232](https://github.com/Leon-87-7/vig/pull/232) | fix(db): make telegram_delivery a stored domain of {off,on} (#231) | pr/231-telegram-delivery-domain→main | #231 | ✅ Merged |
| [#230](https://github.com/Leon-87-7/vig/pull/230) | fix: guard TelegramToggle against failed PUT | fix/telegram-toggle-failed-put→main | — | ✅ Merged |
| [#229](https://github.com/Leon-87-7/vig/pull/229) | refactor: extract PDF intake into a deep module (#228) | refactor/228-pdf-intake→main | #228 | ✅ Merged |
| [#227](https://github.com/Leon-87-7/vig/pull/227) | feat: Doc Parser dashboard page (ADR-0029) | feat/doc-parser-dashboard→main | #217 | ✅ Merged |
| [#216](https://github.com/Leon-87-7/vig/pull/216) | fix(web): mobile responsiveness across the dashboard | fix/mobile-responsiveness→main | — | ✅ Merged |
| [#215](https://github.com/Leon-87-7/vig/pull/215) | feat(short): vision titles, drop key_phrases, add clickable Links Found (#211 #212 #213) | feat/short-pipeline-cleanup→main | #211, #212, #213 | ✅ Merged |
| [#214](https://github.com/Leon-87-7/vig/pull/214) | feat(web): segmented content-type tabs + login page design | ui/second-touchups→main | — | ✅ Merged |
| [#210](https://github.com/Leon-87-7/vig/pull/210) | feat(web): job tag menu, controls accordion, denser feed cards | ui/job-tag-menu→main | — | ✅ Merged |
| [#209](https://github.com/Leon-87-7/vig/pull/209) | feat(skills): add /spec-to-kanban wrapper | feat/spec-to-kanban-skill→main | — | ✅ Merged |
| [#200](https://github.com/Leon-87-7/vig/pull/200) | fix+feat(document): dispatch fallthrough fix + fast-follow (#156 #157 #158) | fix/document-dispatch-fallthrough→main | #156, #157, #158 | ✅ Merged |
| [#199](https://github.com/Leon-87-7/vig/pull/199) | docs(brain): graph map plan — ADR-0027/0028, CONTEXT, issues #194–#198 | feat/brain-graph-map→main | #194, #198 | ✅ Merged |
| [#193](https://github.com/Leon-87-7/vig/pull/193) | feat(web): mobile-first UI/UX makeover + per-space icons (#185–#192) | feat/ui-ux-makeover→main | #185, #192 | ✅ Merged |
| [#184](https://github.com/Leon-87-7/vig/pull/184) | fix: hide cancelled jobs from feed and brain search | fix/hide-cancelled-from-feed-and-brain→main | — | ✅ Merged |
| [#183](https://github.com/Leon-87-7/vig/pull/183) | refactor: centralize extract_json and job_tag utilities | refactor/centralize-extract-json-and-job-tag→main | — | ✅ Merged |
| [#182](https://github.com/Leon-87-7/vig/pull/182) | feat(document): PDF document pipeline MVP (#150–#155) | feat/document-pipeline-mvp→main | #150, #155 | ✅ Merged |
| [#181](https://github.com/Leon-87-7/vig/pull/181) | feat(web/feed): tighten stats + filter layout, merge recovery into a controls bar | feat/web-feed-layout→main | — | ✅ Merged |
| [#180](https://github.com/Leon-87-7/vig/pull/180) | fix(web): localize dates, harden ExportModal, clear dead code + cover untested logic | feat/web-date-localization→main | — | ✅ Merged |
| [#179](https://github.com/Leon-87-7/vig/pull/179) | chore: ponytail-audit cleanup — drop shims, dead flag, committed pyscn snapshots | chore/ponytail-cleanup→main | — | ✅ Merged |
| [#178](https://github.com/Leon-87-7/vig/pull/178) | feat(web): instant feed filtering + silent freshness + keep-warm ping (#175–#177) | feat/175-177-feed-freshness→main | #175 | ✅ Merged |
| [#174](https://github.com/Leon-87-7/vig/pull/174) | feat(web): add dashboard job recovery panel | codex-dashboard-recovery-panel→main | #167, #168, #169, #170, #171 | ✅ Merged |
| [#173](https://github.com/Leon-87-7/vig/pull/173) | fix(web/feed): guard feed fetch race so tabs only show their content type | fix/165-feed-race-guard→main | #165 | ✅ Merged |
| [#172](https://github.com/Leon-87-7/vig/pull/172) | fix(web/jobs): populate short-pipeline job detail pages | fix/164-short-job-detail→main | #164 | ✅ Merged |
| [#163](https://github.com/Leon-87-7/vig/pull/163) | fix(article/backfill): continue og:image scan on bad scheme; SQL LIMIT on short backfill | fix/greptile-149-followup→main | — | ✅ Merged |
| [#149](https://github.com/Leon-87-7/vig/pull/149) | Resolve feed thumbnail issues #142-#148 | codex-issues-142-148-feed-thumbnails→main | #142, #148 | ✅ Merged |
| [#141](https://github.com/Leon-87-7/vig/pull/141) | feat(web): Operator's Console design system — spec, tokens, drawer nav, full migration | feat/operators-console-design→main | — | ✅ Merged |
| [#140](https://github.com/Leon-87-7/vig/pull/140) | refactor: drive pyscn + fallow static-analysis gates to green | refactor/static-analysis-green→main | — | ✅ Merged |
| [#139](https://github.com/Leon-87-7/vig/pull/139) | feat(photo): media_group_id debounce replaces photoBatch commands (#137) | worktree-agent-ab8d0c4a71e30b5f7→main | #137 | ❌ Closed |
| [#138](https://github.com/Leon-87-7/vig/pull/138) | feat(photo): remove Quick Links footer + media_group_id debounce (#136 #137) | worktree-agent-aab29c4329161fb60→main | #136, #137 | ✅ Merged |
| [#135](https://github.com/Leon-87-7/vig/pull/135) | refactor(hooks): extract custom hooks + add vitest test infrastructure | refactor/hooks-121-129→main | — | ✅ Merged |
| [#134](https://github.com/Leon-87-7/vig/pull/134) | refactor(frontend): extract custom hooks across all dashboard pages (#121-129) | refactor/hooks-121-129→main | #121 | ✅ Merged |
| [#120](https://github.com/Leon-87-7/vig/pull/120) | feat(github+repo): topics field, v2 cache key, _prioritize_tree, and _build_repo_prompt improvements | feat/118-119-repo-prompt-improvements→main | #118, #119 | ✅ Merged |
| [#116](https://github.com/Leon-87-7/vig/pull/116) | fix(queue/api/db): brpop idle handling, OpenAPI schema, per-chat ignored domains | repo-pipeline→main | — | ❌ Closed |
| [#115](https://github.com/Leon-87-7/vig/pull/115) | fix(spaces): ExportModal popup-block, controlled input, N+1 DB loop | pr/spaces-s7-s8→main | — | ✅ Merged |
| [#114](https://github.com/Leon-87-7/vig/pull/114) | feat(web): S5/S6 job annotations + spaces CRUD, S11 brain semantic-search | pr/web-s2-s3-s4→main | — | ✅ Merged |
| [#113](https://github.com/Leon-87-7/vig/pull/113) | feat(short-pipeline): transcript tail — closes #97 #98 #99 #100 | dev→main | #97, #98, #99, #100 | ✅ Merged |
| [#112](https://github.com/Leon-87-7/vig/pull/112) | feat(web): S2/S3/S4 — feed, job detail, tags CRUD | pr/web-s2-s3-s4→main | — | ✅ Merged |
| [#111](https://github.com/Leon-87-7/vig/pull/111) | feat(web): S7/S8 — space context blobs + export composer | pr/spaces-s7-s8→pr/spaces-s5-s6 | — | ❌ Closed |
| [#110](https://github.com/Leon-87-7/vig/pull/110) | feat(short-pipeline): ADR-0020 — guaranteed transcript on every short job | pr/adr-0020-transcript→main | — | ✅ Merged |
| [#109](https://github.com/Leon-87-7/vig/pull/109) | feat(web): S5/S6 — job annotations + spaces CRUD | pr/spaces-s5-s6→pr/web-s2-s3-s4 | — | ✅ Merged |
| [#108](https://github.com/Leon-87-7/vig/pull/108) | feat(web): S11 — brain semantic-search page | pr/brain-search-s11→pr/web-s2-s3-s4 | — | ✅ Merged |
| [#107](https://github.com/Leon-87-7/vig/pull/107) | feat(templates): user-defined templates CRUD + /templates command | pr/templates→pr/web-s2-s3-s4 | — | ✅ Merged |
| [#106](https://github.com/Leon-87-7/vig/pull/106) | feat(controls): S10 — Allowed/Ignored Domains tabs | pr/web-controls-s10→main | — | ✅ Merged |
| [#105](https://github.com/Leon-87-7/vig/pull/105) | feat(auth): S1 — auth hardening + cleanup | pr/auth-s1-fixes→main | — | ✅ Merged |
| [#104](https://github.com/Leon-87-7/vig/pull/104) | 🐛 fix(enrichment): repair malformed Gemini JSON with json-repair fallback | dev→main | — | ✅ Merged |
| [#80](https://github.com/Leon-87-7/vig/pull/80) | feat(repo): full repo pipeline #2-#8 (issues #67-#73) | repo-pipeline→main | #67 | ✅ Merged |
| [#74](https://github.com/Leon-87-7/vig/pull/74) | feat(repo): GitHub repo URL routing + stub processor | feat/repo-pipeline-66→main | #66 | ✅ Merged |
| [#65](https://github.com/Leon-87-7/vig/pull/65) | feat(jina): markdown_cache + /download_md + /force cache invalidation | feat/60-jina-markdown-cache→main | #60 | ✅ Merged |
| [#64](https://github.com/Leon-87-7/vig/pull/64) | feat(allowlist): /allowlist family + allowed_domains table + ARTICLE_DEFAULT_DOMAINS (#61) | feat/61-allowlist-family→main | #61 | ✅ Merged |
| [#63](https://github.com/Leon-87-7/vig/pull/63) | refactor(sheets): consolidate three GOOGLE_SHEETS_ID_* vars into one with named tabs (#59) | refactor/59-sheets-consolidate-tabs→main | #59 | ✅ Merged |
| [#58](https://github.com/Leon-87-7/vig/pull/58) | feat(webhook): /freestyle slash command for short and long pipelines | feat/54-freestyle-slash-command→main | #54 | ✅ Merged |
| [#57](https://github.com/Leon-87-7/vig/pull/57) | feat(webhook): template picker keyboard replaces direct gemini_yes enqueue | feat/53-template-picker-keyboard→main | #53 | ✅ Merged |
| [#56](https://github.com/Leon-87-7/vig/pull/56) | feat(enrichment): substitute freestyle_prompt for extra_instructions | feat/52-enrichment-freestyle-prompt→main | #52 | ✅ Merged |
| [#55](https://github.com/Leon-87-7/vig/pull/55) | feat(db): add jobs.freestyle_prompt column | feat/51-jobs-freestyle-prompt→main | #51 | ✅ Merged |
| [#50](https://github.com/Leon-87-7/vig/pull/50) | fix(test_short_video): stub get_ignored_domains in _patch_pipeline | fix/stub-get-ignored-domains→main | #47 | ✅ Merged |
| [#49](https://github.com/Leon-87-7/vig/pull/49) | refactor(gemini): collapse 4 fallback loops into one unified module (ADR-0011) | refactor/unify-gemini-call-paths→main | #39 | ✅ Merged |
| [#48](https://github.com/Leon-87-7/vig/pull/48) | fix(gemini_photo): add _UI_CHROME_PATTERNS drop to _filter_grounded_links | fix/ui-chrome-followed-by-filter→main | #36 | ✅ Merged |
| [#45](https://github.com/Leon-87-7/vig/pull/45) | refactor(database): replace silent ALTER TABLE blocks with PRAGMA user_version migration runner | refactor/user-version-migrations→main | #43 | ✅ Merged |
| [#44](https://github.com/Leon-87-7/vig/pull/44) | refactor(database): add set_prd_slot_status — narrow the update_job_status escape hatch | refactor/prd-slot-status→main | #41 | ✅ Merged |
| [#40](https://github.com/Leon-87-7/vig/pull/40) | refactor: unify template-matching tables into the Template module (#38) | refactor/38-unify-template-tables→main | #38 | ✅ Merged |
| [#31](https://github.com/Leon-87-7/vig/pull/31) | refactor(#25): replace _handle_callback elif chain with dispatch table | worktree-agent-ad4befae6823a8cd3→main | #25 | ✅ Merged |
| [#30](https://github.com/Leon-87-7/vig/pull/30) | refactor(#24): extract run_prd() skeleton from run_auto/run_intent | worktree-agent-a516f10e59bd7c633→main | #24 | ✅ Merged |
| [#29](https://github.com/Leon-87-7/vig/pull/29) | feat(#23): GeminiClient core module + migrate enrichment.py | worktree-agent-a8b8a8dda45b0f1fb→main | #23 | ✅ Merged |
| [#28](https://github.com/Leon-87-7/vig/pull/28) | feat(#21): GitHub service + Redis cache for repo enrichment | worktree-agent-a0fe5775b79547014→main | #21 | ✅ Merged |
| [#20](https://github.com/Leon-87-7/vig/pull/20) | feat(#17/#18): template system — data layer + handler layer (Phases 1–8) | feat/template-system-17-18→main | #17, #18 | ✅ Merged |
| [#19](https://github.com/Leon-87-7/vig/pull/19) | feat(#15): extend /transcript to support TikTok/Instagram via yt-dlp | feat/15-tiktok-instagram-transcript→main | #15 | ✅ Merged |
| [#14](https://github.com/Leon-87-7/vig/pull/14) | feat(#7): Mini-PRD intent slot + /spec + chat_state routing | feat/issue-7-intent-slot→main | #7 | ✅ Merged |
| [#12](https://github.com/Leon-87-7/vig/pull/12) | feat: brain backfill, photo OCR, and Mini-PRD auto slot (#6, #8, #9, #11) | feat/issues-6-8-9-11-brain-photo-prd→main | #6, #8, #9, #11 | ✅ Merged |
