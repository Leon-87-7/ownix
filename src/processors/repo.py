"""Repo pipeline processor — full implementation."""
from __future__ import annotations

import asyncio
import json as _json
import re as _re
from datetime import datetime, timezone
from urllib.parse import urlparse

from src import brain, database
from src.config import settings
from src.services import gemini
from src.services.gemini import GeminiUnavailableError
from src.services.github import fetch_repo_bundle
from src.services.sheets import append_repo_row, update_repo_row
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


def _sanitize_filename(owner: str, repo: str, *, job_id: str = "") -> str:
    raw = f"{owner}-{repo}"
    sanitized = _re.sub(r"[^a-zA-Z0-9 \-_.]", "", raw).strip("-").strip()[:80]
    return f"{sanitized}.md" if sanitized else f"{job_id}.md"


def render_repo_markdown(analysis: dict, bundle: dict) -> str:
    owner = bundle.get("owner", "")
    repo = bundle.get("repo", "")
    meta = bundle.get("metadata") or {}
    stars = meta.get("stars", 0)
    forks = meta.get("forks", 0)
    language = meta.get("language") or "Unknown"
    days = _days_ago(meta.get("pushed_at"))
    repo_url = f"https://github.com/{owner}/{repo}"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tagline = analysis.get("tagline", "")
    tech_stack = analysis.get("tech_stack") or []
    for_dev = analysis.get("for_developers") or {}
    for_edu = analysis.get("for_education") or {}

    lines = [
        f"# {owner}/{repo}", "",
        f"> {tagline}", "",
        f"⭐ {stars:,}  🔀 {forks:,}  💻 {language}  📅 {days} days ago", "",
    ]
    if meta.get("archived"):
        lines += ["## ⚠️ Archived — no longer maintained", ""]
    if bundle.get("no_readme"):
        lines += ["## ℹ️ No README detected — analysis is shallower than usual", ""]

    lines += ["## Tech Stack", ""]
    lines += [f"- {t}" for t in tech_stack] or ["_(none)_"]
    lines += ["", "## 🛠 For Developers", "", "### Project Ideas", ""]
    lines += [f"- {i}" for i in (for_dev.get("project_ideas") or [])] or ["_(none)_"]
    lines += ["", "### When to Use", "", for_dev.get("when_to_use", ""), "",
              "### Avoid When", "", for_dev.get("avoid_when", ""), ""]
    lines += ["## 🎓 For Education", "", "### Concepts Taught", ""]
    lines += [f"- {c}" for c in (for_edu.get("concepts_taught") or [])] or ["_(none)_"]
    lines += ["", "### Prerequisites", ""]
    lines += [f"- {p}" for p in (for_edu.get("prerequisites") or [])] or ["_(none)_"]
    lines += ["", "### Curriculum Hooks", ""]
    for hook in (for_edu.get("curriculum_hooks") or []):
        fp = hook.get("file_pointer")
        pointer = f" — `{fp}`" if fp else ""
        lines.append(f"- **{hook.get('concept', '')}**{pointer}")
        lines.append(f"  {hook.get('why', '')}")
    if not (for_edu.get("curriculum_hooks") or []):
        lines.append("_(none)_")

    lines += ["", "---", "", f"🔗 [{repo_url}]({repo_url})", f"_Generated by vig at {timestamp}_"]
    return "\n".join(lines)


async def _brain_ingest_safe(repo_url: str, *, topic: str, source_job_id: str) -> None:
    try:
        await brain.ingest_links([{"url": repo_url}], topic=topic, source_job_id=source_job_id)
        log.info("repo_brain_ingested", url=repo_url)
    except Exception as exc:
        log.warning("repo_brain_ingest_failed", url=repo_url, error=str(exc)[:120])


async def _sheets_append_safe(job_id: str, job: dict, analysis: dict, bundle: dict) -> None:
    try:
        row_idx = await append_repo_row(job, analysis, bundle)
        if row_idx is not None:
            await database.update_job_status(job_id, "done", sheets_row_id=str(row_idx))
    except Exception as exc:
        log.warning("repo_sheets_append_failed", job_id=job_id, error=str(exc)[:120])


async def _sheets_update_safe(row_idx: int, job: dict, analysis: dict, bundle: dict) -> None:
    try:
        await update_repo_row(row_idx, job, analysis, bundle)
    except Exception as exc:
        log.warning("repo_sheets_update_failed", job_id=job.get("id"), error=str(exc)[:120])


