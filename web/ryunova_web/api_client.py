from __future__ import annotations

from typing import Any

import requests
from django.conf import settings
from requests.exceptions import RequestException


def _api_base() -> str:
    """Prefer internal Docker URL for server-side requests; fall back to public RYUNOVA_API_BASE."""
    internal = getattr(settings, "RYUNOVA_API_BASE_INTERNAL", "") or ""
    return internal.strip() or settings.RYUNOVA_API_BASE


class ApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None, detail: Any = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


def _api_unreachable_message() -> str:
    return (
        "Cannot reach the FastAPI backend (port 8000). "
        "Open a second terminal and run: "
        "cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    )


def _request(method: str, url: str, **kwargs: Any) -> requests.Response:
    try:
        return requests.request(method, url, **kwargs)
    except RequestException as exc:
        raise ApiError(
            "API unreachable",
            None,
            {"detail": _api_unreachable_message()},
        ) from exc


def _headers(token: str | None, organisation_id: str | None = None) -> dict[str, str]:
    h = {"Accept": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if organisation_id:
        h["X-Organisation-Id"] = organisation_id
    return h


def api_get(
    path: str,
    token: str | None,
    params: dict | None = None,
    *,
    organisation_id: str | None = None,
) -> Any:
    url = f"{_api_base()}{path}"
    r = _request(
        "GET",
        url,
        headers=_headers(token, organisation_id),
        params=params or {},
        timeout=30,
    )
    if r.status_code == 204:
        return None
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ApiError("API request failed", r.status_code, detail)
    if r.content:
        return r.json()
    return None


def api_post_json(
    path: str,
    token: str | None,
    data: dict,
    params: dict | None = None,
    *,
    organisation_id: str | None = None,
) -> Any:
    url = f"{_api_base()}{path}"
    r = _request(
        "POST",
        url,
        headers={**_headers(token, organisation_id), "Content-Type": "application/json"},
        json=data,
        params=params or {},
        timeout=30,
    )
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ApiError("API request failed", r.status_code, detail)
    if r.status_code == 204:
        return None
    return r.json() if r.content else None


def api_patch_json(
    path: str,
    token: str | None,
    data: dict,
    *,
    organisation_id: str | None = None,
) -> Any:
    url = f"{_api_base()}{path}"
    r = _request(
        "PATCH",
        url,
        headers={**_headers(token, organisation_id), "Content-Type": "application/json"},
        json=data,
        timeout=30,
    )
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ApiError("API request failed", r.status_code, detail)
    return r.json() if r.content else None


def api_delete(
    path: str,
    token: str | None,
    *,
    organisation_id: str | None = None,
) -> None:
    url = f"{_api_base()}{path}"
    r = _request("DELETE", url, headers=_headers(token, organisation_id), timeout=30)
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ApiError("API request failed", r.status_code, detail)


def api_post_multipart(
    path: str,
    token: str | None,
    files: dict,
    data: dict | None = None,
    *,
    organisation_id: str | None = None,
) -> Any:
    url = f"{_api_base()}{path}"
    r = _request(
        "POST",
        url,
        headers=_headers(token, organisation_id),
        files=files,
        data=data or {},
        timeout=120,
    )
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ApiError("API request failed", r.status_code, detail)
    return r.json() if r.content else None


def api_post_form(
    path: str,
    token: str | None,
    data: dict,
    *,
    organisation_id: str | None = None,
) -> Any:
    """POST application/x-www-form-urlencoded (e.g. FastAPI Form() without files)."""
    url = f"{_api_base()}{path}"
    r = _request(
        "POST",
        url,
        headers=_headers(token, organisation_id),
        data=data,
        timeout=120,
    )
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ApiError("API request failed", r.status_code, detail)
    return r.json() if r.content else None


def login(email: str, password: str) -> dict[str, Any]:
    """Returns full login JSON: access_token, organisations, is_platform_user, user_admin_access, etc."""
    url = f"{_api_base()}/auth/login"
    r = _request(
        "POST",
        url,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        json={"email": email, "password": password},
        timeout=30,
    )
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ApiError("Login failed", r.status_code, detail)
    return r.json()


def verify_email(token: str) -> dict[str, Any]:
    url = f"{_api_base()}/auth/verify-email"
    r = _request(
        "POST",
        url,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        json={"token": token},
        timeout=30,
    )
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ApiError("Verification failed", r.status_code, detail)
    if r.status_code == 204:
        return {}
    return r.json() if r.content else {}


def login_otp_request(email: str) -> None:
    """POST /auth/login-otp/request — always succeeds HTTP-wise if API is up."""
    url = f"{_api_base()}/auth/login-otp/request"
    r = _request(
        "POST",
        url,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        json={"email": email.strip().lower()},
        timeout=30,
    )
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ApiError("Could not request sign-in code", r.status_code, detail)


def login_otp_verify(email: str, code: str) -> dict[str, Any]:
    """POST /auth/login-otp/verify — returns same shape as login()."""
    url = f"{_api_base()}/auth/login-otp/verify"
    r = _request(
        "POST",
        url,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        json={"email": email.strip().lower(), "code": code.strip()},
        timeout=30,
    )
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ApiError("Sign-in code verification failed", r.status_code, detail)
    return r.json()
