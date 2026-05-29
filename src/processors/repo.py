"""Repo pipeline processor — full implementation."""
from __future__ import annotations

import asyncio
import json as _json
import re as _re
from datetime import datetime, timezone
from urllib.parse import urlparse

from src import database
from src.config import settings
from src.services import gemini
from src.services.github import fetch_repo_bundle
from src.telegram.sender import send_document, send_inline_keyboard, send_message
from src.utils.logger import get_logger

log = get_logger(__name__)


def _parse_owner_repo(url: str) -> tuple[str, str]:
    parts = [s for s in urlparse(url).path.split("/") if s]
    return parts[0], parts[1]


def _days_ago(pushed_at: str | None) -> int:
    if not pushed_at:
        return 0
    try:
        pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - pushed).days
    except Exception:
        return 0


def _normalize_repo_url(url: str) -> str:
    owner, repo = _parse_owner_repo(url)
    return f"https://github.com/{owner}/{repo}"


def _format_bundle_message(owner: str, repo: str, bundle: dict) -> str:
    meta = bundle.get("metadata") or {}
    stars = meta.get("stars", 0)
    forks = meta.get("forks", 0)
    language = meta.get("language") or "Unknown"
    days = _days_ago(meta.get("pushed_at"))
    readme_bytes = len(bundle.get("readme", ""))
    raw_kb = bundle.get("readme_raw_bytes", 0) / 1024
    tree_count = len(bundle.get("tree", []))
    manifests = bundle.get("manifests") or {}
    manifest_list = ", ".join(sorted(manifests.keys())) if manifests else "none"
    repo_url = f"https://github.com/{owner}/{repo}"

    return (
        f"📦 {owner}/{repo}\n"
        f"⭐ {stars:,} | 🔀 {forks:,} | 💻 {language} | 📅 {days} days ago\n"
        "\n"
        f"📄 README: {readme_bytes} bytes ({raw_kb:.1f} KB raw)\n"
        f"🗂  Tree: {tree_count} files\n"
        f"📦 Manifests: {manifest_list}\n"
        "\n"
        "🚧 Gemini analysis coming soon.\n"
        "\n"
        f"🔗 {repo_url}"
    )


# ---------------------------------------------------------------------------
# Gemini schema + prompt builder (#68)
# ---------------------------------------------------------------------------

REPO_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "tagline": {"type": "string"},
        "tech_stack": {"type": "array", "items": {"type": "string"}},
        "for_developers": {
            "type": "object",
            "properties": {
                "project_ideas": {"type": "array", "items": {"type": "string"}},
                "when_to_use": {"type": "string"},
                "avoid_when": {"type": "string"},
            },
            "required": ["project_ideas", "when_to_use", "avoid_when"],
        },
        "for_education": {
            "type": "object",
            "properties": {
                "concepts_taught": {"type": "array", "items": {"type": "string"}},
                "prerequisites": {"type": "array", "items": {"type": "string"}},
                "curriculum_hooks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "concept": {"type": "string"},
                            "file_pointer": {"type": ["string", "null"]},
                            "why": {"type": "string"},
                        },
                        "required": ["concept", "file_pointer", "why"],
                    },
                },
            },
            "required": ["concepts_taught", "prerequisites", "curriculum_hooks"],
        },
    },
    "required": ["title", "tagline", "tech_stack", "for_developers", "for_education"],
}


def _build_repo_prompt(
    bundle: dict,
    freestyle_prompt: str | None = None,
    flags: dict | None = None,
) -> str:
    owner = bundle.get("owner", "")
    repo = bundle.get("repo", "")
    meta = bundle.get("metadata") or {}
    no_readme = (flags or {}).get("no_readme", bundle.get("no_readme", False))
    tree = bundle.get("tree", [])
    manifests = bundle.get("manifests") or {}
    readme = bundle.get("readme", "")

    system_frame = (
        "You are a technical analyst evaluating open-source repositories for "
        "developer utility and educational value. Be specific, concise, and opinionated."
    )

    meta_block = (
        f"Repository: {owner}/{repo}\n"
        f"Stars: {meta.get('stars', 0):,} | Forks: {meta.get('forks', 0):,} | "
        f"Language: {meta.get('language') or 'Unknown'}\n"
        f"Description: {meta.get('description') or '(none)'}\n"
    )
    if meta.get("archived"):
        meta_block += "⚠️ This repository is ARCHIVED.\n"

    tree_sample = tree[:200]
    tree_block = "File tree:\n" + "\n".join(f"  {p}" for p in tree_sample)

    if manifests:
        manifest_block = "Package manifests:\n" + "\n\n".join(
            f"--- {p} ---\n{c[:2_000]}" for p, c in manifests.items()
        )
    else:
        manifest_block = "Package manifests: (none detected)"

    if no_readme:
        readme_block = (
            "README: (not available — no README in this repository)\n"
            "Instruction: lean on the file tree and manifests for analysis. "
            "Flag in the tagline that no README was found."
        )
    else:
        readme_block = f"README (preprocessed):\n{readme[:10_000]}"

    if freestyle_prompt:
        focus_block = f"User instruction: {freestyle_prompt}\nAnswer using the repository context above."
    else:
        focus_block = (
            "Extract a structured analysis matching the JSON schema. "
            "Be specific about developer use-cases and educational concepts."
        )

    return "\n\n".join([system_frame, meta_block, tree_block, manifest_block, readme_block, focus_block])


