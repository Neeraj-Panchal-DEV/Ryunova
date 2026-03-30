"""Rewrite API public URLs in responses so LAN clients can load media (not 127.0.0.1 on their device)."""

from __future__ import annotations

from django.conf import settings

from ryunova_web.workspace import reconcile_workspace_session

# FastAPI default dev URLs embedded in JSON/HTML from the API
_LOCAL_API_PREFIXES = (
    "http://127.0.0.1:",
    "http://localhost:",
)


class RewriteApiPublicUrlMiddleware:
    """Replace loopback API host:port with this request's hostname + API port."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not getattr(settings, "RYUNOVA_REWRITE_API_PUBLIC_IN_RESPONSES", False):
            return response
        ct = response.get("Content-Type", "") or ""
        if "text/html" not in ct and "application/json" not in ct and "text/javascript" not in ct:
            return response
        if getattr(response, "streaming", False):
            return response
        content = getattr(response, "content", None)
        if not content:
            return response
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return response
        host = request.get_host()
        scheme = "https" if request.is_secure() else "http"
        hostname = host.split(":")[0]
        api_port = getattr(settings, "RYUNOVA_API_PUBLIC_PORT", "8000")
        replacement_root = f"{scheme}://{hostname}:{api_port}"
        changed = False
        for prefix in _LOCAL_API_PREFIXES:
            if prefix not in text:
                continue
            # Replace only our API port (default 8000) to avoid clobbering other localhost URLs
            needle = f"{prefix}{api_port}"
            if needle in text:
                text = text.replace(needle, replacement_root)
                changed = True
        if not changed:
            return response
        response.content = text.encode("utf-8")
        if response.has_header("Content-Length"):
            del response["Content-Length"]
        return response


class WorkspaceSessionMiddleware:
    """Keep organisation scope consistent with membership (single-org auto-scope, no forged org id)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        reconcile_workspace_session(request)
        return self.get_response(request)
