#!/usr/bin/env python3
"""
Local YouTube Transcript Server
Replaces Apify node in n8n workflow.

Setup:
    pip install youtube-transcript-api flask yt-dlp waitress

Run:
    python transcript_server.py

n8n HTTP Request node config:
    Method: GET
    URL: http://10.0.0.4:5151/transcript
    Query param: url = {{ $json.url }}
"""

from flask import Flask, request, jsonify
from urllib.parse import urlparse
import ipaddress
import socket
from youtube_transcript_api import YouTubeTranscriptApi
from waitress import serve
import yt_dlp
import re
import os
import subprocess
import tempfile
import base64
import shutil
from PIL import Image
import io

INSTAGRAM_COOKIES = os.environ.get(
    "INSTAGRAM_COOKIES",
    r"C:\\Users\\leone\\Desktop\\codeKitchen\\vig\\credentials\\instagram_cookies.txt",
)
INSTAGRAM_MAX_SLIDES = 10

TRANSCRIPT_SERVICE_TOKEN = os.environ.get("TRANSCRIPT_SERVICE_TOKEN", "")
_INTERNAL_TOKEN_HEADER = "X-Ownix-Internal-Token"
_MAX_URL_LENGTH = 2048


def _auth_failed():
    expected = TRANSCRIPT_SERVICE_TOKEN
    if not expected:
        return False
    return request.headers.get(_INTERNAL_TOKEN_HEADER, "") != expected


def _reject(error_type: str, message: str, status: int = 400):
    return jsonify({"error": {"type": error_type, "message": message}}), status


def _validate_public_http_url(url: str):
    if len(url) > _MAX_URL_LENGTH:
        return "URL too long"
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "URL must be http(s) with a host"
    try:
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(3.0)
        try:
            infos = socket.getaddrinfo(parsed.hostname, None, type=socket.SOCK_STREAM)
        finally:
            socket.setdefaulttimeout(old_timeout)
    except (socket.gaierror, socket.timeout):
        return "URL host could not be resolved"
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            return "URL host resolves to a non-public address"
    return None


def _validate_request_url():
    if _auth_failed():
        return None, _reject("unauthorized", "Unauthorized", 401)
    url = request.args.get("url")
    if not url:
        return None, _reject("missing_url", "No URL provided", 400)
    error = _validate_public_http_url(url)
    if error:
        return None, _reject("invalid_url", error, 400)
    return url, None


