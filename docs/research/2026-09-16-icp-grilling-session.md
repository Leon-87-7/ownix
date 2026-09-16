# ICP grilling session — Ownix, as dogfooded by its own operator

Date: 2026-09-16
Method: `mattpocock-skills:grilling` — the user (Ownix's operator/primary user, per `PRODUCT.md`) was interviewed feature-by-feature against a fresh feature list pulled from the codebase (`docs/seed/CAPABILITY_MAP.md`, updated same session — see that file's 2026-09-15 changelog note). Goal: find out what a real dogfooder actually thinks of each feature and why, then feed it into `docs/brand/ICP.md`. Transcript below is verbatim Q + my recommended answer (➡️) + the user's actual answer; synthesis at the end.

---

## Round 1 — ingestion pipelines

**Q1 — Short video analysis.** ➡️ Guessed: yes, highest-volume input.
> Yes — and this is also how I process many GitHub repos: pushed to the repo pipeline as a follow-up in the short pipeline.

**Q2 — Long YouTube video → transcript + enrichment.** ➡️ Guessed: yes, different consumption mode.
> Yes, many times I just submit half-watched videos to get the whole transcript and enrichment for the links — if it's a top-10-list-style video and I don't have the mental bandwidth at the moment but I need the list.

**Q3 — Article ingestion.** ➡️ Guessed: yes, core "staying current" material.
> Not sure I'd be disappointed, but I'm sure there are potential users who have much more usage in the article pipeline.

**Q4 — GitHub repo analysis.** ➡️ Guessed: yes, central to the "tool gatherer" job.
> Yes! This is a key context maker (although maybe there could be more fine-tuning of the prompt).

**Q5 — PDF/document parsing.** ➡️ Guessed: uncertain, occasional use.
> Yes — I use it in my day job, with installation and service grounding, to lay out the checklist of equipment and critical points before the work begins.

**Q6 — Photo/screenshot link extraction.** ➡️ Guessed: yes, lowest-friction capture path.
> Yes.

**Q7 — Direct link add (no processing).** ➡️ Guessed: mild, low-priority fallback.
> Yes — this is a domain I just got to know and I feel it'll be of use in the near future.

**Q8 — Domain allow/ignore rules.** ➡️ Guessed: no, hygiene only.
> Agree with your suggestion.

## Round 2a — branch decisions opened by round 1

**Q9 — The field-service PDF finding.** ➡️ Recommended: bracket as anecdote, one parking-lot line in ICP Open Questions.
> Yes, agreed.

**Q10 — The short-video → repo-followup chain.** ➡️ Recommended: name it as one compound JTBD, not two separate pipeline uses.
> Agreed.

## Round 2b — Second Brain + Generation

**Q11 — Semantic search.** ➡️ Guessed: yes, the payoff step for everything fed in.
> Yes.

**Q12 — Link graph.** ➡️ Guessed: uncertain, more browsing/serendipity than daily driver.
> Not really (never used it). — *Revised after a follow-up explaining what it actually is vs. the Feed's Links tab:* it does change my answer — I don't use it, but MCP phase 3 should be pulling its data from this graph, so I'd like it as a "peek under the hood" feature rather than something I pull by hand.

**Q13 — Shared Brain.** ➡️ Guessed: dormant, solo operator.
> There is no shared brain [i.e. not applicable — no other opted-in members yet].

**Q14 — Mini-PRD / spec generation.** ➡️ Guessed: yes, central to the "building Ownix" side.
> Not using it as frequently as I wish to.

**Q15 — Freestyle / custom-prompt reprocessing.** ➡️ Guessed: mild, occasional escape hatch.
> This is a must.

**Q16 — Recipes (named saved prompts).** ➡️ Guessed: uncertain.
> Maybe this is a real feature I'm sleeping on, or it is not fully deployed as intended. — *Resolved by a fact-check dispatched mid-session:* confirmed broken, not an adoption gap. `db/templates.py` + `api/templates.py` have full CRUD, but job submission's template resolution (`api/jobs.py:_resolve_job_template`) only accepts built-in templates or the literal `"freestyle"` — it never looks up a saved recipe. The web UI (`prompts/page.tsx`) has no "apply this recipe" action, and Telegram's `/freestyle` is a separate, unrelated ad-hoc mechanism. There is no path, from web or Telegram, to actually run a saved recipe against a link or job. Filed as a product bug, not an ICP finding.

## Round 3 — organization + dashboard/access surfaces

**Q17 — Feed.** ➡️ Guessed: yes, home base.
> Yes, this is the main page for me — searching jobs and links, and the `G+T` shortcut for bookmarks. Really useful for in-the-zone work; all my important URLs are just there, full screen.

**Q18 — Intake.** ➡️ Guessed: secondary to Telegram.
> Secondary — even Discord submission is better for me, there's just a short response with no extras.

