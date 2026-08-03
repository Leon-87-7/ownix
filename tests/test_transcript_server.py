"""Tests for transcript_server.py — issue #15 (TikTok/Instagram support)."""

from __future__ import annotations

import base64

import pytest
from unittest.mock import MagicMock, patch

from transcript_server import _detect_platform, _download_audio_b64, _parse_vtt, app


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


def test_metadata_preserves_float_duration(client, monkeypatch):
    monkeypatch.setattr("transcript_server.TRANSCRIPT_SERVICE_TOKEN", "")
    monkeypatch.setattr(
        "transcript_server.socket.getaddrinfo",
        lambda *a, **k: [(None, None, None, None, ("8.8.8.8", 0))],
    )
    with patch(
        "transcript_server.yt_dlp.YoutubeDL",
        return_value=_make_ydl_mock({"duration": 19.201}),
    ):
        data = client.get("/metadata?url=https://facebook.com/share/v/123").get_json()

    assert data["duration"] == 19.201
    assert isinstance(data["duration"], float)


def test_metadata_error_has_matching_duration_shape(client, monkeypatch):
    monkeypatch.setattr("transcript_server.TRANSCRIPT_SERVICE_TOKEN", "")
    monkeypatch.setattr(
        "transcript_server.socket.getaddrinfo",
        lambda *a, **k: [(None, None, None, None, ("8.8.8.8", 0))],
    )
    with patch(
        "transcript_server.yt_dlp.YoutubeDL",
        side_effect=RuntimeError("extract failed"),
    ):
        response = client.get("/metadata?url=https://facebook.com/share/v/123")

    assert response.status_code == 200
    assert response.get_json()["duration"] is None


@pytest.mark.parametrize(
    ("extractor", "url", "expected"),
    [
        ("Youtube", "https://youtube.com/shorts/abc", "youtube_shorts"),
        ("TikTok", "https://tiktok.com/@u/video/1", "tiktok"),
        ("Instagram", "https://instagram.com/reel/abc", "instagram_reels"),
        ("Facebook", "https://facebook.com/share/v/1", "facebook"),
        ("Twitter", "https://x.com/u/status/1", "twitter"),
        ("", "https://example.com/video", "unknown"),
    ],
)
def test_detect_platform_preserves_known_names_and_exposes_other_extractors(
    extractor, url, expected
):
    assert _detect_platform(extractor, url) == expected


def test_tiktok_url_returns_transcript(client, tmp_path):
    vtt = tmp_path / "tiktok123.en.vtt"
    vtt.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello TikTok\n", encoding="utf-8")

    with (
        patch("transcript_server.tempfile.mkdtemp", return_value=str(tmp_path)),
        patch(
            "transcript_server.yt_dlp.YoutubeDL", return_value=_make_ydl_mock({"id": "tiktok123"})
        ),
        patch("transcript_server.shutil.rmtree"),
    ):
        resp = client.get("/transcript?url=https://www.tiktok.com/@user/video/1234567890")

    data = resp.get_json()
    assert isinstance(data, list)
    assert data[0]["videoId"] == "tiktok123"
    assert "Hello TikTok" in data[0]["text"]


def test_instagram_reel_url_returns_transcript(client, tmp_path):
    vtt = tmp_path / "igvid123.en.vtt"
    vtt.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello Reels\n", encoding="utf-8")

    with (
        patch("transcript_server.tempfile.mkdtemp", return_value=str(tmp_path)),
        patch(
            "transcript_server.yt_dlp.YoutubeDL", return_value=_make_ydl_mock({"id": "igvid123"})
        ),
        patch("transcript_server.shutil.rmtree"),
    ):
        resp = client.get("/transcript?url=https://www.instagram.com/reel/DVNolBNE6vV/")

    data = resp.get_json()
    assert data[0]["videoId"] == "igvid123"
    assert "Hello Reels" in data[0]["text"]


# ---------------------------------------------------------------------------
# /transcript endpoint — audio fallback (issue #32)
# ---------------------------------------------------------------------------


def test_download_audio_b64_returns_base64_and_mime(tmp_path):
    """Reads the yt-dlp audio file off disk, returns (base64, mime) by extension."""
    (tmp_path / "audio.webm").write_bytes(b"OGGSAUDIO")

    with patch(
        "transcript_server.yt_dlp.YoutubeDL",
        return_value=_make_ydl_mock({"id": "x"}),
    ):
        b64, mime = _download_audio_b64("https://example.com/v", str(tmp_path))

    assert base64.b64decode(b64) == b"OGGSAUDIO"
    assert mime == "audio/webm"


