# TypeScript doc-storage + read-aloud app — link research

Context: candidate tools/repos for a new TypeScript web app described as
"a mash of Audible and Dropbox" — document storage plus read-aloud (TTS)
playback. Sourced from the Ownix Second Brain Index on 2026-09-19.

## Storage/backend foundation

- [Supabase](https://supabase.com) — Postgres + Auth + Storage + Realtime + Functions in one; good fit for a Dropbox-style doc store.
- [Neon](https://neon.com) — serverless, branchable Postgres; alternative to Supabase if DB and storage should stay separate.
- [IndexedDB (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API) — client-side storage for offline caching of docs/audio.
- [caamer20/Telegram-Drive](https://github.com/caamer20/Telegram-Drive) — architecture reference for turning a chat backend into unlimited cloud storage (Tauri/Rust/React; not TS-native, but the storage-abstraction pattern is worth studying).

## Read-aloud / TTS

- [fish.audio](https://fish.audio) — TTS + voice cloning API with a Node.js example; most directly usable for the "Audible" half.
- [neuphonic/neutts-air](https://huggingface.co/spaces/neuphonic/neutts-air) — voice-cloning TTS reference/demo.
- [ffmpeg.org](https://www.ffmpeg.org) — audio format conversion/streaming, needed regardless of TTS provider.
- [snapotter.com](https://snapotter.com) — self-hosted file-processing (OCR, transcribe, convert) across PDF/audio/video/image; closest single tool to the actual mash-up.

## TypeScript scaffolding

- [create-better-t-stack](https://github.com/AmanVarshney01/create-better-t-stack) — CLI to scaffold a type-safe TS full stack (frontend/backend/db/auth); good starting skeleton.
- [bun.sh](https://bun.sh) — fast TS/JS runtime + bundler if a lighter stack than Node is preferred.

## Considered and skipped

DJI/RØDE mic pages, a Gmail trick, U-Haul, openculture.com (content site, not a tool),
fallow / componentry / animate-ui / opentui / sandcastle (dev tooling or UI libs, not
core to storage + TTS).
