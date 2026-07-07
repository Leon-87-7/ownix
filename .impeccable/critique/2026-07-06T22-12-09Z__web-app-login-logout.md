---
target: login page and logout page
total_score: 34
p0_count: 0
p1_count: 0
timestamp: 2026-07-06T22-12-09Z
slug: web-app-login-logout
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 4 | Pending state, widget skeleton, aria-live all present |
| 2 | Match System / Real World | 4 | Specific 401 vs network error copy |
| 3 | User Control and Freedom | 4 | Retry preserves last attempt; clear path back |
| 4 | Consistency and Standards | 3 | Shared AuthShell unifies the pair; Telegram widget still can't inherit button vocab |
| 5 | Error Prevention | 3 | Single-action screens |
| 6 | Recognition Rather Than Recall | 3 | Self-evident |
| 7 | Flexibility and Efficiency | 3 | One-tap auth, auto-redirect |
| 8 | Aesthetic and Minimalist Design | 4 | Nested card + glass gone; redundancy cut to one beat |
| 9 | Error Recovery | 4 | Plain-language errors + retry, keeps lastAuthUser |
| 10 | Help and Documentation | 2 | Still no "why Telegram?" for a true first-timer |
| **Total** | | **34/40** | **Good — top of band, polish territory** |

## Anti-Patterns Verdict

**LLM assessment:** The two DESIGN.md violations from the prior run (24/40) are gone. Logout is a single `rounded-lg border border-line bg-surface` plate — no nested card, no backdrop-blur glass. The green status-done checkmark borrow is replaced with a neutral `bg-raised text-ink` tile. Login is a proper state machine with loading skeleton, role="status"/role="alert", aria-busy, and specific error messages. Shared `AuthShell` resolves the asymmetry. Reads as deliberate product work.

**Deterministic scan:** `detect.mjs` clean — `[]`, exit 0, across login/logout pages + auth-shell.tsx.

**Visual overlays:** Fallback — login's control is the remote Telegram widget iframe; source + token review substituted.

## What's Working

- The auth state machine: idle → pending → error with distinct 401 vs network copy, retry replaying stored lastAuthUser, and aria-live announcement. P1 fully closed.
- `AuthShell` refactor: the -translate-y-[55px] magic number, logo, background now in one place; the pair can't drift apart again.
- Logout correctly minimal: one plate, one neutral confirmation icon, "Session closed," one signal button.

## Priority Issues (all minor)

- **[P2] First-timer gets no "why Telegram?" context.** Someone without the existing bot relationship sees a Telegram button and no explanation of why a video console authenticates through Telegram. Fix: one context line or a "New here?" link. Judgment call — single-operator today. → /impeccable onboard
- **[P3] ~~`logout-card-enter` keyframe now fires on login too~~** — RESOLVED: keyframe renamed to `auth-card-enter` in globals.css (line 143) and referenced correctly in AuthShell (line 15). Animation works for both login/logout as intended.
- **[P3] Telegram widget can't inherit console button vocabulary** — renders in Telegram's own blue/font inside the framed card. Inherent to third-party widget; accept. → no action.

## Persona Red Flags

**Sam (Accessibility):** Much improved — role="status"/role="alert" + aria-live announce pending/error/retry. Remaining unavoidable gap: injected Telegram iframe internal keyboard/SR behavior is outside control.

**Jordan (First-Timer / operator):** Persistent flag — no context for the Telegram IdP choice (the P2).

**Riley (Stress Tester):** Network kill → specific "could not reach the login service" + retry. Widget script fail → dedicated role="alert" fallback. Robust. Leftover: logout asserts "Session closed" statically regardless of real session state, but it's a display-only terminal page — low risk.

## Minor Observations

- Dead `disabled:` styles on retry button — authError is cleared when retryAuth sets pending, so the error block holding the button never renders during pending; disabled branch unreachable. Harmless, deletable.
- Neutral logout checkmark reads as "acknowledged" rather than "success" — conscious tradeoff to avoid status-hue borrow.

## Questions to Consider

- Does the first-timer/"why Telegram" gap matter while single-operator, or is it deferred until multi-tenant signup?
- Should the entrance animation stay on login (an interactive screen) or be reserved for logout (a terminal confirmation)?
