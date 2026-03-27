"""Fetch remote images for product import with basic SSRF mitigation."""

from __future__ import annotations

import ipaddress
import re
import socket
import uuid
from urllib.parse import urlparse

import httpx

# Images only (no video from URL in MVP).
_ALLOWED_CT = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})
_CT_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

_MAGIC = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"RIFF", "image/webp"),  # further check: WEBP at 8..12
)


def slug_from_product_title(title: str, max_len: int = 72) -> str:
    """Filesystem-safe stem from product title."""
    t = re.sub(r"[^\w\s-]", "", (title or "").strip(), flags=re.UNICODE)
    t = re.sub(r"[-\s]+", "-", t).lower().strip("-")
    return (t[:max_len] if t else "product").strip("-") or "product"


def validate_public_http_url(url: str) -> tuple[bool, str]:
    """Reject non-http(s), missing host, localhost, and private/reserved IPs."""
    raw = (url or "").strip()
    if not raw:
        return False, "URL is empty"
    try:
        parsed = urlparse(raw)
    except Exception:
        return False, "Invalid URL"
    if parsed.scheme not in ("http", "https"):
        return False, "Only http and https URLs are allowed"
    host = parsed.hostname
    if not host:
        return False, "Invalid host"
    hl = host.lower()
    if hl == "localhost" or hl.endswith(".localhost"):
        return False, "Local addresses are not allowed"
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False, "Could not resolve host"
    for _fam, _type, _proto, _canon, sockaddr in infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False, "Address not allowed"
    return True, ""


def _sniff_image_type(data: bytes) -> str | None:
    if len(data) < 12:
        return None
    for sig, ct in _MAGIC:
        if data.startswith(sig):
            if ct == "image/webp":
                if len(data) >= 12 and data[8:12] == b"WEBP":
                    return ct
                return None
            return ct
    return None


def normalize_image_content_type(declared: str | None, body: bytes) -> tuple[str | None, str | None]:
    """
    Returns (content_type, error_message).
    Prefer magic bytes; fall back to declared Content-Type if it matches allow-list.
    """
    sniffed = _sniff_image_type(body)
    decl = (declared or "").split(";")[0].strip().lower()
    if decl == "image/jpg":
        decl = "image/jpeg"
    if sniffed:
        return sniffed, None
    if decl in _ALLOWED_CT:
        return decl, None
    return None, "Response is not a recognised image (JPEG, PNG, GIF, or WebP)"


def build_stored_filename(product_title: str, content_type: str) -> str:
    ext = _CT_EXT.get(content_type, ".img")
    stem = slug_from_product_title(product_title)
    return f"{stem}-{uuid.uuid4().hex[:10]}{ext}"


async def download_image_bytes(url: str, max_bytes: int) -> tuple[bytes, str, str]:
    """
    GET url (follow redirects); validate each hop is public http(s).
    Returns (body, final_url, declared_content_type) or raises httpx.HTTPError / ValueError.
    """
    ok, err = validate_public_http_url(url)
    if not ok:
        raise ValueError(err)

    headers = {"User-Agent": "RyuNovaPlatform/1.0 (product image import)"}
    async with httpx.AsyncClient(
        headers=headers,
        follow_redirects=True,
        max_redirects=5,
        timeout=httpx.Timeout(30.0, connect=10.0),
    ) as client:
        async with client.stream("GET", url) as response:
            # Final URL after redirects
            final = str(response.url)
            ok_f, err_f = validate_public_http_url(final)
            if not ok_f:
                raise ValueError(f"Redirect blocked: {err_f}")
            response.raise_for_status()
            decl_ct = response.headers.get("content-type")

            total = 0
            chunks: list[bytes] = []
            async for chunk in response.aiter_bytes(65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"Image exceeds maximum size ({max_bytes // (1024 * 1024)} MB)")
                chunks.append(chunk)

    body = b"".join(chunks)
    if len(body) < 32:
        raise ValueError("Downloaded file is too small to be an image")

    ct, verr = normalize_image_content_type(decl_ct, body)
    if verr or not ct:
        raise ValueError(verr or "Not an image")
    if ct not in _ALLOWED_CT:
        raise ValueError("Only JPEG, PNG, GIF, and WebP images can be imported from a URL")

    return body, final, ct
