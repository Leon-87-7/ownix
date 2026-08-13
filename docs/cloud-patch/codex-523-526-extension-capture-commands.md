# Codex prompt — implement issues #523–#526 (extension capture commands)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `CONTEXT.md`, especially `Extension capture command` (line 42), `URL
   deduplication`, `Link pipeline`, and `Article allowlist` — these are the
   accepted product semantics from the 2026-08-13 grill. For this feature the
   Extension capture command entry is authoritative where the older generic
   Link-pipeline wording could imply that an extension fallback may reinterpret
   a recognized video/repo URL; it may not.
2. `docs/adr/0029-doc-parser-dashboard-page.md`,
   `docs/adr/0033-shared-job-creation-core.md`, and
   `docs/adr/0039-link-pipeline-direct-add.md` — preserve the hardened Document
   boundary, shared dedup/create/enqueue ownership, and Link job semantics.
3. `CLAUDE.md` — architecture, project conventions, and exact test/lint
   commands. Also read `DESIGN.md` and `PRODUCT.md` before changing the popup.
4. Shared intake and document paths: `src/intake/models.py`,
   `src/intake/router.py`, `src/api/intake.py`, `src/api/parsed.py`,
   `src/services/pdf_intake.py`, `src/services/jobs.py`, `src/api/jobs.py`, and
   the matching tests under `tests/`.
5. Extension paths: `extension/chrome/manifest.json`, `popup.html`,
   `src/api.ts`, `src/background.ts`, `src/popup.ts`, `src/auth.ts`, and the
   existing Vitest files under `extension/chrome/test/`.
6. GitHub issues #523–#526
   (`gh issue view <n> --repo Leon-87-7/ownix`) — each issue's acceptance
   criteria are the definition of done for that slice.

## Key decisions already made (do not relitigate)

- This is one cohesive feature implemented in dependency order:
  `#523 → #524 → #525 → #526`. Keep the app and extension working after every
  slice.
- Four commands exist. Windows suggestions are `Ctrl+Shift+1` Automatic,
  `Ctrl+Shift+2` Article, `Ctrl+Shift+3` Link, and `Ctrl+Shift+4` Document.
  Other platforms expose all four commands unbound for manual configuration.
- A shortcut is explicit consent and runs with the popup closed. Do not add a
  confirmation dialog, route-selection checkboxes, or page-injected UI.
- Pipeline detection always runs first. If a URL is already recognized, that
  pipeline wins under all four commands: Video stays Video, Repo stays Repo,
  Article stays Article, and recognizable Document stays Document.
- Fallback intent is consulted only for an otherwise rejected URL. Article
  persists the exact normalized hostname then starts an Article job; Link
  starts a Link job; Document securely attempts an HTTPS resource even when
  its path has no document extension.
- Automatic rejection creates no job and performs no allowlist mutation. An
  Article permission remains durable if later job creation/enqueue fails.
- Do not change URL-only job deduplication. Different commands must not create
  parallel jobs for the same URL merely by selecting different intents.
- Feedback is a native notification toast plus temporary extension-action
  badge. Toasts contain only action, normalized domain, and outcome — never a
  full URL, title, selected text, token/auth detail, or raw backend exception.
- Clicking a success toast opens the resulting Ownix job. Repeated identical
  URL-and-command presses while the first request is in flight get quiet badge
  acknowledgement and no second request/toast.
- The popup remains a manual Automatic-send fallback and shortcut-discovery
  surface. It must show the bindings Chrome actually reports, including
  remapped and unbound states.

## Work order

### #523 — route document URLs through shared intake

- Current finding: `src/intake/router.py:90–97` calls `detect_pipeline` with
  the user's Article allowlist, then treats both `rejected` and `document` as
  unsupported. `src/api/intake.py:30` exposes only URL/text request fields.
- Existing secure path: `src/api/parsed.py:59` owns Document job storage and
  creation; `src/api/parsed.py:128–135` exposes remote URL intake;
  `src/services/pdf_intake.py:39` content-validates and line 62 starts the
  HTTPS/SSRF/no-redirect/capped remote fetch. Reuse and, where necessary,
  extract this orchestration so shared intake does not fork the trust boundary.
- Fix direction: make a recognizable supported document URL submitted through
  the channel-neutral router produce the same Document job/response as the
  parsed URL endpoint. Do not import channel-private metadata or duplicate the
  downloader. Keep `IntakeResponse` and HTTP adapter error translation clean;
  do not turn the channel-neutral model into a FastAPI request model.
- Existing valid Video/Repo/Article submissions and genuinely unsupported
  automatic URLs must keep their current behavior.
- Add regression coverage in the established intake-router, intake-API,
  parsed-API, and PDF-intake test files for success, deduplication, invalid
  bytes, unsafe fetches, and unchanged non-document routing.

### #524 — explicit shared-intake fallback intents

- Current finding: `src/intake/models.py:62` and `src/api/intake.py:30` contain
  no typed processing intent; `extension/chrome/src/api.ts:24` likewise sends
  only URL/text. `src/services/jobs.py:55–80` remains the shared URL-only
  dedup/create/enqueue owner.
