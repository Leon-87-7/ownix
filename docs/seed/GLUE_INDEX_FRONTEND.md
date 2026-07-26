# vig — Frontend Glue-Layer Index

**Last Updated:** 2026-07-25
<!-- seed-index: coverage=bd806a4 drift=bd806a4 -->

Covers `web/app/**` route pages/layouts and the "wiring" components in
`web/components/` — the ones that compose hooks + API data + child
components into a working screen, or own cross-domain handlers/navigation.
Pure presentational/leaf components (icons, badges, tooltips) are excluded;
see `FUNCTION_INDEX.md` for the already-documented `web/lib/` (including all
hooks) — hooks are referenced by name below, not re-described.

---

## Surprises / notable findings

1. **`RecoveryPanel` secretly drives the command launcher, not just its own UI.** It calls `useSubmitJobOptional()` and registers its "Clear failed" action into `SubmitJobProvider`'s command-shortcut table (key `c`) via a ref-based effect — so the global `c` keyboard shortcut on the Feed page is actually implemented inside a component that looks like a self-contained status widget.
2. **`SubmitJobProvider` (in `web/components/feed/submit-job.tsx`) is the single largest piece of cross-domain glue in the app** — global keyboard shortcuts (`n`/`d`/`u`/`l`/`c`/`/`/`*`/Cmd+Shift+K), three dialogs (Submit URL, Ingest Link, Ingest Docs), a slide-up mobile Sheet, and the job-submission POST itself all live in one provider mounted once in the dashboard layout. Nothing under `feed/`, `doc-parser/`, or the header could add a "submit" affordance without going through it.
3. **`ExportModal` (`ui/export-modal.tsx`) is Spaces-only despite living in `ui/`** — its only caller is `spaces/[id]/page.tsx`; the name is generic but the domain is not.
4. **`useSpaceUrls.reorderUrl` (called from `UrlsTab`) and `useSpaceContext.reorderBlob` (called from `ContextTab`) duplicate the same optimistic-swap-then-refetch pattern** on top of `swapSortOrder()` — this is the same duplication `FUNCTION_INDEX.md` already flagged (frontend finding #7), visible here at the call site as two nearly identical `ReorderButtons` wirings.
5. **`DevPersonaSwitch` and `RestrictedFacade`/`InviteGate` all read/write the same `ownix_preview` cookie indirectly through `/restricted`** (a route handler, `web/app/restricted/route.ts`, not a page) — none of the in-scope components set the cookie directly; they all navigate to `/restricted` (or `/restricted?exit=1`) and let that route decide, which is easy to miss since it's not a `page.tsx` and technically out of this survey's scope.
6. **`job-card-tags.tsx` fires one tag fetch per rendered card** (`useJobTags(jobId, 'ok')` inside `JobCardTags`, mounted by both `JobCard` and `PreviewCard`) — flagged in its own source comment as a scaling risk ("N feed cards = N tag fetches") with a suggested future fix (fold tags into `/api/jobs`).

---

## Feed

#### `FeedPage(): JSX.Element` — `web/app/(dashboard)/feed/page.tsx`
**Does:** Route shell that wraps `FeedPageContent` in a `Suspense` boundary (required because the content reads `useSearchParams`). All real wiring lives in `FeedPageContent`.
**Called from:** Route entry point: `/feed`
**Usage:** Route path `/feed`

#### `FeedPageContent(): JSX.Element` — `web/app/(dashboard)/feed/page.tsx`
**Does:** The Feed page's full orchestration layer — merges `useFeedData` (server jobs), `useSubmitJob`'s `lastAccepted` (optimistic rows for a just-submitted job), and `useFuseSearch` (client-side fuzzy filter) into one job list; drives `useInFlightPolling` to keep refreshing while any job is still processing; owns the Jobs/Links tab switch (gating Links behind `useLinksTable({ enabled })`), the grid/list layout toggle (persisted to `localStorage`), and a single URL-param cleanup effect that folds OAuth-return (`?google=`), share-target (`?share_url=`), and `?view=links` handling into one `router.replace`. Registers Feed's search-focus behavior into the global command launcher via `registerFeedSearch`. Composes `StatsOverview`, `FilterBar`, `RecoveryPanel`, `LinksTable`/`LinksSearchBar`, `PreviewGrid`, and `JobCard`.
**Called from:** `FeedPage` (same file)
**Usage:** `<FeedPageContent />` inside a `Suspense` boundary

#### `RestrictedIntroModal(): JSX.Element` — `web/app/(dashboard)/feed/page.tsx`
**Does:** One-time (per browser session, via a session cookie rather than `sessionStorage` so it holds across tabs) dialog explaining Restricted mode, shown only when `useRestrictedMode().restricted` is true. "Get access" routes to `/login?from=restricted`.
**Called from:** `FeedPageContent` (same file)
**Usage:** `<RestrictedIntroModal />`

#### `JobCard({ job, contentType, status }): JSX.Element` — `web/components/feed/job-card.tsx`
**Does:** The Feed list-view row — a full-card overlay `<Link>` (built via `buildJobHref`) to the job detail page, with `StatusBadge`/`PlatformBadge`/`DateTime` plus a `JobCardTags` dropdown layered above the link so its button isn't an invalid interactive descendant of the anchor.
**Called from:** `FeedPageContent` (`web/app/(dashboard)/feed/page.tsx`)
**Usage:** `<JobCard job={job} contentType={ctFilter} status={stFilter} />`

#### `JobCardTags({ jobId, countOnly }): JSX.Element` — `web/components/feed/job-card-tags.tsx`
**Does:** Fetches and renders a job's attached tags via `useJobTags(jobId, 'ok')`, composing `TagChips` + `TagMenu` (from `ui/tag-picker.tsx`). `countOnly` suppresses the chip row and shows just the menu's count badge — used by the denser `PreviewCard`.
**Called from:** `JobCard` (`job-card.tsx`), `PreviewCard` (`preview-card.tsx`)
**Usage:** `<JobCardTags jobId={job.id} countOnly />`

#### `PreviewCard({ job, platformGlyph, contentType, status, variant, className }): JSX.Element` — `web/components/feed/preview-card.tsx`
**Does:** The grid-view equivalent of `JobCard` — full-card overlay link, `Thumbnail` (internal), title/status row, and a count-only `JobCardTags`. `variant` (`default`/`bento`/`compact`) drives per-layout spacing so `PreviewGrid` can reuse one card across three grid shapes.
**Called from:** `PreviewGrid` (`preview-grid.tsx`)
**Usage:** `<PreviewCard job={job} contentType={contentType} status={status} variant="bento" />`

#### `PreviewGrid({ jobs, contentType, status, variant }): JSX.Element` — `web/components/feed/preview-grid.tsx`
**Does:** Thin layout wrapper — picks a CSS grid class (`uniform`/`bento`/`shorts`) and maps `jobs` to `PreviewCard`, translating grid `variant` into the card's own `variant` prop plus per-item bento row-span classes based on `job.thumbnail_kind`.
**Called from:** `FeedPageContent` (`web/app/(dashboard)/feed/page.tsx`)
**Usage:** `<PreviewGrid jobs={displayedJobs} contentType={ctFilter} variant="bento" />`

#### `LinksTable({ linksData }): JSX.Element` / `LinksSearchBar({ linksData }): JSX.Element` / `LinkPreviewPanel({ linksData }): JSX.Element` — `web/components/feed/links-table.tsx`
**Does:** The Feed's "Links" tab — a desktop table + mobile card list driven entirely by `useLinksTable`'s returned `UseLinksTableResult` (pagination, sort order, keyboard row navigation with ↑/↓, hover/selection-driven preview fetch). `LinksSearchBar` renders inside `FilterBar`'s tab row (via its `searchSlot` prop) instead of below the table, since Links hides the standard job filters. `LinkPreviewPanel` shows the selected row's og:image (proxied same-origin via `linkPreviewImageUrl`) and tag cluster.
**Called from:** `FeedPageContent` (`web/app/(dashboard)/feed/page.tsx`)
**Usage:** `<LinksTable linksData={linksData} />`, `searchSlot={<LinksSearchBar linksData={linksData} />}`

#### `RecoveryPanel({ contentType, onRecovered, active }): JSX.Element | null` — `web/components/feed/recovery-panel.tsx`
**Does:** Surfaces `useRecovery`'s stuck/failed-job counts as an expandable action row (retry pending, retry failed, clear failed with a `confirm()` guard) and — see finding #1 above — mirrors its "clear failed" action into `SubmitJobProvider`'s global `c` shortcut via `registerFeedRecovery`. `active={false}` (used on the Links tab) suppresses the whole panel since links have no job-status lifecycle.
**Called from:** `FeedPageContent` (`web/app/(dashboard)/feed/page.tsx`) via `FilterBar`'s `recoveryPanel` slot
**Usage:** `<RecoveryPanel contentType={ctFilter} onRecovered={refreshFeed} active={!showingLinks} />`

#### `StatsOverview({ stats, contentType }): JSX.Element` — `web/components/feed/stats-overview.tsx`
**Does:** Renders the Feed's total/done/pending/error/processing breakdown — a collapsible single-line summary on mobile, a `StatCard` grid on desktop. Purely presentational over the `stats` prop (no fetch of its own); the data comes from `useFeedData` upstream.
**Called from:** `FeedPageContent` (`web/app/(dashboard)/feed/page.tsx`)
**Usage:** `<StatsOverview stats={stats} contentType={ctFilter} />`

#### `SubmitJobProvider({ children }): JSX.Element` / `useSubmitJob()` / `useSubmitJobOptional()` — `web/components/feed/submit-job.tsx`
**Does:** App-wide context provider (mounted once in the dashboard layout) owning: three dialogs (Submit URL via `SubmitUrlForm`, Ingest Link, Ingest Docs via `DocUploadPanel`), a mobile intake `Sheet`, the global keyboard-shortcut table (`n`/`d`/`u`/`l`/`c`/`/`/`*`, plus Cmd/Ctrl+Shift+K for the command launcher), and the actual `POST /api/jobs` submission logic for both "submit URL" and "ingest link" flows. Restricted-mode-aware: every "open" action is gated through `showRestrictedToast` when `useRestrictedMode().restricted`. `useSubmitJobOptional` is a non-throwing variant for components (like `RecoveryPanel`) that might render outside the provider in isolated tests.
**Called from:** `web/app/(dashboard)/layout.tsx`; consumed via `useSubmitJob()`/`useSubmitJobOptional()` from `FeedPageContent`, `AppHeader`, `RecoveryPanel`
**Usage:** `<SubmitJobProvider>{children}</SubmitJobProvider>` wrapping the dashboard; `const { openIntake, lastAccepted } = useSubmitJob()`

#### `SubmitUrlForm(props): JSX.Element` — `web/components/feed/submit-url-form.tsx`
**Does:** Pure controlled form (URL input, template `<select>`, conditional freestyle-prompt textarea, submit button) — all state and the submit handler are owned by `SubmitJobProvider`; this component only renders/dispatches the props it's given.
**Called from:** `SubmitJobProvider` (`submit-job.tsx`)
**Usage:** `<SubmitUrlForm url={url} onUrlChange={setUrl} template={template} onSubmit={submitJob} ... />`

---

## Brain

#### `BrainPage(): JSX.Element` — `web/app/(dashboard)/brain/page.tsx`
**Does:** Wires `useSemanticSearch` (query state, search execution, result/error/loading state machine) to a search input and to `BrainGraph`, so the same query drives both the ranked result list and the force-directed graph visualization. Handles the "blank query" guard locally (focuses the input, shows a warning) before delegating to the hook's `runSearch`.
**Called from:** Route entry point: `/brain`
**Usage:** Route path `/brain`

#### `BrainGraph({ results, searchState }): JSX.Element` — `web/components/brain/brain-graph.tsx`
**Does:** Renders the Second Brain link graph via a dynamically-imported (`ssr: false`) `react-force-graph-2d`, fetching its own `nodes`/`edges` payload independently of the search box, then cross-references `results` (the semantic-search matches from `useSemanticSearch`) to highlight matching nodes in signal amber and dim the rest. Owns node coloring by topic (deterministic hash → palette), HTML-escaped tooltips, camera fit/reset controls (`GraphControl`), and motion timing — the most visually complex component in the app outside the landing page.
**Called from:** `BrainPage` (`brain/page.tsx`)
**Usage:** `<BrainGraph results={results} searchState={searchState} />`

---

## Spaces

#### `SpacesPage(): JSX.Element` — `web/app/(dashboard)/spaces/page.tsx`
**Does:** Restricted-mode gate: renders `RestrictedFacade` when `useRestrictedMode().restricted`, otherwise delegates to `SpacesWorkspace`.
**Called from:** Route entry point: `/spaces`
**Usage:** Route path `/spaces`

#### `SpacesWorkspace(): JSX.Element` — `web/app/(dashboard)/spaces/page.tsx`
**Does:** Lists all Spaces (`useSpaceList`) as a `SpaceCard` grid, plus an inline create form driven by `useCreateSpace` (name/color/icon picker from `SPACE_ICONS`). Owns loading/error/empty states directly (not via `feed-states.tsx` helpers, except `SkeletonBlock`).
**Called from:** `SpacesPage` (same file)
**Usage:** `<SpacesWorkspace />`

#### `SpaceCard({ space, onDeleted }): JSX.Element` — `web/components/spaces/space-card.tsx`
**Does:** A Space tile linking to `/spaces/[id]`, with its own inline delete-confirm flow (`DELETE /api/spaces/[id]`) that swaps the whole card into a "Delete this space?" confirmation state rather than using a shared modal.
**Called from:** `SpacesWorkspace` (`spaces/page.tsx`)
**Usage:** `<SpaceCard space={space} onDeleted={reload} />`

#### `SpaceDetailPage(): JSX.Element` — `web/app/(dashboard)/spaces/[id]/page.tsx`
**Does:** The single-space page — combines `useSpaceDetail` (fetch/fetchState) and `useSpaceEdit` (inline rename/recolor form) with a local delete handler (`DELETE /api/spaces/[id]`, `router.push('/spaces')` on success), a `TabBar` switching between `UrlsTab` and `ContextTab`, and an on-demand `ExportModal`. Uses `useParams()` rather than the page's `params` prop (a documented Next 16 gotcha — reading `params` directly returns `undefined` client-side and 404s the fetch).
**Called from:** Route entry point: `/spaces/[id]`
**Usage:** Route path `/spaces/[id]`

#### `UrlsTab({ spaceId }): JSX.Element` — `web/app/(dashboard)/spaces/[id]/UrlsTab.tsx`
**Does:** Lists jobs pinned to this space (`useSpaceUrls`) with reorder (`ReorderButtons` → `reorderUrl`), remove, and an "add job" `<select>` populated from `allJobs` minus already-pinned ids.
**Called from:** `SpaceDetailPage` (`spaces/[id]/page.tsx`)
**Usage:** `{activeTab === "urls" && <UrlsTab spaceId={id} />}`

#### `ContextTab({ spaceId }): JSX.Element` — `web/app/(dashboard)/spaces/[id]/ContextTab.tsx`
**Does:** Manages the space's free-text "context blobs" (`useSpaceContext`) — add/rename/reorder/delete, each blob edited via a dynamically-imported `MarkdownEditor` (`ssr: false`, so it never ships to the server bundle).
**Called from:** `SpaceDetailPage` (`spaces/[id]/page.tsx`)
**Usage:** `{activeTab === "context" && <ContextTab spaceId={id} />}`

#### `ExportModal({ spaceId, spaceName, onClose }): JSX.Element` (default export) — `web/components/ui/export-modal.tsx`
**Does:** Fetches `/api/spaces/[id]/export/markdown` on mount, then offers four export paths: client-side `.md`/`.txt` blob download, browser print-to-PDF (`printMarkdown`), and a "Create Google Doc" button wired to `useGdocExport` (surfaces a specific "Drive not configured → fall back to PDF" error state). Despite living under `ui/`, it is Spaces-only — see finding #3.
**Called from:** `SpaceDetailPage` (`spaces/[id]/page.tsx`)
**Usage:** `{showExport && <ExportModal spaceId={id} spaceName={space.name} onClose={() => setShowExport(false)} />}`

---

## Doc Parser

#### `DocParserPage(): JSX.Element` — `web/app/(dashboard)/doc-parser/page.tsx`
**Does:** Restricted-mode gate (`RestrictedFacade` vs `DocParserWorkspace`), same pattern as `SpacesPage`.
**Called from:** Route entry point: `/doc-parser`
**Usage:** Route path `/doc-parser`

#### `DocParserWorkspace(): JSX.Element` — `web/app/(dashboard)/doc-parser/page.tsx`
**Does:** Lists document jobs (`GET /api/jobs?content_type=document`), live-updated via a raw `EventSource('/api/parsed/events')` SSE subscription (not one of the documented hooks) that re-triggers the fetch on a `jobs` event — the ref-indirection (`loadRef`) exists so the SSE handler always calls the latest `load` closure without tearing down/reconnecting the EventSource on every status-filter change. Composes `FilterBar`, `DocUploadPanel`, and per-row `TelegramToggle`.
**Called from:** `DocParserPage` (same file)
**Usage:** `<DocParserWorkspace />`

#### `DocUploadPanel({ onUploaded, flat }): JSX.Element` — `web/components/doc-parser/doc-upload-panel.tsx`
**Does:** Both document-intake paths in one component — drag/drop or click-to-browse file upload (`POST /api/parsed/upload`) and a URL-fetch form (`POST /api/parsed/url`) — reporting the resulting job id back via `onUploaded` so callers can route to it. `flat` strips card chrome for use inside a dialog (the global "Ingest Docs" flow in `SubmitJobProvider`).
**Called from:** `DocParserWorkspace` (`doc-parser/page.tsx`), `SubmitJobProvider` (`feed/submit-job.tsx`)
**Usage:** `<DocUploadPanel onUploaded={(jobId) => go(jobId ? \`/doc-parser/${jobId}\` : '/doc-parser')} flat />`

#### `DocDetail(): JSX.Element` (default export, file `doc-parser/[id]/page.tsx`)
**Does:** The document job detail page — loads the job + its parsed `Output[]` in parallel, then owns two mutating actions (`clean` → `POST /api/parsed/[id]/clean`, `freestyle` → `POST /api/parsed/[id]/freestyle` with a random-prompt picker dialog) that both funnel through a shared `runAction` helper (busy/error state + `reloadKey` bump to refetch). Renders `TelegramToggle`, `DocumentSourceChip`, and one `OutputCard` per output (each with its own copy/download-as-file actions).
**Called from:** Route entry point: `/doc-parser/[id]`
**Usage:** Route path `/doc-parser/[id]`

#### `DocumentSourceChip({ source }): JSX.Element` — `web/components/doc-parser/document-source-chip.tsx`
**Does:** Parses a document job's `source` string into a display chip — recognizes the content-addressed `documents/<sha256>.<ext>` GCS key pattern (via `getDocumentSourceMeta`) and falls back to parsing it as a URL/filename otherwise, with a copy-to-clipboard button for the id/sha.
**Called from:** `DocDetail` (`doc-parser/[id]/page.tsx`)
**Usage:** `<DocumentSourceChip source={job.url} />`

#### `TelegramToggle({ jobId, value }): JSX.Element` — `web/components/doc-parser/telegram-toggle.tsx`
**Does:** Three-state (`off`/`on`/`retroactive`) delivery toggle — a tap flips `off`↔`on`, a 1.5s pointer-hold sets `retroactive` (re-deliver already-processed output) — persisting via `PUT /api/parsed/[id]/telegram-delivery` and reconciling local state with whatever the server actually stored.
**Called from:** `DocParserWorkspace` (`doc-parser/page.tsx`), `DocDetail` (`doc-parser/[id]/page.tsx`)
**Usage:** `<TelegramToggle jobId={job.id} value={job.telegram_delivery} />`

---

## Controls / Prompts

#### `ControlsPage(): JSX.Element` — `web/app/(dashboard)/controls/page.tsx`
**Does:** Restricted-mode gate, then composes three independent settings sections inside collapsible `Section`s: `TagsTab` (tag CRUD), two `DomainTab` instances pointed at different API paths (`/api/controls/allowed-domains` vs `/api/controls/ignored-domains` — same component, different data), and `RecoveryTab` (global, not content-type-scoped, recovery actions).
**Called from:** Route entry point: `/controls`
**Usage:** Route path `/controls`

#### `PromptsPage(): JSX.Element` / `PromptsWorkspace(): JSX.Element` — `web/app/(dashboard)/prompts/page.tsx`
**Does:** Restricted-mode gate + workspace listing user-created enrichment templates (`useTemplateList`), with `CreateForm` (name/description/extra-instructions, name pattern-locked to `[a-z0-9_-]+`) and `UserTemplateRow` (inline edit/delete per template, each with its own optimistic error handling).
**Called from:** Route entry point: `/prompts`
**Usage:** Route path `/prompts`

---

## Job Detail

#### `JobDetailPage(): JSX.Element` — `web/app/(dashboard)/jobs/[id]/page.tsx`
**Does:** The single-job page — combines `useJobDetail` (fetch/fetchState), `useJobAnnotation` (notes, saved via a dynamically-imported `MarkdownEditor`), and `useJobTags` into one screen. Picks the field set to render (`SHORT_FIELDS` vs `ENRICHMENT_FIELDS` from `lib/job-detail-utils`) based on `job.content_type`, and renders each as a `FieldCard`. Restricted-mode disables the notes editor with a tooltip instead of hiding it.
**Called from:** Route entry point: `/jobs/[id]`
**Usage:** Route path `/jobs/[id]`

#### `JobHeader({ job, tags }): JSX.Element` — `web/app/(dashboard)/jobs/[id]/page.tsx`
**Does:** Title/URL/badges header plus adjacent-job pager: fetches `previous_id`/`next_id` from `/api/jobs/[id]/adjacent` (skipped entirely in Restricted mode, since that endpoint is session-gated and would just 401) and wires ArrowLeft/ArrowRight keyboard navigation to them (guarded so it doesn't fire while a form field has focus, via `isEditableTarget`).
**Called from:** `JobDetailPage` (same file)
**Usage:** `<JobHeader job={job} tags={<><TagChips .../><TagMenu .../></>} />`

#### `JobActionsBar({ job, hasFields }): JSX.Element | null` — `web/app/(dashboard)/jobs/[id]/page.tsx`
**Does:** Renders the Drive-link row for a job — "Open this file in Drive" (from `job.drive_url`) and, independently, "Open Ownix folder" (fetched fresh from `/api/google/folder`, gated on `useGoogleStatus().connected`) — plus a "Copy all" button that serializes every present field via `buildMarkdown(job)`.
**Called from:** `JobDetailPage` (same file)
**Usage:** `<JobActionsBar job={job} hasFields={presentFields.length > 0} />`

#### `TagMenu({ jobTags, allTags, onToggle, onCreate, trigger }): JSX.Element` / `TagChips({ jobTags, onRemove }): JSX.Element` — `web/components/ui/tag-picker.tsx`
**Does:** Shared tag-attachment UI used by both the Job Detail page and `JobCardTags`. `TagMenu` is a Radix dropdown with per-tag checkbox rows plus a "New tag…" entry that opens `CreateTagModal` (name/meaning/preset-color-swatch/icon picker); `TagChips` renders attached tags as removable pills.
**Called from:** `JobDetailPage`/`JobHeader` (`jobs/[id]/page.tsx`), `JobCardTags` (`feed/job-card-tags.tsx`), `DocDetail` (`doc-parser/[id]/page.tsx`)
**Usage:** `<TagMenu jobTags={jobTags} allTags={allTags} onToggle={toggleTag} onCreate={createTag} />`

---

## Shell / Layout / Navigation

#### `RootLayout({ children }): JSX.Element` — `web/app/layout.tsx`
**Does:** The outermost HTML shell — loads `Inter`/`JetBrains Mono` fonts, wraps everything in `MockProvider` (so MSW can intercept the very first paint's fetches in `NEXT_PUBLIC_API_MOCK=1` mode) and mounts `SwRegister`. Also conditionally injects an `impeccable` live-reload dev script in development.
**Called from:** Root layout for every route in the app
**Usage:** Implicit — wraps all pages

#### `DashboardLayout({ children }): JSX.Element` — `web/app/(dashboard)/layout.tsx`
**Does:** The `(dashboard)` route group's shell — resolves Restricted mode server-side (`isRestrictedRequest`, cookie + backend cross-check so a stale `ownix_preview` cookie can't override an approved session — see finding #5) and nests every dashboard-wide provider in one fixed order: `TooltipProvider` → `RestrictedModeProvider` → `InviteGate` → `GoogleStatusProvider` → `SubmitJobProvider`, then renders `Sidebar` + `AppHeader` + the scrollable content region (with `ScrollToTop`). `DevPersonaSwitch` is mounted **outside** `InviteGate` deliberately, so it survives the gate screen.
**Called from:** Layout for every route under `web/app/(dashboard)/`
**Usage:** Implicit — wraps `/feed`, `/brain`, `/spaces`, `/doc-parser`, `/controls`, `/prompts`, `/jobs/[id]`

#### `Sidebar(): JSX.Element` — `web/components/shell/sidebar.tsx`
**Does:** The primary nav — a collapsed icon rail on desktop that expands into a full slide-in drawer (with proper APG dialog focus-trap/return-focus/Escape/scroll-lock handling) on click or via a mobile pull-tab. Composes `useSessionUser()` + `useGoogleStatus()` into a combined avatar/connect/disconnect block, with its own `confirm()`-gated disconnect flow.
**Called from:** `DashboardLayout` (`(dashboard)/layout.tsx`)
**Usage:** `<Sidebar />`

#### `AppHeader(): JSX.Element` — `web/components/shell/app-header.tsx`
**Does:** Top bar — wordmark link home, a Restricted-mode banner (with a "Get access" link) in place of the normal tagline when `useRestrictedMode().restricted`, and the "Open command launcher" button wired to `useSubmitJob().openCommand`.
**Called from:** `DashboardLayout` (`(dashboard)/layout.tsx`)
**Usage:** `<AppHeader />`

#### `PageShell({ width, className, children }): JSX.Element` / `PageHeader({ title, icon, description, action }): JSX.Element` — `web/components/shell/page-shell.tsx`
**Does:** The one shared page-container/title-row pair every dashboard page roots in — deliberately dumb layout-only components (max-width + vertical rhythm), included here because nearly every other entry in this document composes them.
**Called from:** Every dashboard page (`feed`, `brain`, `spaces`, `doc-parser`, `controls`, `prompts`, `jobs/[id]`) and `RestrictedFacade`
**Usage:** `<PageShell><PageHeader icon={Brain} title="Brain" /> ... </PageShell>`

#### `AuthShell({ children }): JSX.Element` — `web/components/shell/auth-shell.tsx`
**Does:** Shared full-bleed background/wordmark chrome for the two standalone auth pages (`/login`, `/logout`) — no data logic of its own, but is the layout every auth-flow page composes into.
**Called from:** `LoginPage` (`app/login/page.tsx`), `LogoutPage` (`app/logout/page.tsx`)
**Usage:** `<AuthShell><TelegramLoginWidget /></AuthShell>`

#### `PublicShell({ active, children }): JSX.Element` / `LegalLayout`/`LegalArticle`/`LegalTitle`/`LegalSection`/`LegalList`/`LegalLink` — `web/components/shell/public-shell.tsx`
**Does:** Header/nav chrome + typographic building blocks for the two public legal pages (`/privacy`, `/terms`), with `active` driving the current-page nav highlight.
**Called from:** `web/app/privacy/page.tsx`, `web/app/terms/page.tsx` (both otherwise out of scope as static content)
**Usage:** `<PublicShell active="privacy">...</PublicShell>`

#### `RestrictedFacade({ icon, title, children }): JSX.Element` — `web/components/shell/restricted-facade.tsx`
**Does:** The standard "this feature is locked in preview mode" page body — `PageShell` + `PageHeader` with a "Get access" CTA to `/login?from=restricted`, plus an explanatory paragraph. One component reused verbatim by four different page-level restricted branches.
**Called from:** `DocParserPage`, `PromptsPage`, `SpacesPage`, `ControlsPage`
**Usage:** `if (restricted) return <RestrictedFacade icon={LayoutGrid} title="Collections">...</RestrictedFacade>;`

#### `InviteGate({ children, restricted }): JSX.Element | null` — `web/components/shell/invite-gate.tsx`
**Does:** Session/approval gate wrapping the entire dashboard (below the Restricted-mode branch, which short-circuits it entirely). Fetches `/api/auth/me`, redirects to `/login` on 401/403, and renders `GateScreen` (blocked/pending copy) or an `EmailModal` (first-login email capture) instead of `children` until the user is `approved` with an email on file. In mock mode (`mockModeEnabled()`), short-circuits to a fixed `MOCK_SESSION_USER` instead of fetching.
**Called from:** `DashboardLayout` (`(dashboard)/layout.tsx`)
**Usage:** `<InviteGate restricted={restricted}>{children}</InviteGate>`

#### `GoogleStatusProvider({ children }): JSX.Element` / `useGoogleStatus()` — `web/components/shell/google-status.tsx`
**Does:** Fetches/holds the current user's Google-connection boolean (`GET /api/google/status`) and exposes `refresh`/`disconnect` (`POST /api/google/disconnect`) through context; Restricted mode short-circuits both to a no-op/toast instead of hitting the API.
**Called from:** `DashboardLayout` (`(dashboard)/layout.tsx`); consumed via `useGoogleStatus()` from `Sidebar`, `FeedPageContent`, `JobActionsBar`
**Usage:** `const { connected, disconnect } = useGoogleStatus();`

#### `MockProvider({ children }): JSX.Element` (default export) — `web/components/shell/mock-provider.tsx`
**Does:** In `NEXT_PUBLIC_API_MOCK=1` mode, dynamically imports and starts the MSW browser worker before rendering `children` at all (holding render with `null` until the worker is ready, so first-paint fetches can't race past the mock interceptors); a no-op passthrough otherwise.
**Called from:** `RootLayout` (`app/layout.tsx`)
**Usage:** `<MockProvider>{children}</MockProvider>`

#### `SwRegister(): null` (default export) — `web/components/shell/sw-register.tsx`
**Does:** Registers `/sw.js` as the app's service worker on mount, skipped entirely in mock mode.
**Called from:** `RootLayout` (`app/layout.tsx`)
**Usage:** `<SwRegister />`

#### `ScrollToTop(): JSX.Element` — `web/components/shell/scroll-to-top.tsx`
**Does:** Floating scroll-to-top button scoped to the dashboard's own scroll container (`[data-dashboard-scroll]`, since the app header sits above it and isn't part of the scrollable region) — visible once scrolled past 200px.
**Called from:** `DashboardLayout` (`(dashboard)/layout.tsx`)
**Usage:** `<ScrollToTop />`

#### `TelegramLoginWidget({ align }): JSX.Element` — `web/components/shell/telegram-login-widget.tsx`
**Does:** Injects the official Telegram login `<script>` widget, wires its `onauth` callback to `POST /api/auth/telegram`, and on success does a **hard** `window.location.href = '/feed'` navigation rather than `router.replace` — deliberately, because the dashboard layout's Restricted-mode flag is derived server-side from cookies, and a soft nav can reuse a stale Router Cache entry from an earlier anonymous visit. Also exposes a `devLogin()` path (`POST /api/auth/dev-login`) shown only on `localhost` in development.
**Called from:** `LandingPage` (`app/page.tsx`), `LoginPage` (`app/login/page.tsx`, via `AuthShell`)
**Usage:** `<TelegramLoginWidget align="start" />`

#### `DevPersonaSwitch(): JSX.Element | null` (default export) — `web/components/ui/dev-persona-switch.tsx`
**Does:** Dev-only (`NODE_ENV !== 'production' && NEXT_PUBLIC_API_MOCK === '1'`) draggable floating toggle between the mock approved user and the Restricted-mode visitor persona — a plain `<a href="/restricted[?exit=1]">` rather than a client nav, since flipping personas requires the route handler to actually set/clear the `ownix_preview` cookie (see finding #5).
**Called from:** `DashboardLayout` (`(dashboard)/layout.tsx`, mounted outside `InviteGate`)
**Usage:** `<DevPersonaSwitch />`

#### `FilterBar(props): JSX.Element` / `SegmentedTabs` / `FilterButton` — `web/components/ui/filter-bar.tsx`
**Does:** The shared content-type-tabs + search + status-filter row used by both Feed and Doc Parser. `searchSlot` lets a caller (Links) swap in a custom search control in the same layout slot; `hideSearchAndFilters` drops the status row entirely for views with no job-status concept; `leadingItem` on `SegmentedTabs` flows a page-level action (e.g. Feed's mobile Submit button) into the tab wrap grid.
**Called from:** `FeedPageContent` (`feed/page.tsx`), `DocParserWorkspace` (`doc-parser/page.tsx`)
**Usage:** `<FilterBar tabs={contentTypeTabs} tabValue={ctFilter} onTabChange={setContentType} query={query} setQuery={setQuery} statusValue={stFilter} onStatusChange={setStFilter} recoveryPanel={<RecoveryPanel .../>} />`

#### `ReorderButtons({ onUp, onDown, disableUp, disableDown }): JSX.Element` — `web/components/ui/reorder-buttons.tsx`
**Does:** Tiny shared up/down control — no data logic itself, but is the trigger for the duplicated reorder pattern called out in finding #4.
**Called from:** `ContextTab` (`spaces/[id]/ContextTab.tsx`), `UrlsTab` (`spaces/[id]/UrlsTab.tsx`)
**Usage:** `<ReorderButtons onUp={() => reorderBlob(idx, 'up')} onDown={() => reorderBlob(idx, 'down')} disableUp={idx === 0} disableDown={idx === blobs.length - 1} />`

---

## Auth & Restricted Mode

#### `LoginPage(): JSX.Element` — `web/app/login/page.tsx`
**Does:** Composes `AuthShell` + `TelegramLoginWidget` with a disabled/locked "Connect to Google" hint (Google connect only unlocks post-approval) and a back-to-home link.
**Called from:** Route entry point: `/login`
**Usage:** Route path `/login`

#### `LogoutPage(): JSX.Element` — `web/app/logout/page.tsx`
**Does:** Static "Session closed" confirmation inside `AuthShell`, with a link back to `/login`. No fetch of its own — the actual session-clearing happens server-side before this page is reached.
**Called from:** Route entry point: `/logout`
**Usage:** Route path `/logout`

#### `MiniAppPage(): JSX.Element` — `web/app/mini/page.tsx`
**Does:** The Telegram Mini App entry surface — reads `window.Telegram.WebApp.initData` (or a `?tgWebAppData` query fallback), verifies it against `POST /api/auth/miniapp/session`, and on success shows a "Connect Google" button that opens the returned `google_connect_url` via `WebApp.openLink` (falling back to `window.location.assign` outside Telegram) — `openLink` specifically requires an absolute URL since native Telegram clients can't resolve a relative path.
**Called from:** Route entry point: `/mini`
**Usage:** Route path `/mini`

---

## Landing / Public

#### `LandingPage(): JSX.Element` — `web/app/page.tsx`
**Does:** The public marketing homepage. Server-reads the `vig_session` cookie (making the route dynamic) purely to pick CTA copy ("Open feed" vs "Look inside") — the actual approved/restricted routing decision is delegated to `/restricted` (a route handler) regardless of which label is shown. Composes `TelegramLoginWidget`-adjacent nav, `HeroGradient`, `AppSlot`, `DemoVideo`, and static feature/testimonial sections built from local constant data (`indexBadges`, `tiles`).
**Called from:** Route entry point: `/`
**Usage:** Route path `/`

**Note:** `AppSlot` and `DemoVideo` were checked against the "wire real data" bar and found to be pure client-side animation (an icon-cycling `setInterval` gated by `useReducedMotion`, and an `IntersectionObserver`-driven autoplay/pause) with no fetch or domain-hook usage — same as `CountUp`/`HeroGradient`, they're intentionally omitted as leaf/presentational.

---

## Out of scope but touched by this survey

- `web/app/restricted/route.ts` — not a `page.tsx`, so excluded from the entries above, but it's the actual implementation behind every "Get access" / persona-switch link in this document (sets/clears the `ownix_preview` cookie based on a backend approval check). Worth reading alongside `InviteGate`, `RestrictedFacade`, and `DevPersonaSwitch` if working on Restricted mode.
- `web/app/offline/page.tsx`, `web/app/privacy/page.tsx`, `web/app/terms/page.tsx` — confirmed static/no data wiring (offline page is inline-styled with a single "Retry Feed" link; privacy/terms are `PublicShell`-wrapped static legal copy) — skipped as out of scope.

---

## See also

- `FUNCTION_INDEX.md` — the hook/utility layer this file builds on top of.
- `GLUE_INDEX_BACKEND.md` — the backend orchestration this frontend layer talks to.
- `CAPABILITY_MAP.md` — top-down capability → owning module lookup.
