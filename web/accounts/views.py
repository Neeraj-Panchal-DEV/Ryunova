import logging
from urllib.parse import urlencode

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from accounts.emails import email_delivery_is_console_only, send_user_invite_email
from accounts.bot_gate import (
    login_form_challenge_context,
    login_gate_fail_message,
    prepare_login_get_page,
    refresh_login_bot_challenge,
    verify_login_bot_gate,
)
from accounts.human_challenge import human_challenge_template_context, refresh_human_challenge
from accounts.turnstile import is_turnstile_enabled
from ryunova_web.api_client import (
    ApiError,
    api_get,
    api_patch_json,
    api_post_form,
    api_post_json,
    api_post_multipart,
    login,
    login_otp_request,
    login_otp_verify,
    verify_email,
)
from ryunova_web.context_processors import refresh_session_nav_user
from ryunova_web.workspace import SESSION_KEY_ORG_USERS_LIST, needs_workspace_selection

logger = logging.getLogger(__name__)


def _err_msg(e: ApiError) -> str:
    d = e.detail
    if isinstance(d, dict):
        if "detail" in d:
            return str(d["detail"])
        return str(d)
    if isinstance(d, list):
        return "; ".join(str(x) for x in d)
    return str(d or e.message)


def _err_msg_profile_admin_api(e: ApiError) -> str:
    """Starlette returns {\"detail\": \"Not Found\"} when no route matches — common if uvicorn was not restarted."""
    if e.status_code == 404 and isinstance(e.detail, dict):
        if str(e.detail.get("detail", "")).strip().lower() == "not found":
            return (
                "The API has no admin profile route (404). Restart the FastAPI server from the backend "
                "project (uvicorn app.main:app) so routes such as GET /api/v1/admin/users/{id}/profile are loaded."
            )
    return _err_msg(e)


def _session_orgs(request) -> list:
    raw = request.session.get("organisations") or []
    return raw if isinstance(raw, list) else []


def _org_name_for_id(request, org_id: str) -> str:
    for o in _session_orgs(request):
        if isinstance(o, dict) and str(o.get("id")) == str(org_id):
            return str(o.get("name") or org_id)
    return org_id


def _org_in_session(request, org_id: str) -> bool:
    return any(isinstance(o, dict) and str(o.get("id")) == str(org_id) for o in _session_orgs(request))


def _is_platform(request) -> bool:
    return bool(request.session.get("is_platform_user"))


def _apply_login_response_to_session(request, body: dict) -> str:
    """Persist API login JSON and return redirect name: 'dashboard' | 'select_organisation'."""
    request.session["access_token"] = body["access_token"]
    is_plat = bool(body.get("is_platform_user") or body.get("is_system_user"))
    request.session["is_platform_user"] = is_plat
    request.session["user_admin_access"] = bool(body.get("user_admin_access", False))
    orgs = body.get("organisations") or []
    request.session["organisations"] = orgs

    if not is_plat:
        if len(orgs) == 0:
            request.session.flush()
            return "__no_orgs__"
        if len(orgs) == 1:
            request.session["organisation_id"] = str(orgs[0]["id"])
            request.session["workspace_scope_confirmed"] = True
            refresh_session_nav_user(request)
            return "dashboard"
        request.session.pop("organisation_id", None)
        request.session["workspace_scope_confirmed"] = False
        refresh_session_nav_user(request)
        return "select_organisation"

    request.session.pop("organisation_id", None)
    request.session["workspace_scope_confirmed"] = False
    refresh_session_nav_user(request)
    return "select_organisation"


