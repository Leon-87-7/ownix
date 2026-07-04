# vig — Task grouping for broad-bandwidth grilling

Groups the briefs in `docs/TASK.md` by domain/proximity so related tasks can be
grilled together in one session instead of one at a time. This file is a
reference index only — titles point back at the full briefs in `docs/TASK.md`;
nothing is duplicated here. Re-derive groupings from `docs/TASK.md` if it
changes; this file isn't kept in sync automatically.

---

## Group A — Ingest surfaces & the create-job pipeline core

All three add a new way a URL/repo becomes a job, and all three touch (or
should reuse) the same create-job + enqueue core and `detect_pipeline`/
`Pipeline` classification. Tasks 4 and 9 already carry an explicit
`Grill together` note in `docs/TASK.md`; 16 wasn't cross-referenced there but
sits in the same code path (`_route_url`, `detect_pipeline`) and is worth
settling alongside them.

- ## 4. Dashboard URL submission — a second ingest surface
- ## 9. Offer extracted GitHub repos as a follow-up repo analysis
- ## 16. Link pipeline — bare URLs get a native Telegram preview + a Brain Links row

## Group B — Brain page: Links table, graph & tagging

Everything here lives on `web/app/(dashboard)/brain/page.tsx` / `src/brain.py`
and touches the same `links` table and `LinksTable` component. Task 3 (already
issued) established the table these build on; its open questions (canonical
URL form) echo into 11. Tasks 7 and 10 have since shipped via PR #316.

- ## 3. Extracted-links table in the Brain page ✅ ISSUED TO GITHUB #238
- ## 7. Better navigation for the Brain "Links" table ✅ ISSUED TO GITHUB #306
- ## 8. Controls UI on the Brain search graph
- ## 10. Char-count truncation for the links-table description (ui/ux) ✅ ISSUED TO GITHUB #305
- ## 11. Tags should follow the URL, not the job (many-to-many)

## Group C — Public brand pages & OAuth verification

All three are unauthenticated, public-facing pages driven by the same Google
OAuth branding-verification requirement (issue #203 / epic #201) and the same
login-page brand treatment (`layered-waves-log.svg` + logo lockup). 13 and 14
already carry an explicit `Grill together` note; 15 is the sidebar's entry
point into 13's pages, same domain — it has since shipped alongside 13.

- ## 13. Brand the /privacy and /terms pages ✅ DONE
- ## 14. Public home page — fix Google OAuth branding verification rejection
- ## 15. Sidebar links to Terms & Privacy (one row, between GitHub and Sign out) ✅ ISSUED TO GITHUB #307, #308

## Group D — Design system tokens

Standalone — a single source-of-truth change (`web/tailwind.config.ts` +
`DESIGN.md`), but its outcome (new signal/dark hexes) affects the visual
language every other UI-facing group above renders against. Consider grilling
this first if its open questions (warm vs. cool chassis, pending-yellow
collision) would reshape DESIGN.md guidance those groups are told to follow.

- ## 12. Repalette: new signal orange + dark plate tokens

## Group E — App shell / installability

Standalone infra task, no domain overlap with the others.

- ## 6. Make the web app an installable PWA

## Group F — Job deletion (standalone)

Task 19 sits on the same job-card real estate as task 7's dense-table
thinking and task 11's per-URL tagging, but its own brief explicitly disclaims
a shared decision ("no shared decision, just adjacent surface area") — kept
standalone rather than folded into Group B.

- ## 19. Delete button for jobs — DB + Telegram message, with confirm/"don't show again", swipe-to-delete on mobile

---

## Done / issued — reference only, no grilling needed

- ## 1. Segmented tabs line breaks on mobile ✅ DONE
- ## 2. Tag creation modal not responsive ✅ DONE
- ## 5. Reconcile the export-isolation PRs (#207, #208) before building on them ✅ DONE
- ## 17. Persistent account/status affordance — Google connection state + Telegram identity ✅ DONE — issued #292–#295, merged PR #296
- ## 18. Job details page — previous/next navigation buttons ✅ ISSUED TO GITHUB #309
- ## 20. Feed — a Docs tab that redirects to the Doc Parser page ✅ ISSUED TO GITHUB #310