def _classify_github_error(exc: Exception) -> str:
    """Map a GitHub API exception to a user-visible message."""
    if isinstance(exc, FileNotFoundError):
        return "Repo not found or private — check the URL."
    status = getattr(getattr(exc, "response", None), "status_code", None)
    headers = getattr(getattr(exc, "response", None), "headers", {}) or {}
    if status == 403 and str(headers.get("X-RateLimit-Remaining", "1")) == "0":
        return "GitHub API limit hit, try again in an hour."
    if status in (401, 403):
        return "GitHub authentication failed — check GITHUB_TOKEN."
    if status == 404:
        return "Repo not found or private — check the URL."
    return "GitHub unavailable, retry."


async def run(job: dict) -> None:
    job_id = job["id"]
    chat_id = job["chat_id"]
    url = job["url"]
    freestyle_prompt = job.get("freestyle_prompt")

    await database.update_job_status(job_id, "processing")
    owner, repo = _parse_owner_repo(url)

    try:
        bundle = await fetch_repo_bundle(owner, repo, settings.GITHUB_TOKEN)
    except Exception as exc:
        log.warning("repo_github_error", job_id=job_id, error=str(exc)[:120])
        await database.update_job_status(job_id, "error", error_msg=str(exc)[:200])
        await send_message(chat_id, f"❌ {_classify_github_error(exc)}")
        return

    flags = {"no_readme": bundle.get("no_readme", False)}
    prompt = _build_repo_prompt(bundle, freestyle_prompt=freestyle_prompt, flags=flags)

    try:
        raw = await gemini.generate(prompt, model="gemini-2.5-flash", schema=REPO_ANALYSIS_SCHEMA)
    except GeminiUnavailableError as exc:
        log.error("repo_gemini_failed", job_id=job_id)
        await database.update_job_status(job_id, "error", error_msg=str(exc)[:200])
        await send_message(chat_id, "❌ Gemini unavailable, try /force later.")
        return

    try:
        analysis = _json.loads(raw)
    except Exception:
        m = _re.search(r"\{[\s\S]*\}", raw)
        try:
            analysis = _json.loads(m.group(0)) if m else {}
        except Exception:
            analysis = {}

    await database.update_job_status(
        job_id, "done",
        template_analysis=_json.dumps(analysis),
        title=f"{owner}/{repo}",
        ai_topic=analysis.get("tagline", ""),
        ai_objective=(analysis.get("for_developers") or {}).get("when_to_use", ""),
        ai_action_points=_json.dumps((analysis.get("for_developers") or {}).get("project_ideas", [])),
        ai_tools=_json.dumps(analysis.get("tech_stack", [])),
    )

    # Warning prefix lines for archived / no-README
    warning_lines: list[str] = []
    meta = bundle.get("metadata") or {}
    if meta.get("archived"):
        warning_lines.append("⚠️ Archived — no longer maintained")
    if bundle.get("no_readme"):
        warning_lines.append("ℹ️ No README detected — analysis is shallower than usual")

    # Document (non-fatal)
    filename = _sanitize_filename(owner, repo, job_id=job_id)
    try:
        await send_document(chat_id, render_repo_markdown(analysis, bundle).encode(), filename)
    except Exception as exc:
        log.warning("repo_doc_send_failed", job_id=job_id, error=str(exc)[:120])

    # Summary + Freestyle button
    prefix = "\n".join(warning_lines) + "\n\n" if warning_lines else ""
    summary = prefix + _format_summary_message(owner, repo, analysis, bundle)
    freestyle_btn = [[{"text": "✍️ Freestyle", "callback_data": f"template_freestyle:{job_id}"}]]
    await send_inline_keyboard(chat_id, summary, freestyle_btn)

    # Sheets — fire-and-forget
    current_job = {"id": job_id, "url": url, "created_at": job.get("created_at", ""), "status": "done"}
    sheets_row_id = job.get("sheets_row_id")
    if sheets_row_id:
        asyncio.create_task(_sheets_update_safe(int(sheets_row_id), current_job, analysis, bundle))
    else:
        asyncio.create_task(_sheets_append_safe(job_id, current_job, analysis, bundle))

    # Brain ingest — fire-and-forget
    asyncio.create_task(_brain_ingest_safe(
        _normalize_repo_url(url), topic=analysis.get("tagline", ""), source_job_id=job_id,
    ))

    log.info("repo_pipeline_done", job_id=job_id, repo=f"{owner}/{repo}")
