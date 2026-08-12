---
adr: "0049"
title: Canonical tag tokens and Telegram tagged URL submission
status: accepted
date: 2026-08-12
---

## Context

Ownix already parses `#tag` tokens in its channel-neutral intake router, but Telegram's
legacy URL adapter does not use that path. The original token normalization also erased all
punctuation, making `#readlater`, `#read_later`, and `#read-later` indistinguishable and
preventing names such as `C++`, `R&D`, and `AI/ML` from being addressed losslessly.

## Decision

A tag token is a whitespace/start-anchored `#` followed by any non-whitespace payload.
Underscores encode spaces; all other characters are literal. Canonical comparison is
case-insensitive, collapses display-name whitespace to one underscore, and preserves other
punctuation. Thus `#read_later` selects **Read Later**, `#readlater` selects **Readlater**,
and `#c++` selects **C++**. URL fragments remain safe because their `#` is not anchored by
whitespace or the start of the message.

The same codec governs Telegram, dashboard, extension intake, tag creation/update collision
validation, and `/taglist` presentation. New canonical-token collisions are rejected;
pre-existing collisions remain visible but ambiguous until renamed. Unknown, ambiguous, or
failed tag attachments never block URL processing.

Telegram gains `/tag` as a discoverable alias for tagged URL submission and `/taglist` as a
read-only vocabulary view. Tagged submissions attach **Job tags**, never Link tags; tags are
organizational metadata and do not affect routing or enrichment. Tag-bearing submissions
preserve unrelated pending prompt state, while ordinary untagged commands retain their
existing state behavior. `/force <url> [#tags]` keeps force semantics, adds tags
additively, and works consistently through the shared intake command.

## Consequences

- The earlier punctuation-dropping match rule is intentionally incompatible and has no
  fallback: `#readlater` no longer selects **Read Later**.
- Punctuation at the end of a token is literal; `#c++,` selects **C++,**, not **C++**.
- Telegram hashtag highlighting is presentation only. Ownix parses raw text because Telegram's
  entity grammar is narrower than the Ownix tag vocabulary.
- Existing catalog collisions require human cleanup, but remain readable and are surfaced by
  `/taglist` instead of being silently resolved.
