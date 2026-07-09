---
adr: "0034"
title: Ownix product identity and dashboard design-system transition
status: accepted
date: 2026-07-09
---

## Context

The web product is moving from the old VIG / operator-console presentation to
Ownix: a quiet premium system for collecting the internet a user cares about,
returning to it through an owned Feed, and optionally contributing signal to the
Brain.

The previous visual and copy system mixed several incompatible ideas:

- VIG as an internal pipeline name.
- "Operator Console" as the dashboard metaphor.
- "Second Brain" and other legacy labels in user-facing surfaces.
- Background imagery and decorative treatments that competed with the new dark
  plate ladder.
- Page names that described implementation areas rather than the product model.

The new COPYRIGHT.md and DESIGN.md establish Ownix as the product-facing system.
The branch updates the web UI to follow that system.

## Decision

### 1. Ownix is the product-facing identity

Use Ownix in product-facing web UI, metadata, manifest, legal pages, auth
screens, favicon/app icon, and design documentation.

Keep VIG as an internal repository/backend/service name unless a later migration
explicitly renames code, packages, deployment names, API paths, or GitHub
metadata. This avoids coupling a visual identity pass to a risky platform rename.

### 2. DESIGN.md and Tailwind tokens are the normative visual source

The Ownix palette in DESIGN.md and `web/tailwind.config.ts` is the source of
truth for web colors:

- Canvas / surface / raised plate ladder for structure.
- Index Amber for action, selection, focus, and current navigation only.
- Contrasignal for secondary informational emphasis.
- Semantic status colors for status badges and state, never as action color.
- Brain gradient only where the shared Brain is the subject.

`design-ownix-preview.html` is a review artifact for the transition. It is not a
runtime dependency.

### 3. Product-facing page names follow the Ownix model

The route paths stay stable for now, but visible navigation and page headers use
the new product terms:

| Route | User-facing name | Reason |
| --- | --- | --- |
| `/` | Feed | The owned stream of saved and processed items. |
| `/doc-parser` | Docs | Short product label for saved document intake and outputs, not the parser implementation. |
| `/brain` | Brain | The shared semantic layer. Avoid "Second Brain" in new copy. |
| `/spaces` | Collections | A user-owned grouping of saved items. |
| `/prompts` | Recipes | Reusable enrichment instructions, named as product behavior rather than raw prompts. |
| `/controls` | Settings | Familiar product language for tags, domains, and recovery options. |

Internal component, hook, and API names may still use the legacy nouns
(`SpacesPage`, `/doc-parser`, template hooks, controls endpoints). Those names
are migration debt, not current user-facing language.

### 4. The dashboard shell becomes an Ownix product shell

The global shell uses:

- Ownix wordmark plus the fixed rhythm `Collect. / Index.`,
  `Own. / Feed.`, `Recall. / Brain.`.
- A compact icon rail with the Ownix mark.
- Stable app-header height above the scrollable dashboard region so the page
  scrollbar starts below the header.
- A simplified page background on dashboard surfaces. Login and logout may keep
  their authored background imagery because those screens are public/auth
  ceremony, not repeated work surfaces.

### 5. Legal and access copy follows Ownix

Terms, privacy, invite/access, login/logout, mini app, and metadata copy should
describe Ownix as invite-only, personal, and ownership-oriented. They should not
present the product as an operator console or as a generic dashboard.

## Consequences

- The web UI reads as Ownix while backend/service names can remain VIG until a
  separate technical rename is justified.
- Future UI copy should prefer the terms Feed, Docs, Brain, Collections,
  Recipes, and Settings unless an ADR changes the product language.
- Tests that assert visible page headings or nav labels should assert the Ownix
  terms, not the legacy implementation nouns.
- Route renames are intentionally out of scope. Renaming `/doc-parser`,
  `/spaces`, `/prompts`, or `/controls` requires a separate compatibility plan
  for links, tests, and user bookmarks.
- Legacy logo assets under `web/images` and `web/public/images` may remain as
  historical/generated assets until an asset cleanup pass removes or replaces
  unused files.

## Considered alternatives

- **Keep VIG and Operator Console wording.** Rejected: it contradicts the new
  copyright/design direction and keeps the product framed as an internal tool.
- **Rename routes and code modules in the same branch.** Rejected: visible names
  can change safely without breaking URLs, test fixtures, API assumptions, or
  user bookmarks. A route/code rename is a separate migration.
- **Remove all background imagery.** Rejected: the repeated dashboard surfaces
  should be plate-based, but login/logout screens can keep authored imagery as
  part of the auth ceremony.
- **Use Brain gradient broadly as brand decoration.** Rejected: the design
  system reserves that gradient for Brain surfaces so amber can remain the only
  action signal.
