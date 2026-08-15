# Ownix UI Component Inventory

Generated: 2026-08-15  
Scope: All reusable components in `web/components/`

---

## UI Primitives (`web/components/ui/`)

| Component | Props / Variants | States |
|-----------|------------------|--------|
| **badges.tsx** | `TypeBadge`: label (string: short/long/article/repo/link) | outlined border, text-colored |
| | `StatusBadge`: label (string: done/pending/queued/processing/enriching/transcript_done/error/cancelled) | filled background + text color per status |
| **ghost-button.tsx** | accent: 'signal' \| 'contrasignal' \| 'body' (default); borderLine: '1' \| '2' (default); children; as (element type, default 'button'); className | hover:bg-raised, active:scale-[0.96], focus-visible:ring-2 (signal), disabled:opacity-50 |
| **dialog.tsx** (Radix-based) | DialogContent: hideClose (omit X affordance), className, style; DialogTitle, DialogDescription | data-[state=open]:animate-tooltip-in, data-[state=closed]:animate-tooltip-out; centered via translate; keyboard handling (Escape, outside-click) |
| **sheet.tsx** (Radix-based) | SheetContent: className; SheetTitle, SheetDescription | bottom-sheet slide-up animation (animate-slide-up-in / animate-slide-up-out); inset-x-0 bottom-0; safe-area-inset-bottom |
| **confirm-dialog.tsx** | trigger (ReactNode); title, description, confirmLabel (string); pending (boolean); onConfirm (callback); children (extra content) | pending state: disabled buttons, loading text ("Deleting…"); confirm button: bg-status-error; hover:brightness-110 |
| **tooltip.tsx** | content (ReactNode, optional); side: 'top' \| 'bottom' \| 'left' \| 'right' (default 'top'); align: 'start' \| 'center' \| 'end' (default 'center'); mono (boolean, mono font); controlled open/onOpenChange | data-[state=delayed-open]:animate-tooltip-in, data-[state=instant-open]:animate-tooltip-in; hidden if content falsy/empty |
| **tab-bar.tsx** | tabs (T[]); active (T); onChange; labels (partial record); generic type-safe | active tab: border-b-2 border-signal text-ink; inactive: text-body hover:text-ink |
| **tag-picker.tsx** | TagMenu: jobTags (TagSummary[]); allTags (TagSummary[]); onToggle, onCreate; trigger (optional ReactNode) | menu data-[state=open]:border-line-strong; highlighted item: data-[highlighted]:bg-raised; checkbox: checked/unchecked |
| | TagMark: tag, className (size) | icon from TAG_ICON_NAMES or colored dot |
| | IconPicker: value (icon name or null); color; onSelect | button aria-pressed, selected: border-signal text-ink; unselected: border-line text-muted |
| | TagChips: jobTags, onRemove, compact (mobile truncate name to 3 chars) | inline-flex, border border-line bg-raised, sm:hidden (truncated), sm:inline (full) |
| **tag-form.tsx** | initial (TagFormState); onSubmit, onCancel, submitLabel; onDelete | submitting state: button disabled, text "Saving…"; error: text-status-error; 2-col layout on desktop (sm:) |
| **copy-button.tsx** | value (string to copy); ariaLabel; label (display text) | default: Copy icon; after copy (1.5s): Check icon, label becomes "Copied!" |
| **filter-bar.tsx** | FilterBar: tabs (FilterTab[]), tabValue, onTabChange, query, setQuery, searchInputId, statusFilters, statusValue, onStatusChange, recoveryPanel, actionSlot, hideSearchAndFilters, searchSlot, scrollTabsOnMobile | SegmentedTabs: active tab border-signal text-onsignal fill (bottom-to-top clip-path: inset(0) when active); inactive: border-line hover underline; mobile: 4-column grid; search collapse/expand on mobile (grid-rows-[0fr] / [1fr]) |
| | SegmentedTabs: tabs, value, onChange, label, leadingItem, scrollOnMobile | active: border-signal text-onsignal; disabled: border-line bg-surface text-muted; hover underline on desktop; count badge: bg-on-signal px-1 border |
| | FilterButton (internal): label, active, onClick | active: bg-contrasignal-deep text-onsignal; inactive: border border-line bg-surface hover:bg-raised |
| **date-time.tsx** | iso (ISO string) | SSR: UTC string; hydration: client reformats to browser locale |
| **platform-icon.tsx** | PlatformGlyph: url, contentType (optional), size (default 16), className | youtube/shorts/instagram/tiktok/github → custom SVG; article → favicon; unknown → FileText icon; onError → fallback icon |
| | PlatformBadge: url, contentType | h-6 w-6 border border-line bg-canvas, contains PlatformGlyph (size 14) |
| **export-modal.tsx** | spaceId, spaceName, onClose | loading (SkeletonBlock); loadError (text-status-error); done (gdocStatus: "done" → green success text); exporting: button disabled "Creating Google Doc…" |
| **markdown-editor.tsx** | initialMarkdown, onSave | debounced 800ms on markdown change; displays label "Notes"; prose styling; min-h-[6rem]; border border-line |
| **no-preview-ring.tsx** | seed (for deterministic placement), label (optional) | static ring with rotating text, opacity-60, seeded position/size/angle; logo center, fade effect |
| **preview-motif.tsx** | label, ariaLabel (optional), className, size: 'default' \| 'fill'; treatment: 'default' \| 'hero' | logo animation: 7s (default) or 35s (hero); ring animation: 14s (default) or 35s (hero); motion-safe:animate; hero: gradient fill on text |
| **footer.tsx** | (none) | flex, text-muted, logo animate-ownix-logo-cycle; hover:scale-110 hover:rotate-[-6deg] |
| **public-header.tsx** | (none) | flex items-center, border border-line, backdrop-blur-sm; logo hover effects (scale/rotate); nav links transition-ui |
| **reorder-buttons.tsx** | onUp, onDown, disableUp, disableDown | up/down buttons: text-muted hover:text-ink disabled:opacity-30 |
| **dev-persona-switch.tsx** | (none, dev-only) | fixed bottom-10 right-10 z-50; draggable (pointer events); PulsingBorder shader; green (mock user) or red (visitor); shows if `NODE_ENV !== production && NEXT_PUBLIC_API_MOCK === '1'` |