def test_download_audio_b64_raises_when_no_file(tmp_path):
    """yt-dlp produced no audio file → RuntimeError (surfaces as transcription_failed)."""
    with patch(
        "transcript_server.yt_dlp.YoutubeDL",
        return_value=_make_ydl_mock({"id": "x"}),
    ):
        with pytest.raises(RuntimeError):
            _download_audio_b64("https://example.com/v", str(tmp_path))


def test_no_captions_falls_back_to_audio(client, tmp_path):
    """Caption-less non-YouTube video → audio download, returns base64 + fallback marker."""
    # No .vtt files; pre-create the audio file the (mocked) yt-dlp 'downloads'.
    (tmp_path / "audio.m4a").write_bytes(b"\x00\x01FAKEAUDIO")

    with (
        patch("transcript_server.tempfile.mkdtemp", return_value=str(tmp_path)),
        patch("transcript_server.yt_dlp.YoutubeDL", return_value=_make_ydl_mock({"id": "reel123"})),
        patch("transcript_server.shutil.rmtree"),
    ):
        resp = client.get("/transcript?url=https://www.instagram.com/reel/DVNolBNE6vV/")

    data = resp.get_json()
    assert data[0]["fallback"] == "audio"
    assert data[0]["mime_type"] == "audio/mp4"
    assert base64.b64decode(data[0]["audio_b64"]) == b"\x00\x01FAKEAUDIO"


def test_caption_extraction_failure_falls_back_to_audio(client, tmp_path):
    """Outer yt-dlp caption call throws → audio fallback is still attempted."""
    (tmp_path / "audio.m4a").write_bytes(b"\x00\x02FAKEAUDIO")

    caption_mock = _make_ydl_mock({"id": "reel_fail"})
    caption_mock.extract_info.side_effect = [RuntimeError("yt-dlp caption error"), None]

    with (
        patch("transcript_server.tempfile.mkdtemp", return_value=str(tmp_path)),
        patch("transcript_server.yt_dlp.YoutubeDL", return_value=caption_mock),
        patch("transcript_server.shutil.rmtree"),
    ):
        resp = client.get("/transcript?url=https://www.instagram.com/reel/DVNolBNE6vV/")

    data = resp.get_json()
    assert data[0]["fallback"] == "audio"
    assert data[0]["mime_type"] == "audio/mp4"
    assert base64.b64decode(data[0]["audio_b64"]) == b"\x00\x02FAKEAUDIO"


def test_audio_download_failure_returns_transcription_failed(client, tmp_path):
    """No captions and no audio file produced → transcription_failed error."""
    with (
        patch("transcript_server.tempfile.mkdtemp", return_value=str(tmp_path)),
        patch("transcript_server.yt_dlp.YoutubeDL", return_value=_make_ydl_mock({"id": "reel404"})),
        patch("transcript_server.shutil.rmtree"),
    ):
        resp = client.get("/transcript?url=https://www.tiktok.com/@user/video/9999999999")

    data = resp.get_json()
    assert data[0]["error"]["type"] == "transcription_failed"


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


def test_transcript_rejects_missing_internal_token(client, monkeypatch):
    monkeypatch.setattr("transcript_server.TRANSCRIPT_SERVICE_TOKEN", "secret")
    resp = client.get("/metadata?url=https://www.youtube.com/watch?v=abc123")
    assert resp.status_code == 401


def test_transcript_rejects_private_resolved_url(client, monkeypatch):
    monkeypatch.setattr("transcript_server.TRANSCRIPT_SERVICE_TOKEN", "")
    monkeypatch.setattr(
        "transcript_server.socket.getaddrinfo",
        lambda *a, **k: [(None, None, None, None, ("127.0.0.1", 0))],
    )
    resp = client.get("/metadata?url=https://example.com/video")
    assert resp.status_code == 400
    assert resp.get_json()["error"]["type"] == "invalid_url"


def test_short_frames_rejects_out_of_range_params(client, monkeypatch):
    monkeypatch.setattr("transcript_server.TRANSCRIPT_SERVICE_TOKEN", "")
    monkeypatch.setattr(
        "transcript_server.socket.getaddrinfo",
        lambda *a, **k: [(None, None, None, None, ("8.8.8.8", 0))],
    )
    resp = client.get("/short_frames?url=https://example.com/video&max_frames=9999")
    assert resp.status_code == 400
