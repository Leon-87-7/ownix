# User pain-point language — primary-source research

Date: 2026-09-15
Scope: find real, first-hand posts/comments where people express the "accumulation without transformation" pain Ownix/vig solves — saved videos/articles piling up unused, wanting to turn them into something usable (agent context, script, study notes). Used to (a) find early users to recruit, (b) mine literal customer language for landing-page copy. Research only — no code changes.

**Tooling constraint, stated up front (HN pass):** `WebFetch` returned a hard "unable to fetch" error for `reddit.com`, `old.reddit.com`, and (implicitly, via search results only) `x.com`/`twitter.com` — those platforms could not be queried directly for raw thread/comment text. `WebSearch` against `site:reddit.com` / `site:x.com` consistently surfaced secondary sources (blog posts, app-store listings, marketing pages *about* the phenomenon) instead of actual Reddit/X post text, even with exact-phrase queries. The one channel that worked reliably in that first pass was the **HN Algolia API** (`hn.algolia.com/api/v1/search`, fetchable directly, returns real comment text with item IDs) — all verbatim quotes in §1–2's original pass are sourced from it.

**Update — Reddit pass (same day, via `claude-in-chrome` live browser session):** the WebFetch block does not apply to a real rendered browser session. A manual Reddit search pass (`reddit.com/search`) closed most of the gaps flagged in §4 — see new §1b and §2b below. X/Twitter still untried (no live session run against it yet).

---

## 1. Row-one (builder) findings — feeding video/article content into an AI coding agent

### Key Takeaways

