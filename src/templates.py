from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class PromptTemplate:
    name: str
    description: str
    trigger_patterns: List[str]
    extra_instructions: str = ""
    brave_search: bool = False


PROMPT_TEMPLATES: Dict[str, PromptTemplate] = {
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
        trigger_patterns=["how to", "tutorial", "guide", "step by step", "walkthrough"],
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
        trigger_patterns=["coding", "programming", "developer", "engineering", "api", "framework", "architecture"],
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
        trigger_patterns=["review", "unboxing", "versus", "vs ", "comparison", "best", "worth it"],
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
        trigger_patterns=["explained", "story", "why ", "history of", "the truth about", "deep dive"],
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
