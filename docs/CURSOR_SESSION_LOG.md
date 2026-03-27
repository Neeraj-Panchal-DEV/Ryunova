# Cursor session log

Short notes from AI pairing sessions so they **travel with the repo** (Git). Cursor chat history itself stays on each machine unless Cursor syncs it for your account.

**Also see:** [DESIGN_DEVELOPMENT_HISTORY.md](DESIGN_DEVELOPMENT_HISTORY.md), [CONVERSATION_HISTORY.md](CONVERSATION_HISTORY.md), [MULTI_TENANT.md](MULTI_TENANT.md).

---

## Template (copy per session)

```text
### YYYY-MM-DD — <one-line topic>

- **Asked / goal:**
- **Decisions / changes:** (files, env, DB)
- **Commands / URLs worth remembering:**
- **Follow-ups:**
```

---

## Entries

### 2026-03-25 — Catalog save 500 + LAN images

- **Asked / goal:** Product/category/brand saves failing; images broken when using LAN IP.
- **Decisions / changes:** Added `OrganisationContext.require_organisation_id()` (was missing → AttributeError/500). Django `RewriteApiPublicUrlMiddleware` rewrites `http://127.0.0.1:8000` / `localhost:8000` in HTML/JSON to the request host + API port when `RYUNOVA_REWRITE_API_PUBLIC_IN_RESPONSES` (default on in DEBUG). Improved quick-add `fetch` error parsing for API `detail`.
- **Follow-ups:** Platform users in **All organisations** must **scope one org** before creating catalog rows.

### 2026-03-24 — Session log + dev ergonomics

- **Asked / goal:** Repo-local place to record Cursor/agent context for other machines.
- **Decisions / changes:** Added this file; optional `python-dotenv` in Django settings.