@require_GET
def human_challenge_refresh_view(request):
    """Return a new multiple-choice human question (session); used by login forms without full reload."""
    if is_turnstile_enabled():
        return JsonResponse({"error": "turnstile_active"}, status=404)
    refresh_human_challenge(request)
    ctx = human_challenge_template_context(request)
    opts = ctx.get("human_options") or []
    return JsonResponse(
        {
            "question": ctx.get("human_question") or "",
            "options": [{"id": o.get("id", ""), "label": o.get("label", "")} for o in opts if isinstance(o, dict)],
        }
    )


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.session.get("access_token"):
        if needs_workspace_selection(request):
            return redirect("select_organisation")
        return redirect("dashboard")
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        if not verify_login_bot_gate(request):
            refresh_login_bot_challenge(request)
            messages.error(request, login_gate_fail_message())
            ctx = login_form_challenge_context(request)
            ctx["email"] = email
            return render(request, "accounts/login.html", ctx)
        try:
            body = login(email, password)
        except ApiError as e:
            refresh_login_bot_challenge(request)
            detail = e.detail
            if isinstance(detail, dict) and "detail" in detail:
                msg = detail["detail"]
            elif isinstance(detail, list):
                msg = str(detail)
            else:
                msg = str(detail or e.message)
            messages.error(request, msg)
            ctx = login_form_challenge_context(request)
            ctx["email"] = email
            return render(request, "accounts/login.html", ctx)

        nxt = _apply_login_response_to_session(request, body)
        if nxt == "__no_orgs__":
            messages.error(request, "Your account is not linked to any organisation. Contact a platform administrator.")
            refresh_login_bot_challenge(request)
            ctx = login_form_challenge_context(request)
            ctx["email"] = email
            return render(request, "accounts/login.html", ctx)
        if nxt == "dashboard":
            messages.success(request, "Signed in.")
            return redirect("dashboard")
        messages.success(
            request,
            "Signed in. Choose an organisation to continue."
            if nxt == "select_organisation" and not request.session.get("is_platform_user")
            else "Signed in. Choose your workspace to continue.",
        )
        return redirect("select_organisation")

    return render(request, "accounts/login.html", prepare_login_get_page(request))


@require_http_methods(["GET", "POST"])
def login_code_view(request):
    """Slack-style: email → 6-digit code → session (same as password login)."""
    if request.session.get("access_token"):
        if needs_workspace_selection(request):
            return redirect("select_organisation")
        return redirect("dashboard")

    if request.method == "GET" and request.GET.get("reset") == "1":
        request.session.pop("login_otp_email", None)
        return redirect("login_code")

    def _code_page(extra: dict):
        return render(
            request,
            "accounts/login_code.html",
            {**login_form_challenge_context(request), **extra},
        )

    ctx: dict = {"step": 1, "email": ""}
    pending = (request.session.get("login_otp_email") or "").strip().lower()
    if request.method == "GET" and pending:
        ctx = {"step": 2, "email": pending}

    if request.method == "POST":
        step = (request.POST.get("step") or "1").strip()
        if step == "1":
            email = (request.POST.get("email") or "").strip().lower()
            if not verify_login_bot_gate(request):
                refresh_login_bot_challenge(request)
                messages.error(request, login_gate_fail_message())
                return _code_page({"step": 1, "email": email})
            if not email:
                messages.error(request, "Enter your email address.")
                refresh_login_bot_challenge(request)
                return _code_page({"step": 1, "email": ""})
            try:
                login_otp_request(email)
            except ApiError as e:
                refresh_login_bot_challenge(request)
                messages.error(request, _err_msg(e))
                return _code_page({"step": 1, "email": email})
            request.session["login_otp_email"] = email
            messages.success(
                request,
                "If that email is registered and verified, we sent a 6-digit code. It expires in 15 minutes.",
            )
            return redirect("login_code")
        # step 2
        email = (request.session.get("login_otp_email") or "").strip().lower()
        code = (request.POST.get("code") or "").strip().replace(" ", "")
        if not verify_login_bot_gate(request):
            refresh_login_bot_challenge(request)
            messages.error(request, login_gate_fail_message())
            return _code_page({"step": 2, "email": email})
        if not email:
            messages.error(request, "Start again and request a new code.")
            return redirect("login_code")
        if len(code) != 6 or not code.isdigit():
            refresh_login_bot_challenge(request)
            messages.error(request, "Enter the 6-digit code from your email.")
            return _code_page({"step": 2, "email": email})
        try:
            body = login_otp_verify(email, code)
        except ApiError as e:
            refresh_login_bot_challenge(request)
            detail = e.detail
            if isinstance(detail, dict) and "detail" in detail:
                msg = detail["detail"]
            else:
                msg = str(detail or e.message)
            messages.error(request, msg)
            return _code_page({"step": 2, "email": email})

        request.session.pop("login_otp_email", None)
        nxt = _apply_login_response_to_session(request, body)
        if nxt == "__no_orgs__":
            messages.error(request, "Your account is not linked to any organisation. Contact a platform administrator.")
            refresh_login_bot_challenge(request)
            return render(request, "accounts/login.html", prepare_login_get_page(request))
        if nxt == "dashboard":
            messages.success(request, "Signed in.")
            return redirect("dashboard")
        messages.success(
            request,
            "Signed in. Choose an organisation to continue."
            if not request.session.get("is_platform_user")
            else "Signed in. Choose your workspace to continue.",
        )
        return redirect("select_organisation")

    return render(
        request,
        "accounts/login_code.html",
        {**prepare_login_get_page(request), **ctx},
    )


