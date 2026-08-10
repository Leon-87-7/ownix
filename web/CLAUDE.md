# CLAUDE.md (web/)

Guidance for Claude Code when working under `web/` (the Next.js dashboard). See the repo-root `CLAUDE.md` for backend/project-wide guidance.

## Design Context

Frontend design (the `web/` Next.js dashboard) is guided by `PRODUCT.md` at the
repo root — register (`product`), users, purpose, brand personality (**bold,
precise, crafted**), anti-references, design principles, and the WCAG AA + reduced-motion
bar. The visual system lives in `DESIGN.md` at the repo root — North Star "The
Operator's Console": dark plate ladder, one rationed signal orange (`#f6921e`)
that always means _act here_, JetBrains Mono for machine facts, flat-by-default
elevation. Read both before any UI work; DESIGN.md's frontmatter tokens are
normative. Reference inspirations are archived in `designs/`.
The `impeccable` design skill lives at `agent-knowledge/skills/impeccable/` — read its `SKILL.md` before any UI work.

### Component layout (`web/components/`)

Every component lives at `web/components/<area>/<kebab-name>.tsx` — there are no
loose files at the components root. To find one, pick the folder by what it is:

- `shell/` — app chrome imported by layouts/shells (header, sidebar, page-shell, auth/public shells, invite/restricted gates, google-status, mock-provider).
- `ui/` — shared primitives used by 2+ features (badges, platform-icon, date-time, filter-bar, spinner, tab-bar, dialog, tooltip, export-modal, tag-picker, markdown-editor, …).
- `feed/`, `doc-parser/`, `brain/`, `spaces/`, `landing/` — feature folders named after the dashboard route that consumes them.
- `svg/` — icon components.

Files are kebab-case; a component's `.test.tsx` sits beside it. No barrel
`index.ts` files (they hurt grep-ability) — import the file directly, e.g.
`@/components/feed/job-card`.