---

## Shell Components (`web/components/shell/`)

| Component | Props / Variants | States |
|-----------|------------------|--------|
| **app-header.tsx** | (none, global sticky header) | Sticky z-20 bg-canvas/85 backdrop-blur-md; restricted mode: signal badge; command launcher (Ctrl+Shift+K, tooltip); mobile-center, sm-left layout |
| **page-shell.tsx** | PageShell: width: 'default' (max-w-5xl) \| 'narrow' (max-w-3xl); className; children | mx-auto space-y-6 |
| | PageHeader: title, icon (LucideIcon, optional), description, action | flex flex-wrap gap-3; icon: text-signal; title: 2xl font-semibold; action shrink-0 |
| **sidebar.tsx** | (none, collapsible nav) | Collapsed rail (desktop hidden, sm flex): w-16, icon-only NavLinks (active: bg-raised text-signal); Expanded drawer (fixed inset-y-0 left-0): w-56, slide-in/out; mobile pull-tab (left-0 top-1/2); backdrop (fixed inset-0 z-40); focus management (APG dialog pattern); user avatar with GoogleConnectedAvatar (PulsingBorder if connected); sign-out form |
| | NavLink: item (NavItem), pathname, collapsed, tabbable | active: bg-raised text-signal; inactive: text-body hover:bg-raised hover:text-ink; tooltip on collapsed |
| **google-status.tsx** (provider) | GoogleStatusProvider: children | exports useGoogleStatus(): { connected, refresh, disconnect } |
| **auth-shell.tsx** | children (ReactNode) | flex min-h-screen flex-col items-center justify-center; bg-canvas; animated layered-waves SVG background (saturate-0.5, mask-image); auth-card-enter animation |
| **invite-gate.tsx** | children, restricted (boolean), hasSession (boolean) | Loading: PreviewMotif "CHECKING ACCESS"; LoadError: section with retry button; GateScreen (pending/blocked); QueueStatusBanner (user.status=pending); EmailModal (user.email missing) |
| | GateScreen: status ('pending' \| 'blocked') | h2 text-2xl font-semibold text-ink; rounded-lg border border-line bg-surface p-6 |
| | EmailModal: onSaved callback | input: border-line bg-canvas focus:border-signal; error: text-status-error; saving: button disabled |
| **public-shell.tsx** | PublicShell: active (PublicPage), children | min-h-screen; header: border-b border-line bg-surface; nav links transition-ui |
| | LegalLayout: active, children | grid lg:grid-cols-[1fr_15rem]; sidebar sticky lg:top-8 |
| | LegalArticle, LegalTitle, LegalSection, LegalList, LegalLink | typography helpers for legal pages |
| **restricted-facade.tsx** | icon (LucideIcon), title, children | PageShell wrapper; PageHeader with "Get access" button; signal badge; blue section |

