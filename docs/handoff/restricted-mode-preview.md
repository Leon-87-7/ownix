# Restricted Mode Product Spec

_Grill-with-docs session, 2026-07-11. Domain term recorded in `CONTEXT.md`; architectural decision recorded in ADR-0035._

## Product Intent

Ownix needs a public "look inside" path that shows the real product surface before a visitor has access. The current experience is too gated and too hard to navigate:

- Signed-in users cannot naturally return to the landing page because `/` redirects valid sessions to `/feed`.
- Logged-out visitors cannot see the product at all.
- The path from real Feed back to public landing currently requires logging out, then going through login, then using "Back to landing page".

Restricted mode fixes this by making the landing page a real home surface again and letting visitors browse a read-only, bounded sample of Leon's Index.

The preview must feel like the actual dashboard, not a static marketing mock. Visitors should see the same shell, sidebar, Feed tabs, page structure, and action affordances. The product should teach itself by letting people move around, search, filter, open preview details, and discover where actions would be.

The safety boundary is equally important: restricted mode must never weaken authenticated APIs, create write access, expose private/export links, or make Leon's sampled rows indexable by search engines.

## Canonical Term

Use **Restricted mode**.

Avoid:

- Demo mode
- Public tenant
- Anonymous user
- Guest account
- Read-only login

Restricted mode is not a Tenant, not an Approved user, and not an Invite gate state. It is a visitor-facing preview state backed by a functional session cookie and dedicated read-only preview endpoints.

## References

- `CONTEXT.md`: `Restricted mode`
- `docs/adr/0035-restricted-mode-preview.md`
- Follow-up issue for out-of-scope access policy change: `#352 Auto-approve new users while keeping operator block controls`

## Core Decisions

### Landing Page

The public landing page remains reachable for everyone, including signed-in users.

The primary CTA always says:

```txt
Look inside
```

The CTA destination is session-aware:

- Anonymous visitor: enter Restricted mode.
- Pending Invite gate user: enter Restricted mode.
- Blocked Invite gate user: enter Restricted mode.
- Approved user: go to normal Feed.

The middleware must stop redirecting signed-in users away from `/`.

### Preview Cookie

Entering Restricted mode sets a functional session cookie:

```txt
ownix_preview=1
```

Properties:

- Session-only.
- No personal data.
- No tracking identifier.
- Used only to preserve preview navigation and authorize dedicated read-only preview endpoints.
- Should be `HttpOnly`, `SameSite=Lax`, and `Secure` in production.

Lifecycle:

- Set when entering Restricted mode.
- Kept while the visitor navigates the dashboard preview.
- Kept when the visitor returns to the landing page.
- Kept while the visitor goes to `/login?from=restricted`.
- Cleared after successful approved sign-in before routing to the normal Feed.
- Cleared naturally at browser-session end.

### Preview Endpoints

Do not relax normal dashboard API authorization.

Restricted mode must use dedicated read-only preview endpoints. These endpoints use server-side `OPERATOR_CHAT_ID`; they must ignore user-supplied `chat_id`, tenant IDs, or other scope selectors.

Normal endpoints stay protected:

- `/api/jobs`
- `/api/jobs/stats`
- `/api/jobs/{id}`
- submit/recovery endpoints
- tag endpoints
- annotation endpoints
- Google endpoints
- document parser mutation endpoints
- any other authenticated dashboard write/read surface not intentionally exposed as preview

Preview endpoints should have lightweight rate limiting and/or short cache headers to reduce scraping loops and accidental refresh storms.

### Preview Corpus

Restricted mode shows a diversified Operator preview corpus:

- Up to 50 non-cancelled Feed items from Leon's data.
- Prefer items created in the last 12 hours.
- Backfill older non-cancelled items when needed.
- Cap each Feed tab at 20 items so a Reels-heavy corpus does not make the product look narrower than it is.

The current expectation is that normal activity skews heavily toward Reels, so sampling must preserve tab coverage across videos, articles, repos, and links where possible.

Brain remains as-is for now.

### Feed And Detail Preview

