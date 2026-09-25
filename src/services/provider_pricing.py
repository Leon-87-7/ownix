"""Versioned Gemini price catalog + conservative pre-call cost estimation
(handoff §2). A reservation is taken *before* a paid call using an estimate
computed here from validated, already-capped input sizes; a settled charge
uses the provider's own token usage when the response reports it, else falls
back to the same estimate.

Prices are USD micros per 1,000,000 tokens (never `REAL`). Never hardcode a
price at the migration/database layer — this module is the one place prices
live, so they can be corrected without touching the ledger schema.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.utils.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class Price:
    input_per_million_micros: int
    output_per_million_micros: int


# ponytail: representative Gemini 2.5 pricing at time of writing (USD micros
# per 1M tokens) — verify against ai.google.dev/pricing before enabling paid
# fallback for real spend; this is a starting catalog, not a live price feed.
GEMINI_PRICES: dict[str, Price] = {
    "gemini-2.5-flash": Price(input_per_million_micros=300_000, output_per_million_micros=2_500_000),
    "gemini-2.5-flash-lite": Price(input_per_million_micros=100_000, output_per_million_micros=400_000),
    "gemini-2.5-pro": Price(input_per_million_micros=1_250_000, output_per_million_micros=10_000_000),
    "gemini-embedding-001": Price(input_per_million_micros=150_000, output_per_million_micros=0),
}
_DEFAULT_PRICE = GEMINI_PRICES["gemini-2.5-flash"]

#: Rough chars-per-token heuristic for English-ish text/code/JSON — ceil-divided,
#: so it over-, never under-, estimates input tokens.
_CHARS_PER_TOKEN = 4
#: Gemini's documented flat per-image token cost (<=384px tile, 1 tile/image
#: for the frame sizes this app sends).
_IMAGE_TOKEN_EQUIVALENT = 258

#: Conservative output envelope for the app's bounded-JSON Gemini calls
#: (title/summary/links objects) — actual output is almost always far smaller.
DEFAULT_MAX_OUTPUT_TOKENS = 2048
#: Free-text generate() envelope — high enough that output (incl. 2.5-pro's
#: mandatory thinking) is never cut off, and reserved in full so the paid
#: spending limit can't be overshot.
TEXT_MAX_OUTPUT_TOKENS = 32768


def _price_for(model: str) -> Price:
    price = GEMINI_PRICES.get(model)
    if price is None:
        log.warning("provider_pricing.unknown_model", model=model)
        return _DEFAULT_PRICE
    return price


def _micros(tokens: int, per_million_micros: int) -> int:
    return (tokens * per_million_micros) // 1_000_000


def estimate_text_micros(
    *, model: str, input_chars: int, max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
) -> int:
    price = _price_for(model)
    input_tokens = max(1, -(-input_chars // _CHARS_PER_TOKEN))
    return _micros(input_tokens, price.input_per_million_micros) + _micros(
        max_output_tokens, price.output_per_million_micros
    )


def estimate_vision_micros(
    *, model: str, image_count: int, max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
) -> int:
    price = _price_for(model)
    input_tokens = max(1, image_count) * _IMAGE_TOKEN_EQUIVALENT
    return _micros(input_tokens, price.input_per_million_micros) + _micros(
        max_output_tokens, price.output_per_million_micros
    )


def estimate_embedding_micros(*, model: str, input_chars: int) -> int:
    price = _price_for(model)
    input_tokens = max(1, -(-input_chars // _CHARS_PER_TOKEN))
    return _micros(input_tokens, price.input_per_million_micros)


#: Rough proxy for audio input cost: Gemini prices audio around 32 tokens/sec;
#: assuming ~16kbps compressed voice/video audio gives an approximate
#: bytes→token ratio from the base64 payload size alone, with no need to
#: decode or probe actual duration.
#: ponytail: an approximation, not a duration probe — tighten (decode and use
#: real duration) if audio ever becomes the dominant paid-call cost driver.
_AUDIO_TOKENS_PER_RAW_BYTE = 0.016
_AUDIO_DEFAULT_MAX_OUTPUT_TOKENS = 8192  # transcript output can run long
#: Gemini 2.5 Flash prices audio input separately from its text/image/video
#: rate (`Price.input_per_million_micros`) — $1.00/1M tokens vs. $0.30/1M.
_AUDIO_INPUT_PER_MILLION_MICROS = 1_000_000


def estimate_audio_micros(
    *, model: str, audio_b64_len: int, max_output_tokens: int = _AUDIO_DEFAULT_MAX_OUTPUT_TOKENS
) -> int:
    price = _price_for(model)
    raw_bytes = audio_b64_len * 3 // 4
    input_tokens = max(1, int(raw_bytes * _AUDIO_TOKENS_PER_RAW_BYTE))
    return _micros(input_tokens, _AUDIO_INPUT_PER_MILLION_MICROS) + _micros(
        max_output_tokens, price.output_per_million_micros
    )


def actual_text_micros(*, model: str, prompt_tokens: int, output_tokens: int) -> int:
    """Real cost from the provider's own reported token usage."""
    price = _price_for(model)
    return _micros(prompt_tokens, price.input_per_million_micros) + _micros(
        output_tokens, price.output_per_million_micros
    )


def actual_micros_from_response(model: str, response: object, *, fallback_micros: int) -> int:
    """Prefer the provider's own `usage_metadata` token counts; fall back to
    the pre-call estimate when the response doesn't report usage (e.g.
    embeddings) — per handoff §2, "settle the conservative estimate unless
    provider usage proves a smaller value"."""
    usage = getattr(response, "usage_metadata", None)
    prompt_tokens = getattr(usage, "prompt_token_count", None) if usage is not None else None
    output_tokens = getattr(usage, "candidates_token_count", None) if usage is not None else None
    if prompt_tokens is None or output_tokens is None:
        return fallback_micros
    # Billed the same as regular output tokens, but reported separately from
    # candidates_token_count whenever thinking is enabled — omitting them
    # would settle for less than the provider actually charged.
    thinking_tokens = getattr(usage, "thoughts_token_count", None) or 0
    return actual_text_micros(
        model=model, prompt_tokens=prompt_tokens, output_tokens=output_tokens + thinking_tokens
    )