---

## Feed Components (`web/components/feed/`)

| Component | Props / Variants | States |
|-----------|------------------|--------|
| **job-card.tsx** | job (JobSummary), contentType (optional), status (optional) | border border-line bg-surface rounded-lg transition-ui hover:bg-raised; overlay link (inset-0, focus-visible:ring); tags dropdown (pointer-events-auto z-10) |
| **preview-card.tsx** | job (JobSummary), index, platformGlyph (optional), contentType, status, variant: 'default' \| 'bento' \| 'compact' (default); className | Thumbnail: aspect-video (bento/landscape), aspect-[9/16] (portrait/compact), fade on load error; group hover:border-line-strong hover:bg-raised; title truncate; tag count badge; datetime mono text-xs |
| | Variant `bento`: thumbnail stretches to fill row-spanned cell, meta wraps below | sm:aspect-auto sm:h-full; flex-1 on mobile grid collapse |
| | Variant `compact`: 5-up grid, portrait 9:16, status badge dropped | text-xs title, compact spacing |
| **stat-card.tsx** | label (string, uppercase mono), value (number), tooltip (optional), valueClass (status hue, default 'text-ink'), className | border border-line bg-surface rounded-lg px-4 py-3; tabular-nums text-stat font-semibold |
| **job-card-tags.tsx** | jobId, countOnly (boolean) | Tag dropdown or count badge; pointer-events-auto z-10 |
| **feed-states.tsx** | SkeletonList, SkeletonGrid, SkeletonLine, SkeletonBlock, ErrorBanner, EmptyState | SkeletonList: 5 SkeletonRow items; SkeletonGrid: 3x2 SkeletonPreviewCard items; ErrorBanner: border-status-error-tint bg-status-error-tint, Retry button; EmptyState: border border-line bg-surface, conditional text (filters vs no jobs) |
| **preview-grid.tsx** | (grid container, consumer assembles PreviewCard children) | grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 |
| **links-table.tsx** | (consumer component, table of links) | table layout, header row, row striping |
| **stats-overview.tsx** | (consumer component, StatCard grid) | flex flex-wrap gap-3 |
| **recovery-panel.tsx** | (recovery UI) | (unknown, co-located with filter-bar) |
| **folder-tag-form.tsx** | (space folder creation) | (unknown, co-located with feed) |
| **submit-job.tsx** | (submit job modal) | (unknown, co-located with feed) |
| **submit-url-form.tsx** | (URL form) | (unknown, co-located with feed) |

---

## Intake Components (`web/components/intake/`)

| Component | Props / Variants | States |
|-----------|------------------|--------|
| **intake-response-card.tsx** | item (IntakeThreadItem), onAction (callback), pendingActionId, openOfferId, onOpenOffer, onSaveOffer | negative background (status-error-tint) for error/unsupported/rejected/job_deduped; border-status-error/40; label KIND_LABEL; retry button (retrying: disabled); PreviewCard if job.status===done; IntakeStatusLine if processing; IntakeLinksList if artifacts; IntakeActions if onAction |
| **intake-tag-offer.tsx** | action (IntakeActionShape), open (boolean), onOpen, onCancel, onSave, index, total | Closed: button border-line bg-raised hover:border-signal; Open: TagForm inline in p-3 border border-line bg-canvas; "N more" hint |
| **intake-state-banner.tsx** | (polls /api/intake/state) | border-signal/40 bg-status-pending-tint; displays mode label + job_id suffix; Cancel button (cancelling: disabled); cancelError: text-status-error |
| **intake-status-line.tsx** | status (job status) | (unknown, referenced by intake-response-card) |
| **intake-links-list.tsx** | links (Link[]) | (unknown, referenced by intake-response-card) |
| **intake-actions.tsx** | actions (IntakeActionShape[]), onAction, pendingActionId | (unknown, referenced by intake-response-card) |
| **intake-composer.tsx** | (intake message composer) | (unknown) |
| **intake-command-palette.tsx** | (command launcher in intake) | (unknown) |
| **intake-thread.tsx** | (thread display) | (unknown) |
| **intake-upload-dropzone.tsx** | (drag-drop zone) | (unknown) |

