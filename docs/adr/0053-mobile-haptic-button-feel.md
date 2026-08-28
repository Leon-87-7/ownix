---
adr: "0053"
title: mobile haptic button feel — layered vibration + accessibility opt-outs
status: accepted
date: 2026-08-28
---

## Context

Request: give buttons a "haptic feel" on mobile, across the `web/` dashboard (the
Telegram bot's inline-keyboard buttons are rendered by the Telegram client itself —
out of scope, Ownix has no control over their tap feel).

Verified directly against current platform docs before designing around it (not from
memory): **WebKit has never implemented the Web Vibration API, on any Apple platform,
in any version** — Safari, and every other iOS browser (Chrome-on-iOS,
Firefox-on-iOS) sits on WebKit and inherits the gap. A JS-triggerable
checkbox-toggle workaround existed briefly but Apple closed it in iOS 26.5. Chrome/
Chromium on Android and Samsung Internet do support `navigator.vibrate()`. Firefox
129+ removed support entirely, on every platform. Global support sits at ~77%, all of
it Android/Chromium. ([MDN: Vibration API](https://developer.mozilla.org/en-US/docs/Web/API/Vibration_API),
[caniuse: navigator.vibrate](https://caniuse.com/mdn-api_navigator_vibrate)) This means
"real" haptic feedback is structurally an Android-only enhancement, not a cross-platform
capability with an iOS bug to fix later.

Codebase facts that shaped delivery, not just the vibration call itself:

- No canonical `Button` component exists. `GhostButton` (`web/components/ui/ghost-button.tsx`)
  is used in only 6 files; the rest is ~150 raw `<button>` occurrences across 38 files,
  plus several independent purpose-built buttons. 21 more files carry raw `<a>`/`next/link`
  usage.
- A de facto press-feedback convention already exists, just scattered:
  `active:scale-[0.96] motion-reduce:active:scale-100` appears in 26 files, already
  respecting `PRODUCT.md`'s "Reduced motion is not optional" bar.
- The app is a real installable PWA (`web/app/manifest.json`: `display: "standalone"`,
  icons, `share_target`), not just a responsive site — reinforcing that native-app-like
  tap feedback is in scope, not a cosmetic afterthought.
- `DESIGN.md`'s brand principle: "one rationed signal orange that always means *act
  here*" — restraint is a stated design value, not incidental.
- Controls (`web/app/(dashboard)/controls/page.tsx`) already has a per-user,
  backend-persisted settings pattern: `RecoveryTab` reads/writes
  `/api/controls/recovery-settings`. `useReducedMotion`
  (`web/lib/hooks/useReducedMotion.ts`) is currently a live, unstored
  `prefers-reduced-motion` media-query read with no override.

## Considered options

- **Vibration-only, no visual fallback.** Rejected — leaves iOS users with literally
  nothing, in an app they may well have installed to their home screen.
- **Visual-only, never call `navigator.vibrate()`.** Rejected — forgoes a real,
  available enhancement for the ~77% of mobile users on Android/Chromium for the sake
  of platform parity that isn't actually achievable.
- **Layered: real vibration on Android/Chromium (feature-detected) + a universal
  visual press effect as the actual cross-platform "feel."** Chosen — the visual
  effect is what every user experiences; vibration is a bonus layer on top where the
  platform allows it, with no special-casing needed for Firefox 129+ or future WebKit
  changes (both just fall out of the `'vibrate' in navigator` check).
- **Full `Button`/anchor consolidation now, riding on the haptics change.** Considered
  and rejected twice — once for buttons alone, again when extended to anchors
  (~60 files, ~170+ call sites combined). The press-feedback hook doesn't require a
  shared component to attach to; bundling a design-system refactor into a haptics PR
  multiplies review risk and blast radius for no functional gain. Tracked as a
  separate, unscoped follow-up task instead.
- **Vibrate on every button press vs. only outcome-bearing actions.** Chosen the
  latter — ambient vibration on every nav click/filter toggle contradicts the
  rationed-signal restraint `DESIGN.md` already commits to, and would make Android
  users want to mute the app rather than feel it. Real vibration is reserved for
  outcome-bearing moments: submit/cancel/retry (in-flight job actions), intake
  accept/reject (`submit-job.tsx`, Android share-target intake), destructive-confirm,
  and error states.
- **Press-only vs. passive/live vibration on background job-status changes.** Chosen
  press-only — a passive notification path (vibrate the moment a watched job flips to
  `done`/`error` with no button touched) is a materially different, bigger feature
  (background status-watching) than "buttons feel right when tapped," and wasn't
  otherwise in scope.
- **Accessibility toggle persistence: `localStorage` vs. backend-persisted per-user.**
  Chosen backend-persisted, mirroring `RecoveryTab`'s existing `/api/controls/*`
  GET/PUT convention exactly, so the setting follows the user across devices like
  every other Controls preference.
- **Stored preference vs. live OS query: layered (stored wins once set) vs.
  double-gated (both must agree).** Chosen layered — one source of truth once a user
  has an explicit preference, seeded from `prefers-reduced-motion` on first load so it
  respects the OS default out of the box.

## Decision

Add haptic button feel to `web/` only, as a layered strategy:

1. **Mechanism.** One reusable press-feedback hook fires a visual press effect (the
   existing `active:scale-[0.96]`-style affordance) on `pointerdown`/`touchstart`,
   touch/mobile-only (`pointer: coarse`) — desktop mouse clicks are unaffected. Real
   `navigator.vibrate()` fires separately, feature-detected, only on outcome-bearing
   actions (see above), never on the raw press itself.
2. **Rollout.** Applied opportunistically, not as a big-bang migration: v1 targets are
   `GhostButton`'s 6 call sites plus the 26 files already carrying
   `active:scale-[0.96]`. The remaining raw `<button>`/`<a>` usages pick it up later,
   file-by-file or via the separate consolidation follow-up — not blocking this change.
3. **Accessibility.** New "Accessibility" section on Controls with two checkboxes —
   *Visual motion* and *Haptic motion* (schema left open to add more) — persisted
   per-user via `/api/controls/accessibility-settings` (GET/PUT, new DB
   column/migration), seeded from the live `prefers-reduced-motion` query on first
   load, authoritative once saved. The checkboxes themselves (and every future control
   on that page) get the same press-feedback hook — no exemption for being form
   controls rather than buttons.

## Consequences

- iOS/Safari users never get real device vibration through this feature — that's a
  platform constraint, not a bug to chase. The visual press effect is the actual
  cross-platform "feel" and must carry the UX on its own for them.
- Requires a small backend change (new `/api/controls/accessibility-settings` route +
  migration) alongside the frontend work — not purely a `web/` change.
- Button/anchor consolidation into a shared `Pressable`-style primitive is explicitly
  deferred; this ADR is not an argument against doing it later, just against bundling
  it here.
- If WebKit ever ships the Vibration API, or another browser drops it, the
  feature-detection gate (`'vibrate' in navigator`) absorbs the change automatically —
  no code path here hardcodes a platform/browser check.
