# Critique — `login` + `logout` pages

_Impeccable `/critique` run, 2026-07-06. Score 24/40 (Acceptable). Snapshot: `.impeccable/critique/2026-07-06T21-11-30Z__web-app-login-logout.md`._

Targets: `web/app/login/page.tsx`, `web/app/logout/page.tsx`.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | Login has no loading state during `fetch` and no feedback on auth failure |
| 2 | Match System / Real World | 3 | Natural copy; Telegram is a real-world auth the user recognizes |
| 3 | User Control and Freedom | 3 | Logout offers a clean way back; login failure leaves no guided retry |
| 4 | Consistency and Standards | 2 | Bare login vs elaborate logout card; Telegram widget breaks button vocabulary |
| 5 | Error Prevention | 3 | Single-action screens; little room for user error |
| 6 | Recognition Rather Than Recall | 3 | Both screens are self-evident |
| 7 | Flexibility and Efficiency | 3 | One-tap auth, auto-redirect on success |
| 8 | Aesthetic and Minimalist Design | 2 | Logout: nested card + resting glass + triple redundant messaging |
| 9 | Error Recovery | 1 | Failed auth is silent — no message, no retry, no recovery |
| 10 | Help and Documentation | 2 | No context for "why Telegram?"; first-timer unguided |
| **Total** | | **24/40** | **Acceptable — real gaps before a paying user is happy** |

## Anti-Patterns Verdict

**LLM assessment:** Neither page reads as generic AI slop — no gradient text, no eyebrow, no hero-metric template, and both correctly honor the shared wave-background + `-translate-y-[55px]` motif. But the logout card trips two specific DESIGN.md bans: it's a **nested card** (`rounded-xl bg-surface/85` wrapping `rounded-lg bg-canvas/70`) and it's **resting glassmorphism** (`backdrop-blur-sm` on `bg-surface/85` at rest). The Plate Rule says depth is the plate ladder + hairline — nothing at rest floats, glass is never a default. This card floats on blur. Login, by contrast, is almost too bare; the asymmetry between the two halves of one auth pair is the bigger tell than any single element.

**Deterministic scan:** `detect.mjs` ran clean on both files — `[]`, exit 0. No mechanical slop patterns. The issues here are compositional and behavioral, which the detector doesn't catch.

**Visual overlays:** Not available. Login's sole control is a remote Telegram widget iframe needing live bot config + a real session; a localhost spin-up wouldn't render the meaningful state, so no user-visible overlay was produced. Source + token review substituted.

## Overall Impression

Two competent, on-brand auth screens that share a background but not a level of care. Logout got the design attention (entrance animation, confirmation card, considered copy); login got the plumbing. The single biggest opportunity is the **login failure path** — a rejected auth currently does literally nothing, the one place an auth screen cannot be silent.

## What's Working

- **The shared background system.** Same masked, desaturated wave at 50% opacity, identical optical centering on both — decorative bg that recedes so orange stays the one signal. Exactly DESIGN.md's intent.
- **Correct signal discipline on logout.** "Sign in with Telegram" is the one signal-orange element, `text-onsignal` dark-on-orange, proper `ring-signal` focus. Textbook Signal Rule.
- **Accessibility bones are right.** `sr-only` h1, `aria-hidden` on decorative img + icon, real focus rings, `motion-reduce:animate-none` on the entrance.

## Priority Issues

- **[P1] Login auth failure is silent.** `onTelegramAuth` redirects on `res.ok` and otherwise does nothing — no error, no loading during the `fetch`, no retry. **Why:** a rejected user (expired hash, unauthorized account, server 500) is stranded on a screen identical to success. Worst failure a login can have. **Fix:** pending state during fetch + inline plain-language error with retry on `!res.ok`. → `/impeccable harden`
- **[P1] Logout card violates flat-by-default.** Outer `bg-surface/85 backdrop-blur-sm` wraps inner `bg-canvas/70` — a nested card floating on blur at rest. **Why:** DESIGN.md bans both nested cards and resting glass; the one spot that'd fail a design-system review. **Fix:** collapse to a single `bg-surface` plate + 1px hairline, drop the blur. → `/impeccable distill`
- **[P2] The pair is visually asymmetric.** Polished animated card vs bare centered stack. **Why:** one conceptual pair, mismatched care makes login feel unfinished. **Fix:** pick one level of ceremony and apply to both. → `/impeccable polish`
- **[P2] No skeleton/fallback for the Telegram widget.** Script injects async into an empty container; blank space while loading, dead end if it fails (blocker/network). **Fix:** reserve height, placeholder while loading, fallback message on error. → `/impeccable harden`
- **[P3] Redundant messaging on logout.** "Session closed" + "See you soon" + "signed out successfully" say it three times. **Fix:** checkmark + one headline + button. → `/impeccable clarify`

## Persona Red Flags

**Sam (Accessibility):** Login's control is a Telegram iframe — its keyboard order, focus, and SR labeling are outside your control and unverified. The "Sign in to your console" `<p>` isn't associated with the button. On failure nothing is announced (no `aria-live`).

**Riley (Stress Tester):** Kills the network after tapping auth → screen sits unchanged, no error, no recovery. On logout, refresh/back re-shows "See you soon" even though session state lives elsewhere — the page asserts a state it doesn't verify.

**Jordan (First-Timer / the operator):** Lands on `/login` asked to auth with Telegram with zero explanation of _why_ a video console uses Telegram as its IdP. No "new here?" affordance. Without the existing bot relationship, they're stuck.

## Minor Observations

- `active:scale-[0.96]` on the logout button is a fine press cue (not banned bounce) — but it's the only press animation in the pair; login's widget button can't receive it. Another asymmetry symptom.
- The green `status-done` tint on the logout checkmark borrows a _pipeline_ status hue for a non-job success. Defensible, but a conscious call worth making.
- Both pages hardcode `-translate-y-[55px]` + `h-16` logo. Fine as a pair; if a third auth-adjacent screen appears, this wants to be a shared layout, not copy-paste.

## Questions to Consider

- What does a _rejected_ login look like? Right now it looks exactly like a success that hasn't redirected yet.
- Is "See you soon" the operator's voice or a consumer app's? The brand allows "a little delighted" — inside that line or over it?
- Should login and logout share one framed shell so ceremony is defined once and both inherit it?

---

## Action Plan

Decisions from the critique review: tackle **both P1s (login first)**, **level login up** to logout's ceremony, full scope.

1. **`/impeccable harden`** _(login)_ — Add missing states to `login/page.tsx`: pending indicator during the `/api/auth/telegram` fetch, inline plain-language error + retry on `!res.ok` (with `aria-live`), and a reserved-height skeleton + failure fallback for the async Telegram widget. Clears **P1 (silent failure)** + **P2 (no widget fallback)**.
2. **`/impeccable distill`** _(logout)_ — Collapse the nested card to a single `bg-surface` plate on the ladder, drop `backdrop-blur-sm`, let plate step + 1px hairline carry depth. Trim redundant messaging. Clears **P1 (flat-by-default / nested-card / glass)**.
3. **`/impeccable polish`** _(the pair)_ — Level login up to logout's framed ceremony, extract shared `-translate-y-[55px]` + logo + background into one auth shell, resolve the green `status-done` hue call. Clears **P2 asymmetry** + minor observations.
4. **`/impeccable clarify`** _(logout copy)_ — Settle the "Session closed / See you soon / signed out successfully" redundancy into one beat; decide if "See you soon" is on-voice. Clears **P3**.
5. **`/impeccable polish`** — Final pass across both to confirm states, focus, and reduced-motion hold together.
