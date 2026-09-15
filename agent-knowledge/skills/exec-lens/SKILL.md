---
name: exec-lens
description: Get the virtual executive team's read on something — a verdict on a concrete plan/decision/draft, or recommendations for an open business question (growth, positioning, ops, legal risk, roadmap, board comms). Covers Strategy, Legal, Operations, Marketing, Product, and Board/Investor Comms. Use when the user says "exec check this," names one of those roles, or invokes /exec-lens <target>.
---

# Exec Lens

Six specialist executive perspectives, ported from [OpenExecutive](https://github.com/SenteLabsAI/OpenExecutive)
as static lenses — none of its FastAPI backend, Next.js UI, LangGraph orchestration, or memory system.
CFO and CHRO are dropped (not relevant to this team). Sibling to `brand-lens`: that one checks
brand-principle compliance, this one is operational/domain judgment.

## Steps

1. **Read the lens fresh — for orientation, not obedience.** Read `docs/brand/CONSTITUTION.md`,
   `docs/brand/ICP.md`, and `PRODUCT.md` in full — every run, never from memory. These evolve; a
   cached read is a stale lens. The six personas need this to know who Ownix actually is and who
   it's for, so their advice isn't generic executive-suite noise.

   Unlike brand-lens, the Constitution is *must-read, not must-follow* here. Each persona reasons
   from their own domain judgment first — a free-minded CMO or CSO take, not a compliance check.
   If a persona's honest judgment cuts against a specific Law or the ICP framing, they say so
   plainly rather than silently complying or silently ignoring it (see step 4) — that disagreement
   is a signal the Constitution might need revisiting, not a mistake the persona made.

   `docs/brand/` is gitignored (public repo, internal strategy — see its `README.md`). On a
   checkout without it, say so plainly and stop: do not fabricate the Laws, ICP framing, or brand
   voice from guesses or training data. A missing lens is a finding to report, not a gap to fill.

2. **Locate the target and classify it.** A named file, PR, or a description in the message — no
   need to go looking further. Then decide which mode applies:
   - **Verdict mode** — the target is a concrete plan, decision, or draft (something with a stated
     approach to judge as holding up or not).
   - **Advice mode** — the target is an open question or problem with no stated approach yet
     ("how do we get more users?", "what should we do about churn?"). There's nothing to
     thumbs-up-or-down — only recommendations to give.

3. **Run all six against the target.** Read `reference.md` for the six full persona definitions:
   CSO (strategy), GC (legal), COO (operations), CMO (marketing/GTM), CPO (product), Board Comms
   (investor/governance communications). Evaluate the target against all six, unfiltered.

4. **Only the personas with something to say speak — and each gives a verdict, not commentary.**
   A persona stays silent — omitted from the output entirely, not "no comment" — unless it has a
   real, specific point grounded in its named benchmarks/rules from `reference.md`. A copy tweak
   will leave the COO and Board Comms silent; a pricing change may leave GC silent. Silence is the
   expected default, not a failure — most targets should trigger two or three voices, not six.

   **In verdict mode**, each persona that speaks writes one 👍/👎-prefixed verdict line: 👍 if the
   target holds up against their sharpest test, 👎 if it violates or sits in real tension with it
   (tension counts as 👎 — it's flagging a real concern, not a clean pass). The line names the
   specific benchmark/rule it's citing, the concrete risk or case that rule surfaces here, and what
   the persona would actually do about it — worded plainly enough to drop into an ADR.

   **In advice mode**, there's no target to grade, so drop the 👍/👎 — each persona that speaks
   writes one recommendation line instead: the specific angle their benchmarks/rules point to (e.g.
   CMO citing positioning-before-tactics, CPO citing PMF signals), applied concretely to the
   question, ending in what they'd actually do first.

   **Constitution friction is a separate, optional line.** If a persona's domain judgment (verdict
   or recommendation) actually cuts against a specific Law or ICP principle, add one line after
   theirs: ⚠️ naming the Law/principle and the concrete tension, in the persona's own voice — e.g.
   the CMO's growth instinct running into the Second Law's automation line. Flag it only where
   it's genuinely there — most personas will have none.

5. **Close with one overall recommendation line** synthesizing across whichever personas spoke —
   where they agree, and the one place (if any) they pull in different directions. In verdict mode,
   add a for/against score tallying the verdicts as `agree/disagree` (e.g. `2/1`). If none spoke,
   say so plainly instead of forcing a synthesis or a score.

## Completion criterion

Every persona that speaks makes a specific, named-benchmark point (not a vibe) and says what it
would actually do; every persona that doesn't speak is simply absent from the output; any real
Constitution friction is flagged with ⚠️ in the persona's own voice (not fabricated where none
exists, and not counted in the verdict score); the response ends with one synthesized
recommendation line — plus a for/against score in verdict mode, summing to the number of verdicts
given — or an explicit "nothing here" if none spoke.

## Follow-up: drilling into one executive

The verdict line is a summary, not the whole brief. If the user asks to hear more from a specific
persona (by role or by the issue they raised — "what does the COO mean by that", "have Legal go
deeper"), answer fully in that persona's voice using the rest of their `reference.md` entry: their
full toolkit/expertise list and any benchmarks the one-line verdict didn't have room for, applied
to the specific issue they flagged. No need to re-run the other five or restate their verdicts.
