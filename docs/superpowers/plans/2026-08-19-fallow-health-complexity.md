# fallow health gate: complexity remediation (web/)

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development
> or superpowers:executing-plans to work this task-by-task. Steps use checkbox
> (`- [ ]`) syntax for tracking. Read `agent-knowledge/skills/code-health/SKILL.md`
> first — this doc is a worklist for its `health` gate, not a replacement for it.

**Goal:** Drive `fallow health` (web/) from 38 above-threshold functions to 0,
without changing rendered markup/classes or observable behavior.

**Status of the other two fallow gates (already green, don't re-touch without
reason):** `dead-code` 0 issues, `dupes` 2 of 6 groups remaining (deliberately
left — see "Deferred, not forgotten" below). pyscn (Python side) is green,
Health 85/B, no action needed there.

**Baseline (2026-08-19, after the dead-code + dupes pass in
`chore/code-health-pyscn-fallow-green`):**

```
cd web && npm run test:coverage && npx fallow health --coverage coverage/coverage-final.json
```

| Metric | Value |
| --- | --- |
| fallow health score | 88.5/100 (A) |
| functions above threshold | 38 (3 critical, 8 high, 27 moderate) |
| thresholds | cyclomatic ≤20, cognitive ≤15, CRAP ≤30, unit size ≤60 lines |

**Hard constraints (same as the 2026-06-11 static-analysis-green plan):**

- DESIGN.md / PRODUCT.md govern any web component changes — extraction must
  not alter rendered markup, classes, or behavior. Characterization tests
  first, on untested code, per superpowers:test-driven-development.
- `src/telegram/webhook.py` is out of scope here (Python side is already
  green).
- Never merge to main; branch off `origin/main`, small conventional commits,
  PR at the end. No Claude attribution footers in commits.
- Re-run `cd web && npx tsc --noEmit && npx vitest run` after every task.

---

## Priority order (fallow's own `targets` ranking, highest score first)

### Tier 1 — critical severity (CRAP/cognitive far over threshold)

- [ ] **`components/shell/sidebar.tsx:229` `Sidebar`** — CRAP 90.2, cyclomatic
      35, cognitive 57, file is 645 LOC. Highest-impact single fix in this
      list (fallow target score 16.3, "extract_complex_functions"). Likely
      candidate: split by nav-section (each collapsible group is probably a
      self-contained sub-render) the way `SegmentedTabs`/`PublicNavLink` were
      pulled out in the dupes pass — look for repeated per-item render logic
      inside the 35-branch function first, since a duplicate-shaped extract
      often kills complexity and duplication in the same move.
- [ ] **`app/(dashboard)/feed/page.tsx:138` `FeedPageContent`** — CRAP 36.7,
      cyclomatic 32, cognitive 66, file 652 LOC (fallow target score 17.8).
      **Note:** this page was already split once, in the 2026-06-11 plan's
      Task 10 (`StatsOverview`/`FilterBar`/`feed-states` were extracted from
      a 193-line `page.tsx`). It has regrown past that split — check what's
      accumulated inside `FeedPageContent` since (submit-job wiring? recovery
      panel state?) before re-extracting, so the new split accounts for
      what's actually there now rather than redoing the old shape.
- [ ] **`components/feed/submit-job.tsx:278` `SubmitJobProvider`** —
      cognitive 47 (cyclomatic only 9 — this is a nesting/branching-shape
      problem, not raw branch count), file 883 LOC (fallow target score
      29.2, highest score in the whole list). `submit-job.tsx` is also the
      single largest file in this worklist; read it whole before touching it.

### Tier 2 — high severity

- [ ] **`app/(dashboard)/jobs/[id]/page.tsx:838` `JobDetailPage`** — CRAP 32,
      cyclomatic 32, cognitive 33, file 1112 LOC (fallow target score 17.8).
      Largest file in `web/`. The `CardCopyButton` dupe was already thinned
      out in this pass (now uses `useCopyFeedback`) — look for more
      state-machine-shaped inline components in this file that could move to
      `lib/hooks/` the same way.
- [ ] `components/shell/telegram-login-widget.tsx:24` `TelegramLoginWidget` —
      cyclomatic 16, cognitive 26.
- [ ] `lib/hooks/useFolderTagForm.ts:88` `confirm` — cyclomatic 16,
      cognitive 27.
- [ ] `components/ui/filter-bar.tsx:192` `FilterBar` — cyclomatic 9,
      cognitive 26. (Note: this file was touched in the dead-code pass —
      `DEFAULT_STATUS_FILTERS`/`SegmentedTabs` un-exported — re-check current
      line numbers before starting.)