- People already manually do the "transcript → agent context" workflow Ownix automates, and describe it as copy-paste friction: **mceachen** — "copy-paste the whole transcript into Claude or chatgpt and tell it to summarize with whatever resolution you want" — [HN comment](https://news.ycombinator.com/item?id=44827101)
- Same workflow named as a recurring time cost, not a one-off: **ryu_zenmaster** — "I was wasting 2 hours a week copying content into claude or chatgpt" (built their own webpage-to-markdown capture tool in response) — [HN comment](https://news.ycombinator.com/item?id=45643082)
- Same pattern for YouTube specifically: **WendyTheWillow** — "Instead of hand-formatting a transcript I pull from YouTube, I paste it into Claude and have it reformat" — [HN comment](https://news.ycombinator.com/item?id=38190401)
- And again: **paulcole** — "Copy the transcript. Go to Claude, 'Summarize key bullet points' + paste the transcript" — [HN comment](https://news.ycombinator.com/item?id=41931352)
- A builder who hit this friction hard enough to ship a point-solution: **nikhonit** — "I realized most YouTube transcript APIs were either overpriced or lacked good integration for LLM workflows," building a JSON transcript API with MCP support specifically for agent workflows — [HN comment](https://news.ycombinator.com/item?id=46364842), tool: [Show HN: A JSON API for YouTube Transcript with MCP Support](https://news.ycombinator.com/item?id=46368162)
- Market-signal corroboration (not direct pain quotes, but repeated independent solves of the same problem = real demand): at least seven other **"Show HN: YouTube transcript → LLM/agent"** tools surfaced in one HN search — transcript-to-document generators, Whisper-based cleaners, MCP servers, a Claude-Code-transcript-into-Codex bridge — e.g. [Show HN: YouTube Transcript Optimizer](https://news.ycombinator.com/item?id=41636074), [Show HN: I made a tool to extract YouTube transcripts and skip the fluff](https://news.ycombinator.com/item?id=43706591), [Show HN: A CLI tool to transcribe and clean YouTube videos with Whisper and LLMs](https://news.ycombinator.com/item?id=44353447), [Show HN: Pull Claude Code transcripts into your Codex session, and vice versa](https://news.ycombinator.com/item?id=48777790)

**Not found (HN pass):** no primary-source quote of the more specific row-one framing used in the ICP ("I re-watched a tutorial just to find the one command I needed" / "I want this video as spec for my coding agent"). What was found is adjacent and one level more general — people already treat pasted transcripts as agent input, but nobody quoted here explicitly names *re-watching to re-extract* as the trigger, or names an *AI coding agent* (Claude Code/Cursor specifically) as the destination rather than a general chat LLM.

### 1b. Reddit pass — still adjacent, still not a bullseye on the trigger moment

- Direct confirmation of the manual "watch-later backlog → want the outline without watching" pattern, named specifically against Claude: OP **Ok-Toe5692**, r/ClaudeAI — "I have a ton of videos in the watch later related to AI, but my time is limited, and I want to have an outline of the video before watching it." / "I would like to make a summary of the video, but Claude told me it cannot fetch and summarize the video by providing the link." — [r/ClaudeAI: "HELP: Claude cannot summarize YT videos"](https://www.reddit.com/r/ClaudeAI/comments/1t6sc1l/help_claude_cannot_summarize_yt_videos/)
- Commenters on that thread confirm the same copy-paste-transcript workaround found on HN, independently: **SubstantialCrow** — "download the transcript of the video and paste it into the chat"; **NimbusFPV** — "pull just subtitles... Use Claude to summarize the subtitles and make a summary file, then make an index of the summary files" (i.e., manually hand-building the exact index Ownix's Second Brain automates) — same thread.
- Searched directly for the ICP's specific "re-watch a tutorial to re-extract one command, feed it to a coding agent" framing (`"watched the video again" claude OR cursor`, `r/cursor` search for "youtube tutorial context") — **still not found**. r/cursor context-question threads found are about codebase/file context, not video/tutorial context, so this remains a real gap, not just an HN-tooling artifact — see updated §4.

---

## 2. Row-two (creator/social/student) findings

### Key Takeaways

- One adjacent student/study-notes data point: **geekraver** — describes pasting video transcriptions into ChatGPT with a study-notes prompt instead of taking the tool's auto-generated summary at face value — [HN comment](https://news.ycombinator.com/item?id=40104641). Adjacent, not confirmed lecture-specific — the video type isn't stated in the excerpt.
- General "accumulation without transformation" pain (not video-specific, but the same underlying complaint the Constitution names) shows up clearly for saved links/bookmarks:
  - **markatkinson** — "my bookmarks are a graveyard for things I'll never read" — [HN comment](https://news.ycombinator.com/item?id=14066062)
  - **Patlakh** — "50+ open tabs, bookmark graveyards, nothing gets read" — [HN comment](https://news.ycombinator.com/item?id=46735640)
  - **moogly** — "it was a graveyard where links went to die" / "All those things are where tabs go to die, never to be read again" — [HN comment](https://news.ycombinator.com/item?id=14828978)
- Personal-notes/second-brain version of the same pain: **barrkel** — "Most of these logs are write only. They can help as a kind of written rubber duck. And about 1 in 100 turn out to be extremely useful" — describing a personal log system where the vast majority of entries are never revisited — [HN comment](https://news.ycombinator.com/item?id=44402799)

**Not found (HN pass):** no primary-source post from a content creator (pulling a saved clip back up for a script/quote) or a social manager (tracking competitor/trend content) turned up in this pass — zero hits for either sub-persona specifically. Everything in the original §2 is HN-sourced, which skews technical/builder-adjacent even where the topic is general bookmarking.

### 2b. Reddit pass — row-two pain, directly confirmed, video-specific

This closes the row-two gap flagged above. Strongest single thread: **r/nosurf**, OP **quitescoller** — ["Anyone else save a hundred 'life-changing' reels and never open them again?"](https://www.reddit.com/r/nosurf/comments/1wc862t/anyone_else_save_a_hundred_lifechanging_reels_and/) (103 upvotes, 32 comments):
- "But now every third reel feels *important*. A hack I should try, a tip I should remember. So I save it. 'I'll come back to this later.' I never come back to it."
- "My saved folder is now a graveyard of hundreds of reels I've never reopened. It's weirdly stressful — I'm collecting advice faster than I could ever actually use it."
- OP's own follow-up comment is close to a verbatim restatement of the Constitution's "accumulation without transformation" framing, produced with no prompting toward that language: "The thing I struggle with even beyond saving is that by the time I revisit something, I've totally forgotten why I saved it or what was even useful about it. A reel loses its context fast — it's just a thumbnail and a vague 'past me thought this mattered.'"
- Corroborating comments, same thread: **Kath-r-in** — "I was just cleaning up screenshots on my desktop yesterday and some of them don't even look familiar, and I'm like, why did I want to save that!!!"; **Olallieberry9870** — "i won't lie i found myself about to save this comment. now realizing i'll prob never go back and look at it. it's a problem"; **Natural-Attempt-3922** describes a manual once-a-month calendar-reminder workaround (a "someday" file) as their coping mechanism — a manual version of Ownix's job.
- **Note:** r/nosurf's own rule #1 is "NO APPS. No self promotion posts; no surveys; no research; no studies" — this sub is a language-mining source only, not a recruiting or posting channel.

Social-manager / creator confirmation, **r/socialmedia**, OP **Significant_Fig7446** — ["Does anyone else have hundreds of saved Reels they never actually use?"](https://www.reddit.com/r/socialmedia/comments/1s7458b/does_anyone_else_have_hundreds_of_saved_reels/) (posted while explicitly validating a similar product idea — a competitor/demand signal, not just a pain post):
- "I've been talking to a bunch of smm and creators lately and nearly everyone has the same thing: hundreds of posts saved across Instagram collections, DMs to themselves, screenshots buried in their camera roll — all saved as 'inspiration' — and then never touched again."
- "The content either disappears (creator deletes it, goes private), or it just drowns in the pile and you forget why you saved it in the first place." — this second clause directly validates Ownix's "ownership of an already-transformed copy, regardless of what happens to the source platform" pitch (ICP.md §"Why not Notion/Pocket").
- Comment, **wilzerjeanbaptiste**: "Yeah this is basically universal. Every creator I talk to has the same problem, hundreds of saved posts that just collect dust."

Also surfaced, not yet opened/quoted (leads for a future pass): r/ContentCreators duplicate of the same socialmedia question; r/SideProject — "How I solved the problem of never finding saved Instagram reels when I actually need them" (a builder describing having shipped a competitor-adjacent tool: "It's like having a conversation with someone who's watched all your saved reels and can recall any of them perfectly").

---

## 3. Search-query strings for ongoing recruiting + copy-mining

### HN Algolia (worked reliably — direct API, no auth, real comment text)

Base: `https://hn.algolia.com/api/v1/search?query=<phrase>&tags=comment`

- `paste transcript into claude`
- `youtube transcript context agent`
- `read it later graveyard`
- `second brain notes never review`
- `bookmark graveyard`
- `wasting hours copying content`

### Reddit (not fetchable via `WebFetch`; done via `claude-in-chrome` live browser session instead — works fine, see §1b/§2b)

Confirmed productive (used in this pass, via `reddit.com/search/?q=...`):
- `"paste the transcript" claude` → row-one manual-workaround thread (§1b)
- `saved reels never watch` → the single best row-two thread (§2b) — reuse this one, it's a strong query
- `youtube tutorial context` restricted to `r/cursor` → mostly codebase-context noise, not video-context; not productive

Still worth trying (not run this pass):
- `r/ClaudeAI`, `r/cursor` search: `feed this into claude code`, `spec from video`, `youtube tutorial claude code`
- `r/ChatGPTCoding`, `r/AI_Agents` search: `transcript as spec`, `video as context`
- `r/DataHoarder` search: `reel backlog`
- `r/ObsidianMD`, `r/PKMS` search: `youtube video notes never`, `transcript workflow`
- `r/SideProject`, `r/ContentCreators` — already have one strong hit each (§2b); worth a full read-through, not just search

### X/Twitter (not automatable with current tools — `WebSearch site:x.com` surfaced only vendor/product tweets, no individual pain posts; try Twitter's own search UI directly)

- `"wish I could feed this into" claude OR cursor`
- `"paste the transcript" claude code`
- `"I keep losing" saved videos OR reels`
- `"never rewatch" reels OR tiktok`

---

## 4. Explicit gaps — do not treat as validated without further work

- **X/Twitter still has zero primary-source quotes.** Neither pass reached it — the HN-pass agent's `WebSearch site:x.com` only returned vendor/marketing tweets, and the Reddit pass didn't attempt X. Still needs a live logged-in browser pass (`claude-in-chrome` against x.com/search) before the X leg of the CSO/CMO-recommended channel list (r/ClaudeAI, r/cursor, Discords, X) counts as covered.
- **RESOLVED — row-two (creator/social-manager) pain is now directly confirmed**, video-specific and Reddit-sourced: see §2b (r/nosurf, r/socialmedia). Treat student-specific pain as still unconfirmed — the closest evidence is still the HN study-notes comment in §2, which doesn't specify lecture video.
- **Still open — no verified quote ties "re-watching a video to re-extract one detail" directly to "AI coding agent context."** Both passes found the same adjacent signal (people already paste transcripts into Claude/ChatGPT/Cursor manually) but neither found the specific vivid moment from the ICP's "trigger moment" open question — this looks like a real gap in what people post about, not a tooling artifact, since the Reddit pass could reach the platforms and still didn't find it. Worth testing via direct outreach/DMs rather than more searching.
- **Sample size is still small and non-random** (a handful of HN + Reddit search results, not a systematic scrape) — treat every phrase above as a lead to search further or validate in outreach conversations, not as statistically representative "the" customer language.
