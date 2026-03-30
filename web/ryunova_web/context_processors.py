import time
import zlib

from django.conf import settings


def api_media(request):
    return {
        "RYUNOVA_API_BASE": settings.RYUNOVA_API_BASE,
        "RYUNOVA_API_PUBLIC": getattr(settings, "RYUNOVA_API_PUBLIC", "http://127.0.0.1:8000"),
    }


def turnstile(request):
    site = getattr(settings, "TURNSTILE_SITE_KEY", "") or ""
    secret = getattr(settings, "TURNSTILE_SECRET_KEY", "") or ""
    use = bool(site.strip() and secret.strip())
    return {
        "use_turnstile": use,
        "turnstile_site_key": site.strip(),
    }


def _nav_initials(display_name: str, email: str) -> str:
    dn = (display_name or "").strip()
    if dn:
        parts = dn.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()[:2]
        return dn[:2].upper() if len(dn) >= 2 else dn[0].upper()
    em = (email or "").strip()
    if em:
        return em[:2].upper()
    return "?"


def _avatar_cache_bust(url: str) -> int:
    """Stable per URL; changes when avatar path changes (browser cache-bust query)."""
    return zlib.adler32((url or "").encode("utf-8")) & 0x7FFFFFFF


def _avatar_src(url: str, v: int) -> str:
    if not url:
        return ""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}v={v}"


def me_dict_to_nav(me: dict) -> dict:
    """Serialize GET /auth/me JSON for Django session + template nav."""
    url = me.get("avatar_url") or ""
    v = _avatar_cache_bust(url)
    return {
        "id": str(me.get("id", "")),
        "email": me.get("email") or "",
        "display_name": (me.get("display_name") or "").strip(),
        "avatar_url": url,
        "avatar_v": v,
        "avatar_src": _avatar_src(url, v),
        "initials": _nav_initials(me.get("display_name") or "", me.get("email") or ""),
    }


def _ensure_nav_avatar_fields(nu: dict) -> dict:
    """Fill avatar_v / avatar_src for legacy session nav_user entries (no API call)."""
    if not isinstance(nu, dict):
        return nu
    url = nu.get("avatar_url") or ""
    v = nu.get("avatar_v")
    if v is None:
        v = _avatar_cache_bust(url)
    src = nu.get("avatar_src")
    if not src and url:
        src = _avatar_src(url, v)
    return {**nu, "avatar_v": v, "avatar_src": src or ""}


def refresh_session_nav_user(request) -> None:
    """Call after login or profile update when access_token is set."""
    from ryunova_web.api_client import ApiError, api_get

    token = request.session.get("access_token")
    if not token:
        request.session.pop("nav_user", None)
        request.session.pop("nav_user_refresh_at", None)
        request.session.pop("is_platform_user", None)
        request.session.pop("user_admin_access", None)
        return
    try:
        me = api_get("/auth/me", token)
    except ApiError:
        request.session.pop("nav_user", None)
        request.session.pop("nav_user_refresh_at", None)
        request.session.pop("is_platform_user", None)
        request.session.pop("user_admin_access", None)
        return
    if not me:
        request.session.pop("nav_user", None)
        request.session.pop("nav_user_refresh_at", None)
        request.session.pop("is_platform_user", None)
        request.session.pop("user_admin_access", None)
        return
    request.session["nav_user"] = me_dict_to_nav(me)
    request.session["nav_user_refresh_at"] = time.time()
    # /auth/me may return is_system_user as alias of is_platform_user (same flag)
    request.session["is_platform_user"] = bool(me.get("is_platform_user") or me.get("is_system_user"))
    request.session["user_admin_access"] = bool(me.get("user_admin_access"))
    request.session.modified = True


def workspace_context(request):
    """Header brand, footer, workspace labels, and user-menu org / change-organisation context."""
    orgs = request.session.get("organisations") or []
    if not isinstance(orgs, list):
        orgs = []
    oid = request.session.get("organisation_id")
    org_display_name = None
    if oid:
        for o in orgs:
            if not isinstance(o, dict):
                continue
            if str(o.get("id")) == str(oid):
                raw_name = o.get("name")
                org_display_name = str(raw_name).strip() if raw_name is not None else ""
                if not org_display_name:
                    org_display_name = None
                break
    is_plat = bool(request.session.get("is_platform_user"))
    token = bool(request.session.get("access_token"))

    # Chip label: scoped org name, or platform “all orgs” mode
    if is_plat and not oid:
        chip_label = "All organisations"
    elif org_display_name:
        chip_label = org_display_name
    else:
        chip_label = None

    # Logo / header title: "eCommerce" until an organisation is scoped; then the organisation name.
    if oid and org_display_name:
        header_brand_name = org_display_name
    else:
        header_brand_name = "eCommerce"

    # Footer: organisation name when signed in with a scoped org; otherwise product name
    if not token:
        footer_brand_name = "RYUNOVA PLATFORM"
    elif oid and org_display_name:
        footer_brand_name = org_display_name
    else:
        footer_brand_name = "RYUNOVA PLATFORM"

    show_link = token and (is_plat or len(orgs) > 1)

    # User menu (avatar dropdown): org context + “Change organisation” before Sign out
    workspace_menu_org_line = None
    if token:
        if is_plat and not oid:
            workspace_menu_org_line = "All organisations"
        elif org_display_name:
            workspace_menu_org_line = org_display_name
    workspace_show_change_org_link = show_link

    chip_text = chip_label
    chip_title = "Organisation"
    if token and chip_label:
        if not is_plat and len(orgs) > 1 and org_display_name:
            chip_text = "Switch organisation"
            chip_title = str(org_display_name)
        elif show_link:
            chip_title = "Switch organisation"

    return {
        "header_brand_name": header_brand_name,
        "footer_brand_name": footer_brand_name,
        "workspace_org_label": chip_text,
        "workspace_org_chip_title": chip_title,
        "workspace_show_switcher": show_link,
        "workspace_menu_org_line": workspace_menu_org_line,
        "workspace_show_change_org_link": workspace_show_change_org_link,
    }


def nav_user(request):
    """Use session nav_user; refresh from GET /auth/me when cache is missing or past TTL."""
    from ryunova_web.api_client import ApiError, api_get

    token = request.session.get("access_token")
    if not token:
        return {"nav_user": None}

    ttl = float(getattr(settings, "NAV_USER_ME_TTL_SECONDS", 300))
    cached = request.session.get("nav_user")
    refreshed_at = request.session.get("nav_user_refresh_at")

    if (
        isinstance(cached, dict)
        and cached.get("id")
        and refreshed_at is not None
        and (time.time() - float(refreshed_at)) < ttl
    ):
        return {"nav_user": _ensure_nav_avatar_fields(cached)}

    try:
        me = api_get("/auth/me", token)
    except ApiError:
        if isinstance(cached, dict) and cached.get("id"):
            return {"nav_user": _ensure_nav_avatar_fields(cached)}
        return {"nav_user": None}
    if not me:
        return {"nav_user": None}
    nu = me_dict_to_nav(me)
    request.session["nav_user"] = nu
    request.session["nav_user_refresh_at"] = time.time()
    # /auth/me may return is_system_user as alias of is_platform_user (same flag)
    request.session["is_platform_user"] = bool(me.get("is_platform_user") or me.get("is_system_user"))
    request.session["user_admin_access"] = bool(me.get("user_admin_access"))
    request.session.modified = True
    return {"nav_user": nu}
