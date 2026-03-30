"""Workspace scope in session: organisation picker runs once per sign-in when required.

Platform users and non–platform users with multiple organisations must confirm scope
(All organisations, or a specific org) before the dashboard and catalog routes load.
"""

from __future__ import annotations

# Session key: which organisation the org-users admin UI is scoped to (see manage_organisation_users_view).
SESSION_KEY_ORG_USERS_LIST = "organisation_users_list_org_id"


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


def _reconcile_org_users_list_session(request, valid_ids: set[str]) -> None:
    """Drop org-users admin scope if it is not in the user's membership list (login snapshot)."""
    raw = request.session.get(SESSION_KEY_ORG_USERS_LIST)
    if not raw:
        return
    if str(raw) not in valid_ids:
        request.session.pop(SESSION_KEY_ORG_USERS_LIST, None)
        request.session.modified = True


def reconcile_workspace_session(request) -> None:
    """Align session organisation with login-time membership (cannot pick arbitrary orgs via devtools).

    - Non–platform: ``organisation_id`` must be one of ``session['organisations']``. Invalid values are cleared.
    - Non–platform, exactly one org: always scope to that org (no picker; fixes tampering).
    - Platform: if ``organisation_id`` is set, it must appear in the session org list (same as login snapshot).
    """
    if not request.session.get("access_token"):
        return
    orgs = _session_orgs(request)
    valid_ids = {str(o.get("id")) for o in orgs if isinstance(o, dict) and o.get("id")}
    is_plat = is_platform_user_session(request)
    oid = request.session.get("organisation_id")

    if not is_plat:
        if not orgs:
            _reconcile_org_users_list_session(request, valid_ids)
            return
        if len(orgs) == 1:
            only = str(orgs[0].get("id"))
            if only and str(oid or "") != only:
                request.session["organisation_id"] = only
                request.session["workspace_scope_confirmed"] = True
                request.session.modified = True
            _reconcile_org_users_list_session(request, valid_ids)
            return
        if oid and str(oid) not in valid_ids:
            request.session.pop("organisation_id", None)
            request.session["workspace_scope_confirmed"] = False
            request.session.modified = True
        _reconcile_org_users_list_session(request, valid_ids)
        return

    if oid is not None and str(oid) not in valid_ids:
        request.session.pop("organisation_id", None)
        request.session.modified = True
    _reconcile_org_users_list_session(request, valid_ids)
