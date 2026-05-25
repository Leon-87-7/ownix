---
adr: "0011"
title: Unify all Gemini call paths into one module (reverses the "own loops" scoping)
status: accepted
date: 2026-05-25
amends: "0006"
---

## Context

The free→paid key fallback loop (try free key, then paid key on failure, raise
on total failure) is implemented four separate times:

| Call | Function | Returns / raises on total failure |
| --- | --- | --- |
| text | `GeminiClient.generate` | `GeminiUnavailableError` |
| video Vision | `call_gemini_vision` | `RuntimeError` |
| photo Vision | `call_gemini_photo_links` | `RuntimeError` |
| embeddings | `brain._embed_sync` (sync key loop) | — |

Additional duplication in the same cluster:

- `_extract_json` is byte-identical in the video-vision and photo-vision modules.
- `resolve_tool_urls` — a *text* call — lives in the video-vision module and
  re-implements JSON-fence stripping inline instead of reusing `_extract_json`.

CONTEXT.md's `GeminiClient` glossary entry deliberately scoped the client to
text only: *"Vision and embedding calls are out of scope — they keep their own
loops."* That scoping is the documented source of the four-way duplication.

There is also a latent inconsistency: ADR-0006's Consequences state that total
failure "raises `RuntimeError`," while the text client raises the typed
`GeminiUnavailableError`. The two doc sources disagree, and the code follows
both — text raises the typed error, vision/photo raise `RuntimeError`.

## Decision

Reverse the "own loops" scoping. One `gemini` module owns a single free→paid
fallback loop, one `_call_sync(parts, *, model, schema, config)`, and one
`_extract_json`. Text, video-vision, photo-vision, and embeddings become thin
wrappers that assemble `parts` and pass model + schema; the retry/threading
policy lives behind a small interface.

On total failure, every path raises `GeminiUnavailableError` — the typed
exception becomes canonical, superseding the `RuntimeError` wording. This
**amends ADR-0006's Consequences** accordingly; ADR-0006's free→paid *policy*
is unchanged and is in fact honored by centralizing it in one place.

## Rationale

- **Leverage** — all retry/threading sits behind one interface
  (`generate` / `generate_vision` / `embed`); a key, logging, or backoff change
  touches one function, not four.
- **Locality** — the free→paid policy (ADR-0006) lives in exactly one place.
- **Tests** — the "both keys fail" path needs one test instead of three.
- **Consistency** — one error type (`GeminiUnavailableError`) replaces the
  current `GeminiUnavailableError`/`RuntimeError` split.
- The friction is real (four copies), not theoretical, which is why the
  documented "own loops" decision is worth reopening.

## Consequences

- The CONTEXT.md `GeminiClient` glossary entry must be updated when the refactor
  lands: vision and embeddings no longer "keep their own loops." Until the code
  change merges, CONTEXT.md still describes the pre-reversal state — this ADR is
  the authoritative record of the decision in the interim.
- ADR-0006's Consequences line referencing `RuntimeError` is superseded by this
  ADR: total Gemini failure raises `GeminiUnavailableError` from one place.
- Callers that currently catch `RuntimeError` from vision/photo calls must be
  updated to catch `GeminiUnavailableError` (or its supertype).
- Tracked by issue #39.
