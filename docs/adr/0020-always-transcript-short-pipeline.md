---
adr: "0020"
title: Short pipeline always produces a transcript, independent of the prompt template
status: accepted
date: 2026-06-02
---

## Context

Today the short pipeline only touches a transcript when a prompt template is set: plain-URL short jobs `return` after the Vision delivery (`short_video.py`) and never call the transcript service. Even on the template path, the transcript text is persisted to `jobs.transcript` only on the caption-based branch — the caption-less audio-fallback branch (ADR-0009) throws the transcript away, storing only the `template_analysis`.

We want a transcript for **every** short job, regardless of whether a template was requested — persisted to the DB, uploaded to Drive, and delivered to the user as its own document — bringing the short pipeline in line with how the long pipeline already treats its transcript.

## Decision

Decouple transcript acquisition from the template/enrichment fork. The transcript becomes a guaranteed-*attempted* step on every short job.

1. **Three homes.** Every produced transcript is (a) persisted to `jobs.transcript`, (b) uploaded to Drive as a distinct `{job_id}_transcript.md` artifact, and (c) sent to the user as its own Telegram document — separate from the existing `{job_id}_short.md` analysis artifact, mirroring the long pipeline.

2. **Always transcribe (Option A), via the existing Gemini key.** Caption-less videos are transcribed with a transcription-only Gemini call using the existing free→paid key fallback (Invariant #4 / ADR-0006, ADR-0011). No new provider. OpenRouter was evaluated and rejected (see Alternatives).

3. **Fetch once, up front; two-call budget preserved.** The transcript is fetched once before the template fork and the enrichment path consumes the stored text. To avoid double-transcribing on caption-less template jobs, `enrich_audio` now **returns the transcript text** it already produces internally, so the single fused transcribe-and-enrich call serves both needs. Resulting budget is unchanged on every path:
   - plain caption'd: Vision + free captions = **1 call**
   - plain caption-less: Vision + transcribe-only = **2 calls**
   - template caption'd: Vision + enrich = **2 calls**
   - template caption-less: Vision + fused transcribe-and-enrich = **2 calls**

4. **Delivery is the tail, uniformly.** Persistence happens the moment the text exists, but the transcript document + Drive upload are always the **last** thing the short pipeline emits — after any enrichment. This makes ordering uniform across all paths at zero extra cost (persistence and delivery are separable).

5. **Best-effort, with an explicit failure taxonomy.** Vision success already marks the job `done`; a transcript problem never regresses status or fails the job. The tail emits a specific note per situation:
   - sidecar download/HTTP error → `⚠️ Transcript service error: <message>`
   - caption-less → *not an error*; audio route kicks in automatically
   - Gemini transcription fails (`GeminiUnavailableError`) → `⚠️ Transcription failed — Gemini unavailable`
   - succeeds but empty (silent / no speech) → `⚠️ I'm wordless`

6. **`key_phrases` whenever text exists.** The local key-phrase extraction now runs for any short job with a transcript, not just template jobs. No new job status is introduced.

## Alternatives considered

| Alternative | Rejected because |
|---|---|
| Captions-only (no transcription on caption-less plain jobs) | Leaves a hole exactly where short videos most often have no captions (silent TikToks); not truly "regardless" |
| OpenRouter Nemotron Nano Omni `:free` as transcriber | Only genuinely-free audio model on OpenRouter, but a general omni LLM (not ASR), lower quality on noisy short-form audio, `:free` rate/training caveats, and a third provider that breaks Invariant #4. We already own a free Gemini audio path |
| Separate transcription call then enrich (caption-less template) | Third Gemini call on the most expensive path; breaks the two-call budget |
| Guarantee transcript document *before* enrichment | Would force the third call on caption-less template jobs; delivering at the tail gives uniform ordering for free |
| Append transcript into the `{job_id}_short.md` analysis markdown | Transcript stops being independently addressable (FTS5 / NotebookLM ingest); mixes two concerns in one document |
| Put the transcript in the Short Video Analysis sheet | Bulky/noisy in a cell; transcript already has three homes (DB, Drive, document) |
| Hard-fail the job when no transcript | Vision already succeeded and was delivered; regressing a `done` job to `error` over a genuinely wordless clip is the wrong trade-off |

## Consequences

- Supersedes ADR-0009's note that "`jobs.transcript` stays empty for caption-less Reels... `key_phrases` step is skipped." Caption-less short jobs now persist a transcript and run key-phrase extraction.
- `enrich_audio` gains the transcript text in its return shape; callers updated to persist it.
- Every short job now performs a transcript-service call and (on success) one extra Drive upload + one extra Telegram document. Plain caption-less short jobs go from one Gemini call to two.
- "Regardless of the prompt template" guarantees the transcript *attempt*, not a transcript in 100% of cases — genuinely wordless videos surface `⚠️ I'm wordless`.
