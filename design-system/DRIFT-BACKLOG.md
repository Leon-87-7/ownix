# Drift Backlog (fix in separate PRs)

Filed per the Phase 1 gate decision "document as-is, fix drift separately"
(`DECISIONS.md` #3). None of these are touched by the design-system gallery work —
that work only documents current reality. Each item below is an independent,
small change to the **app**, to be done as its own commit/PR.

Sourced from `_inventory/drift.md` and `_inventory/tokens.md`.

## Doc-only

- [ ] **`DESIGN.md §2` ink/body prose** — change the §2 Neutral prose values from
  `ink #f4f1eb / body #c6c1b8` to the canonical frontmatter values
  `ink #e6e6e6 / body #b8b8b8` (gate decision #1). Doc-only; no code change.
- [ ] **`web/CLAUDE.md:11`** — signal color cited as `#f6921e`; correct to the real
  value `#d99a45`. Doc-only.

## App (small, low-risk)

- [ ] **`web/components/ui/filter-bar.tsx:184`** — FilterButton active state uses
  `bg-contrasignal-deep text-onsignal hover:bg-contrasignal`. The Chips rule
  (`DESIGN.md §5`) says active selections earn Index Amber: use
  `bg-signal text-onsignal hover:bg-signal-bright` — matching the SegmentedTabs
  active fill (`filter-bar.tsx:102`). If the divergence is intentional, document
  the exception in `DESIGN.md` instead.
- [ ] **`web/components/ui/confirm-dialog.tsx:68`** — replace the `text-[#1b1309]`
  literal with the `text-onsignal` token (same value, named).

## Untokenized palettes — decided to LEAVE as exceptions (gate #4)

Not action items; recorded so a future audit doesn't re-flag them. If a later
decision reverses this, promote them to named tokens (`topic-*`, `tag-*`) in
`DESIGN.md` + `tailwind.config.ts`.

- Brain graph topic colors (7) — `web/components/brain/brain-graph.tsx:31`
- Tag preset colors (8 off-token of 12) — `web/components/ui/tag-picker.tsx:40-51`
- Bespoke subtle-line `rgba()` shadows — `web/components/feed/links-table.tsx:651,654`

## Found during Phase 2 (@ds authoring) — needs a decision, not filed elsewhere

- [ ] **`web/components/landing/onboarding-textblock.tsx` is a 0-byte empty
  file**, not just an unused component like `markdown-editor.tsx` /
  `public-header.tsx` (the two real zero-usage components from the Phase 1
  gate). `git log` shows it was added in commit 9c89d3f ("...add onboarding
  text block") but the file body never landed. No `@ds` block was written for
  it — there's no implementation to document. Needs one of: restore the
  intended content, or delete the stray file. Flagging for a decision rather
  than guessing which.

## Optional refactors (not drift — no behavior change)

- [ ] Merge `onboarding-stepper` + `mobile-onboarding-stepper` into one responsive
  component (Agent B).
- [ ] Unify the tag-creation schema shared by `tag-form` and `tag-picker`'s
  CreateTagModal (Agent B).
