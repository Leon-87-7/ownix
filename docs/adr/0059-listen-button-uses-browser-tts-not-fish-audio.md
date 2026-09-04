# Listen button uses browser `speechSynthesis`, not Fish.Audio

**Status:** accepted

## Context

The [[Listen button]] feature (job-detail enrichment fields + Space context blob) was
originally scoped around Fish.Audio's TTS API, which was the whole reason the feature
came up — it offers natural AI voices with inline emotion/effect tags
(`[laugh]`, `[excited]`, etc.) at a free tier (`s2.1-pro-free`).

Two things closed that path off for v1:

1. v1 was locked to **flat, neutral narration** — no emotion/effect tags — so Fish.Audio's
   actual differentiator (expressive AI voice + emotion control) isn't exercised yet.
2. Fish.Audio's concurrency limit is tiered by **prepaid spend**: accounts under $100
   spent (which includes any account using only the free model) get **5 concurrent
   requests, platform-wide**, on whatever single API key Ownix holds. Calling it would
   also require a new `src/services/fish_audio.py` + dashboard endpoint to keep the key
   server-side (every other external API in this codebase — Gemini, Drive, GitHub, Jina,
   Brave — follows that shape; none are called directly from the browser).

With no emotion tags in scope, none of that backend/quota engineering buys anything yet.

## Decision

v1 uses the browser-native **Web Speech API** (`speechSynthesis` +
`SpeechSynthesisUtterance`) client-side. Zero backend, zero API key, zero server-side
quota, zero cost — though only one browser utterance can play at a time regardless
(`useSpeech` cancels the queue before speaking, so a second click interrupts rather
than queuing). Voice quality is generic/OS-dependent instead of Fish.Audio's AI voice.

## Consequences

Fish.Audio (or self-hosted `fish-speech`) remains the named upgrade path if/when emotion
tags come into scope for this feature — that decision should re-open the backend-service
question (see the concurrency/key-exposure reasoning above) rather than reusing v1's
client-only shape.