def logout_view(request):
    request.session.flush()
    messages.info(request, "Signed out.")
    return redirect("home")


def _require_api_token(request):
    if not request.session.get("access_token"):
        return redirect("login")
    return None


@require_http_methods(["GET", "POST"])
def select_organisation_view(request):
    if red := _require_api_token(request):
        return red
    orgs = _session_orgs(request)
    is_plat = _is_platform(request)

    if not is_plat:
        if len(orgs) == 0:
            messages.error(request, "No organisations available for your account.")
            return redirect("logout")
        if len(orgs) == 1:
            request.session["organisation_id"] = str(orgs[0]["id"])
            request.session["workspace_scope_confirmed"] = True
            messages.info(request, "Organisation selected.")
            return redirect("dashboard")

    if request.method == "POST":
        # Single-org members never use the picker; ignore forged POSTs.
        if not is_plat and len(orgs) == 1:
            request.session["organisation_id"] = str(orgs[0]["id"])
            request.session["workspace_scope_confirmed"] = True
            request.session.modified = True
            return redirect("dashboard")
        choice = (request.POST.get("organisation_id") or "").strip()
        if is_plat and choice == "__all__":
            request.session.pop("organisation_id", None)
            request.session["workspace_scope_confirmed"] = True
            messages.success(request, "Workspace: all organisations.")
            return redirect("dashboard")
        valid = {str(o.get("id")) for o in orgs if isinstance(o, dict)}
        if choice not in valid:
            messages.error(request, "Please choose a valid organisation.")
        else:
            request.session["organisation_id"] = choice
            request.session["workspace_scope_confirmed"] = True
            messages.success(request, "Organisation selected.")
            return redirect("dashboard")

    return render(
        request,
        "accounts/select_organisation.html",
        {
            "organisations": orgs,
            "is_platform_user": is_plat,
            "current_organisation_id": request.session.get("organisation_id"),
        },
    )


def _send_invite_email(
    request, resp: dict, org_id: str, display_name: str | None, *, reminder: bool = False
) -> None:
    org_name = _org_name_for_id(request, org_id)
    path = reverse("verify_email") + "?" + urlencode({"token": resp["verification_token"]})
    verify_url = request.build_absolute_uri(path)
    send_user_invite_email(
        to_email=resp["email"],
        organisation_name=org_name,
        verify_url=verify_url,
        temporary_password=resp["temporary_password"],
        display_name=display_name,
        reminder=reminder,
    )


def _flash_invite_email_outcome(request, recipient_email: str) -> None:
    """After a successful Django mail send(): explain console vs real SMTP so admins are not misled."""
    if email_delivery_is_console_only():
        messages.warning(
            request,
            (
                f"Account created for {recipient_email}. "
                "No email was delivered to their inbox: SMTP is not configured (set EMAIL_HOST_USER and "
                "EMAIL_HOST_PASSWORD in web/.env). The invitation is only printed in the terminal where "
                "Django runs—copy the verify link and temporary password from there, or configure SMTP "
                "(docs/EMAIL_SETTINGS.md)."
            ),
        )
    else:
        messages.success(
            request,
            f"Invitation sent to {recipient_email}. They must verify email before signing in.",
        )


