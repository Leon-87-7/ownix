# Handoff: intake `-` palette + job detail "Back to feed"

Two independent, unrelated web UI items. Both ready to implement — do not
batch into one commit, they touch different components with no shared code.

## Constraints for whoever picks this up

- `web/CLAUDE.md`: components live at `web/components/<area>/<kebab-name>.tsx`,
  no barrel files, `.test.tsx` colocated.
- Follow `DESIGN.md` (signal orange is rationed, dark plate ladder) for any
  new visual affordance.
- Don't touch anything outside the two scoped diffs below.

---

## Item 2 (ready): "Back to feed" should return to where the user came from

**Current behavior** — `web/app/(dashboard)/jobs/[id]/page.tsx:416-421`
(inside `JobHeader`):

```tsx
<Link
  href="/feed"
  className="mb-4 flex h-11 w-full items-center gap-1.5 rounded-md border border-line bg-surface px-3 text-sm font-medium text-body transition-ui hover:bg-raised hover:text-ink sm:inline-flex sm:h-auto sm:w-auto sm:rounded-none sm:border-0 sm:bg-transparent sm:px-0 sm:text-xs sm:font-normal sm:text-muted sm:hover:bg-transparent"
>
  <span aria-hidden="true">&#8592;</span> Back to feed
</Link>
```

This is hardcoded to `/feed`, so it always lands on the All tab regardless of
where the user actually came from (a filtered feed tab, Brain graph, Spaces,
a search result, a deep link, …).

**What's already in place, half-used** — `JobHeader` already computes
`scopeQuery` from the `content_type`/`status` search params
(`lib/job-detail-utils.ts:36` `jobScopeQuery`, `lib/job-detail-utils.ts:47`
`buildJobHref`) and uses it for the Previous/Next adjacent-job pager
(`jobHref`, `page.tsx:363-364`). It is *not* applied to the "Back to feed"
link. Note this only round-trips Feed-tab scope — it doesn't help when the
user arrived from Brain/Spaces/search, which is the actual case the user is
complaining about.

**Existing precedent in the same file** — the delete handler already does
real "return to wherever I came from" navigation
(`page.tsx:937-938`):

```tsx
if (window.history.length > 1) router.back();
else router.push('/feed');
```

**Fix**: make the "Back to feed" link in `JobHeader` use the same pattern —
`router.back()` when there's history to go back to, falling back to
`/feed${scopeQuery ? '?' + scopeQuery : ''}` when there isn't (e.g. the page
was opened directly via a shared link, so `window.history.length <= 1`).
Concretely: turn the `<Link>` into a `<button>` (or keep `<Link href="/feed">`
purely as the no-JS fallback and intercept the click), matching the existing
`onClick` + `router` wiring style already used for delete.

**Do not touch**: the three other "Back to feed" links in this file
(`page.tsx:881-887`, `893-899`, `905-911`) — those are the `not_found` /
`forbidden` / `error` fetch states, where there's no valid job/scope context
to return to, so plain `/feed` is correct there and should stay.

**Test**: extend/add a test in this route's existing test file for
`JobHeader` — navigate to a job from a filtered feed tab (or via
`window.history`), click "Back to feed", assert it lands back where the user
was rather than always on `/feed`.

---

## Item 1 (ready): intake `-` palette for custom recipes

**Ask**: typing `-` at the start of the composer should open a palette
listing the user's custom recipes (prompt templates from `/prompts`), the
same way `/` opens the slash-command palette.

**Backend is already done** — this is a pure frontend task. The submit-side
shortcut exists end to end:

- `src/intake/router.py:78-79` — `_route()` recognizes a leading `-name`
  token (`text[0] == '-' and text[1].isalnum()`) before falling through to
  URL detection, and dispatches to `commands.user_template_shortcut`.
- `src/intake/commands.py:264-323` — `user_template_shortcut(chat_id, text)`
  parses `-name <url>`, loads the caller's **user** template by name
  (`database.get_user_template_by_name` — built-ins are excluded on purpose,
  matching "custom recipes" in the ask), and enqueues the job with that
  template's `extra_instructions` as the freestyle prompt.
- `src/api/templates.py:31` — the recipe-name validator already rejects
  names starting with `-` or `/`, reserving this syntax on the recipe side
  too.
- Per the docstring at `commands.py:270-275`, `-name <url>` typed into the
  dashboard composer already routes correctly today — it's only
  undiscoverable, because nothing in the UI suggests it or lists what `name`
  can be.

**Recipe data is already fetched dashboard-side** — `GET /api/templates`
(`src/api/templates.py:55-63`) returns built-ins then the caller's templates,
each `{ name, description, extra_instructions, is_builtin, ... }`, and
`web/lib/hooks/useTemplateList.ts` already wraps it for the `/prompts` page.
The `-` palette should show **only `is_builtin === false` entries** — built-in
templates aren't invocable via `-name` server-side, so listing them would
offer a shortcut that 404s.

**Implementation shape** — mirror the existing `/` palette:

1. In `web/components/intake/intake-command-palette.tsx` (or a sibling file
   if it's cleaner to keep the two concerns apart — team's call), add a
   `-`-triggered counterpart to `commandQuery`/`matchCommands`
   (`intake-command-palette.tsx:44-53`): triggers only at position 0, no
   whitespace, same as `/`'s rule.
2. Fetch recipes with `useTemplateList()` (`web/lib/hooks/useTemplateList.ts:25`)
   instead of a new endpoint, filtered to `!t.is_builtin`.
3. Wire a second `paletteOpen` condition into
   `web/components/intake/intake-composer.tsx` alongside the existing `/`
   one (`intake-composer.tsx:38-40`), reusing the same arrow-key/Enter/Tab/Escape
   handling (`handleKeyDown`, `intake-composer.tsx:61-77`) and `complete()`
   pattern — completing a recipe should insert `-name ` (trailing space, cursor
   ready for the URL), exactly like `complete()` does for commands
   (`intake-composer.tsx:42-46`).
4. Placeholder/empty-state copy: if the user has zero custom recipes, either
   suppress the palette (mirrors `IntakeCommandPalette` returning `null` on
   empty, `intake-command-palette.tsx:68`) or point them at `/prompts` to
   create one — team's call, not load-bearing.

**Test**: extend `web/components/intake/intake-composer.test.tsx` — typing
`-` with custom templates loaded shows the palette; selecting one completes
`-name `; typing `-` with zero custom templates shows no palette (or the
create-one nudge, whichever is chosen).