Search and filters work normally over the restricted preview corpus.

Visitors can open read-only job detail previews only for jobs inside the preview corpus.

Preview payload policy:

- Source URLs may be clickable outbound links.
- Drive/export/private integration links must be stripped.
- Enrichment and summary fields should be shown because they communicate product value.
- Raw transcript fields should be capped or omitted.

### Navigation

Once entered, Restricted mode persists across internal dashboard navigation. Sidebar links should not bounce visitors to login.

The sidebar remains free and functional.

Docs, Collections, Recipes, and Settings should render as read-only product surfaces:

- Use real Operator-derived read-only data where safe read endpoints already exist.
- Use read-only facades where exposing real data would require new sensitive read surfaces or too much setup.

Direct normal dashboard routes without Restricted mode still obey the Invite gate.

### Actions

Mutating controls stay visible. The preview should teach the affordances instead of hiding them.

Blocked action behavior has two permitted patterns:

- Disabled affordance with tooltip:

```txt
Restricted mode on
```

- Clickable affordance that intentionally shows one global restricted-mode toast and performs no action.

Use the clickable toast pattern where friction is part of teaching the product.

Backend mutation protection is non-negotiable. UI blocking is not the security boundary.

### Global Toast

Use one global restricted-mode toast pattern.

Canonical title:

```txt
Restricted mode on
```

Body can be contextual if needed, but the global pattern should stay recognizable. Examples:

- `Sign in to submit URLs to your own Index.`
- `Sign in to change workspace settings.`

### Feed Intro Modal

On first entry to Restricted mode, show an explanatory modal once per browser session.

Modal copy:

```txt
This preview uses a read-only sample from Leon's Index, balanced across Feed tabs so you can see videos, articles, repos, and links. Actions are locked until you get access.
```

Modal actions:

- `Get access`
- `Keep looking`

Both actions match the Feed `Submit` / `Docs` action-chip treatment:

- `border-b`
- `border-line`
- `bg-canvas`

Button color rules:

- `Get access`: signal bottom line.
- `Keep looking`: `contrasignal-deep` bottom line.

`Keep looking` dismisses the explanatory modal for the whole browser session.

`Get access` routes to:

```txt
/login?from=restricted
```

### AppHeader Banner

After the modal is dismissed, the AppHeader remains explicit about Restricted mode.

In Restricted mode, the banner replaces the normal rhythm block:

```txt
Collect.  Own.  Recall.
Index.   Feed. Brain.
```

Restricted banner layout:

```txt
Restricted mode on | Get access
You're viewing a read-only sample of Leon's Index
```

`Get access` routes to `/login?from=restricted`.

The banner should occupy the same conceptual area as the rhythm block, including on mobile. The attached grilling screenshot highlighted the current rhythm block as the target replacement area.

### Login Page

All `/login` variants use the same access sequence, not only `/login?from=restricted`.

Layout:

1. Context copy:

```txt
Sign in to save your own links and unlock actions.
```

2. Telegram widget.
3. Locked `Connect Google` affordance.

Google connection remains locked until the signed-in user is approved. Telegram is the identity step; Google belongs to an approved Tenant and should not be available to anonymous, pending, or blocked users.

### Privacy Page

Update the Privacy page with a small functional-cookie note.

Copy:

```txt
Ownix may set a session cookie named ownix_preview to keep the read-only preview active while you browse. It does not identify you or track you across sites.
```

This should be a small note, not a full legal rewrite.

### SEO

The public landing page can remain indexable.

Restricted dashboard preview pages must be `noindex` so sampled rows from Leon's Index do not become public search results.

## Non-Goals

- Do not implement automatic user approval in this work. That is issue `#352`.
- Do not make normal `/api/jobs` public.
- Do not create a public/anonymous Tenant.
- Do not expose Drive URLs or other export/private integration links.
- Do not make restricted dashboard pages indexable.
- Do not put Google OAuth before Telegram sign-in.
- Do not hide all action affordances; the preview should show the real product shape.

## Delivery Plan

Split implementation into two PRs.

