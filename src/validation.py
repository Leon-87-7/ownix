from __future__ import annotations

from typing import Optional

TEMPLATE_INDICATORS = {
    "method":    ["step", "first", "next", "then", "click", "navigate", "configure", "open", "select"],
    "technical": ["code", "function", "class", "import", "api", "library", "error", "debug", "install"],
    "review":    ["recommend", "rating", "pros", "cons", "worth", "price", "quality", "feature", "versus"],
    "narrative": ["story", "explain", "why", "because", "history", "reason", "background"],
}


def score_template_match(transcript: str) -> dict[str, int]:
    text = transcript.lower()
    return {
        name: sum(text.count(kw) for kw in keywords)
        for name, keywords in TEMPLATE_INDICATORS.items()
    }


def validate_template_choice(template: str, transcript: str) -> Optional[str]:
    """Return warning string on clear mismatch, else None. Call only for explicit-command jobs."""
    if template not in TEMPLATE_INDICATORS:
        return None
    scores = score_template_match(transcript)
    chosen_score = scores.get(template, 0)
    best = max(scores, key=scores.get)
    best_score = scores[best]
    if chosen_score < 5 and best_score > 15 and best_score > chosen_score * 3:
        return (
            f"Template mismatch detected. This video looks more like "
            f"**{best}** than **{template}**. "
            f"Results may be suboptimal — retry with `/{best} <url>` if needed."
        )
    return None
