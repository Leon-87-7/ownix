# Code Health Report — 2026-09-13

Scheduled run of the `code-health-triager` subagent (pyscn + fallow), read-only. No prior
report existed, so this is the first recorded baseline — findings below are flagged as
new/standing rather than confirmed regressions.

## Tool status

- **pyscn**: ran clean via `uvx pyscn@latest analyze src transcript_server.py --json`
  (`rtk` binary not present in this environment, so pyscn ran bare — no mangling occurred).
  Health score **85/100 (Grade B)** — passes the ≥85 gate, no ❌ category.
  Baseline report: `.pyscn/reports/analyze_20260913_050144.json`.
- **fallow**: ran via `rtk proxy npx fallow` in `web/`, exit 1 (expected — repo isn't
  fallow-green). `web/node_modules` didn't exist beforehand; ran `npm install` first
  (dependency install only, no source edited) to avoid fallow misreporting
  dependency/import data.

No code was changed by this run.

## Bottom line

21 items worth a look: 7 from pyscn, 14 from fallow.

## pyscn findings (backend)

High-risk complexity (pyscn's own tier):

1. `src/intake/router.py:57` — `_route`, CC 16 / cognitive 30. Highest-complexity
   production function in the repo.
2. `src/services/ops_bot.py:316` — `handle_command`, CC 14 / cognitive 29.
3. `src/auth/middleware.py:64` — `SessionMiddleware.dispatch`, CC 13 / cognitive 27.
4. `src/auth/identity.py:63` — `resolve_owner`, CC 11 / cognitive 30.
5. `src/processors/article.py:151` — `run`, CC 11 / cognitive 29.
   - `src/telegram/webhook.py:1759` `_safe_get_pdf` (CC 8 / cognitive 26) also flagged,
     but falls under ADR-0015 wontfix (in-file split only).
   - ~24 more production functions at CC 10–14 (medium risk) not itemized — see the
     JSON report for the full list.

6. Duplicate code ≥0.85 similarity in `src/` (7 groups):
   - `src/database.py:1341-1354` / `:1381-1394` / `:1427-1436` (3-way clone)
   - `src/api/auth.py:260-283` / `:324-344`
   - `src/auth/extension_tokens.py:109-118` / `:121-130`
   - `src/database.py:3162-3178` / `:3181-3197`
   - `src/processors/enrichment.py:260-270` / `:285-295`
   - `src/telegram/webhook.py:1080-1094` / `:1120-1134`
   - `src/telegram/webhook.py:2063-2073` / `:2076-2088`

7. Architecture: 90% compliant.
   - One `layer` error: `src.intake.uploads` → `src.api.parsed` (application → presentation),
     no line location given.
   - 39 generic "module mixes N dependency concerns" warnings spanning nearly every
     `src/` module — volume/pattern looks like a config-calibration artifact (similar to
     the "unknown layer" noise category), not 39 discrete defects.

## fallow findings (frontend, `web/`)

Real complexity (CC ≥ 10, effort: refactor):

1. `web/app/(dashboard)/feed/page.tsx:164` — `FeedPageContent`, CC 37 / cognitive 76,
   565 lines. Most severe in repo.
2. `web/components/shell/sidebar.tsx:229` — `Sidebar`, CC 34 / cognitive 56, 404 lines.
3. `web/components/intake/intake-response-card.tsx:30` — `IntakeResponseCard`,
   CC 28 / cognitive 20.
4. `web/components/feed/submit-job.tsx:219` — arrow fn, CC 21, CRAP 116.3.
5. `web/components/newsletter-digest/newsletter-digest-detail.tsx:48` —
   `NewsletterDigestDetail`, CC 19 / cognitive 36 (also the site of duplication finding #9).
6. `web/app/(dashboard)/spaces/[id]/page.tsx:26` — `SpaceDetailPage`, CC 18 / cognitive 30.
   - ~20 more functions at CC 10–17 not itemized — start with `lib/job-markdown.ts`.

Needs tests, not refactor (high CRAP, low CC):

7. `web/app/page.tsx:83` — `LandingPage`, CRAP 90.0, CC only 9 — coverage gap.
8. `web/components/ui/dev-persona-switch.tsx:39` — CRAP 72.0, CC only 8 — coverage gap.

Duplication (real, production code):

9. `web/components/newsletter-digest/newsletter-candidate-row.tsx:9-92` ↔
   `newsletter-digest-detail.tsx:36-418` — 383-line duplicate block (largest in repo,
   ties into finding #5's refactor).
10. `web/components/newsletter-digest/newsletter-candidate-card.tsx` ↔
    `newsletter-candidate-row.tsx` — 3-group clone family, 68 lines total
    (lines 1-20, 57-72/57-88).
11. `web/components/landing/app-slot.tsx:36-62` ↔
    `web/components/landing/destination-slot.tsx:15-40` — 27-line clone.
12. `web/app/page.tsx:337-369` ↔ `:471-502` — 33-line self-duplicate.

Unused exports (verify with `tsc --noEmit` before removing):

13. `web/lib/feed-scope.ts:12` (`isKnownContentType`), `:32` (`jobScopeQuery`);
    `web/lib/hooks/useMergedTags.ts:8` (`LINK_BACKED_CONTENT_TYPES`);
    `web/lib/keyboard.ts:27` (`hasOpenDialog`);
    `web/components/feed/submit-job.tsx:38` (type `IntakeActionKey`, re-export).

Structural:

14. Circular dependency: `web/components/ui/tag-form.tsx` ↔
    `web/components/ui/tag-picker.tsx`.

### Noted, not counted (likely false positives)

- `next-env.d.ts:3` unresolved import to `.next/types/routes.d.ts` — expected, no build
  has run yet.
- `@stryker-mutator/typescript-checker` "unused" devDependency and
  `@stryker-mutator/api` "unlisted" dependency both trace to `web/stryker.config.mjs`,
  which deliberately disables the typescript-checker pending unrelated type-error debt
  (comment in that file) — intentional, not a defect.

## Next steps

For an interactive fix session, use `/code-health` or see
`agent-knowledge/skills/code-health/SKILL.md`. Tested recipes for these exact defects
are in `docs/superpowers/plans/2026-06-11-static-analysis-green.md`.