- Existing behaviors to reuse: `src/database.py:1617/1628` persists and reads
  per-chat Article domains; `src/api/jobs.py:141–166` demonstrates explicit
  Link job creation and its content-type mismatch guard; `src/api/parsed.py:59`
  is the Document creation path.
- Fix direction: add an additive, typed intent to the channel-neutral message
  and HTTP request contract. Route detected pipelines first. Only on rejection:
  Article normalizes/persists the exact hostname before starting Article;
  Link requests `content_type="link"`; Document invokes the hardened fetch and
  content sniff for any HTTPS URL. To support an extensionless explicit
  Document URL, separate the automatic “looks like a document” gate from the
  secure fetch/content validation — do not weaken SSRF, redirect, byte, or size
  checks.
- Preserve URL-only deduplication and all existing valid explicit `/addlink`,
  dashboard Link modal, parsed URL, and automatic pipeline flows.
- Add focused model/API/router tests for invalid intent, pipeline precedence,
  exact-host allowlisting, consent surviving downstream failure, Link fallback,
  extensionless Document success/failure, automatic no-side-effect rejection,
  and cross-intent deduplication.

### #525 — background extension capture commands

- Current finding: `extension/chrome/manifest.json:1–27` is Manifest V3 with a
  module service worker, `activeTab`, notifications, and no `commands` block.
  `extension/chrome/src/background.ts:45` handles only context-menu clicks;
  its existing native notification helper is at line 36. The API client at
  `extension/chrome/src/api.ts:68` already uses paired bearer auth and a fresh
  idempotency key.
- Fix direction: declare the four commands with Windows-only suggestions and
  handle `chrome.commands.onCommand` in the background worker. Map command to
  typed intake intent, validate the active tab is HTTP(S), and share submission
  and safe-feedback helpers with the context-menu path where that reduces
  duplication without changing context-menu semantics.
- Track active submissions by normalized URL + command for the lifetime of the
  pending promise. Set a quiet progress badge, suppress duplicates, and always
  clear/replace badge state deterministically. Associate success-notification
  IDs with safe Ownix job URLs so notification clicks open the job; clean that
  mapping after use.
- Pairing failure opens the existing extension Options/setup surface. Browser
  internal pages, extension pages, blank tabs, and other non-HTTP(S) tabs create
  nothing. Automatic unsupported feedback points users to Article/Link/Document
  commands without exposing the page URL.
- Existing popup sends, page/link/selection context menus, pairing, host
  allowlisting, and rate-limit handling must keep working.
- Expand the service-worker/API Vitest stubs and tests for all commands,
  Windows/default manifest shape, intent mapping, protected tabs, pairing,
  badge lifecycle, privacy-safe notifications, success navigation, and
  in-flight suppression.

### #526 — shortcut discovery in the popup

- Current finding: `extension/chrome/src/popup.ts:25–61` only discovers the
  active tab and wires the manual Automatic send; `popup.html` has only tab
  text, `#send-btn`, and status. Existing popup tests begin in
  `extension/chrome/test/popup.test.ts:23`.
- Fix direction: retain the manual action and add a compact four-command
  reference driven by `chrome.commands.getAll()`. Display Chrome's runtime
  shortcut string, not a hard-coded copy of the manifest suggestion. Treat an
  empty shortcut as unbound and give direct, accurate instructions for Chrome's
  extension-shortcut settings; do not claim the extension can programmatically
  force a binding.
- Follow the Ownix design principles: quiet hierarchy, accessible labels and
  focus states, no decorative motion, no route-choice checkboxes, and no
  suggestion that an unavailable shortcut is active.
- Existing manual send/status/error behavior must keep working.
- Extend the colocated popup tests for accepted Windows suggestions, user
  remaps, unbound commands, command ordering/naming, and manual fallback.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Do not touch files or areas outside shared intake/document routing, the Chrome
  extension, their focused tests, and documentation required to keep those
  contracts accurate. Do not refactor unrelated code in files you open.
- Do not change URL-only deduplication, existing pipeline ownership, existing
  Link-entry semantics outside this extension fallback, or Document security
  controls.
- Preserve any pre-existing working-tree changes; do not revert or overwrite
  work you did not create.
- Backend verification from the repo root:
  `python -m pytest tests/test_api_intake.py tests/test_intake_router.py tests/test_parsed_api.py tests/test_pdf_intake.py tests/test_jobs_api.py -q`, then
  `python -m pytest tests -q`, and `ruff check src/`. Never run tests through
  the `rtk` hook.
- Extension verification from `extension/chrome/`: `npm test` and
  `npm run build`.

## Deliverable

Uncommitted working-tree changes implementing #523–#526 in order, with focused
regression tests for each issue and the full verification above. Finish with a
short per-issue summary, commands/results, and any blocker that genuinely needs
a human decision. Do not commit, push, create a branch, or open a PR.
