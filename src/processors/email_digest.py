"""Newsletter email digest processor."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from src import database
from src.services import gemini
from src.services.gemini import GeminiUnavailableError
from src.utils.logger import get_logger
from src.utils.og_image import extract_essential_og
from src.utils.public_html import fetch_public_html, resolve_public_redirect_url

log = get_logger(__name__)

_MAX_LINKS_PER_ISSUE = 50
_PROMPT_BODY_LIMIT = 20_000
_TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "_ga"}
_VIEW_ONLINE_TEXT = ("view online", "view in browser", "read online", "web version")
_UNSUBSCRIBE_MARKERS = (
    "unsubscribe",
    "manage preferences",
    "manage-preferences",
    "email preferences",
    "subscription preferences",
)


@dataclass(frozen=True)
class DigestLink:
    href: str
    text: str


class _DigestLinkParser(HTMLParser):
    """Small <a href> extractor, mirroring the stdlib parser shape used for bookmarks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[DigestLink] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a" or self._href is not None:
            return
        attr_map = {name.lower(): (value or "").strip() for name, value in attrs}
        href = attr_map.get("href")
        if href:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._href is None:
            return
        text = " ".join("".join(self._text).split())
        self.links.append(DigestLink(self._href, text))
        self._href = None
        self._text = []


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def extract_digest_links(html: str) -> list[DigestLink]:
    parser = _DigestLinkParser()
    parser.feed(html or "")
    return parser.links


def strip_html_text(html: str) -> str:
    parser = _TextParser()
    parser.feed(html or "")
    return "\n".join(parser.parts)


def canonicalize_candidate_url(url: str) -> str:
    parts = urlsplit(url)
    kept = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in _TRACKING_PARAMS:
            continue
        kept.append((key, value))
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path,
            urlencode(kept, doseq=True),
            parts.fragment,
        )
    )


def _normalized_href(href: str) -> str | None:
    value = href.strip()
    if value.startswith("//"):
        value = f"https:{value}"
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    return value


def _is_unsubscribe(link: DigestLink) -> bool:
    haystack = f"{link.text} {link.href}".lower()
    return any(marker in haystack for marker in _UNSUBSCRIBE_MARKERS)


def _is_view_online(link: DigestLink) -> bool:
    text = link.text.lower()
    return any(marker in text for marker in _VIEW_ONLINE_TEXT)


def _is_pixel_like_url(url: str) -> bool:
    parts = urlsplit(url)
    lowered = f"{parts.netloc}{parts.path}".lower()
    if lowered.endswith((".gif", ".png", ".jpg", ".jpeg", ".webp", ".avif")):
        return True
    return "1x1" in lowered or "pixel" in lowered


async def _resolve_links(
    links: list[DigestLink],
    *,
    client: httpx.AsyncClient,
) -> list[DigestLink]:
    resolved: list[DigestLink] = []
    seen: set[str] = set()
    for link in links[:_MAX_LINKS_PER_ISSUE]:
        href = _normalized_href(link.href)
        if href is None:
            continue
        try:
            final_url = await resolve_public_redirect_url(href, client=client)
        except Exception as exc:
            log.info("email_digest.resolve_failed", url=href[:200], error=str(exc)[:120])
            continue
        if not final_url or _is_pixel_like_url(final_url):
            continue
        candidate = DigestLink(final_url, link.text)
        if _is_unsubscribe(candidate):
            continue
        canonical = canonicalize_candidate_url(final_url)
        if canonical in seen:
            continue
        seen.add(canonical)
        resolved.append(candidate)
        if len(resolved) >= _MAX_LINKS_PER_ISSUE:
            break
    return resolved


async def _extract_resolved_links(html: str, *, client: httpx.AsyncClient) -> list[DigestLink]:
    links = extract_digest_links(html)
    content_links: list[DigestLink] = []
    view_online_links: list[DigestLink] = []
    for link in links:
        if _is_unsubscribe(link):
            continue
        if _is_view_online(link):
            view_online_links.append(link)
            continue
        content_links.append(link)

    resolved = await _resolve_links(content_links, client=client)
    if resolved:
        return resolved

    for view_link in view_online_links:
        href = _normalized_href(view_link.href)
        if href is None:
            continue
        landing = await fetch_public_html(href, client=client)
        if landing is None:
            continue
        fallback_links = [
            link
            for link in extract_digest_links(landing.html)
            if not _is_unsubscribe(link) and not _is_view_online(link)
        ]
        resolved = await _resolve_links(fallback_links, client=client)
        if resolved:
            return resolved
    return []


