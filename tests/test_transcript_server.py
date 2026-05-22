"""Tests for transcript_server.py — issue #15 (TikTok/Instagram support)."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from transcript_server import _parse_vtt, app


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# _parse_vtt
# ---------------------------------------------------------------------------

def test_parse_vtt_strips_headers_timestamps_and_tags(tmp_path):
    vtt = tmp_path / "test.vtt"
    vtt.write_text(
        "WEBVTT\n"
        "Kind: captions\n"
        "Language: en\n"
        "\n"
        "00:00:01.000 --> 00:00:03.000\n"
        "Hello <c>world</c>\n"
        "\n"
        "00:00:03.000 --> 00:00:05.000\n"
        "How are you\n",
        encoding="utf-8",
    )
    assert _parse_vtt(str(vtt)) == "Hello world How are you"


def test_parse_vtt_deduplicates_consecutive_repeated_lines(tmp_path):
    vtt = tmp_path / "test.vtt"
    vtt.write_text(
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:02.000\nHello\n\n"
        "00:00:02.000 --> 00:00:03.000\nHello\n\n"
        "00:00:03.000 --> 00:00:04.000\nworld\n",
        encoding="utf-8",
    )
    assert _parse_vtt(str(vtt)) == "Hello world"


# ---------------------------------------------------------------------------
# /transcript endpoint — yt-dlp fallback path
# ---------------------------------------------------------------------------

def _make_ydl_mock(info: dict) -> MagicMock:
    m = MagicMock()
    m.__enter__ = MagicMock(return_value=m)
    m.__exit__ = MagicMock(return_value=False)
    m.extract_info.return_value = info
    return m


def test_tiktok_url_returns_transcript(client, tmp_path):
    vtt = tmp_path / "tiktok123.en.vtt"
    vtt.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello TikTok\n", encoding="utf-8")

    with patch("transcript_server.tempfile.mkdtemp", return_value=str(tmp_path)), \
         patch("transcript_server.yt_dlp.YoutubeDL", return_value=_make_ydl_mock({"id": "tiktok123"})), \
         patch("transcript_server.shutil.rmtree"):
        resp = client.get("/transcript?url=https://www.tiktok.com/@user/video/1234567890")

    data = resp.get_json()
    assert isinstance(data, list)
    assert data[0]["videoId"] == "tiktok123"
    assert "Hello TikTok" in data[0]["text"]


def test_instagram_reel_url_returns_transcript(client, tmp_path):
    vtt = tmp_path / "igvid123.en.vtt"
    vtt.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello Reels\n", encoding="utf-8")

    with patch("transcript_server.tempfile.mkdtemp", return_value=str(tmp_path)), \
         patch("transcript_server.yt_dlp.YoutubeDL", return_value=_make_ydl_mock({"id": "igvid123"})), \
         patch("transcript_server.shutil.rmtree"):
        resp = client.get("/transcript?url=https://www.instagram.com/reel/DVNolBNE6vV/")

    data = resp.get_json()
    assert data[0]["videoId"] == "igvid123"
    assert "Hello Reels" in data[0]["text"]


def test_no_captions_returns_no_transcript_error(client, tmp_path):
    with patch("transcript_server.tempfile.mkdtemp", return_value=str(tmp_path)), \
         patch("transcript_server.yt_dlp.YoutubeDL", return_value=_make_ydl_mock({"id": "musiconly"})), \
         patch("transcript_server.shutil.rmtree"):
        resp = client.get("/transcript?url=https://www.tiktok.com/@user/video/9999999999")

    data = resp.get_json()
    assert data[0]["error"]["type"] == "no_transcript"


# ---------------------------------------------------------------------------
# /transcript endpoint — YouTube path (regression)
# ---------------------------------------------------------------------------

def test_youtube_url_uses_youtube_transcript_api(client):
    snippet = MagicMock()
    snippet.text = "hello youtube"
    mock_ytt = MagicMock()
    mock_ytt.fetch.return_value = [snippet]

    with patch("transcript_server.YouTubeTranscriptApi", return_value=mock_ytt):
        resp = client.get("/transcript?url=https://www.youtube.com/watch?v=abc123")

    data = resp.get_json()
    assert data[0]["videoId"] == "abc123"
    assert data[0]["text"] == "hello youtube"