@require_http_methods(["GET", "POST"])
def invite_user_platform_view(request):
    """Platform users: invite to any organisation."""
    if red := _require_api_token(request):
        return red
    if not _is_platform(request):
        messages.error(request, "Only platform users can invite people to any organisation.")
        return redirect("dashboard")
    token = request.session["access_token"]
    orgs = _session_orgs(request)
    if not orgs:
        messages.error(request, "There are no organisations yet. Create one first.")
        return redirect("create_organisation")

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        display_name = (request.POST.get("display_name") or "").strip() or None
        org_id = (request.POST.get("organisation_id") or "").strip()
        valid = {str(o.get("id")) for o in orgs if isinstance(o, dict)}
        ctx = {"organisations": orgs, "invite_title": "Invite user (any organisation)", "invite_mode": "platform"}
        if org_id not in valid:
            messages.error(request, "Choose a valid organisation.")
            return render(request, "accounts/invite_user.html", {**ctx, "email": email, "display_name": display_name or "", "organisation_id": org_id})
        if not email:
            messages.error(request, "Email is required.")
            return render(request, "accounts/invite_user.html", {**ctx, "email": "", "display_name": display_name or "", "organisation_id": org_id})
        try:
            resp = api_post_json(
                "/admin/users/invite",
                token,
                {"email": email, "organisation_id": org_id, "display_name": display_name},
            )
        except ApiError as e:
            messages.error(request, _err_msg(e))
            return render(request, "accounts/invite_user.html", {**ctx, "email": email, "display_name": display_name or "", "organisation_id": org_id})
        try:
            _send_invite_email(request, resp, org_id, display_name)
            _flash_invite_email_outcome(request, resp["email"])
        except Exception as exc:
            logger.exception("invite email failed")
            messages.warning(request, f"User was created but email failed ({exc}). Share verify link and password securely.")
        return redirect("invite_user_platform")

    return render(
        request,
        "accounts/invite_user.html",
        {
            "organisations": orgs,
            "invite_title": "Invite user (any organisation)",
            "invite_mode": "platform",
        },
    )


@require_http_methods(["GET", "POST"])
def invite_user_organisation_view(request):
    """Organisation user-admins: invite only to the current workspace organisation."""
    if red := _require_api_token(request):
        return red
    if not request.session.get("user_admin_access"):
        messages.error(request, "You need organisation user-admin access to invite people to your organisation.")
        return redirect("dashboard")
    org_id = request.session.get("organisation_id")
    if not org_id:
        messages.error(request, "Choose an organisation first.")
        return redirect("select_organisation")
    token = request.session["access_token"]
    org_name = _org_name_for_id(request, org_id)

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        display_name = (request.POST.get("display_name") or "").strip() or None
        ctx = {
            "invite_title": "Invite team member",
            "invite_mode": "organisation",
            "fixed_organisation_id": org_id,
            "fixed_organisation_name": org_name,
        }
        if not email:
            messages.error(request, "Email is required.")
            return render(request, "accounts/invite_user.html", {**ctx, "email": "", "display_name": display_name or ""})
        try:
            resp = api_post_json(
                "/admin/users/invite",
                token,
                {"email": email, "organisation_id": org_id, "display_name": display_name},
                organisation_id=org_id,
            )
        except ApiError as e:
            messages.error(request, _err_msg(e))
            return render(request, "accounts/invite_user.html", {**ctx, "email": email, "display_name": display_name or ""})
        try:
            _send_invite_email(request, resp, org_id, display_name)
            _flash_invite_email_outcome(request, resp["email"])
        except Exception as exc:
            logger.exception("invite email failed")
            messages.warning(request, f"User was created but email failed ({exc}). Share verify link and password securely.")
        return redirect("invite_user_organisation")

    return render(
        request,
        "accounts/invite_user.html",
        {
            "invite_title": "Invite team member",
            "invite_mode": "organisation",
            "fixed_organisation_id": org_id,
            "fixed_organisation_name": org_name,
        },
    )


@require_http_methods(["GET", "POST"])
def create_organisation_view(request):
    if red := _require_api_token(request):
        return red
    if not _is_platform(request):
        messages.error(request, "Only platform users can create organisations.")
        return redirect("dashboard")
    token = request.session["access_token"]

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        slug = (request.POST.get("slug") or "").strip() or None
        description = (request.POST.get("description") or "").strip() or None
        logo = request.FILES.get("logo")
        if not name:
            messages.error(request, "Organisation name is required.")
            return render(request, "accounts/create_organisation.html", {"name": "", "slug": slug or "", "description": description or ""})
        form_data = {"name": name}
        if slug:
            form_data["slug"] = slug
        if description:
            form_data["description"] = description
        try:
            if logo:
                data = logo.read()
                ct = logo.content_type or "application/octet-stream"
                created = api_post_multipart(
                    "/organisations",
                    token,
                    {"logo": (logo.name, data, ct)},
                    data=form_data,
                )
            else:
                created = api_post_form("/organisations", token, form_data)
        except ApiError as e:
            messages.error(request, _err_msg(e))
            return render(
                request,
                "accounts/create_organisation.html",
                {"name": name, "slug": slug or "", "description": description or ""},
            )
        messages.success(request, f"Organisation “{created.get('name', name)}” created.")
        try:
            orgs = api_get("/organisations", token) or []
            request.session["organisations"] = orgs
            request.session.modified = True
        except ApiError:
            pass
        return redirect("create_organisation")

    return render(request, "accounts/create_organisation.html", {})