- [ ] `components/ui/dev-persona-switch.tsx:39` `DevPersonaSwitch` — CRAP 72
      (dev-only tooling component; confirm it's actually reachable in
      production bundles before investing much here — may be a case for
      `health.ignore` in `.fallowrc.json` instead of a refactor, if it's
      dev/test-only).
- [ ] `lib/hooks/useFeedData.ts:110` `useFeedData` — cyclomatic 7,
      cognitive 29.
- [ ] `lib/mocks/handlers.ts` (3 findings, lines 109/154/214) — this is the
      MSW mock-handler file; consider `add_test_coverage` (fallow's own
      suggestion, target score 12.0) or excluding it like
      `mockServiceWorker.js` was excluded in this pass, since it's
      test/demo-mode infrastructure, not app logic.
- [ ] `lib/hooks/useLinksTable.ts:53` `useLinksTable` — cyclomatic 5,
      cognitive 27.

### Tier 3 — moderate severity (27 functions)

Lower priority individually; several cluster in files also flagged as
"high impact split" targets by fallow, so fixing the split likely clears
multiple moderate findings in one pass:

- `lib/job-detail-utils.ts` (180 LOC, 5 dependents, fallow target score 26.4
  — highest "split_high_impact" score in the list)
- `lib/hooks/useTagList.ts` (44 LOC, 6 dependents, score 23.4)
- `lib/hooks/useJobTags.ts` (51 LOC, 4 dependents, score 21.6)
- `components/doc-parser/telegram-toggle.tsx` (57 LOC, 5 dependents,
  score 20.9)
- `components/brain/brain-graph.tsx` (274 LOC, 3 dependents, score 17.3)

Remaining moderate-tier functions (one line each — full detail via
`npx fallow health --coverage coverage/coverage-final.json --format json`,
`.findings[]` where `severity == "moderate"`):
`components/intake/intake-response-card.tsx:30`,
`components/feed/links-table.tsx:531`,
`components/feed/recovery-panel.tsx:32`,
`components/intake/intake-composer.tsx:23`,
`app/(dashboard)/spaces/[id]/page.tsx:17`,
`components/shell/invite-gate.tsx:184`,
`components/ui/export-modal.tsx:39`,
`components/ui/filter-bar.tsx:81`,
`components/feed/preview-card.tsx:31` (`Thumbnail`),
`app/(dashboard)/doc-parser/[id]/page.tsx:100,210`,
`app/(dashboard)/doc-parser/page.tsx:68`,
`app/(dashboard)/jobs/[id]/page.tsx:339,398`,
`components/controls/extension-tokens-panel.tsx:19`,
`app/page.tsx:72` (`LandingPage`, CRAP 42 — landing page, see markup-risk
note below before touching),
`components/landing/onboarding-stepper.tsx:110`,
`app/(dashboard)/controls/page.tsx:332`,
`app/mini/page.tsx:18,38`,
`app/(dashboard)/feed/layout.tsx:5`,
`components/feed/submit-job.tsx:382` (separate from the Tier-1
`SubmitJobProvider` finding in the same file),
`components/intake/intake-upload-dropzone.tsx:19`.

---

## Deferred, not forgotten: the 2 fallow `dupes` groups left unfixed

Both are on the public landing page (`app/page.tsx`, governed by
PRODUCT.md/DESIGN.md) and were judged not worth the markup-regression risk
for a ~25-30 line saving:

1. **Footer** (`app/page.tsx:996-1039` vs `components/ui/footer.tsx`) — the
   landing footer has a wider container (`w-11/12 max-w-7xl` vs `w-5/12`), a
   `#top` anchor instead of a home `Link`, extra hover-transition classes,
   and no `TooltipProvider` wrap. Real differences, not copy-paste laziness.
2. **Showcase section** (`app/page.tsx:324-356` vs `458-489`) — same layout
   wrapper, different heading/testimonial copy per instance. Landing-page
   marketing copy is edited independently per section; collapsing into one
   templated component would make future copy edits harder, not easier.

If these are revisited, do it as a deliberate design decision (confirm with
whoever owns DESIGN.md/PRODUCT.md changes), not as a mechanical dedup.

---

## Recipe reminders (from `agent-knowledge/skills/code-health/SKILL.md`)

- Characterization tests **before** refactoring untested code; re-run the
  file's tests after every extraction.
- fallow CRAP ≈ 30 with low cyclomatic/cognitive → often a coverage gap, not
  a real complexity problem — re-run with `--coverage` before trusting a
  moderate-tier finding (several in Tier 3 may resolve once
  `coverage-final.json` is regenerated post-refactor; the numbers above are
  already coverage-informed as of 2026-08-19).
- One commit per fix, small and reviewable — this doc has 3 critical + 8
  high + ~5 file-level splits worth their own commits; don't try to land it
  as one PR.