---

## Brain Components (`web/components/brain/`)

| Component | Props / Variants | States |
|-----------|------------------|--------|
| **brain-graph.tsx** | results (SearchResult[]), searchState (string: 'results' \| other) | loading: text "Loading Brain graph…"; error: text-status-error "Could not load Brain graph"; empty: text-body "No Brain nodes yet"; ready: ForceGraph2D + controls + topic filter; topic buttons: active bg-raised text-ink ring-line-strong; inactive bg-transparent text-body ring-line; opacity-40 if hidden; GraphControl buttons: hover:bg-raised disabled:opacity-40 |

---

## Spaces Components (`web/components/spaces/`)

| Component | Props / Variants | States |
|-----------|------------------|--------|
| **space-card.tsx** | space (SpaceSummary), onDeleted (callback) | default: group relative overflow-hidden border border-line bg-surface rounded-lg transition-ui hover:bg-raised; icon (space.icon or fallback); color wash (gradient via hex+14 alpha); delete button visible mobile, sm:group-hover; confirming state: min-h-[100px] flex flex-col items-center justify-center, confirm/cancel buttons; deleting: button disabled; failed: text-status-error |

---

## Doc-Parser Components (`web/components/doc-parser/`)

| Component | Props / Variants | States |
|-----------|------------------|--------|
| **document-source-chip.tsx** | source (string: SHA-256 path or URL) | inline-flex items-center gap-2 border border-line bg-canvas rounded-md px-3 py-2 text-xs text-muted; copy button: default ClipboardCopy icon; copied (1.5s): Check icon text-status-done; copy_failed: text-status-error |
| **doc-upload-panel.tsx** | (doc upload UI) | (unknown) |
| **telegram-toggle.tsx** | (Telegram sync toggle) | (unknown) |

---

## Landing Components (`web/components/landing/`)

| Component | Props / Variants | States |
|-----------|------------------|--------|
| **onboarding-stepper.tsx** | (scroll-driven stepper, 3 steps) | desktop (sm+) + motion-safe: pinned section, overlapped steps via grid, progress rail (signal fill bottom-to-top), focus management, snap-to-labels; mobile/reduced-motion: stacked cards; step state: opacity (0→1), y (28→0), pointerEvents (none→auto); CTA autoAlpha (0→1) on final step |
| | STEPS constant: array of {id, kicker, surface, icon, title, body, meta} | (step definitions, exported for reuse) |
| **count-up.tsx** | (counting animation) | (unknown) |
| **demo-video.tsx** | (video embed) | (unknown) |
| **hero-gradient.tsx** | (hero gradient background) | (unknown) |
| **mobile-onboarding-stepper.tsx** | (mobile variant of stepper) | (unknown) |
| **app-slot.tsx** | (slot component) | (unknown) |
| **wordmark-marquee.tsx** | (scrolling wordmark) | (unknown) |

---

## SVG Icon Components (`web/components/svg/`)

All icon files export a single component (typically default or named export) that accepts `className` prop and renders an `<svg>` element. States are typically minimal (color via className, aria-hidden, focusable attributes).

| Component | Usage |
|-----------|-------|
| `chrome-icon.tsx` | Browser icon |
| `desktop.tsx` | Desktop device icon |
| `github-icon.tsx` | GitHub mark (path-based) |
| `github-wordmark.tsx` | GitHub wordmark |
| `google-drive-icon.tsx` | Google Drive mark |
| `google-icon.tsx` | Google "G" mark (path-based) |
| `instagram-icon.tsx` | Instagram brand |
| `instagram-wordmark.tsx` | Instagram wordmark |
| `mobile-device-icon.tsx` | Mobile device icon |
| `openai-icon.tsx` | OpenAI mark |
| `ownix-add-icon.tsx` | Ownix "add" custom icon |
| `ownix-share-icon.tsx` | Ownix "share" custom icon |
| `pdf-icon.tsx` | PDF file icon |
| `puzzle-piece.tsx` | Puzzle piece icon |
| `telegram-icon.tsx` | Telegram brand |
| `tiktok-icon.tsx` | TikTok brand |
| `tiktok-wordmark.tsx` | TikTok wordmark |
| `youtube-icon.tsx` | YouTube brand |
| `youtube-shorts-icon.tsx` | YouTube Shorts icon |
| `youtube-wordmark.tsx` | YouTube wordmark |

