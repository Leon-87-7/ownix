"""Pure space-export composer (issue #95 / S8).

compose_space_export is I/O-free and deterministic — safe to unit-test
with fixtures and reuse as a future NotebookLM-push payload.

Expected structure of each ``job`` dict in the *jobs* list:
  id, title, url, content_type
  ai_topic, ai_objective, ai_action_points, ai_tools
  promise_gap, template_analysis
  notes       (from job_annotations; empty string if absent)
  tags        (list[dict] with id, name, meaning for tags applied to this job)
"""
from __future__ import annotations


def compose_space_export(
    space: dict,
    blobs: list[dict],
    jobs: list[dict],
    tags: list[dict],
) -> str:
    """Return the full export markdown for *space*.

    Args:
        space:  Space row dict (name, color, …).
        blobs:  Context blob rows ordered by sort_order.
        jobs:   Job rows (with enrichment fields, notes, and a ``tags`` list).
        tags:   Full tag catalog — filtered to used tags only inside.
    """
    lines: list[str] = []

    # 1. Space heading
    lines.append(f"# {space['name']}")
    lines.append("")

    # 2. Context blobs (in sort_order)
    for blob in blobs:
        if blob.get("name"):
            lines.append(f"## {blob['name']}")
            lines.append("")
        content = (blob.get("content") or "").strip()
        if content:
            lines.append(content)
            lines.append("")

    # 3. Tag legend — only tags actually used by jobs in this space
    used_tag_ids: set[str] = set()
    for job in jobs:
        for jt in job.get("tags") or []:
            used_tag_ids.add(jt["id"])

    used_tags = [t for t in tags if t["id"] in used_tag_ids]
    if used_tags:
        lines.append("## Tag legend")
        lines.append("")
        for tag in sorted(used_tags, key=lambda t: t["name"]):
            meaning = tag.get("meaning") or ""
            lines.append(f"Name: {tag['name']} meaning: {meaning}")
        lines.append("")

    # 4. Sources — one block per job
    if jobs:
        lines.append("## Sources")
        lines.append("")

    for job in jobs:
        title = (job.get("title") or "").strip() or job.get("url", "")
        job_tags = job.get("tags") or []
        tag_label = ", ".join(t["name"] for t in job_tags) if job_tags else ""
        heading = f"### {title}"
        if tag_label:
            heading += f"  [tags: {tag_label}]"
        lines.append(heading)
        lines.append("")
        lines.append(job.get("url", ""))
        lines.append("")

        _field(lines, "Topic", job.get("ai_topic"))
        _field(lines, "Objective", job.get("ai_objective"))
        _field(lines, "Action points", job.get("ai_action_points"))
        _field(lines, "Tools", job.get("ai_tools"))
        _field(lines, "Promise gap", job.get("promise_gap"))
        _field(lines, "Template analysis", job.get("template_analysis"))

        notes = (job.get("notes") or "").strip()
        lines.append(f"**My notes:** {notes}" if notes else "**My notes:**")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _field(lines: list[str], label: str, value: str | None) -> None:
    if value and value.strip():
        lines.append(f"**{label}:** {value.strip()}")
        lines.append("")
