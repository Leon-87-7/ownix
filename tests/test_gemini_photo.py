"""Unit tests for photo-link extraction in src/services/gemini.py — no network calls."""

from __future__ import annotations

import pytest

from src.services.gemini import _domain_for_match, _filter_grounded_links


# ---------------------------------------------------------------------------
# _domain_for_match
# ---------------------------------------------------------------------------


def test_domain_strips_scheme_and_path():
    assert _domain_for_match("https://trustmrr.com/leaderboard") == "trustmrr.com"


def test_domain_strips_www():
    assert _domain_for_match("https://www.trustmrr.com") == "trustmrr.com"


def test_domain_no_scheme():
    assert _domain_for_match("trustmrr.com") == "trustmrr.com"


def test_domain_empty():
    assert _domain_for_match("") == ""


# ---------------------------------------------------------------------------
# _filter_grounded_links — core scenarios
# ---------------------------------------------------------------------------


def _link(url, verbatim=None):
    return {"url": url, "label": "L", "description": "D", "verbatim": verbatim}


def test_keeps_domain_in_verbatim():
    links = [_link("https://trustmrr.com", verbatim="TrustMRR.com")]
    assert [l["url"] for l in _filter_grounded_links(links, "")] == ["https://trustmrr.com"]


def test_drops_brand_only_verbatim():
    """ThreadCan card label with no TLD — must be dropped."""
    links = [_link("https://threadcan.com", verbatim="ThreadCan")]
    assert _filter_grounded_links(links, "") == []


def test_drops_missing_verbatim():
    links = [_link("https://gojiberryai.com")]
    assert _filter_grounded_links(links, "") == []


def test_drops_none_verbatim():
    links = [_link("https://gojiberryai.com", verbatim=None)]
    assert _filter_grounded_links(links, "") == []


def test_drops_no_tld_in_url():
    links = [_link("not-a-url", verbatim="not-a-url")]
    assert _filter_grounded_links(links, "") == []


def test_keeps_domain_in_summary_fallback():
    """Domain not in verbatim but present in summary → kept (summary is model-generated OCR prose)."""
    links = [_link("https://fiddl.art", verbatim="Fiddl.art")]
    result = _filter_grounded_links(links, "The image shows Fiddl.art and other cards.")
    assert [l["url"] for l in result] == ["https://fiddl.art"]


def test_keeps_handle_with_platform_visible():
    """@kirkstencell shown on Instagram → kept only when 'instagram' appears in verbatim."""
    link = _link(
        "https://instagram.com/kirkstencell",
        verbatim="@kirkstencell on instagram",
    )
    assert [l["url"] for l in _filter_grounded_links([link], "")] == [
        "https://instagram.com/kirkstencell"
    ]


def test_drops_handle_without_platform():
    """@kirkstencell with no platform context → drop."""
    link = _link("https://instagram.com/kirkstencell", verbatim="kirkstencell")
    assert _filter_grounded_links([link], "") == []


def test_drops_handle_missing_at():
    """Platform present but no leading @ in verbatim — not a grounded handle."""
    link = _link(
        "https://instagram.com/kirkstencell",
        verbatim="instagram kirkstencell",
    )
    assert _filter_grounded_links([link], "") == []


def test_drops_ui_chrome_followed_by():
    """Domain in a 'Followed by X' phrase → Gemini includes phrase context in verbatim → dropped."""
    link = _link("https://chase.h.ai", verbatim="Followed by chase.h.ai and 1 other")
    assert _filter_grounded_links([link], "") == []


def test_drops_ui_chrome_verbatim():
    """Any verbatim that contains 'followed by' is dropped."""
    link = _link("https://chase.h.ai", verbatim="followed by chase.h.ai")
    assert _filter_grounded_links([link], "") == []


def test_keeps_link_when_chrome_signal_not_in_verbatim():
    """Real promoted link survives even if summary prose happens to mention follower context."""
    link = _link("https://trustmrr.com", verbatim="TrustMRR.com — database of verified startup revenues")
    summary = "TrustMRR.com leaderboard. Followed by chase.h.ai and 1 other."
    result = _filter_grounded_links([link], summary)
    assert [l["url"] for l in result] == ["https://trustmrr.com"]


def test_empty_links():
    assert _filter_grounded_links([], "") == []


# ---------------------------------------------------------------------------
# Full screenshot scenario — the 21-link hallucination that triggered this fix
# ---------------------------------------------------------------------------


_SCREENSHOT_LINKS = [
    # Only real URL visible in the image (TrustMRR.com is rendered as text)
    _link("https://trustmrr.com", verbatim="TrustMRR.com"),
    # Brand name cards — no domain rendered, Gemini appended .com
    _link("https://threadcan.com", verbatim="ThreadCan"),
    _link("https://redactai.com", verbatim="RedactAI"),
    _link("https://sidestack.io", verbatim="Sidestack.io"),  # .io visible → kept
    _link("https://gojiberryai.com", verbatim="GojiberryAI"),
    _link("https://adkit.com", verbatim="AdKit"),
    _link("https://handoff.com", verbatim="Handoff"),
    _link("https://virlo.com", verbatim="Virlo"),
    _link("https://zernio.com", verbatim="Zernio"),
    _link("https://proventools.com", verbatim="ProvenTools"),
    _link("https://atyourservice.com", verbatim="AtYourService"),
    _link("https://replymer.com", verbatim="Replymer"),
    _link("https://makeugc.com", verbatim="MakeUGC"),
    _link("https://trixie.com", verbatim="Trixie"),
    _link("https://rezi.com", verbatim="Rezi"),
    _link("https://kibu.com", verbatim="Kibu"),
    _link("https://cometly.com", verbatim="Cometly"),
    _link("https://1capture.com", verbatim="1Capture"),
    _link("https://chase.h.ai", verbatim="Followed by chase.h.ai and 1 other"),  # UI chrome → dropped
    # Handle without platform in verbatim
    _link("https://instagram.com/kirkstencell", verbatim="kirkstencell"),
    # Fiddl.art — TLD appears in label text
    _link("https://fiddl.art", verbatim="Fiddl.art"),
]

_EXPECTED_KEPT = {
    "https://trustmrr.com",
    "https://sidestack.io",
    "https://fiddl.art",
}


def test_screenshot_hallucination_scenario():
    result = _filter_grounded_links(_SCREENSHOT_LINKS, summary="TrustMRR leaderboard screenshot")
    kept_urls = {l["url"] for l in result}
    assert kept_urls == _EXPECTED_KEPT
