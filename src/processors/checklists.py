"""On-demand "/checklists" command — engineering-recommendation checklist
extracted from a short/long video transcript.

Unlike the Mini-PRD (src/processors/prd.py), this is a single inline Gemini
call with no lock, no queue task, no Drive/Sheets/Brain side effects — see
docs/superpowers/plans/2026-08-11-checklists-command.md.
"""
from __future__ import annotations

from src.config import settings
from src.processors.prd import sample_transcript

CHECKLISTS_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "applicable": {"type": "boolean"},
        "topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "directive": {"type": "string"},
                },
                "required": ["name", "directive"],
            },
        },
    },
    "required": ["applicable", "topics"],
}

_NO_ACTIONABLE_MESSAGE = "No actionable engineering recommendations found in this transcript."


def build_checklists_prompt(job: dict) -> str:
    """Build the Gemini prompt for *job*. Works for both short and long jobs —
    enrichment fields (ai_topic/ai_objective) are included only when present."""
    transcript = sample_transcript(
        job.get("transcript") or "", settings.CHECKLISTS_MAX_TRANSCRIPT_CHARS
    )
    context_lines = [f"Video: {job.get('title', '')}"]
    if job.get("ai_topic"):
        context_lines.append(f"Topic: {job['ai_topic']}")
    if job.get("ai_objective"):
        context_lines.append(f"Objective: {job['ai_objective']}")
    if job.get("summary"):
        context_lines.append(f"Summary: {job['summary']}")
    context = "\n".join(context_lines)

    return (
        "You are a senior software engineer reviewing a video transcript for "
        "concrete, actionable engineering recommendations — the kind of advice "
        "a builder would want to check against their own codebase (e.g. rate "
        "limiting, error handling, observability, compliance, security "
        "practices).\n\n"
        f"{context}\n\n"
        f"Transcript:\n{transcript}\n\n"
        "Extract each distinct actionable recommendation as a checklist topic. "
        "Ignore filler, calls to action, and anything that is not a concrete "
        "engineering/product recommendation. If the transcript has nothing "
        "actionable for a software project, set applicable to false and "
        "return an empty topics list.\n\n"
        "Each topic's directive must be a standalone instruction written for "
        "a coding agent that will act on it directly inside an arbitrary "
        "project — never reference \"the video\" or name a specific project. "
        "Phrase it as: check whether the current project already has this, "
        "present a report, and if it's missing, plan how to implement it.\n\n"
        "Return the result as JSON matching the provided schema."
    )


def build_checklists_markdown(data: dict, *, title: str | None = None) -> str:
    """Render the checklist JSON to markdown. Empty/not-applicable renders a
    short message instead of an empty file."""
    heading = f"# Checklist: {title}" if title else "# Checklist"
    topics = data.get("topics") or []
    if not data.get("applicable") or not topics:
        return f"{heading}\n\n{_NO_ACTIONABLE_MESSAGE}\n"

    lines = [heading, ""]
    for topic in topics:
        name = topic.get("name", "Untitled")
        directive = topic.get("directive", "")
        lines += [f"## {name}", "", directive, ""]
    return "\n".join(lines).rstrip() + "\n"