def _org_header_for_admin_api(request) -> str | None:
    """Platform users omit header; org user-admins must send current workspace org."""
    if _is_platform(request):
        return None
    oid = request.session.get("organisation_id")
    return str(oid) if oid else None


def _user_profile_edit_org_context(request, is_plat: bool) -> tuple[str | None, str]:
    """Resolve X-Organisation-Id for admin profile API; org context from POST body or session (no URL query)."""
    if request.method == "POST":
        q = (request.POST.get("organisation_id") or "").strip()
    else:
        q = (request.GET.get("organisation_id") or "").strip()
        if not q:
            q = (request.session.get(SESSION_KEY_ORG_USERS_LIST) or "").strip()

    if q and _org_in_session(request, q):
        header: str | None = q
    elif is_plat:
        header = None
    else:
        oid = request.session.get("organisation_id")
        header = str(oid) if oid else None

    ui_org = q
    if not ui_org and not is_plat:
        ui_org = str(request.session.get("organisation_id") or "")
    if is_plat and not ui_org:
        ui_org = str(request.session.get(SESSION_KEY_ORG_USERS_LIST) or "")
    return header, ui_org


def _redirect_organisation_users_after_profile_error(request):
    return redirect("organisation_users_manage")


@require_http_methods(["GET", "POST"])
def manage_organisation_users_view(request):
    """Platform: pick organisation. Platform or org user-admin: list members, invite, resend."""
    if red := _require_api_token(request):
        return red
    is_plat = _is_platform(request)
    is_org_admin = bool(request.session.get("user_admin_access"))
    if not is_plat and not is_org_admin:
        messages.error(
            request,
            "You need platform access or organisation user-admin access to manage organisation members.",
        )
        return redirect("dashboard")
    token = request.session["access_token"]

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "reset_org_list":
            request.session.pop(SESSION_KEY_ORG_USERS_LIST, None)
            request.session.modified = True
            return redirect(reverse("organisation_users_manage"))

        oid = (request.POST.get("organisation_id") or "").strip()
        if not oid or not _org_in_session(request, oid):
            messages.error(request, "Invalid organisation.")
            return redirect("organisation_users_manage")
        request.session[SESSION_KEY_ORG_USERS_LIST] = oid
        request.session.modified = True
        next_url = reverse("organisation_users_manage")

        if action == "invite":
            email = (request.POST.get("email") or "").strip().lower()
            display_name = (request.POST.get("display_name") or "").strip() or None
            if not email:
                messages.error(request, "Email is required.")
                return redirect(next_url)
            try:
                resp = api_post_json(
                    "/admin/users/invite",
                    token,
                    {"email": email, "organisation_id": oid, "display_name": display_name},
                )
            except ApiError as e:
                messages.error(request, _err_msg(e))
                return redirect(next_url)
            try:
                _send_invite_email(request, resp, oid, display_name)
                _flash_invite_email_outcome(request, resp["email"])
            except Exception as exc:
                logger.exception("invite email failed")
                messages.warning(
                    request,
                    f"User was created but the invitation email could not be sent ({exc}). "
                    "Share the verify link and temporary password securely.",
                )
            return redirect(next_url)

        if action == "resend_invite":
            uid = (request.POST.get("user_id") or "").strip()
            if not uid:
                messages.error(request, "Missing user.")
                return redirect(next_url)
            try:
                resp = api_post_json(
                    f"/admin/users/{uid}/resend-invite",
                    token,
                    {"organisation_id": oid},
                )
            except ApiError as e:
                messages.error(request, _err_msg(e))
                return redirect(next_url)
            try:
                _send_invite_email(request, resp, oid, None, reminder=True)
                _flash_invite_email_outcome(request, resp["email"])
            except Exception as exc:
                logger.exception("resend invite email failed")
                messages.warning(
                    request,
                    f"Invitation was refreshed but the email could not be sent ({exc}). "
                    "Share the verify link and temporary password securely.",
                )
            return redirect(next_url)

        if action == "set_user_admin":
            if not is_plat:
                messages.error(request, "Only platform users can change organisation user-admin access.")
                return redirect(next_url)
            uid = (request.POST.get("user_id") or "").strip()
            raw = (request.POST.get("user_admin_access") or "").strip().lower()
            grant = raw in ("true", "1", "yes", "on")
            if not uid:
                messages.error(request, "Missing user.")
                return redirect(next_url)
            try:
                api_patch_json(f"/admin/users/{uid}", token, {"user_admin_access": grant})
            except ApiError as e:
                messages.error(request, _err_msg(e))
                return redirect(next_url)
            messages.success(
                request,
                "Organisation user-admin access enabled." if grant else "Organisation user-admin access removed.",
            )
            return redirect(next_url)

        messages.error(request, "Unknown action.")
        return redirect("organisation_users_manage")

    raw_q = (request.GET.get("organisation_id") or "").strip()
    q_org = raw_q or (request.session.get(SESSION_KEY_ORG_USERS_LIST) or "").strip()

    if not q_org:
        if is_plat:
            request.session.pop(SESSION_KEY_ORG_USERS_LIST, None)
            request.session.modified = True
            return render(
                request,
                "accounts/organisation_users_pick.html",
                {"organisations": _session_orgs(request)},
            )
        oid = request.session.get("organisation_id")
        if not oid:
            messages.error(request, "Choose an organisation to manage members.")
            return redirect("select_organisation")
        request.session[SESSION_KEY_ORG_USERS_LIST] = str(oid)
        request.session.modified = True
        return redirect(reverse("organisation_users_manage"))

    if not _org_in_session(request, q_org):
        messages.error(request, "That organisation is not in your list. Refresh or sign in again.")
        request.session.pop(SESSION_KEY_ORG_USERS_LIST, None)
        request.session.modified = True
        return redirect("organisation_users_manage")

    try:
        members = api_get(
            f"/admin/organisations/{q_org}/users",
            token,
            organisation_id=_org_header_for_admin_api(request),
        ) or []
    except ApiError as e:
        messages.error(request, _err_msg(e))
        return redirect("organisation_users_manage")

    if not isinstance(members, list):
        members = []

    request.session[SESSION_KEY_ORG_USERS_LIST] = str(q_org)
    request.session.modified = True
    if raw_q:
        return redirect(reverse("organisation_users_manage"))

    return render(
        request,
        "accounts/organisation_users.html",
        {
            "organisation_id": q_org,
            "organisation_name": _org_name_for_id(request, q_org),
            "members": members,
            "is_platform_user": is_plat,
        },
    )


