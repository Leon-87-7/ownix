---
adr: "0035"
title: Restricted mode read-only product preview
status: accepted
date: 2026-07-11
---

## Context

Ownix needs a public "look inside" path that lets visitors understand the
product before they have access. The previous routing made the public landing
page hard to reach for signed-in users because `/` redirected sessions straight
to `/feed`; meanwhile logged-out visitors could not inspect the product at all.

The product goal is a real preview, not a static marketing demo: visitors should
see the same dashboard shell, Feed tabs, navigation, and action affordances that
approved users see. The security risk is that the preview is based on
Operator-derived data, so it must not weaken the authenticated dashboard
boundary or expose private/export integration fields.

## Decision

### 1. Landing remains reachable and the CTA is session-aware

The public landing page stays reachable for everyone. Its primary CTA always
says `Look inside`.

The destination is session-aware:

- Anonymous visitors enter Restricted mode.
- Pending or blocked Invite gate users enter Restricted mode.
- Approved users go to their normal Feed.

The middleware must not redirect signed-in users away from `/`.

### 2. Restricted mode uses a functional preview cookie

Entering Restricted mode sets a functional session cookie:

```txt
ownix_preview=1
```

The cookie stores no personal data and no tracking identifier. It exists to
preserve preview navigation and authorize only dedicated read-only preview
endpoints. Returning to landing or ordinary navigation does not clear it.
Approved sign-in clears it before routing to the normal Feed, and browser
session end clears it naturally.

### 3. Preview data comes from dedicated read-only endpoints

Restricted mode must not relax the normal `/api/jobs`, recovery, submit, tag,
annotation, Google, or parser authorization rules.

Preview data is served by dedicated read-only preview endpoints. Those endpoints
use server-side Operator scope from `OPERATOR_CHAT_ID`; they ignore any
user-supplied `chat_id` or tenant selector.

Because these endpoints are public reads over Operator-derived data, they should
have lightweight rate limiting and/or short cache headers to prevent scraping
loops and accidental refresh storms.

Preview payloads may expose source URLs as outbound links, but must strip
private/export integration links such as Drive URLs. Detail previews include
value-bearing enrichment and summary fields, but raw transcript fields are
capped or omitted.

### 4. The preview corpus is diversified

Restricted mode shows a diversified Operator preview corpus:

- Up to 50 non-cancelled Feed items from Leon's data.
- Prefer items created in the last 12 hours.
- Backfill older non-cancelled items when needed.
- Cap each Feed tab at 20 items so a Reels-heavy corpus does not flatten the
  product demo.

Visitors may open read-only job detail previews only for jobs inside that
restricted preview corpus.

Brain remains as-is for now.

### 5. Navigation is broad, actions are blocked

Once entered, Restricted mode persists across internal dashboard navigation so
sidebar links do not bounce visitors to login. Direct normal dashboard routes
without Restricted mode still obey the Invite gate.

The sidebar stays free and functional. Docs, Collections, Recipes, and Settings
use real Operator-derived read-only data where safe read endpoints already
exist; otherwise they render read-only facades of the real surfaces.

Mutating controls remain visible. Depending on the surface, they either:

- render as disabled affordances with tooltip `Restricted mode on`, or
- accept the click and show one global restricted-mode toast without performing
  the action.

All backend mutations remain denied by normal authorization.

### 6. Restricted mode has persistent, explicit chrome

The Feed introduces Restricted mode with a once-per-browser-session explanatory
modal:

```txt
This preview uses a read-only sample from Leon's Index, balanced across Feed
tabs so you can see videos, articles, repos, and links. Actions are locked until
you get access.
```

Modal actions are `Get access` and `Keep looking`, both matching the Feed
`Submit`/`Docs` action-chip treatment (`border-b border-line bg-canvas`).
`Get access` uses a signal bottom line. `Keep looking` uses `contrasignal-deep`
and dismisses the modal for the whole browser session.

After dismissal, the AppHeader replaces the normal
`Collect / Own / Recall . Index / Feed / Brain` rhythm block with a persistent
Restricted mode banner:

```txt
Restricted mode on | Get access
You're viewing a read-only sample of Leon's Index
```

`Get access` routes to `/login?from=restricted`.

### 7. Restricted preview pages are not indexable

The public landing page can remain indexable. Restricted dashboard preview pages
must send `noindex` metadata or headers so Leon's sampled rows do not become
public search results.

### 8. Login shows the access sequence

All `/login` variants use the same access sequence:

1. Context copy such as `Sign in to save your own links and unlock actions.`
2. Telegram widget.
3. Locked `Connect Google` affordance.

`Connect Google` remains locked until the signed-in user is approved because
Google connection belongs to an approved Tenant, not to an anonymous visitor or
pending Invite gate user.

## Consequences

- Visitors can inspect the real product shape without receiving write access.
- The normal authenticated API boundary remains intact.
- Operator-derived preview data has an explicit sampling and field-stripping
  policy.
- The public preview now has a small functional cookie. The Privacy page should
  describe it as a necessary/functional cookie, not a tracking cookie, with copy
  equivalent to: `Ownix may set a session cookie named ownix_preview to keep the
  read-only preview active while you browse. It does not identify you or track
  you across sites.`
- UI components need a shared Restricted mode state so action blocking, toast
  behavior, AppHeader chrome, and sidebar navigation stay consistent.
- Tests should cover session-aware landing behavior, preview-cookie routing,
  preview endpoint authorization, AppHeader banner replacement, modal
  dismissal, and blocked action feedback.
- Implementation should land in two PRs: first the routing/auth preview
  foundation (`Look inside`, `ownix_preview`, dedicated preview endpoints,
  noindex, privacy copy, tests), then the full restricted UX (modal, banner,
  disabled/toast actions, sidebar page facades, login sequence polish).

## Considered alternatives

- **Let anonymous users call normal dashboard APIs with a query param.**
  Rejected: this would make a URL parameter part of the authorization boundary.
  Preview data needs separate read-only endpoints.
- **Build a separate static preview route.** Rejected: it would drift from the
  real dashboard and fail to demonstrate the product surface honestly.
- **Expose the latest 25 rows only.** Rejected: Leon's real activity is often
  Reels-heavy, so a pure latest-row sample would make the product look narrower
  than it is.
- **Hide or remove locked actions.** Rejected: the preview should teach the real
  product affordances. Actions stay visible but do not mutate state.
- **Put Google OAuth before Telegram sign-in.** Rejected: Telegram establishes
  identity, and Google connection belongs to an approved Tenant.
