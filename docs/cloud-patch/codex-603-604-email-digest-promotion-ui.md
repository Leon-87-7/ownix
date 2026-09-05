# Codex prompt — implement issues #603–#604 (email digest pipeline, batch 2: promotion + detail page)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

This is **batch 2 of 4** implementing the email-digest feature (#600–#606).
Batch 1 (#600–#602: subscription schema/API/index page, inbound webhook,
worker processor producing `digest_candidates` rows) has already landed in
this working tree — read the actual current code for
`newsletter_subscriptions`/`digest_candidates`/`email_digest_payloads`
(`src/database.py`), the subscription API (`src/api/newsletter_digest.py`
or wherever batch 1 put it — locate it, don't assume a path), and the
processor (`src/processors/email_digest.py`) rather than re-deriving them
from `PLAN.md` alone — batch 1's actual implementation choices (exact
column names, exact route module path) are now the ground truth for this
batch to build on. This batch covers #603 (candidate promotion/dismissal)
and #604 (the frontend detail page). #605 (job-recovery fix) and #606 (ops
Worker) are separate, later batches — do not attempt them.

## Required context — read these first, in this order

1. The actual current code from batch 1 — grep for `newsletter_subscriptions`,
   `digest_candidates`, and `email_digest` across `src/` and `web/` to find
   exactly what landed (table columns, route module, existing hooks/
   components). Treat this as more authoritative than `PLAN.md` for anything
   batch 1 already decided (naming, file location).
2. `PLAN.md` (repo root) — §5 (promotion) and §7 (frontend) are what this
   batch implements. Read the rest for context.
3. `PLAN-REVIEW-LOG.md` (repo root) — Round 1 (promotion claim race, handler
   parity with `POST /api/jobs`), Round 3 (document-pipeline 422 rejection,
   why promotion must branch), Round 2 (ownership/IDOR scoping).
4. `CLAUDE.md` (repo root, and `web/CLAUDE.md`) — layout, test/lint commands.
   Backend: `python -m pytest tests -q` via PowerShell, never the `rtk` Bash
   hook. Frontend: `npm run build && npm run test:run && npm run lint` from
   `web/`.
5. GitHub issues #603, #604 (`gh issue view <n> --repo Leon-87-7/ownix`) —
   each carries its own acceptance criteria; treat those as the per-slice
   definition of done.

## Key decisions already made (do not relitigate)

- **Promotion branches on `detect_pipeline()`**: `document` →
  `POST /api/parsed/url` (`upload_url()`, `src/api/parsed.py:123-128`);
  everything else → the exact same internal handler `POST /api/jobs` uses
  (`_create_pipeline_job()`, `src/api/jobs.py:211-226`) — confirmed
  `src/api/jobs.py:213-214` hard-rejects `pipeline == "document"` with a 422
  ("Document URLs belong in the Doc Parser"), so a document candidate must
  never go through the `POST /api/jobs` path. Never a bare
  `detect_pipeline()` + `create_and_enqueue_job()` reimplementation — that
  diverges from what a human pasting the URL through the dashboard gets
  (allowed-domain lookup, templates).
- **Promotion is an atomic claim before anything else**: `UPDATE
  digest_candidates SET status='promoting' WHERE id=? AND status='pending'`,
  proceed only if it matched a row. Mirror the exact slot-lock idiom
  documented for `prd_auto_status` in `docs/seed/PRD.md:3607-3616`
  (`UPDATE jobs SET prd_auto_status = 'generating' WHERE id = ? AND
  (prd_auto_status IS NULL OR prd_auto_status = 'error')`).
- On promotion success: `digest_candidates.status='promoted'`,
  `job_id=<new job>`, pin via `add_space_url()` (`src/database.py:
  3032-3041`) so it shows in the Space's URLs tab too. On failure: reset
  `status` back to `pending` — the claim must not be a permanent dead end.
- **Dismiss sets `status='dismissed'`, never deletes the row** — it must
  stay in the dedup set so it never resurfaces from a later issue.
