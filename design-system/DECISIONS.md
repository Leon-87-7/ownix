# Design System — Phase 1 Gate Decisions

Recorded 2026-08-15, after the read-only inventory in `_inventory/`. These are the
calls made at the handoff's Phase 1 gate; the gallery build follows from them.

| # | Question | Decision |
|---|----------|----------|
| 1 | `DESIGN.md` contradicts itself on ink/body (frontmatter `#e6e6e6`/`#b8b8b8` vs §2 prose `#f4f1eb`/`#c6c1b8`) | **Frontmatter is canonical.** Code and Tailwind are already correct; the §2 prose is the error and is queued for correction (see backlog). No visual change to the app. |
| 2 | Three zero-usage components (`ui/markdown-editor`, `landing/onboarding-textblock`, `ui/public-header`) | **Keep and document** as unused-but-available. Not deleted. Gallery flags them "no current consumers." |
| 3 | Sequencing of drift fixes vs building the gallery | **Document reality now; file drift separately.** The gallery reflects the app as-is. No app restyling happens inside the design-system work (handoff §6). Fixes tracked in `DRIFT-BACKLOG.md`. |
| 4 | Untokenized brain topic colors (7) + tag presets (8) | **Document as deliberate off-token exceptions.** No code change; gallery labels them as intentional semantic palettes outside the core token set. |

## What these imply for the build

- The gallery documents the **current** app. Drift is surfaced (banners / notes), never silently "corrected" by the gallery.
- Nothing in `DRIFT-BACKLOG.md` blocks the gallery; those are separate PRs.
- The token source of truth for the gallery remains `DESIGN.md` frontmatter → `web/tailwind.config.ts`. The gallery reads compiled values live; it never re-types them.