def _bounded_float(name: str, default: float, minimum: float, maximum: float):
    raw = request.args.get(name, default)
    if isinstance(raw, str) and raw.strip().lower() in ("nan", "+nan", "-nan"):
        raise ValueError(f"{name} must be a number")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number") from None
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _bounded_int(name: str, default: int, minimum: int, maximum: int):
    raw = request.args.get(name, default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an integer") from None
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _with_cookies(ydl_opts: dict, tmp_dir: str) -> dict:
    """Add a writable cookiefile to ydl_opts if INSTAGRAM_COOKIES is configured.

    yt-dlp rewrites the cookiefile, and credentials/ is read-only, so copy to tmp.
    """
    if INSTAGRAM_COOKIES and os.path.exists(INSTAGRAM_COOKIES):
        tmp_cookies = os.path.join(tmp_dir, "cookies.txt")
        shutil.copy2(INSTAGRAM_COOKIES, tmp_cookies)
        ydl_opts["cookiefile"] = tmp_cookies
    return ydl_opts


app = Flask(__name__)


def extract_video_id(url):
    patterns = [
        r"[?&]v=([^&]+)",
        r"youtu\.be/([^?&]+)",
        r"youtube\.com/embed/([^?&]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_primary_media_info(info):
    entries = info.get("entries")
    if entries and isinstance(entries, list) and entries:
        first = entries[0]
        if isinstance(first, dict):
            return first
    return info


def _parse_vtt(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    text_lines = []
    for line in content.splitlines():
        s = line.strip()
        if (
            not s
            or s.startswith("WEBVTT")
            or s.startswith("NOTE")
            or s.startswith("Kind:")
            or s.startswith("Language:")
            or re.match(r"^\d{2}:\d{2}[\d:,.]+\s+-->\s+", s)
        ):
            continue
        cleaned = re.sub(r"<[^>]+>", "", s)
        if cleaned:
            text_lines.append(cleaned)
    # Auto-captions repeat lines aggressively — deduplicate consecutive dupes
    deduped: list[str] = []
    for line in text_lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)
    return " ".join(deduped)


def _download_audio_b64(url: str, tmp_dir: str) -> tuple[str, str]:
    """Download audio-only via yt-dlp, return (base64_string, mime_type)."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": os.path.join(tmp_dir, "audio.%(ext)s"),
    }
    _with_cookies(ydl_opts, tmp_dir)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore
        ydl.extract_info(url, download=True)

    candidates = [f for f in os.listdir(tmp_dir) if f.startswith("audio.")]
    if not candidates:
        raise RuntimeError("yt-dlp produced no audio file")

    audio_path = os.path.join(tmp_dir, candidates[0])
    ext = os.path.splitext(candidates[0])[1].lstrip(".")
    mime_type = {"m4a": "audio/mp4", "webm": "audio/webm", "mp3": "audio/mpeg"}.get(ext, "audio/mp4")

    with open(audio_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")

    return audio_b64, mime_type


def _fetch_vtt_text(url: str, tmp_dir: str) -> tuple[str | None, dict]:
    """Run yt-dlp subtitle extraction; return (parsed VTT text or None, info dict)."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writeautomaticsub": True,
        "writesubtitles": True,
        "subtitleslangs": ["en", "en-orig"],
        "subtitlesformat": "vtt",
        "outtmpl": os.path.join(tmp_dir, "%(id)s.%(ext)s"),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore
        info = dict(ydl.extract_info(url, download=True) or {})
    vtt_files = [f for f in os.listdir(tmp_dir) if f.endswith(".vtt")]
    if vtt_files:
        return _parse_vtt(os.path.join(tmp_dir, vtt_files[0])), info
    return None, info


def _youtube_transcript(video_id: str, url: str):
    """YouTubeTranscriptApi first, yt-dlp subtitles as fallback."""
    try:
        ytt = YouTubeTranscriptApi()
        transcript = ytt.fetch(video_id)
        text = " ".join([snippet.text for snippet in transcript])
        return jsonify([{"videoId": video_id, "text": text}])
    except Exception:
        pass  # IP blocked or no captions — fall through to yt-dlp

    tmp_dir = tempfile.mkdtemp()
    try:
        text, _ = _fetch_vtt_text(url, tmp_dir)
        if text:
            return jsonify([{"videoId": video_id, "text": text}])
    except Exception:
        pass
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return jsonify([{"error": {"type": "IpBlocked", "message": "Could not retrieve transcript via YouTubeTranscriptApi or yt-dlp"}}])


def _generic_transcript(url: str):
    """Non-YouTube (TikTok, Instagram Reels, …): yt-dlp captions, then audio fallback."""
    tmp_dir = tempfile.mkdtemp()
    try:
        # Try caption extraction first; if it throws, fall through to audio.
        caption_text: str | None = None
        vid = "unknown"
        try:
            caption_text, info = _fetch_vtt_text(url, tmp_dir)
            info = get_primary_media_info(info)
            vid = info.get("id", "unknown")
        except Exception:
            pass  # caption extraction failed → try audio fallback below

        if caption_text:
            return jsonify([{"videoId": vid, "text": caption_text}])

        # Caption-less fallback: download audio-only and return it as inline base64.
        # The worker makes a single Gemini call that transcribes + analyzes the audio.
        try:
            audio_b64, mime_type = _download_audio_b64(url, tmp_dir)
            return jsonify([{"audio_b64": audio_b64, "mime_type": mime_type, "fallback": "audio"}])
        except Exception as e:
            return jsonify([{"error": {"type": "transcription_failed", "message": str(e)}}])
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.route("/transcript", methods=["GET"])
def get_transcript():
    url, error_response = _validate_request_url()
    if error_response:
        body, status = error_response
        return jsonify([body.get_json()]), status

    # YouTube path: try YouTubeTranscriptApi first, fall back to yt-dlp subtitles
    video_id = extract_video_id(url)
    if video_id:
        return _youtube_transcript(video_id, url)
    return _generic_transcript(url)


@app.route("/metadata", methods=["GET"])
def get_metadata():
    try:
        url, error_response = _validate_request_url()
        if error_response:
            return error_response

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "logger": type(
                "_NullLogger",
                (),
                {
                    "debug": staticmethod(lambda msg: None),
                    "info": staticmethod(lambda msg: None),
                    "warning": staticmethod(lambda msg: None),
                    "error": staticmethod(lambda msg: None),
                },
            )(),
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore
            info = ydl.extract_info(url, download=False)

        # We added "description" to the return dictionary below
        return jsonify(
            {
                "title": info.get("title", ""),
                "channel": info.get("uploader", "") or info.get("channel", ""),
                "views": str(info.get("view_count", "")),
                "upload_date": info.get("upload_date", ""),
                "description": info.get("description", ""),  # This is the new line
            }
        )
    except Exception as e:
        return jsonify(
            {
                "error": str(e),
                "title": "",
                "channel": "",
                "views": "",
                "upload_date": "",
                "description": "",  # Keep the schema consistent on error
            }
        ), 200


def _detect_platform(extractor: str, url: str) -> str:
    if extractor == "Youtube" and "/shorts/" in url:
        return "youtube_shorts"
    if extractor == "TikTok":
        return "tiktok"
    if extractor == "Instagram":
        return "instagram_reels"
    return "unknown"


def _encode_frames(tmp_frame_dir: str, interval: float) -> list[dict]:
    """Re-encode the ffmpeg frame dumps as base64 JPEG descriptors."""
    frame_files = sorted(
        f for f in os.listdir(tmp_frame_dir) if f.startswith("frame_") and f.endswith(".jpg")
    )
    frames = []
    for i, fname in enumerate(frame_files):
        fpath = os.path.join(tmp_frame_dir, fname)
        with Image.open(fpath) as img:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        frames.append(
            {
                "index": i,
                "timestamp_s": round(i * interval, 2),
                "base64": b64,
                "mime_type": "image/jpeg",
            }
        )
    return frames


@app.route("/short_frames", methods=["GET"])
def get_short_frames():
    url, error_response = _validate_request_url()
    if error_response:
        return error_response

    try:
        interval = _bounded_float("interval", 1.0, 0.1, 10.0)
        max_frames = _bounded_int("max_frames", 20, 1, 120)
        max_width = _bounded_int("max_width", 768, 64, 1920)
    except ValueError as e:
        return jsonify({"error": {"type": "invalid_param", "message": str(e)}}), 400

    NullLogger = type(
        "_NullLogger",
        (),
        {
            "debug": staticmethod(lambda msg: None),
            "info": staticmethod(lambda msg: None),
            "warning": staticmethod(lambda msg: None),
            "error": staticmethod(lambda msg: None),
        },
    )()

    tmp_video_dir = None
    tmp_frame_dir = None
    try:
        # Use temp dirs so yt-dlp controls the filename
        tmp_video_dir = tempfile.mkdtemp()
        tmp_frame_dir = tempfile.mkdtemp()
        outtmpl = os.path.join(tmp_video_dir, "video.%(ext)s")

        # Download video with yt-dlp
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "outtmpl": outtmpl,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "logger": NullLogger,
        }
        _with_cookies(ydl_opts, tmp_video_dir)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore
                info = ydl.extract_info(url, download=True)
        except Exception as e:
            return jsonify({"error": {"type": "download_failed", "message": str(e)}})

        # Find the downloaded file
        candidates = os.listdir(tmp_video_dir)
        if not candidates:
            return jsonify(
                {
                    "error": {
                        "type": "download_failed",
                        "message": "yt-dlp produced no output file",
                    }
                }
            )
        tmp_video = os.path.join(tmp_video_dir, candidates[0])

        duration = info.get("duration") or 0
        if duration > 180:
            return jsonify(
                {
                    "error": {
                        "type": "too_long",
                        "message": f"Video duration {duration}s exceeds 180s limit",
                    }
                }
            )

        platform = _detect_platform(info.get("extractor_key", ""), url)
        title = info.get("title", "")
        video_id = info.get("id", "")

        # Extract frames with ffmpeg
        frame_pattern = os.path.join(tmp_frame_dir, "frame_%04d.jpg")
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            tmp_video,
            "-vf",
            f"fps=1/{interval},scale={max_width}:-1",
            "-vframes",
            str(max_frames),
            frame_pattern,
        ]
        result = subprocess.run(ffmpeg_cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            return jsonify(
                {
                    "error": {
                        "type": "frame_extraction_failed",
                        "message": result.stderr.decode(errors="replace")[:500],
                    }
                }
            )

        frames = _encode_frames(tmp_frame_dir, interval)

        return jsonify(
            {
                "platform": platform,
                "title": title,
                "duration": duration,
                "video_id": video_id,
                "frame_count": len(frames),
                "frames": frames,
            }
        )

    except Exception as e:
        return jsonify({"error": {"type": "unexpected_error", "message": str(e)}})
    finally:
        if tmp_video_dir and os.path.exists(tmp_video_dir):
            shutil.rmtree(tmp_video_dir, ignore_errors=True)
        if tmp_frame_dir and os.path.exists(tmp_frame_dir):
            shutil.rmtree(tmp_frame_dir, ignore_errors=True)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print("Transcript server running on http://0.0.0.0:5151")
    serve(app, host="0.0.0.0", port=5151)
