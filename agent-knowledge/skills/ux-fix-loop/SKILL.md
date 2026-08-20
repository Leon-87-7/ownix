---
name: ux-fix-loop
description: Turns an observed UX/UI defect — often a screenshot — into a brand-grounded, minimal, tested fix. brand-lens supplies the principle, the user picks the solution, TDD implements it. Use when a UI/UX problem surfaces and the fix should be checked against Ownix's brand principles before being built, or the user says "run this through brand-lens then fix it," "propose grounded fixes," or "brand-check this bug and implement the one I pick."
---

# UX Fix Loop

Observe → Ground → Choose → Implement. Turns a spotted defect into a fix that traces to a specific Law, not a vibe, and ships as the smallest tested diff that closes it.

## Steps

1. **Observe the defect precisely.** If given a screenshot, read it and state the concrete symptom as a before/after — what currently happens vs. what should — not a vague "this feels off." Read the actual component/route behind it to confirm the symptom traces to real code, not assumption.

2. **Ground it with `brand-lens`.** Invoke the `brand-lens` skill with the concrete defect (step 1's before/after) as its target, not the general area. Its own completion criterion applies — a 👍/👎 verdict per applicable Law. Every solution proposed in step 3 must trace to one of those verdict lines, not "seems fine."

3. **Propose solutions, cheapest first, then stop.** Grep/read the actual component(s) before proposing — every option must name a real file, and reuse an existing component/prop/pattern already in the codebase over inventing one. Rank by cost, cite the Law each is grounded in, and stop there: which one ships is the user's call, never auto-selected even when the cheapest option is obviously correct.

4. **Build → test → fix → test.** Write the fix directly, scoped to exactly the chosen option — not a broader refactor the investigation surfaced along the way. No red-first step: the code exists before any test runs against it — that upfront cost buys nothing on a change this small and pre-scoped. Run the touched test file(s) against the fix; on a failure, fix and re-run until green. Typecheck, then run the full suite once at the end.
   - Run `/code-review` scoped to the actual diff. Its generic checklist is written for a whole-repo audit; running it against unrelated files sitting dirty in `git status` wastes a review on someone else's in-progress work.
   - Stage and commit only the files that belong to this fix, even when the repo has other unrelated changes sitting dirty.

## Completion criterion

The chosen option is committed: its test file passes against the fix, the full suite passed once at the end, and the commit's staged files are exactly the ones this fix touched — nothing dirty and unrelated swept in.
