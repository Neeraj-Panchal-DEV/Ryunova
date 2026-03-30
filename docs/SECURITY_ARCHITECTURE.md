# User and organisation security — architecture and implementation

This document describes how **authentication**, **organisation (tenant) scoping**, and **defence in depth** work across the FastAPI API and the Django web app. For product concepts (platform user, user admin), see **[MULTI_TENANT.md](MULTI_TENANT.md)**.

---

## 1. Architecture overview

| Layer | Responsibility |
|--------|----------------|
| **PostgreSQL** | Source of truth: users, `ryunova_user_organisations` (membership), org-scoped catalog rows. |
| **FastAPI** | JWT validation, **mandatory membership checks** for tenant-scoped routes, admin rules (platform vs org admin). |
| **Django** | Session-backed UI; sends the same JWT and `X-Organisation-Id` as the browser would not control alone; **session reconciliation** prevents inconsistent or forged workspace scope between page loads. |

**Principle:** The API never trusts Django’s session alone. Every protected API call is authorised with **Bearer token** +, where required, **`X-Organisation-Id`** checked against **live database membership** (or platform rules).

---

## 2. Authentication

- **Mechanism:** JWT (`Authorization: Bearer`) issued by FastAPI on successful login (password or login-OTP). The Django app stores the access token in the server-side session (`access_token`); it is not the full story for authorisation without the API’s user + membership checks.
- **Login eligibility:** Active user, verified email (`email_verified_at`), valid password (or OTP flow). See backend auth routes under `backend/app/routers/auth.py`.
- **Session lifecycle:** Logout uses `session.flush()` (clears token and workspace data). HTTPS and cookie flags in production are described in **[DEPLOYMENT_EC2_ALB.md](DEPLOYMENT_EC2_ALB.md)** (`USE_TLS_BEHIND_PROXY`, `SESSION_COOKIE_SECURE`, etc.).

Optional bot mitigation on login (Turnstile or built-in challenge) is documented in **[TURNSTILE.md](TURNSTILE.md)**.

---

## 3. Authorisation concepts

| Concept | Meaning |
|---------|---------|
| **`is_platform_user`** | Product/platform operator: may list all organisations, optional global “read” mode without `X-Organisation-Id`; creating organisations and certain admin actions are restricted to this role. Alias `is_system_user` in some JSON is identical (legacy). |
| **`user_admin_access`** | Organisation **user admin**: may invite users **only** into organisations they belong to; enforced in API handlers. |
| **Membership** | Non-platform users may only act within organisations linked in `ryunova_user_organisations`. |

---

## 4. API: organisation context (`X-Organisation-Id`)

**Implementation:** `backend/app/org_access.py` — `get_organisation_context` / `OrganisationContextDep`.

- **Non–platform users:** Must send `X-Organisation-Id` for routes that depend on `OrganisationContext`. The UUID is validated; **`user_has_org_membership`** must return true, otherwise **403 Forbidden**.
- **Platform users:** May omit the header (or use `all`) for **read-all** mode (`organisation_id is None`). For a specific org, the header must reference an existing organisation. **Writes** that require a tenant (e.g. catalog mutations) call `require_organisation_id()` — global read-all mode cannot perform those until a scope is chosen (400 with a clear message).

Admin routes (e.g. invites, listing org users) apply additional checks: platform-only vs `user_admin_access` + membership as documented in **[MULTI_TENANT.md](MULTI_TENANT.md)**.

---

## 5. Django: session and workspace scope

The web UI mirrors API rules using **session keys** set at login from the login response (which includes the user’s **organisation list**):

| Session key | Purpose |
|-------------|---------|
| `access_token` | JWT for server-side API calls. |
| `organisations` | Snapshot of orgs the user may access (platform: all orgs; others: memberships). |
| `organisation_id` | Current workspace scope (optional for platform “all orgs” mode). |
| `workspace_scope_confirmed` | User completed org selection (or single-org auto scope). |
| `is_platform_user`, `user_admin_access` | Drives menus and which views are reachable. |
| `organisation_users_list_org_id` | Which org the **Organisation users** admin screen is scoped to (platform org picker / non-platform current org). |

**Implementation files:**

- `web/ryunova_web/workspace.py` — `workspace_scope_confirmed`, `needs_workspace_selection`, `reconcile_workspace_session`.
- `web/ryunova_web/middleware.py` — `WorkspaceSessionMiddleware` runs **after** `SessionMiddleware` and calls `reconcile_workspace_session` on every request.

### 5.1 Session reconciliation (defence in depth)

`reconcile_workspace_session` aligns the session with the **login-time organisation list** so devtools or stale tabs cannot leave the UI in an inconsistent state:

- **Non–platform, multiple orgs:** If `organisation_id` is not in `organisations`, it is cleared and workspace scope is marked unconfirmed (user is sent through **Choose organisation** again).
- **Non–platform, single org:** `organisation_id` is always forced to that org and scope is confirmed (no org switcher UI).
- **Platform:** If `organisation_id` is set but not in the session org list (e.g. stale), it is cleared.
- **`organisation_users_list_org_id`:** If set and **not** in the same membership list, it is removed so the org-users admin UI cannot stay pinned to a foreign org id.

The API still enforces membership on every call; reconciliation protects the **Django UX and session integrity** only.

### 5.2 Org picker and menus

- **Single-org members:** No **Change organisation** entry and no org block in the account menu; direct navigation to `/accounts/select-organisation/` redirects back to the dashboard with scope fixed.
- **Multi-org members and platform users:** Picker and switcher behave as in **[MULTI_TENANT.md](MULTI_TENANT.md)**.

Catalog and dashboard views require a confirmed workspace (`_require_workspace` in `web/catalog/views.py` and related patterns in accounts).

---

## 6. Data access and media

- **Catalog and tenant APIs:** Scoped by `organisation_id` in `OrganisationContext` (see FastAPI routers under `backend/app/routers/`).
- **Profile / avatars:** Organisation context for uploads uses validated membership (see auth/profile routes in the API). Media URLs and disk/S3 layout are covered in **[DEPLOYMENT_EC2_ALB.md](DEPLOYMENT_EC2_ALB.md)** (media paths, `api.*` routing).

---

## 7. Operational notes

- **Membership changes** (adding/removing a user from an org) take effect in the database immediately for **API** calls. The Django **session** still holds a **login-time list of organisations** until the user signs out and signs in again (or you add a future “refresh session” feature). Reconciliation only validates against that snapshot.
- **At least one platform user** should remain; bootstrap SQL patterns are in **[MULTI_TENANT.md](MULTI_TENANT.md)**.

---

## 8. Related code paths (quick reference)

| Area | Location |
|------|----------|
| Org context dependency | `backend/app/org_access.py` |
| JWT / current user | `backend/app/dependencies.py` |
| Login response org list | `backend/app/routers/auth.py` (`_login_response_for_user`) |
| Workspace reconciliation | `web/ryunova_web/workspace.py` |
| Middleware | `web/ryunova_web/middleware.py` (`WorkspaceSessionMiddleware`) |
| API client headers | `web/ryunova_web/api_client.py` (`X-Organisation-Id`) |
| Org picker view | `web/accounts/views.py` (`select_organisation_view`) |

---

*For environment variables and secrets, see **[ENVIRONMENT.md](ENVIRONMENT.md)** and **[DEPLOYMENT_EC2_ALB.md](DEPLOYMENT_EC2_ALB.md)**.*