---

## Near-Duplicate Candidates

### Dialog-Like Modals
- **`dialog.tsx`** vs **`sheet.tsx`**: Both use Radix Dialog, same overlay/close affordance. Dialog is centered (top-1/2), sheet is bottom-anchored (inset-x-0 bottom-0). Likely intentional separation: dialog for central focus, sheet for mobile-friendly modal. No redundancy.
- **`dialog.tsx`** vs **`confirm-dialog.tsx`**: ConfirmDialog is a composed wrapper around Dialog with hardcoded action buttons (Cancel/Confirm), pending state, and destructive styling. Not redundant—ConfirmDialog is task-specific.

### Button-Like Components
- **`ghost-button.tsx`** vs **`tag-picker.tsx`** (IconPicker buttons): GhostButton is a reusable primitive with accent/borderLine props; IconPicker uses inline button styling (border px-2 py-1) for icon grid. Not redundant—different contexts.
- **`tag-picker.tsx`** (TagMenu trigger) vs **`copy-button.tsx`**: TagMenu trigger is a dropdown button (border, px-2 py-1); CopyButton is icon+label with tooltip. Different purposes, no redundancy.

### Badge Components
- **`badges.tsx`** (TypeBadge/StatusBadge) vs **`platform-icon.tsx`** (PlatformBadge): Badges are data labels (content type, status); PlatformBadge is a sourcing affordance (favicon + tooltip). Not redundant.
- **`tag-picker.tsx`** (TagChips) vs **`badges.tsx`** (StatusBadge): TagChips are attached tags with remove affordance; StatusBadge is a read-only status label. Not redundant.

### Card/Container Components
- **`job-card.tsx`** vs **`preview-card.tsx`**: JobCard is a list-row card (compact, text-focused, horizontal layout); PreviewCard is a grid card (thumbnail-driven, three variants: default/bento/compact). Different layouts and use cases—not redundant, but could share thumbnail/metadata rendering logic.
- **`space-card.tsx`** vs **`job-card.tsx`**: SpaceCard has color wash and delete affordance; JobCard is a job entry. Not redundant.

### Form Components
- **`tag-form.tsx`** vs **`tag-picker.tsx`** (CreateTagModal): Both handle tag creation. CreateTagModal is inline in TagMenu dropdown (Dialog modal); TagForm is a standalone form (used in Controls page and intake-tag-offer inline). Not redundant—different surfaces, same underlying domain logic. Could benefit from a unified schema.

### State/Empty Components
- **`feed-states.tsx`** (SkeletonList/Grid/Block) vs **`export-modal.tsx`** (loading): Both show loading spinners. SkeletonList/Grid are reusable placeholders; ExportModal has its own SkeletonBlock imports. Not redundant—SkeletonBlock is the shared primitive.

### Stepper Components
- **`onboarding-stepper.tsx`** vs **`mobile-onboarding-stepper.tsx`**: Desktop scroll-driven stepper with GSAP vs mobile variant. Likely responsive breakpoint handling rather than two separate components (would benefit from refactor into one responsive component).

**Verdict**: No true redundancy detected. Some pairs (e.g., JobCard/PreviewCard, TagForm/CreateTagModal) have semantic overlap but serve distinct contexts. No components appear to be copy-paste duplicates.

---

## Primitives vs Feature Components

### True Shared Primitives (ui/ and shell/)

