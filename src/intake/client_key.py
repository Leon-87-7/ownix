"""Trusted-proxy-aware anonymous client key, for rate-limiting callers with
no session/token yet (public preview reads, MCP/extension pairing redeem).

Was `src.api.preview._preview_client_key` — moved here once a second and
third feature (`src/api/mcp_auth.py`, `src/api/extension_auth.py`) started
importing a preview-owned private helper across a module boundary.
"""

from __future__ import annotations

from ipaddress import ip_address, ip_network

from fastapi import Request

from src.config import settings


def resolve_client_key(request: Request) -> str:
    peer = request.client.host if request.client is not None else None
    if peer and _trusted_proxy_peer(peer):
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.rsplit(",", 1)[-1].strip() or peer
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip() or peer
    if peer:
        return peer
    return "unknown"


def _trusted_proxy_peer(peer: str) -> bool:
    try:
        peer_ip = ip_address(peer)
    except ValueError:
        return False
    for raw_network in settings.PREVIEW_TRUSTED_PROXY_CIDRS.split(","):
        raw_network = raw_network.strip()
        if not raw_network:
            continue
        try:
            if peer_ip in ip_network(raw_network, strict=False):
                return True
        except ValueError:
            continue
    return False
