# Parked Feature Handoff

This is a design handoff for roadmap items that are intentionally parked behind
the document-pipeline MVP and current dashboard work. It is not a sprint plan.
Use it to decide product shape before converting any section into ADRs or
implementation issues.

Primary sources:

- `docs/roadmap.md`
- `docs/adr/0022-centralized-platform-storage.md`
- `docs/adr/0023-liteparse-document-pipeline.md`
- `docs/adr/0025-server-resolved-thumbnails-storage-seam.md`
- `CONTEXT.md` glossary entry: "Brain tiers"
- GitHub issues #150-#158 for the document-pipeline MVP foundation

## Current Baseline

The accepted baseline is:

- Platform-owned GCS is the primary file store.
- Drive and Sheets are opt-in exports, never pipeline dependencies.
- Document MVP is Telegram-first plus direct file URLs.
- Liteparse lives in the `vig-document` sidecar.
- The document sidecar returns plain text for MVP; spatial JSON and screenshots
  are deliberately deferred.
- Markdown rendering is on-demand from cached plain text, not automatic.
- Jobs, enrichment, visibility, and Second Brain records must remain
  tenant-scoped even when a parsed artifact is content-hash deduplicated.

## Parked Feature 1: Drive/Sheets Opt-in Export Migration

### Why It Exists

The product is moving from a single-user personal tool to a multi-user product.
The current unconditional Drive/Sheets writes in `short_video`, `long_video`,
`article`, `repo`, and `prd` are migration debt. They worked for the personal
tool, but they make Google credentials part of the hot path.

### Already Decided

- Primary records live in platform infrastructure.
- Google Drive and Sheets become connected integrations.
- No pipeline may fail because Drive or Sheets failed.
- Export work is background/fire-and-forget.
- Document Analysis export is represented by issue #158, but the broader
  migration covers every existing processor.

### Design Questions

- Is "Connect Google" positioned as backup, export, collaboration, or power-user
  workflow?
- Where does the user see export status: job detail, settings, toast, activity
  log, or all of these?
- Does the user choose Drive, Sheets, or both independently?
- Should export be automatic after connection, manual per job, or configurable
  by content type?
- What happens to existing operator-owned Drive/Sheets artifacts during the
  migration: leave them as legacy links, backfill into platform storage, or hide
  them from new users?
- What is the minimum privacy copy required before asking for Google OAuth
  scopes?

### Product Shape To Resolve

- Settings page for connected integrations.
- Per-job export action and export state.
- Error language for failed export that makes clear the analysis is complete.
- A default export policy after a user connects Google.

### Engineering Shape

- `connected_integrations` table:
  `chat_id, service, access_token, refresh_token, scopes, created_at`.
- `/connect/google` OAuth flow in the web dashboard.
- `user_has_integration(chat_id, "google")` guard.
- Export queue task after primary job completion.
- Existing `GOOGLE_DRIVE_FOLDER_*` and `GOOGLE_SHEETS_ID` env vars become
  optional or legacy-only.

### Do Not Reopen

- Do not make Drive/Sheets required for onboarding.
- Do not let export failure mark the primary job failed.
- Do not turn this into full BYOC storage; ADR-0022 chose centralized storage.

## Parked Feature 2: Large Telegram File Ingestion

### Why It Exists

Telegram Bot API `getFile` caps bot downloads at 20MB. Document MVP rejects
larger files and points users toward future web upload. That is acceptable for
MVP but weak for PDFs, slide decks, and long scanned documents.

### Already Decided

- MVP rejects `document.file_size > 20MB`.
- The preferred upgrade path is the official self-hosted `telegram-bot-api`
  server.
- MTProto user-session approaches are rejected because they reintroduce
  account-suspension and ToS-gray risk.

### Design Questions

- Is large-file support still Telegram-first, or should web upload be the
  preferred path once it exists?
- What upload size is the actual product promise: 50MB, 200MB, 2GB, or plan
  based?
- Should large Telegram files show progress, delayed acknowledgement, or a
  simple "received, processing" message?