@require_http_methods(["GET", "POST"])
def verify_email_view(request):
    token = (request.GET.get("token") or request.POST.get("token") or "").strip()
    if request.method == "POST":
        if not token:
            messages.error(request, "Verification token is missing.")
        else:
            try:
                verify_email(token)
                if request.session.get("access_token"):
                    messages.success(request, "Verification complete.")
                    refresh_session_nav_user(request)
                    return redirect("profile")
                messages.success(request, "Email verified. You can sign in.")
                return redirect("login")
            except ApiError as e:
                messages.error(request, _err_msg(e))
    return render(request, "accounts/verify_email.html", {"token": token})


def _normalize_me_for_profile(me: dict) -> dict:
    if not isinstance(me.get("social_handles"), dict):
        me["social_handles"] = {}
    return me


def _profile_patch_from_post(request) -> dict:
    patch: dict = {}
    for key in ("display_name", "first_name", "last_name", "job_title"):
        v = (request.POST.get(key) or "").strip()
        patch[key] = v or None
    dob = (request.POST.get("date_of_birth") or "").strip()
    patch["date_of_birth"] = dob if dob else None
    dial = (request.POST.get("phone_country_dial") or "").strip()
    national = (request.POST.get("phone_national") or "").strip().replace(" ", "").replace("-", "")
    digits = "".join(c for c in national if c.isdigit())
    if digits:
        d = dial if dial.startswith("+") else (f"+{dial.lstrip('+')}" if dial else "+")
        patch["phone_e164"] = f"{d}{digits}"
    else:
        patch["phone_e164"] = None
    sh = {}
    for key, field in (
        ("twitter", "social_twitter"),
        ("linkedin", "social_linkedin"),
        ("github", "social_github"),
        ("instagram", "social_instagram"),
        ("other", "social_other"),
    ):
        s = (request.POST.get(field) or "").strip()
        if s:
            sh[key] = s
    patch["social_handles"] = sh
    return patch


