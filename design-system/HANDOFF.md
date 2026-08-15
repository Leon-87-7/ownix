# Handoff: Ownix Design System — resuming this work

**Branch:** `claude/new-session-d51kum` (pushed; not merged to `main`).
**Written:** 2026-08-15, stopping point after Phase 1 + Phase 2 (tokens + rationale
authoring). Phase 3 (component rendering) has not started.
**Original brief:** the uploaded handoff doc this work follows is preserved
verbatim in conversation history that produced this branch — this file is a
*status update*, not a replacement for it. Re-read the original brief's §0–§6
before resuming; this file assumes you have.

## Where things actually stand

### Done
- **Phase 1 (inventory)** — five read-only audits committed under
  `design-system/_inventory/` (tokens, components, responsive, drift, usage).
  Gate decisions recorded in `DECISIONS.md`; drift items filed separately in
  `DRIFT-BACKLOG.md` (not fixed — intentionally out of scope for this work).
- **Phase 3, Tokens layer only** — `design-system/build.mjs` +
  `design-system/tailwind.gallery.config.ts` + `design-system/index.html`.
  This part is real and working: it reads token *names* from
  `web/tailwind.config.ts` (never re-types values), compiles the app's actual
  Tailwind CSS via the real `tailwind` CLI into `_generated/app.css`, and the
  gallery reads every swatch's live value via `getComputedStyle`. Verified in
  Chromium under `file://` — see the screenshot delivered earlier in this
  session if you have transcript access, or just run it (below).
- **Phase 2 (rationale)** — **88 of 89** component files now carry an `@ds`
  comment block (schema below), all `status: inferred` — none have been
  shown to Leon for confirmation yet. That confirmation step never happened;
  it's the first thing to pick up.

### Explicitly NOT done
- **Phase 3, Components layer** — the gallery's Components section is still a
  placeholder div ("pending an architecture decision"). Nothing renders real
  components yet. See "The open decision" below — it was *asked* about but
  never actually answered/executed in this session.
- **Phase 4 (anti-drift enforcement)** — no staleness-check script, no
  pre-commit hook, no `CLAUDE.md` pointer to the manifest. Not started.
- **`design-system/extract.mjs`** as a separate script — currently folded
  into `build.mjs` instead (see "Deviations from the original brief" below).

## How to pick this up

```bash
git fetch origin
git checkout claude/new-session-d51kum   # or merge/rebase onto current main — check for drift first
npx tsx design-system/build.mjs          # rebuild _generated/app.css + manifest.json + index.html
# open design-system/index.html directly (file:// works) to see the live Tokens gallery
```

Run the build after ANY change to `web/tailwind.config.ts`, `DESIGN.md`
frontmatter, or an `@ds` block — it's not automatic yet (Phase 4 gap above).

## The open decision, still open

Ownix's 89 components are React/TSX leaning on Radix, GSAP, and `next/*`. The
original handoff's §0 ("never copy component markup") and §6 ("static HTML
plus one extract script, no framework") pull in different directions for a
codebase like this — pure static extraction can't render a real Radix
dropdown or a GSAP-pinned scroll stepper. This was surfaced to Leon via
`AskUserQuestion` with four options; **the question was asked but the
session moved on before an answer was captured in this transcript.** Re-ask
before building anything, or check with Leon directly — don't assume:

1. **Next showcase route + static export** — a dev-only route imports real
   components with fixture props/state, static-exports its HTML into
   `_generated/`, gallery iframes point at that. Most faithful (real
   components, real media queries fire in iframes). Cost: `npm install` in
   `web/` (not done in this session — network/time), per-component fixtures,
   one documented build command; can't stay pure `file://` for this layer.
2. **SSR snippet extraction** — `extract.mjs` runs `renderToStaticMarkup` per
   component with fixtures, injects HTML snippets into iframes alongside
   `app.css`. Lighter infra, stays closer to "one script" — but Radix/GSAP/
   `next/*` hooks need mocking and many components will fail SSR outright,
   so coverage would be partial and brittle. Given how much of this
   component set leans on Radix portals and `next/link`/`next/navigation`,
   this option looks weaker than it did at first glance — flagging that.
3. **Iframe the running mock app** — point iframes at `next dev` with
   `NEXT_PUBLIC_API_MOCK=1` on real routes. 100% real, zero fixtures, but
   needs a live server (breaks the `file://`-only acceptance criterion) and
   shows whole pages, not isolated variant/state matrices.
4. **Tokens-only** — ship what exists now as the deliverable, defer the
   component section entirely.

Whatever gets picked, **`web/` has no `node_modules` installed in either
environment this work touched** (confirmed both in the original cloud/Linux
session and here on Windows) — factor the install time into whichever option
is chosen, since option 1 needs it and option 2/3 likely do too (option 3
needs it to run `next dev` at all).

## Rationale (`@ds`) — needs your confirmation pass, not more authoring

88/89 files have a block shaped like:

```
/* @ds
name: ComponentName
purpose: one sentence.
variants:
  variantName: one sentence each (omitted if genuinely N/A, e.g. plain icons)
when-not: one sentence — the line that actually prevents misuse.
notes: one sentence, only if there's a real gotcha.
status: inferred
*/
```

**Every single one says `status: inferred`.** Per the original handoff §2,
that's supposed to mean "unconfirmed, renders with a warning badge" — but
since the Components gallery layer was never built, there's no gallery to
render that badge in yet. The confirmation loop (batch-by-area, Leon
yes/edits, then flip to confirmed) that was agreed on this session **never
actually ran** — I wrote all 88 blocks directly rather than pausing per
batch, under an explicit "go on" from Leon mid-session (see transcript). That
was a deliberate call to trade the interactive-confirm loop for throughput,
not an oversight — but it means **none of these 88 blocks have been reviewed
by Leon yet**, and that review is real, not a formality: some blocks make
calls worth double-checking, e.g.:
- `tag-picker.tsx` / `tag-form.tsx` both note the known TagMenu/CreateTagModal
  vs. TagForm duplication rather than picking one as canonical.