- Should users be nudged to web upload for anything over 20MB even after the
  self-hosted Bot API exists?
- What failure copy should distinguish Telegram retrieval failure from parse
  failure?

### Product Shape To Resolve

- Maximum supported file size per channel.
- User-facing copy for large-file wait states.
- Whether file size affects pricing, quotas, or retention.
- Whether the web upload surface should supersede this work.

### Engineering Shape

- Add a `telegram-bot-api` container.
- Configure the Telegram client base URL for local Bot API.
- Raise or remove the 20MB pre-check in document ingestion.
- Revisit worker/sidecar memory and timeout budgets for large files.
- Keep raw bytes stored in GCS using the same `documents/{sha256}.{ext}` key.

### Do Not Reopen

- Do not use Telethon/Pyrogram/user-session download for SaaS ingestion.
- Do not bypass GCS by pushing large bytes through Redis or a shared local
  filesystem.

## Parked Feature 3: Document Spatial Source Highlighting

### Why It Exists

Liteparse can expose page-level screenshots and bounding boxes, but the MVP
throws that away because Telegram delivery only needs plain text and enrichment.
Spatial data becomes valuable when the dashboard can show a PDF/source viewer.

### Already Decided

- MVP sidecar returns plain text only.
- Spatial JSON and screenshots are deferred.
- Future storage for spatial JSON should live in GCS, not a DB column.
- Re-parsing or extending the sidecar contract later is acceptable.

### Design Questions

- What is the primary user moment: "jump to source", hover highlight, citation
  evidence, table extraction, or visual slide preview?
- Should source highlighting attach to every enrichment claim or only selected
  fields like references/key points?
- Is the source viewer a job-detail mode, a side panel, or a full-screen review
  surface?
- Should highlights be trust/evidence UI, editing UI, or both?
- Do users need original document download, parsed text, Markdown, and visual
  source view all in one place?
- What is the fallback when a claim cannot be mapped to a bounding box?

### Product Shape To Resolve

- PDF/document viewer layout in the dashboard.
- Highlight interaction model.
- Citation granularity.
- Whether screenshots are rendered lazily per page or generated during parse.
- How this behaves for DOCX/PPTX/XLSX and images, not just PDFs.

### Engineering Shape

- Sidecar contract gains an `include_spatial=true` mode or a second endpoint.
- Store spatial JSON at a GCS key tied to the document hash or job id.
- Store/render page screenshots separately if needed.
- Add API endpoints that enforce job ownership before serving spatial assets.
- Dashboard viewer maps page coordinates to rendered page dimensions.

### Do Not Reopen

- Do not make spatial extraction required for Telegram MVP.
- Do not store large page-coordinate payloads directly in SQLite job columns.
- Do not treat spatial data as tenant-private if keyed only by content hash;
  job visibility must still be tenant-scoped.

## Parked Feature 4: Web UI Pipeline Ingestion

### Why It Exists

The dashboard currently browses and annotates existing results. Telegram remains
the ingestion channel. A complete product needs web ingestion: paste URLs,
upload files, and start analysis without Telegram.

### Already Decided

- Web upload eventually uses the same jobs table and GCS storage path as
  Telegram document ingestion.
- Result delivery on web should be dashboard-native: `GET /api/jobs/{id}`,
  polling, or websocket push.
- No delivery dispatcher is needed until there is a second delivery surface.

### Design Questions

- Is web ingestion a compact command bar, a full upload page, or a contextual
  action inside Spaces?
- Does the user choose a pipeline explicitly, or does vig auto-detect and show
  the detected type?
- Should URL paste and file upload share one composer?
- How does the dashboard show queued, processing, parse failed, enrichment
  failed, export failed, and complete states?
- Should users assign tags/spaces/templates at ingestion time or after results?
- How does web ingestion coexist with Telegram command UX and Freestyle?

### Product Shape To Resolve

- First-screen placement for "new job".
- Upload progress and cancellation.
- Batch upload/paste behavior.
- Post-submit route: stay on composer, open job detail, or show queue.
- Whether web jobs send anything back to Telegram.
- Error taxonomy and copy for non-Telegram users.