**ui/**
- `badges.tsx` — Data label tokens (TypeBadge/StatusBadge) used across feed/detail pages
- `ghost-button.tsx` — Recessed button primitive (accent/borderLine variants, polymorphic `as` prop)
- `dialog.tsx` — Centered modal (Radix wrapper with keyboard/viewport handling)
- `sheet.tsx` — Bottom-anchored modal (Radix wrapper with safe-area inset)
- `tooltip.tsx` — Hover/focus reveal, controlled mode support (Radix wrapper)
- `tab-bar.tsx` — Underline-active tab primitive (generic type-safe, reusable layout)
- `tag-picker.tsx` — Tag attachment/creation UI; TagMark, IconPicker, TagChips also primitives
- `tag-form.tsx` — Tag creation/edit form (reusable across Controls and intake)
- `copy-button.tsx` — Copy-to-clipboard button with feedback (generic value + label)
- `filter-bar.tsx` — Search/filter row (SegmentedTabs, FilterButton; used by feed, doc-parser)
- `date-time.tsx` — Locale-aware datetime (1-liner utility)
- `platform-icon.tsx` — Platform favicon + badge (used in job/preview cards)
- `reorder-buttons.tsx` — Up/down button pair (used in reorderable lists)
- `footer.tsx` — Global footer (used across auth/public pages)
- `public-header.tsx` — Public page header (used on privacy/terms)

**shell/**
- `page-shell.tsx` — Page container (width variants: default/narrow)
- `auth-shell.tsx` — Auth page layout (centered card container)
- `public-shell.tsx` (helpers: LegalLayout, LegalArticle, LegalTitle, etc.) — Legal page layout

### Feature-Specific Components (but reused within scope)

**ui/**
- `confirm-dialog.tsx` — Confirmation modal (composed from dialog primitives, used by spaces delete, etc.)
- `markdown-editor.tsx` — Milkdown editor (specific to space notes editing)
- `export-modal.tsx` — Space export options (specific to spaces feature)
- `preview-motif.tsx` — Animated logo ring (used in loading states across features)
- `no-preview-ring.tsx` — Empty thumbnail stamp (used in preview-card when no image)
- `dev-persona-switch.tsx` — Dev-only mock/restricted mode toggle (development tool)

**shell/**
- `sidebar.tsx` — Collapsible app navigation (nav is app-chrome, but heavily feature-aware: Google status, GitHub link, user avatar)
- `google-status.tsx` — Google connection state provider (feature-specific context, but used across multiple pages)
- `invite-gate.tsx` — Access control gate (session + approval flow, feature-specific business logic)
- `restricted-facade.tsx` — Read-only sample layout wrapper (feature-specific, used to gate restricted view)
- `app-header.tsx` — Global sticky header (app-chrome, but Restricted mode state is feature-aware)

### Feature Components (not shared primitives)

**feed/**
- `job-card.tsx` — List-row card for jobs (feed-specific)
- `preview-card.tsx` — Grid card for jobs (feed-specific, used in multiple layouts: default/bento/compact)
- `stat-card.tsx` — Statistics tile (used in feed overview, could be reused in other dashboards)
- `job-card-tags.tsx` — Tag dropdown for a job (feed-specific)
- `feed-states.tsx` — Feed empty/loading/error states (feed-specific)
- Other feed components: `preview-grid.tsx`, `links-table.tsx`, `stats-overview.tsx`, `recovery-panel.tsx`, `folder-tag-form.tsx`, `submit-job.tsx`, `submit-url-form.tsx`

**intake/**
- `intake-response-card.tsx` — Intake thread response item (intake-specific)
- `intake-tag-offer.tsx` — Inline tag creation offer (intake-specific)
- `intake-state-banner.tsx` — Pending flow banner (intake-specific)
- Other intake components: composed UI for intake flow

**brain/**
- `brain-graph.tsx` — Force-graph visualization (brain-specific, dynamic layout logic)

**spaces/**
- `space-card.tsx` — Collection card with delete affordance (spaces-specific)

**doc-parser/**
- `document-source-chip.tsx` — Document metadata badge (doc-parser-specific)
- Other doc-parser components: upload/toggle UI

**landing/**
- `onboarding-stepper.tsx` — Scroll-driven product tutorial (landing-specific)
- Other landing components: hero/marketing UI

**svg/**
- All icon components are true reusable primitives (used throughout)

### Recommendation

**Current state is healthy.** The primitives (ui/ + core shell/) provide a solid foundation; feature components (feed/, intake/, etc.) compose them without redundancy. The two areas that could benefit from refactoring:

1. **`onboarding-stepper.tsx` + `mobile-onboarding-stepper.tsx`** — Merge into one responsive component with breakpoint-aware rendering instead of two files.
2. **TagForm + CreateTagModal** — Both handle tag creation. CreateTagModal is inline in TagMenu (Dialog); TagForm is standalone. Consider unifying under a single conditional render pattern to avoid schema/validation drift.

Otherwise, the separation of concerns is clean: primitives are generic, composable, and state-agnostic; feature components coordinate them for specific user flows.