def _phone_parts_from_e164(e164: str | None) -> tuple[str, str]:
    if not e164 or not str(e164).strip():
        return ("+61", "")
    s = str(e164).strip()
    if not s.startswith("+"):
        return ("+61", s)
    common = ("+61", "+1", "+44", "+64", "+91", "+86", "+81", "+49", "+33", "+353")
    for p in sorted(common, key=len, reverse=True):
        if s.startswith(p):
            return (p, s[len(p) :])
    return (s[:3], s[3:])


def _profile_display_from_post(request, base_me: dict) -> tuple[dict, str, str]:
    """Rebuild profile `me` and phone row from POST so the form can be re-shown after an API error."""
    me = {**base_me}
    _normalize_me_for_profile(me)
    me["display_name"] = request.POST.get("display_name") or ""
    me["first_name"] = request.POST.get("first_name") or ""
    me["last_name"] = request.POST.get("last_name") or ""
    me["date_of_birth"] = request.POST.get("date_of_birth") or ""
    me["job_title"] = request.POST.get("job_title") or ""
    dial = (request.POST.get("phone_country_dial") or "").strip() or "+61"
    if not dial.startswith("+"):
        dial = f"+{dial.lstrip('+')}"
    national = request.POST.get("phone_national") or ""
    patch = _profile_patch_from_post(request)
    me["phone_e164"] = patch.get("phone_e164")
    sh = {}
    for key, field in (
        ("twitter", "social_twitter"),
        ("linkedin", "social_linkedin"),
        ("github", "social_github"),
        ("instagram", "social_instagram"),
        ("other", "social_other"),
    ):
        sh[key] = request.POST.get(field) or ""
    me["social_handles"] = sh
    return me, dial, national


def _render_profile_page(
    request,
    *,
    me: dict,
    profile_mode: str,
    phone_dial: str,
    phone_national: str,
    form_new_email_request: str = "",
    profile_list_organisation_id: str = "",
):
    return render(
        request,
        "accounts/profile.html",
        {
            "me": me,
            "profile_mode": profile_mode,
            "phone_dial": phone_dial,
            "phone_national": phone_national,
            "form_new_email_request": form_new_email_request,
            "profile_list_organisation_id": profile_list_organisation_id,
        },
    )


@require_http_methods(["GET", "POST"])
def profile_view(request):
    if red := _require_api_token(request):
        return red
    token = request.session["access_token"]

    if request.method == "POST":
        patch = _profile_patch_from_post(request)
        new_email_req = (request.POST.get("new_email_request") or "").strip().lower()
        new_email_raw = request.POST.get("new_email_request") or ""

        def _reload_me_for_form() -> dict:
            return _normalize_me_for_profile(api_get("/auth/me", token))

        try:
            api_patch_json("/auth/me", token, patch)
        except ApiError as e:
            messages.error(request, _err_msg(e))
            try:
                base = _reload_me_for_form()
            except ApiError as e2:
                messages.error(request, _err_msg(e2))
                return redirect("dashboard")
            m, d, n = _profile_display_from_post(request, base)
            return _render_profile_page(
                request,
                me=m,
                profile_mode="self",
                phone_dial=d,
                phone_national=n,
                form_new_email_request=new_email_raw,
            )

        if new_email_req:
            try:
                api_post_json("/auth/me/request-email-change", token, {"new_email": new_email_req})
                messages.success(
                    request,
                    "If that address is available, we sent a confirmation link to it. Your sign-in email stays the same until you confirm.",
                )
            except ApiError as e:
                messages.error(request, _err_msg(e))
                try:
                    base = _reload_me_for_form()
                except ApiError as e2:
                    messages.error(request, _err_msg(e2))
                    return redirect("dashboard")
                m, d, n = _profile_display_from_post(request, base)
                return _render_profile_page(
                    request,
                    me=m,
                    profile_mode="self",
                    phone_dial=d,
                    phone_national=n,
                    form_new_email_request=new_email_raw,
                )

        f = request.FILES.get("avatar")
        if f:
            try:
                data = f.read()
                ct = f.content_type or "application/octet-stream"
                api_post_multipart(
                    "/auth/me/avatar",
                    token,
                    {"file": (f.name, data, ct)},
                    organisation_id=(request.session.get("organisation_id") or None),
                )
            except ApiError as e:
                messages.error(request, _err_msg(e))
                try:
                    base = _reload_me_for_form()
                except ApiError as e2:
                    messages.error(request, _err_msg(e2))
                    return redirect("dashboard")
                m, d, n = _profile_display_from_post(request, base)
                return _render_profile_page(
                    request,
                    me=m,
                    profile_mode="self",
                    phone_dial=d,
                    phone_national=n,
                    form_new_email_request=new_email_raw,
                )

        refresh_session_nav_user(request)
        messages.success(request, "Profile saved.")
        return redirect("profile")

    try:
        me = _normalize_me_for_profile(api_get("/auth/me", token))
    except ApiError as e:
        messages.error(request, _err_msg(e))
        return redirect("dashboard")
    dial, nat = _phone_parts_from_e164(me.get("phone_e164"))
    return _render_profile_page(
        request,
        me=me,
        profile_mode="self",
        phone_dial=dial,
        phone_national=nat,
        form_new_email_request="",
    )