def _format_summary_message(owner: str, repo: str, analysis: dict, bundle: dict) -> str:
    meta = bundle.get("metadata") or {}
    stars = meta.get("stars", 0)
    forks = meta.get("forks", 0)
    language = meta.get("language") or "Unknown"
    days = _days_ago(meta.get("pushed_at"))
    tagline = analysis.get("tagline", "")
    repo_url = f"https://github.com/{owner}/{repo}"
    project_ideas = analysis.get("for_developers", {}).get("project_ideas") or []
    first_idea = (project_ideas[0][:80] + "…") if project_ideas else "—"
    concepts = analysis.get("for_education", {}).get("concepts_taught") or []
    hooks = analysis.get("for_education", {}).get("curriculum_hooks") or []
    edu_line = (concepts[0] if concepts else "") + (f" • {hooks[0]['concept']}…" if hooks else "")

    return "\n".join([
        f"📦 {owner}/{repo}",
        tagline,
        "",
        f"⭐ {stars:,} | 🔀 {forks:,} | 💻 {language} | 📅 {days} days ago",
        "",
        "🛠 For developers",
        f"  {first_idea}",
        "",
        "🎓 For teaching",
        f"  {edu_line}",
        "",
        f"🔗 {repo_url}",
    ])


async def run(job: dict) -> None:
    job_id = job["id"]
    chat_id = job["chat_id"]
    url = job["url"]
    freestyle_prompt = job.get("freestyle_prompt")

    await database.update_job_status(job_id, "processing")
    owner, repo = _parse_owner_repo(url)

    bundle = await fetch_repo_bundle(owner, repo, settings.GITHUB_TOKEN)

    flags = {"no_readme": bundle.get("no_readme", False)}
    prompt = _build_repo_prompt(bundle, freestyle_prompt=freestyle_prompt, flags=flags)

    raw = await gemini.generate(prompt, model="gemini-2.5-flash", schema=REPO_ANALYSIS_SCHEMA)
    try:
        analysis = _json.loads(raw)
    except Exception:
        m = _re.search(r"\{[\s\S]*\}", raw)
        analysis = _json.loads(m.group(0)) if m else {}

    await database.update_job_status(
        job_id, "done",
        template_analysis=_json.dumps(analysis),
        title=f"{owner}/{repo}",
        ai_topic=analysis.get("tagline", ""),
        ai_objective=(analysis.get("for_developers") or {}).get("when_to_use", ""),
        ai_action_points=_json.dumps((analysis.get("for_developers") or {}).get("project_ideas", [])),
        ai_tools=_json.dumps(analysis.get("tech_stack", [])),
    )

    # Document delivery — placeholder (Task 8 adds render_repo_markdown)
    try:
        filename = f"{owner}-{repo}.md"
        doc_content = f"# {owner}/{repo}\n\n{analysis.get('tagline', '')}\n"
        await send_document(chat_id, doc_content.encode(), filename)
    except Exception as exc:
        log.warning("repo_doc_send_failed", job_id=job_id, error=str(exc)[:120])

    # Summary + Freestyle button
    summary = _format_summary_message(owner, repo, analysis, bundle)
    freestyle_btn = [[{"text": "✍️ Freestyle", "callback_data": f"freestyle:{job_id}"}]]
    await send_inline_keyboard(chat_id, summary, freestyle_btn)

    log.info("repo_gemini_done", job_id=job_id, repo=f"{owner}/{repo}")
