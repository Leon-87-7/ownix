"""Shared SSRF host guard — is every address a hostname resolves to publicly routable?"""

from __future__ import annotations

import asyncio
import ipaddress
import socket


async def resolve_public_host(host: str) -> list | None:
    """Resolve *host* via getaddrinfo (off the event loop). None on DNS failure."""
    try:
        return await asyncio.to_thread(socket.getaddrinfo, host, None)
    except socket.gaierror:
        return None


def is_public_ip(ip_str: str) -> bool:
    """False for loopback / private / link-local (incl. 169.254.169.254 cloud
    metadata) / reserved / multicast / unspecified addresses."""
    ip = ipaddress.ip_address(ip_str)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


async def is_public_host(host: str) -> bool:
    """True only when every resolved address for *host* is a public, routable IP.

    ponytail: validates via getaddrinfo, not pinned to the socket — a DNS-rebinding
    attacker could still race the resolution; upgrade to an IP-pinned httpx
    transport (see src.utils.public_html._resolve_safe_public_url) if that threat
    becomes real.
    """
    infos = await resolve_public_host(host)
    if infos is None:
        return False
    return all(is_public_ip(info[4][0]) for info in infos)