@require_http_methods(["GET", "POST"])
def change_password_view(request):
    if red := _require_api_token(request):
        return red
    token = request.session["access_token"]

    if request.method == "POST":
        cur = request.POST.get("current_password", "")
        new = request.POST.get("new_password", "").strip()
        conf = request.POST.get("new_password_confirm", "").strip()
        if new != conf:
            messages.error(request, "New password and confirmation do not match.")
            return redirect("change_password")
        if len(new) < 8:
            messages.error(request, "New password must be at least 8 characters.")
            return redirect("change_password")
        if not cur:
            messages.error(request, "Enter your current password.")
            return redirect("change_password")
        try:
            me_pw = api_get("/auth/me", token)
        except ApiError:
            me_pw = {}
        if not me_pw.get("has_password"):
            messages.error(request, "This account has no password to change.")
            return redirect("change_password")
        try:
            api_post_json("/auth/me/password", token, {"current_password": cur, "new_password": new})
        except ApiError as e:
            messages.error(request, _err_msg(e))
            return redirect("change_password")
        messages.success(request, "Password updated.")
        return redirect("change_password")

    try:
        me = api_get("/auth/me", token)
    except ApiError as e:
        messages.error(request, _err_msg(e))
        return redirect("dashboard")
    return render(request, "accounts/change_password.html", {"me": me})


@require_http_methods(["GET", "POST"])
def user_profile_edit_view(request, user_id):
    """Platform or org user-admin: edit another user in scope (shared organisation)."""
    if red := _require_api_token(request):
        return red
    token = request.session["access_token"]
    uid = str(user_id)
    is_plat = _is_platform(request)
    if not is_plat and not request.session.get("user_admin_access"):
        messages.error(request, "You do not have permission to edit other users.")
        return redirect("dashboard")
    if not is_plat and not request.session.get("organisation_id"):
        messages.error(request, "Choose an organisation first.")
        return redirect("select_organisation")
    org_header, ui_org = _user_profile_edit_org_context(request, is_plat)

    if request.method == "POST":
        patch = _profile_patch_from_post(request)
        admin_email = (request.POST.get("admin_email") or "").strip().lower()
        if admin_email:
            patch["email"] = admin_email
        try:
            api_patch_json(f"/admin/users/{uid}/profile", token, patch, organisation_id=org_header)
        except ApiError as e:
            messages.error(request, _err_msg_profile_admin_api(e))
            try:
                base = _normalize_me_for_profile(
                    api_get(f"/admin/users/{uid}/profile", token, organisation_id=org_header)
                )
            except ApiError as e2:
                messages.error(request, _err_msg_profile_admin_api(e2))
                return _redirect_organisation_users_after_profile_error(request)
            m, d, n = _profile_display_from_post(request, base)
            ae = (request.POST.get("admin_email") or "").strip()
            if ae:
                m["email"] = ae
            return _render_profile_page(
                request,
                me=m,
                profile_mode="admin",
                phone_dial=d,
                phone_national=n,
                form_new_email_request="",
                profile_list_organisation_id=ui_org,
            )
        messages.success(request, "Profile updated.")
        return redirect(reverse("user_profile_edit", kwargs={"user_id": user_id}))

    try:
        target = _normalize_me_for_profile(
            api_get(f"/admin/users/{uid}/profile", token, organisation_id=org_header)
        )
    except ApiError as e:
        messages.error(request, _err_msg_profile_admin_api(e))
        return _redirect_organisation_users_after_profile_error(request)
    dial, nat = _phone_parts_from_e164(target.get("phone_e164"))
    return _render_profile_page(
        request,
        me=target,
        profile_mode="admin",
        phone_dial=dial,
        phone_national=nat,
        form_new_email_request="",
        profile_list_organisation_id=ui_org,
    )