**Q19 — Job detail page.** ➡️ Guessed: yes, core.
> Yes, core page.

**Q20 — Docs.** ➡️ Guessed: yes, given the day-job use.
> Yes.

**Q21 — Collections.** ➡️ Guessed: uncertain, maybe organizes the "someday" links.
> Yes — I use it as my notebooks.
> *(Elaborated later, Q29): more idea boards and pre-built research. I'd eventually like MCP to connect them to agents so the research phase is faster.*

**Q22 — Tags.** ➡️ Guessed: mild, utility/filtering.
> Core feature, a must.
> *(Elaborated later, Q28): tagged by category (css, design, devtools) and status (TICU — tool I currently use, nextup); pinned tags are key for the `G+T` command.*

**Q23 — Newsletter Digest.** ➡️ Guessed: not yet in regular flow, gated as preview/restricted.
> It's fun, but the pile is going up.
> *(Corrected later, Q30): I don't think it goes against the thesis — it's a new form of keeping track of newsletters outside the email box, and it'll probably grow to other sources like blogs and articles.*

**Q24 — Telegram bot.** ➡️ Guessed: yes, obviously.
> Agreed.

**Q25 — Chrome Extension.** ➡️ Guessed: uncertain.
> Useful, with the shortcuts, when I'm surfing through.

**Q26 — MCP clients.** ➡️ Guessed: possibly the feature that closes the loop back to "feed it to my coding agent."
> It's fresh, so I haven't gotten the chance to make a splash with it — and it's only in phase one of three.

**Q27 — Discord pairing.** ➡️ Guessed: no, unused.
> Love the little weight feel [i.e. the lightweight, low-ceremony nature of it].

## Round 4 — follow-ups opened by round 3's surprises

**Q28 — Tags mental model.** See Q22 elaboration above (category × status; pinned tags drive `G+T`).

**Q29 — Collections mental model.** See Q21 elaboration above (idea boards / pre-built research; wants MCP to connect them to agents).

**Q30 — Newsletter Digest tension.** See Q23 correction above (not a thesis conflict — a new, still-maturing tracking channel expected to expand beyond newsletters).

**Q31 — Frictionless-capture preference, named explicitly.** ➡️ Recommended: worth stating in the ICP — this user-type's real trigger is a low-effort capture-while-scrolling reflex, not a deliberate sit-down session.
> Agreed.

---

## Synthesis

**The beachhead JTBD is sharper and different from the original ICP hypothesis.** It isn't "re-watch a tutorial, extract a command, paste it as coding-agent spec." It's a continuous, low-ceremony habit: stay current on tools/design/frontend trends while building something, with a concrete recurring trigger chain — *see a tool demoed in a short clip → pull its repo → evaluate it* (Q1/Q10) — plus a bandwidth-recovery mode — *submit a half-watched listicle-style video to get the transcript/summary instead of finishing it* (Q2). This resolves ICP.md's open "trigger moment" question in the direction of *repeated pattern*, not *acute single moment* — from this one data point; still needs validation beyond N=1.

**Capture wants to be frictionless, not featureful.** Discord ("short response, no extras") and Chrome Extension shortcuts both beat the dashboard's own Intake page, and Discord/Chrome Extension answers were both warmer than expected going in. The dashboard is where you *work* (Feed, Job detail, Docs, Collections); it is not where you *capture*.

**The real desired mechanism is agent-mediated, not human-mediated.** Two independent answers converged on the same want: Collections should feed an AI agent directly via MCP to speed up research (Q29), and the Link graph's real value is as backend infrastructure MCP phase 3 should expose — not a UI to browse by hand (Q12 revision). This is a more specific, more mechanistic version of the original "feed a video into a coding agent as spec" framing: the agent should pull structured, already-organized context from Ownix, not receive a pasted transcript.

**Organization is real and manual, which is why the graph never got adopted.** Tags (category × status, e.g. `TICU`/`nextup`) and Collections (idea boards / pre-built research) are both called "a must" / "core," and both are deliberate, hand-built structures the user already trusts. The Link graph's pitch — auto-discovered relationships — has no foothold against a taxonomy the user already maintains by hand.

**Two features are broken/underused for different reasons, not by user preference:**
- Recipes: confirmed broken — no apply path exists anywhere in the codebase. Product bug, file separately.
- Mini-PRD: "not using it as frequently as I wish to" — a real adoption gap, cause not diagnosed this session.

**Two things are out of ICP scope but worth remembering:**
- Day-job field-service PDF/checklist use (Q5/Q9) — a real, valuable use case, but in a domain disconnected from the dev-tool beachhead. Parking-lot note only.
- Newsletter Digest's current "pile going up" state — not a thesis contradiction per the user's own read, just a new, still-maturing intake channel expected to expand to blogs/articles.