### Engineering Shape

- `POST /api/jobs` accepting URL or file upload.
- Browser upload path writes to GCS, creates a job row, and enqueues the worker
  task.
- Shared routing service so webhook and API do not duplicate pipeline detection.
- Web result surface reads from existing job endpoints or a websocket/polling
  layer.
- Ownership checks must use the authenticated dashboard session.

### Do Not Reopen

- Do not make Telegram-specific delivery assumptions inside processors.
- Do not introduce a separate web-only jobs table.
- Do not use Google Drive as upload staging.

## Parked Feature 5: Brain Tiers

### Why It Exists

The Second Brain link graph is global today. That is tolerable for a single-user
tool, but a product needs a privacy model. The intended future is not
shared-by-default; it is private by default with explicit sharing.

### Already Decided

- Future tiers:
  - Private individual brain: default, `links WHERE chat_id = me`.
  - Community brain: explicit per-link opt-in via `shared_to_community = 1`.
  - Group brain: isolated per group tenant.
- Required columns: `links.chat_id` and `links.shared_to_community DEFAULT 0`.
- Dashboard eventually gets a "My / Community" brain toggle.
- Shared-by-default across all individuals is rejected.

### Design Questions

- What is the user-facing name: My Brain, Community Brain, Shared Brain, Team
  Brain, Spaces Brain?
- Where does the share action live: job detail, link detail, brain search
  results, or all of them?
- Is sharing reversible, and how is removal from community search explained?
- Does community sharing expose source URL only, title/topic, summary, related
  links, or all generated metadata?
- Are group brains tied to Telegram groups, dashboard teams, Spaces, or a new
  tenant model?
- How should search blend My and Community results: separate tabs, toggle,
  merged with badges, or scoped query?

### Product Shape To Resolve

- Sharing controls and confirmation copy.
- Search scope switcher.
- Community result badges and provenance.
- Group/team information architecture.
- Moderation or quality controls for the community corpus.

### Engineering Shape

- Add owner and share columns to `links`.
- Backfill existing global links to the current operator's `chat_id` or mark as
  legacy according to migration design.
- Update brain ingest to write owner `chat_id`.
- Update search queries for My, Community, and Group scopes.
- Add API and UI controls for toggling `shared_to_community`.

### Do Not Reopen

- Do not make user history public by default.
- Do not infer sharing from Spaces membership unless a group-brain design
  explicitly says so.
- Do not let community search bypass tenant visibility rules.

## Suggested Design Order

1. Web UI pipeline ingestion: this defines the second delivery surface and will
   clarify status, upload, and job-detail needs.
2. Drive/Sheets opt-in exports: this affects settings, job detail, and
   completion states across all pipelines.
3. Document spatial source highlighting: best designed once job detail and web
   ingestion flows are mature.
4. Brain tiers: product-defining, but it needs careful privacy and information
   architecture design before implementation.
5. Large Telegram file ingestion: useful operational upgrade, but likely less
   important once web upload exists unless Telegram remains the primary channel.

## Open Cross-Cutting Questions

- What are the retention and deletion semantics for raw files, parsed text,
  Markdown, screenshots, spatial JSON, thumbnails, and exports?
- Which features are plan-gated or quota-gated?
- What is the canonical job state model across Telegram and web?
- Should every artifact have a user-visible "download" affordance?
- How much provenance does the product expose by default?
- What is the user promise around privacy for content-hash deduplicated
  artifacts?

## Not Parked

The following are already represented as implementation issues and should be
treated as the document MVP track, not as open product design:

- #150 GCS content-addressed storage seam
- #151 Telegram file upload ingestion
- #152 Direct document URL routing
- #153 `vig-document` liteparse sidecar
- #154 Parse cache and automatic Gemini enrichment
- #155 Plain text and enrichment Telegram delivery
- #156 On-demand Markdown rendering
- #157 Freestyle re-runs from cached parse
- #158 Document Analysis export hook
