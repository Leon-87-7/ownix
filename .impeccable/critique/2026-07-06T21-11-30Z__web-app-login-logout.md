---
target: login page and logout page
total_score: 24
p0_count: 0
p1_count: 2
timestamp: 2026-07-06T21-11-30Z
slug: web-app-login-logout
---
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

**LLM assessment:** Neither page reads as generic AI slop — no gradient text, no eyebrow, no hero-metric template, and both correctly honor the wave-background + `-translate-y-[55px]` shared motif. But the logout card trips two specific DESIGN.md bans: it's a **nested card** (`rounded-xl bg-surface/85` wrapping `rounded-lg bg-canvas/70`) and it's **resting glassmorphism** (`backdrop-blur-sm` on `bg-surface/85` at rest). DESIGN.md's Plate Rule says depth is the plate ladder + hairline; nothing at rest floats and glass is not a default. This card floats via blur. Login, by contrast, is almost too bare — the asymmetry between the two halves of one auth pair is the bigger tell than any single element.

**Deterministic scan:** `detect.mjs` ran clean on both files — `[]`, exit 0. No mechanical slop patterns (side-stripe borders, gradient text, tracked eyebrows) present. The issues here are compositional and behavioral, which the detector doesn't catch.

**Visual overlays:** Not available. The login page's sole control is a remote Telegram widget iframe requiring live bot config and a real session; a localhost spin-up wouldn't render the meaningful state, so no user-visible overlay was produced. Source + token review substituted.

## Overall Impression

Two competent, on-brand auth screens that share a background but not a level of care. Logout got the design attention (entrance animation, confirmation card, considered copy); login got the plumbing. The single biggest opportunity is the **login failure path** — right now a rejected auth does literally nothing, which is the one place an auth screen cannot afford to be silent.

## What's Working

- **The shared background system.** Both pages use the same masked, desaturated wave motif at 50% opacity with the identical `-translate-y-[55px]` optical centering. That restraint (decorative bg that recedes so orange stays the one signal) is exactly DESIGN.md's intent.
- **Correct signal discipline on logout.** The "Sign in with Telegram" button is the one signal-orange element on the page, with `text-onsignal` dark-on-orange and a proper `ring-signal` focus state. Textbook Signal Rule.
- **Accessibility fundamentals are present.** `sr-only` h1, `aria-hidden` on decorative img and icon, real focus rings, `motion-reduce:animate-none` on the entrance. The bones are right.

## Priority Issues

- **[P1] Login auth failure is silent.** In `login/page.tsx`, `onTelegramAuth` redirects on `res.ok` and otherwise does nothing — no error, no loading indicator during the `fetch`, no retry cue. **Why it matters:** a user whose auth is rejected (expired hash, unauthorized Telegram account, server 500) is stranded on a screen that looks identical to success, with no idea what happened. This is the worst failure a login can have. **Fix:** add pending state on the button/container during the fetch, and render an inline error message on `!res.ok` with a plain-language reason and a retry. **Command:** `/impeccable harden`

- **[P1] Logout card violates flat-by-default (nested card + resting glass).** The outer `bg-surface/85 backdrop-blur-sm` plate wraps an inner `bg-canvas/70` plate — a nested card that floats on blur at rest. **Why it matters:** DESIGN.md explicitly bans both nested cards and decorative glassmorphism; this is the one spot in the pair that would fail a design-system review. **Fix:** collapse to a single plate on the surface ladder (`bg-surface` + 1px hairline), drop `backdrop-blur`, and let the plate step carry depth. **Command:** `/impeccable distill`

- **[P2] The pair is visually asymmetric.** Logout is a polished, animated confirmation card; login is a bare centered stack with a raw third-party button. **Why it matters:** they're one conceptual pair (sign out → sign back in), and the mismatch makes login feel unfinished next to its sibling. **Fix:** give login the same framed treatment (or strip logout toward login's restraint — pick one level of ceremony and apply it to both). **Command:** `/impeccable polish`

- **[P2] No skeleton/fallback for the Telegram widget.** The widget script injects asynchronously into an empty `#tg-login-container`; until it loads there's blank space under "Sign in to your console," and if the script fails (network, blocker) the user hits a dead end with no button and no explanation. **Why it matters:** the primary action can silently never appear. **Fix:** reserve the container's height to avoid layout shift, show a placeholder while loading, and render a fallback message + link if the script errors. **Command:** `/impeccable harden`

- **[P3] Redundant messaging on logout.** "Session closed" (label) + "See you soon" (h2) + "You've been signed out successfully." (body) say the same thing three times. **Why it matters:** minor cognitive noise; violates minimalist design in a screen that should be a single clear beat. **Fix:** keep the checkmark + one headline + the button; cut one of the two supporting lines. **Command:** `/impeccable clarify`

## Persona Red Flags

**Sam (Accessibility-Dependent):** Login's real control is a Telegram-rendered iframe — its keyboard order, focus visibility, and screen-reader labeling are outside your control and unverified. The `<p>Sign in to your console</p>` is not programmatically associated with the button. On failure, nothing is announced (no `aria-live`), so a screen-reader user gets no signal the attempt failed.

**Riley (Stress Tester):** Rejects the happy path immediately — kills the network after tapping Telegram auth, or signs in with an unauthorized account. Result on login: the screen sits unchanged, no error, no console-visible recovery. On logout: refreshing or hitting back re-shows "See you soon" even though the session state is owned elsewhere — the page asserts a state it doesn't itself verify.

**Jordan (First-Timer, project persona — the operator):** Lands on `/login` and is asked to authenticate with Telegram with zero explanation of why a video-intelligence console uses Telegram as its identity provider. No "new here?" affordance, no link to what this is. If they don't already have the bot relationship, they're stuck.

## Minor Observations

- `active:scale-[0.96]` on the logout button is a fine press cue (not the banned elastic/bounce), but it's the only press animation in the pair — login's button can't receive it. Another symptom of the asymmetry.
- The green `status-done` tint on the logout checkmark borrows a status hue for a non-job "success." Real-world green-means-done is defensible, but DESIGN.md reserves status hues for pipeline states; worth a conscious call.
- Both pages hardcode `-translate-y-[55px]` and `h-16` logo — fine as a matched pair, but if a third auth-adjacent screen appears (e.g. an error/unauthorized page), this wants to be a shared layout, not copy-paste.

## Questions to Consider

- What does a *rejected* login look like? Right now it looks exactly like a successful one that hasn't redirected yet.
- Is "See you soon" the operator's voice, or a consumer app's? The brand allows "a little delighted" — is this inside that line or over it?
- Should login and logout share a single framed shell so ceremony is defined once and both inherit it?
