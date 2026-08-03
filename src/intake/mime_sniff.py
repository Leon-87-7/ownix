"""Magic-byte content sniffing for upload hardening (issue #475).

Never trust the client-supplied `Content-Type` header — sniff the actual
bytes and route/reject on that instead.
"""

from __future__ import annotations

_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)

_WEBP_RIFF = b"RIFF"
_WEBP_MARKER = b"WEBP"


def sniff(data: bytes) -> str | None:
    """Return the sniffed MIME type for `data`, or None if unrecognized."""
    for signature, mime in _SIGNATURES:
        if data.startswith(signature):
            return mime
    if data[:4] == _WEBP_RIFF and data[8:12] == _WEBP_MARKER:
        return "image/webp"
    return None
