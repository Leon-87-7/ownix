---
name: brand-lens
description: Evaluate a feature idea, UX flow, copy, product decision, or ADR draft against Ownix's brand principles. Use when the user says "brand check this," "through the brand lens," "does this hold up against the Constitution," "ICP check," or invokes /brand-lens <target>.
---

# Brand Lens

Checks a target against Ownix's brand principles and returns a verdict grounded in a specific Law or principle, not a vibe.

## Steps

1. **Read the lens fresh.** Read `docs/brand/CONSTITUTION.md`, `docs/brand/ICP.md`, and `PRODUCT.md` in full — every run, never from memory. These evolve; a cached read is a stale lens.

   `docs/brand/` is gitignored (public repo, internal strategy — see its `README.md`). On a checkout without it, say so plainly and stop: do not fabricate the Laws, ICP framing, or brand voice from guesses or training data. A missing lens is a finding to report, not a gap to fill.

2. **Locate the target.** If the user named a file, PR, or piece of copy, read it. If they described an idea in the message, that description is the target — no need to go looking for more.

3. **Check the target against each of these, and keep only the ones that actually bear on it:**
   - **First Law (Ownership).** Portable, inspectable, understandable, no Ownix lock-in.
   - **Second Law (Participation creates intimacy).** Run the test verbatim: *"what cognitive value would the user lose if we automated this?"* Automating friction (transcribing, formatting, retrieving) is fair game; automating judgment (deciding what a source means, what applies, what to trust) is not.
   - **Third Law (not anti-AI).** AI should amplify thinking, not replace the participation that builds context.
   - **Fourth Law (accumulated judgment outranks the latest recommendation).** Does the target respect a user's existing tool/workflow choices, or push a "better" recommendation over their accumulated experience?
   - **Purpose's "deliberately."** Does the target require the person to participate, or does it quietly build/act on their behalf?
   - **Emotional arc.** Does the target move someone Grounding → Recognition → Curiosity, or risk Anxiety → Productivity → More consumption?
   - **ICP automation line.** Kills friction, never cognition — the Second Law's test, applied to messaging and positioning specifically.
   - **ICP hoarding framing.** Does the target help transform accumulated content into something used, or just make the pile easier to add to?

4. **Write the verdict.** For each Law/principle that applies, give: which one, the specific line or test it's citing, and a plain judgment — pass, fails, or tension — worded so it could go straight into an ADR. Close with one overall stance sentence.

## Completion criterion

Every applicable Law/principle from step 3 has a verdict line citing its specific test — not a generic "seems on-brand."