async def _fetch_candidate_preview(
    url: str,
    *,
    fallback_title: str | None,
    client: httpx.AsyncClient,
) -> tuple[str | None, str | None]:
    try:
        result = await fetch_public_html(url, client=client)
    except Exception as exc:
        log.info("email_digest.og_fetch_failed", url=url[:200], error=str(exc)[:120])
        return fallback_title, None
    if result is None:
        return fallback_title, None
    tags = extract_essential_og(result.html, result.final_url)
    return tags.get("og:title") or fallback_title, tags.get("og:image")


async def _insert_candidates(space_id: str, links: list[DigestLink], client: httpx.AsyncClient) -> int:
    inserted = 0
    for link in links[:_MAX_LINKS_PER_ISSUE]:
        try:
            candidate_id = await database.insert_digest_candidate(
                space_id=space_id,
                url=link.href,
                canonical_url=canonicalize_candidate_url(link.href),
                title=link.text or None,
            )
            if candidate_id is None:
                continue
            inserted += 1
            title, thumbnail_url = await _fetch_candidate_preview(
                link.href,
                fallback_title=link.text or None,
                client=client,
            )
            if title or thumbnail_url:
                await database.update_digest_candidate_preview(
                    candidate_id=candidate_id,
                    title=title,
                    thumbnail_url=thumbnail_url,
                )
        except Exception as exc:
            log.info("email_digest.candidate_failed", url=link.href[:200], error=str(exc)[:120])
    return inserted


def _build_context_prompt(subject: str, body_text: str) -> str:
    body = body_text[:_PROMPT_BODY_LIMIT]
    return (
        "Write a short editorial context note for this newsletter issue. "
        "Focus on the issue's themes, why it may matter, and what kinds of links "
        "the operator should evaluate. Return Markdown only, 2-4 concise paragraphs.\n\n"
        f"Subject: {subject or 'Untitled'}\n\nNewsletter text:\n{body}"
    )


async def _create_context_blob(space_id: str, subject: str, text: str, html: str) -> None:
    body_text = text.strip() or strip_html_text(html)
    if not body_text:
        return
    try:
        content = await gemini.generate(
            _build_context_prompt(subject, body_text),
            model="gemini-2.5-flash",
        )
    except GeminiUnavailableError:
        log.info("email_digest.context_gemini_unavailable", space_id=space_id)
        return
    except Exception as exc:
        log.info("email_digest.context_failed", space_id=space_id, error=str(exc)[:120])
        return
    if content.strip():
        name = (subject or "Digest context").strip()[:200]
        await database.create_context_blob(space_id=space_id, name=name, content=content.strip())


async def run(job: dict) -> None:
    job_id = job["id"]
    claimed = await database.claim_email_digest_job(job_id)
    if not claimed:
        log.info("email_digest.claim_skipped", job_id=job_id)
        return

    payload = await database.get_email_digest_payload(job_id)
    if payload is None:
        raise RuntimeError("email digest payload missing")
    if payload.get("space_id") is None:
        await database.clear_email_digest_payload(job_id)
        await database.update_job_status(job_id, "done")
        return

    subject = payload.get("subject") or ""
    html = payload.get("html") or ""
    text = payload.get("text") or ""
    if not html and not text:
        await database.update_job_status(job_id, "error", error_msg="Email digest payload is empty")
        return

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(5.0),
        follow_redirects=False,
        headers={"User-Agent": "vig-public-html/1.0 (+https://github.com/Leon-87-7/vig)"},
    ) as client:
        links = await _extract_resolved_links(html, client=client)
        await _insert_candidates(payload["space_id"], links, client)
    await _create_context_blob(payload["space_id"], subject, text, html)
    await database.clear_email_digest_payload(job_id)
    await database.update_job_status(job_id, "done")
    log.info("email_digest.done", job_id=job_id, candidates=len(links))
