---
target: the Ownix landing page
total_score: 32
p0_count: 0
p1_count: 2
timestamp: 2026-07-13T05-36-17Z
slug: web-app-page-tsx
---
# Design Critique: Ownix Landing (`web/app/page.tsx`)

### Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | No cue for what happens *after* "Sign in with Telegram" |
| 2 | Match System / Real World | 3 | Invite card says "drop your email" but offers only a Telegram button |
| 3 | User Control and Freedom | 4 | Nothing traps; every path is reversible |
| 4 | Consistency and Standards | 3 | Three CTA labels ("Get an invite" / "Sign in" / "Sign in with Telegram") funnel to one `/login` |
| 5 | Error Prevention | 3 | "Look inside" → `/restricted` may door-slam strangers |
| 6 | Recognition Rather Than Recall | 4 | Everything shown, nothing to remember |
| 7 | Flexibility and Efficiency | 3 | Returning users get the nav shortcut; fine for a landing |
| 8 | Aesthetic and Minimalist Design | 3 | Uniform section rhythm; dead demo placeholder |
| 9 | Error Recovery | 3 | No failure surfaces on the page itself |
| 10 | Help and Documentation | 3 | "no password · approval within hours" answers the key anxiety; "what happens next" doesn't |
| **Total** | | **32/40** | **Good — solid foundation, address weak areas** |

### Anti-Patterns Verdict

**LLM assessment: PASS.** No gradient text, no eyebrows, no hero-metric template, no card-grid filler. Stat tiles follow DESIGN.md's summary-tile pattern; amber appears only where action lives. Count-up stats are defensible: counting IS the section's argument.

**Deterministic scan: agrees.** Zero findings across `page.tsx`, `app-slot.tsx`, `count-up.tsx`, `hero-gradient.tsx`. No false positives.

**Visual overlays:** not available this session (extension blocks localhost); CLI detector + source review used instead.

### Overall Impression

A confident, disciplined page whose weakest moments are all conversion-flow moments, not visual ones. Fix the funnel semantics (invite card) and the placeholder proof (demo video) and this page is genuinely strong.

### What's Working

1. **The headline triad** — "You watched it. You liked it. *You lost it.*" with the third beat dimmed to muted: typographic storytelling specific to the product's pain.
2. **Evidence as design** — real filename, timestamps, transcript in JetBrains Mono; the page shows a working system instead of claiming one.
3. **System fidelity as trust** — built from the product's own tokens; the promise and the product look the same.

### Priority Issues

- **[P1] Invite card runs three mental models**: "Get an invite" → "Invite-only for now" → "Sign in with Telegram" → "drop your email" (no field). This is the conversion moment; ambiguity here is abandonment. Fix: rewrite card copy as the actual sequence and/or relabel the button ("Request an invite via Telegram"). → /impeccable clarify
- **[P1] Proof section's evidence is fake right now**: "Real capture, real time. No cuts." under a dead play button. Ship demo-capture.mp4 before launch; until then reorder or soften the claim. → content task + /impeccable polish
- **[P2] Three labels, one destination**: nav "Sign in", "Sign in with Telegram", "Get an invite" all resolve to /login. Make invite-path labels about requesting access; keep nav for returning users. → /impeccable clarify
- **[P2] Flat section rhythm**: every section py-12 over identical hairlines; the invite section carries no extra weight at the moment of decision. Vary rhythm (py-16/py-20 for story + invite). → /impeccable layout
- **[P3] "Look inside" → /restricted**: verify what a stranger sees; if it's a cold wall, rename or repoint.

### Persona Red Flags

- **Jordan (First-Timer)**: breaks at the invite card — "it says drop my email but there's no field." Hero mechanic (rotating share icon) lands well.
- **Riley (Stress Tester)**: would document the play button that plays nothing and whatever /restricted does to outsiders. Everything else holds.
- **Casey (Mobile)**: 44px coarse-pointer targets, sub-360px tile stacking, flat mobile scrim all pass. WebGL shader worth one low-end-device look. Bottom invite card = good thumb ergonomics.

### Minor Observations

- Telegram button 36px vs system 32px buttons (inherited from HTML comp).
- Footer link hover (text color) vs nav link hover (plate raise): two grammars for one element class.
- The Brain teaser is plain muted text while the one sanctioned gradient goes unused.

### Questions to Consider

- What if the invite card were the form — one email field beside the Telegram button?
- Does the demo need to be a video? An animated transcript replay (mono lines at real timestamps) is proof in the product's own voice.
- Should the Brain line carry the page's single expressive gradient moment, or is total restraint the stronger tease?