### PR 1: Routing And Preview Foundation

Scope:

- Make `/` reachable for signed-in users.
- Change landing CTA label to `Look inside`.
- Add session-aware CTA destination behavior.
- Add `ownix_preview=1` creation and lifecycle.
- Add dedicated read-only preview endpoints.
- Add preview corpus query rules.
- Add preview detail endpoint guard for corpus membership.
- Strip private/export fields from preview payloads.
- Add `noindex` to restricted dashboard preview pages.
- Add Privacy page functional-cookie note.
- Add tests for routing, cookie lifecycle, endpoint authorization, corpus limits, field stripping, and noindex.

Acceptance criteria:

- Approved signed-in user can visit `/` and click `Look inside` to reach normal Feed.
- Anonymous visitor can click `Look inside` and enter Restricted mode.
- Pending/blocked signed-in user can click `Look inside` and enter Restricted mode.
- Normal dashboard route without preview still obeys Invite gate.
- `ownix_preview=1` does not contain personal data or a tracking token.
- Normal authenticated APIs are not made public.
- Preview endpoints use server-side Operator scope only.
- Preview endpoints return at most 50 non-cancelled items, with per-tab cap of 20.
- Preview detail endpoint only serves jobs inside the current preview corpus.
- Drive/export links are absent from preview payloads.
- Restricted preview pages are `noindex`.

### PR 2: Restricted UX And Facades

Scope:

- Add shared frontend Restricted mode state.
- Add Feed explanatory modal.
- Add whole-session modal dismissal.
- Add AppHeader restricted banner replacing rhythm block.
- Add global restricted-mode toast.
- Add disabled/click-blocked action behavior.
- Preserve Restricted mode across sidebar navigation.
- Add read-only page facades or safe read-only data wiring for Docs, Collections, Recipes, and Settings.
- Update login page sequence and locked `Connect Google` affordance.
- Add tests for AppHeader banner, modal actions, toast behavior, disabled actions, login sequence, and navigation persistence.

Acceptance criteria:

- Restricted mode modal appears once per browser session.
- `Keep looking` dismisses modal for the session.
- `Get access` routes to `/login?from=restricted`.
- AppHeader banner replaces rhythm block in Restricted mode.
- Banner copy matches the spec.
- Sidebar navigation remains functional in Restricted mode.
- Mutating controls never mutate state.
- Clicking blocked controls either shows the global toast or exposes the tooltip, per surface intent.
- Login shows context copy, Telegram widget, then locked Google affordance.
- Approved sign-in clears `ownix_preview` and routes to normal Feed.

## Likely Touch Points

Frontend:

- `web/middleware.ts`
- `web/app/page.tsx`
- `web/app/login/page.tsx`
- `web/app/(dashboard)/layout.tsx`
- `web/app/(dashboard)/feed/page.tsx`
- `web/app/(dashboard)/jobs/[id]/page.tsx`
- `web/components/app-header.tsx`
- `web/components/sidebar.tsx`
- `web/components/submit-job.tsx`
- `web/components/feed/recovery-panel.tsx`
- shared toast/tooltip components
- privacy page route

Backend:

- `src/auth/middleware.py`
- `src/api/jobs.py`
- new preview API router/module, or clearly separated preview handlers
- database helpers for preview corpus selection

Tests:

- `web/middleware.test.ts`
- `web/app/login/page.test.tsx`
- `web/app/(dashboard)/feed/page.test.tsx`
- `web/components/sidebar.test.tsx`
- backend auth/API tests for preview endpoint behavior

## Open Product Edges

These should be resolved during implementation only if they block the build:

- Exact preview endpoint route names.
- Exact global toast component location if no current toast system exists.
- Which non-Feed pages have safe existing read endpoints versus need facades.
- Whether the Brain page needs a specific Restricted mode banner beyond the shared AppHeader.

## Final Notes

Restricted mode is meant to be generous in browsing and strict in authority.

The user-facing feeling should be: "You are inside the real product, looking at a read-only sample."

The implementation feeling should be: "This is a separate public preview surface with tight server-side boundaries."
