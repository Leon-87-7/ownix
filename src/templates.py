from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PromptTemplate:
    name: str
    description: str
    trigger_patterns: list[str]
    extra_instructions: str = ""
    brave_search: bool = False


PROMPT_TEMPLATES: dict[str, PromptTemplate] = {
    "summary": PromptTemplate(
        name="summary",
        description="General content overview (default)",
        trigger_patterns=[],
        extra_instructions="",
        brave_search=False,
    ),
    "method": PromptTemplate(
        name="method",
        description="Extract step-by-step procedural methods",
        trigger_patterns=[
            # routing phrases (title/description)
            "how to", "tutorial", "guide", "step by step", "walkthrough",
            # transcript indicators (formerly TEMPLATE_INDICATORS["method"])
            "step", "first", "next", "then", "click", "navigate", "configure", "open", "select",
        ],
        brave_search=False,
        extra_instructions="""\

### ADDITIONAL EXTRACTION — method template
Append a "template_analysis" key to your JSON with:
{
  "steps": [{"action": "...", "details": "...", "result": "..."}],
  "common_mistakes": "string or empty string",
  "pro_tips": "string or empty string"
}""",
    ),
    "technical": PromptTemplate(
        name="technical",
        description="Extract technical implementation details",
        trigger_patterns=[
            # routing phrases (title/description)
            "coding", "programming", "developer", "engineering", "api", "framework", "architecture",
            # transcript indicators (formerly TEMPLATE_INDICATORS["technical"]; "api" deduped)
            "code", "function", "class", "import", "library", "error", "debug", "install",
        ],
        brave_search=True,
        extra_instructions="""\

### ADDITIONAL EXTRACTION — technical template
Append a "template_analysis" key to your JSON with:
{
  "tech_stack": ["language/framework/tool names"],
  "architecture": "high-level design if described, else empty string",
  "config_notes": "env setup, dependencies, config files",
  "debugging": "issues addressed and solutions shown, else empty string"
}""",
    ),
    "review": PromptTemplate(
        name="review",
        description="Extract product/service review analysis",
        trigger_patterns=[
            # routing phrases (title/description)
            "review", "unboxing", "versus", "vs ", "comparison", "best", "worth it",
            # transcript indicators (formerly TEMPLATE_INDICATORS["review"]; "versus" deduped)
            "recommend", "rating", "pros", "cons", "worth", "price", "quality", "feature",
        ],
        brave_search=True,
        extra_instructions="""\

### ADDITIONAL EXTRACTION — review template
Append a "template_analysis" key to your JSON with:
{
  "features": [{"feature": "...", "description": "...", "rating": "...or empty string"}],
  "pros": ["..."],
  "cons": ["..."],
  "verdict": "final recommendation",
  "price_value": "cost and value assessment if mentioned, else empty string"
}""",
    ),
    "narrative": PromptTemplate(
        name="narrative",
        description="Extract argument structure from essays and explainers",
        trigger_patterns=[
            # routing phrases (title/description)
            "explained", "story", "why ", "history of", "the truth about", "deep dive",
            # transcript indicators (formerly TEMPLATE_INDICATORS["narrative"]; "story" deduped)
            "explain", "why", "because", "history", "reason", "background",
        ],
        brave_search=False,
        extra_instructions="""\

### ADDITIONAL EXTRACTION — narrative template
Append a "template_analysis" key to your JSON with:
{
  "thesis": "central claim or story",
  "supporting_points": ["point with evidence"],
  "key_quotes": ["notable quote"],
  "conclusion": "resolution, final message, call to action"
}""",
    ),
}


def score_template_match(text: str) -> dict[str, int]:
    """Count keyword hits per template, reading the single trigger-pattern table.

    Templates with no keywords (``summary``) are skipped, so the result keys are
    exactly the routable templates. Shared by ``detect_template`` (auto-routing)
    and ``validate_template_choice`` (mismatch warning) — one table, two readers.
    """
    lowered = text.lower()
    return {
        name: sum(lowered.count(kw) for kw in tmpl.trigger_patterns)
        for name, tmpl in PROMPT_TEMPLATES.items()
        if tmpl.trigger_patterns
    }


def validate_template_choice(template: str, transcript: str) -> str | None:
    """Return a warning string on a clear template mismatch, else ``None``.

    Call only for explicit-command jobs. Reads the same keyword table as
    ``detect_template`` so routing and validation can never silently diverge.
    """
    tmpl = PROMPT_TEMPLATES.get(template)
    if tmpl is None or not tmpl.trigger_patterns:
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