- **Ownership**: scope every route through `(id, chat_id)` on the
  subscription first (mirror `_get_owned_space()`,
  `src/api/spaces.py:76-83`), then constrain the candidate lookup through
  that subscription's `space_id` — never a bare `candidate_id` alone.
- **The detail page is a new page, not a `spaces/[id]` variant** — candidates
  aren't jobs, so the existing Space detail page's URLs tab (only ever lists
  pinned jobs) doesn't fit. A promoted candidate shows up there too
  automatically via the `space_urls` pin above — no special wiring needed
  for that.
- **Context blobs reuse the existing `MarkdownEditor` component
  (`web/components/ui/markdown-editor.tsx`) as-is** — no new editor
  component, no new blob endpoints (reuse `/api/spaces/{id}/blobs` CRUD).

## Work order

### #603 — candidate promotion + dismissal

- `POST /api/newsletter-digest/{sub_id}/candidates/{candidate_id}/promote`:
  atomic claim first (see Key Decisions). Branch on `detect_pipeline()`
  (`src/utils/validators.py`) result exactly as described above. On success,
  pin via `add_space_url()`. On failure, reset the claim.
- `DELETE /api/newsletter-digest/{sub_id}/candidates/{candidate_id}`: dismiss
  (see Key Decisions).
- Ownership gating on every route, exactly as described above.
- Tests: promotion creates a job via the actual `POST /api/jobs` path
  (assert allowed-domain/template behavior matches, not a reimplementation);
  document candidate routes through the Doc Parser path; two concurrent
  promotes on the same candidate never create two jobs; promoted candidate
  is pinned into `space_urls` and visible on `/spaces/{id}`; dismissed
  candidate never reappears on re-scan; cross-tenant access rejected.

### #604 — web: newsletter-digest detail page

- New `web/app/(dashboard)/newsletter-digest/[id]/page.tsx`. Use
  `web/app/(dashboard)/spaces/[id]/page.tsx` as the structural reference
  (`PageShell`, `useParams()` for the client-side id — not async page
  props, per that file's own comment on why — `TabBar`, loading/not-found/
  forbidden states), but this is its own page, not a `spaces/[id]` variant.
- Candidate feed: cards (title/thumbnail/URL, tolerate missing
  title/thumbnail) with a "Create job" button (calls #603's promote
  endpoint) and dismiss (calls delete-candidate). Reflect `promoting`/
  `promoted` state without a full reload — disable/relabel the button, link
  through to the resulting job once `job_id` is set.
- Context list: reuse `MarkdownEditor`
  (`web/components/ui/markdown-editor.tsx`) exactly as
  `web/app/(dashboard)/spaces/[id]/ContextTab.tsx` does.
- New hook(s) under `web/lib/hooks/` (mirror `useSpaceDetail.ts` /
  `useSpaceUrls.ts` naming and shape) rather than inlining fetch logic in
  the page component.
- Wire navigation from batch 1's `/newsletter-digest` index page into this
  detail page (`<Link href={\`/newsletter-digest/${id}\`}>`) — locate the
  actual index page batch 1 produced and add the link/row click-through if
  it isn't there yet.
- Tests (Vitest + RTL, colocated `.test.tsx`): promote/dismiss interactions,
  blob rendering, navigation from index.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Don't touch files outside what each slice above names; don't refactor
  unrelated code (including batch 1's own code) beyond what's needed to
  wire this batch in.
- Do not build #605 (recovery fix) or #606 (ops Worker) — separate batches.
- Test commands: `python -m pytest tests -q` (PowerShell, never `rtk`);
  `ruff check src/`; `npm run build && npm run test:run && npm run lint`
  from `web/`.
- Every new API route enforces ownership via `(id, chat_id)` scoping before
  touching a row — no bare `candidate_id`/`sub_id` path param used alone.

## Deliverable

Uncommitted working-tree changes implementing #603–#604 fully: promotion/
dismissal API and the frontend detail page. Regression tests per issue's
acceptance criteria. A short summary per issue noting what was done and
anything that needed a judgment call not already settled in `PLAN.md`/
`PLAN-REVIEW-LOG.md`, including any batch-1 naming/path assumption you had
to confirm by reading the actual code rather than the plan.
