---
name: primary-button
description: Audits a project's primary buttons against 10 rules (height, padding, label style, label copy, contrast, depth, pill radius, single icon, hover/press timing, success state), reports pass/fail per rule with evidence, and plans fixes for the failures. Use when the user says "audit my buttons", "make the button look expensive", "primary button check", "button UX review", or invokes /primary-button.
---

# Primary Button

A rule-based spec for the one button per view that carries the main action. Audit the current project against it, report, then plan fixes. Do not edit code until the user approves the plan.

## The rules

| #   | Rule               | Pass when                                                                                                                                                                             |
| --- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Height             | Rendered height ≥ 44px. Target 48px.                                                                                                                                                  |
| 2   | Horizontal padding | ≥ 24px on each side.                                                                                                                                                                  |
| 3   | Label style        | ~17px (16–18 ok), semi-bold (600), sentence case. No `uppercase` transform, no Title Case.                                                                                            |
| 4   | Label copy         | Verb + object naming what happens next ("Save changes", "Export space"). Fails: "OK", "Submit", "Go", "Continue" with no object.                                                      |
| 5   | Contrast           | Label vs fill > 4.5:1. Button edge vs page > 3:1. Check every theme (light and dark).                                                                                                 |
| 6   | Depth              | Light from above: top-edge highlight (inset 1px light line), soft drop shadow (about `0 8px 24px`, low alpha), optional recessed track behind it. Nothing lit from below or the side. |
| 7   | Corner radius      | Radius = height / 2 (pill). `9999px` counts.                                                                                                                                          |
| 8   | Icon               | At most one icon, about 20px, about 10px gap to the label. Only when it adds meaning. Two or more icons fails.                                                                        |
| 9   | Hover and press    | Visible change starts within 100ms and settles by 300ms. Press = slight depth loss (shadow shrinks, or translateY 1px, or scale 0.98). Respects `prefers-reduced-motion`.             |
| 10  | Success state      | Async actions show progress (spinner) and then a confirmed state (checkmark), not just re-enabling silently. Disabled while pending, width stable (no layout jump).                   |

## Workflow

1. **Find the primary buttons.** Look for the shared button component (`*button*` in the component folder), design tokens (CSS variables, Tailwind config), and the main CTA on each page. Include inline `<button>`s styled as primary that skip the component. In this repo, read `web/CLAUDE.md` first for design conventions.
2. **Resolve real values.** Follow class names and tokens back to pixels and colors. Tailwind: map classes via the config (`h-12` = 48px, `px-6` = 24px). If a value depends on runtime (font scaling, theme), say so rather than guess. When a dev server is available, measure with `getComputedStyle` / `getBoundingClientRect` in the browser.
3. **Check contrast with a tool, not by eye.** Use the `check_contrast` MCP tool when available, otherwise compute WCAG relative luminance. Report the actual ratio.
4. **Report** in the format below.
5. **Plan fixes** for every FAIL and PARTIAL. Prefer changing the one shared component or token over touching each call site. List call sites the fix will not reach.
6. **Wait for approval**, then implement. For rule 10, confirm which actions are async before adding states.

## Report format

```
## Primary button audit — <project>

Buttons found: <component path>, <N> call sites, <M> off-component primaries

| # | Rule | Status | Evidence (file:line, measured value) |
|---|------|--------|--------------------------------------|
| 1 | Height | FAIL | button.tsx:12 `h-10` = 40px |
...

Score: <passes>/10

## Fix plan
1. <rule #> — <change> in <file:line>. Affects <scope>.
```

Status is PASS, PARTIAL (some variants/themes/call sites fail), FAIL, or N/A (for example, rule 10 on a button that navigates instantly). Every status needs evidence. "Looks fine" is not evidence.

## Judgment calls

- Rule 4 is about copy, not styling. Propose the new label per call site. Do not invent actions: if the right verb is unclear, ask.
- Rule 6 in a flat design system: report the conflict and ask before adding shadows. The house style may win.
- Rules 1 and 7 together: a 48px pill has a 24px radius.
- Only one primary button per view. If a view has several, report it. It is a hierarchy problem, not a styling one.

See [REFERENCE.md](REFERENCE.md) for a CSS recipe that passes all 10 rules.
