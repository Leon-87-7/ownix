from __future__ import annotations

from datetime import datetime, timezone


def build_transcript_markdown(
    title: str,
    channel: str,
    views: str,
    video_id: str,
    url: str,
    transcript: str,
) -> str:
    """Build the Phase 1 raw transcript .md file content."""
    fetched_at = datetime.now(timezone.utc).isoformat()
    return (
        f"# {title or 'Untitled'}\n\n"
        f"**Channel:** {channel or 'Unknown'}\n"
        f"**Views:** {views}\n"
        f"**Video ID:** {video_id}\n"
        f"**URL:** {url}\n"
        f"**Fetched:** {fetched_at}\n"
        f"**Char count:** {len(transcript)}\n\n"
        f"---\n\n"
        f"{transcript}\n"
    )


def _humanize_age(days: int) -> str:
    """Render a day-count as a human-readable 'X ago' string.

    Examples: 0 → "today", 1 → "yesterday", 3 → "3 days ago",
    240 → "8 months ago", 800 → "2 years ago".
    """
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 30:
        return f"{days} days ago"
    if days < 365:
        months = days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


def build_enriched_links_message(links: list[dict]) -> str:
    """Format a mixed list of links, some with GitHub enrichment data.

    Enriched GitHub links (``_enriched=True``) are sorted first by
    stars+forks descending, then all remaining links follow in their
    original relative order.  The Quick Links section mirrors the same
    sorted order.

    Expected extra keys on enriched links: ``_enriched`` (bool),
    ``_stars`` (int), ``_forks`` (int), ``_language`` (str|None),
    ``_days_ago`` (int), ``_gh_description`` (str|None).
    """
    enriched = [lnk for lnk in links if lnk.get("_enriched")]
    others = [lnk for lnk in links if not lnk.get("_enriched")]

    # Sort enriched repos by stars + forks, descending
    enriched.sort(key=lambda lnk: lnk.get("_stars", 0) + lnk.get("_forks", 0), reverse=True)

    sorted_links = enriched + others

    labeled_parts: list[str] = []
    for lnk in sorted_links:
        if lnk.get("_enriched"):
            title = lnk.get("_gh_description") or lnk.get("label") or lnk["url"]
            language = lnk.get("_language") or "N/A"
            meta = (
                f"  ⭐ {lnk['_stars']} | 🔀 {lnk['_forks']}"
                f" | 💻 {language} | 📅 {_humanize_age(lnk['_days_ago'])}"
            )
            labeled_parts.append(f"• {title}\n{meta}\n  🔗 {lnk['url']}")
        else:
            label = lnk.get("label") or lnk["url"]
            description = lnk.get("description") or ""
            labeled_parts.append(f"• {label} — {description}\n  🔗 {lnk['url']}")

    labeled = "\n".join(labeled_parts)
    bare = "\n".join(lnk["url"] for lnk in sorted_links)
    return f"🔗 Links Found:\n{labeled}\n\n---\n\n🔗 Quick Links:\n{bare}"