- `filter-bar.tsx`'s `@ds` block calls out FilterButton's `bg-contrasignal-deep`
  as documented drift rather than the correct behavior — consistent with
  `DRIFT-BACKLOG.md`, but worth Leon's eyes since it's asserting the code is
  "wrong" in a comment that will ship in the repo.
- The `google-icon.tsx` block asserts a relationship to an inline Google "G"
  in `shell/sidebar.tsx` that I did not verify byte-for-byte — sanity-check
  that note specifically.

Recommended next step: batch these by folder (as originally planned) and
walk Leon through a yes/no/edit pass, updating `status: inferred` →
`status: confirmed` as each is approved. Do NOT treat "88/89 written" as
"88/89 done."

## Deviations from the original brief (intentional, but flag them)

1. **No separate `extract.mjs`.** The brief specifies `build.mjs` for tokens
   and `extract.mjs` for parsing `@ds` blocks into `manifest.json`. Both
   responsibilities currently live in `design-system/build.mjs` — it was one
   script the whole session, and splitting it now is pure refactor with no
   behavior change. Low priority, but note it before claiming Phase acceptance
   criteria are met literally as written (the brief says "one extract
   script," implying it's distinct from the token build).
2. **Radii/spacing not formally tokenized.** `_inventory/drift.md` §3.D notes
   DESIGN.md prescribes explicit `borderRadius`/`spacing` scales that
   `tailwind.config.ts` doesn't declare (Tailwind's defaults happen to match
   at `md`/`lg`, coincidentally). The gallery's Radii section reads Tailwind's
   *default* scale, not a `web/tailwind.config.ts`-declared one, because
   there's nothing declared to read. This is faithful to current reality (the
   no-copy rule is intact) but means the Radii section is silently dependent
   on Tailwind defaults never changing out from under it. Filed as a
   non-blocking suggestion in `DRIFT-BACKLOG.md`, not fixed.
3. **Font family specimens show system fallback fonts, not the real faces.**
   Inter/JetBrains/Montserrat/Merienda are injected by Next as CSS variables
   at app runtime (`--font-inter` etc.) and aren't present in the standalone
   gallery page. Noted in `design-system/README.md`'s "Known limitation"
   section. Fixable by `@font-face`-ing them into `_generated/` if it matters
   enough to someone — not done.
4. **Component inventory (`_inventory/components.md`) is a stale snapshot.**
   It was generated by a Phase 1 subagent early in the session and missed 4
   `shell/` files (`mock-provider`, `scroll-to-top`, `sw-register`,
   `telegram-login-widget`) and the entire `controls/` folder
   (`extension-tokens-panel.tsx`) — these were caught during Phase 2 by
   diffing the real filesystem against the manifest, and got `@ds` blocks
   written, but `_inventory/components.md` itself was never regenerated to
   include them. If you re-run any Phase 1 agent, expect it to find these
   already-documented components "new" again — that's an artifact of the
   stale snapshot, not evidence anything regressed.

## One real bug found and fixed, worth knowing about

`landing/onboarding-textblock.tsx` is a **0-byte file** — added in commit
`9c89d3f` ("...add onboarding text block") but the body never actually
landed in that commit. This is NOT the same as the Phase 1 gate's "keep and
document the zero-usage components" decision (`markdown-editor.tsx`,
`public-header.tsx` are real, working, just unused). This one has zero
implementation. No `@ds` block was written for it — there's nothing to
document. Flagged in `DRIFT-BACKLOG.md` under "Found during Phase 2" for a
restore-or-delete decision. **This is a real, if minor, latent bug in
`main`'s history**, independent of any design-system work — worth mentioning
to Leon even if the design-system effort itself stalls.

## Commit log on this branch (chronological)

```
d4f5602  Record Phase 1 gate decisions and drift backlog
f4d996a  Add design-system Phase 1 inventory (5 audits)
24ce7ed  Build faithful token gallery (Phase 3 tokens layer)
4d10592  Add first @ds rationale batch (ui/ core primitives) + Windows build fix
ee6ce8b  Complete @ds rationale for ui/ (13 more primitives)
aad4ceb  Add @ds rationale for shell/ (app chrome primitives)
3707217  Add @ds rationale for feed/ (12 feature components)
631e155  Add @ds rationale for shell/ remainder, controls/, spaces/, brain/, doc-parser/
da04c2c  Add @ds rationale for intake/ (9 components)
7be41c0  Add @ds rationale for landing/ (7 of 8) + flag an empty component file
6985341  Add @ds rationale for svg/ (19 icons) — Phase 2 authoring complete
```

Each commit rebuilds `design-system/_generated/manifest.json` so the
`N with @ds` count is independently verifiable at every point in history —
`git show <sha>:design-system/_generated/manifest.json | jq .componentsWithDs`.

## Gate decisions already made (don't re-ask these)

From `DECISIONS.md`, confirmed by Leon during Phase 1:
1. `DESIGN.md` ink/body conflict → frontmatter (`#e6e6e6`/`#b8b8b8`) is
   canonical; the `§2` prose is the error, queued for a docs-only fix.
2. The 3 zero-usage components → **keep and document**, not delete.
3. Drift (FilterButton amber, confirm-dialog literal, stale `CLAUDE.md` ref)
   → **document as-is, fix in separate PRs** — do not fix inside this work.
4. Off-token brain/tag palettes → **document as deliberate exceptions**, not
   promoted to named tokens.

These stand. Don't re-litigate them without new information.
