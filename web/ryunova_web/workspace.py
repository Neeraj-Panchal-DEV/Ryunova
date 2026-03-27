"""Workspace scope in session: organisation picker runs once per sign-in when required.

Platform users and non–platform users with multiple organisations must confirm scope
(All organisations, or a specific org) before the dashboard and catalog routes load.
"""

from __future__ import annotations


def _session_orgs(request) -> list:
    raw = request.session.get("organisations") or []
    return raw if isinstance(raw, list) else []


def is_platform_user_session(request) -> bool:
    return bool(request.session.get("is_platform_user"))


def workspace_scope_confirmed(request) -> bool:
    """True after user has completed the org picker (or single-org auto scope at login)."""
    if request.session.get("workspace_scope_confirmed"):
        return True
    # Legacy sessions: single-org member already had organisation_id set at login
    if not is_platform_user_session(request):
        orgs = _session_orgs(request)
        oid = request.session.get("organisation_id")
        if len(orgs) == 1 and oid and str(orgs[0].get("id")) == str(oid):
            request.session["workspace_scope_confirmed"] = True
            request.session.modified = True
            return True
    return False


def needs_workspace_selection(request) -> bool:
    """Authenticated user must open the organisation picker before using workspace UI."""
    if not request.session.get("access_token"):
        return False
    return not workspace_scope_confirmed(request)
