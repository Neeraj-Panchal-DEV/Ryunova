import json
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qsl, urlencode, urlsplit
from uuid import UUID

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from ryunova_web.api_client import ApiError, api_delete, api_get, api_patch_json, api_post_json, api_post_multipart
from ryunova_web.currency_choices import CURRENCY_CHOICES, normalize_currency_code
from ryunova_web.workspace import needs_workspace_selection


def _token(request):
    return request.session.get("access_token")


def _parse_import_attributes_json(request) -> dict | None:
    raw = (request.POST.get("import_attributes_json") or "").strip()
    if not raw:
        return None
    try:
        d = json.loads(raw)
        return d if isinstance(d, dict) else None
    except json.JSONDecodeError:
        return None


def _merge_product_attributes(existing: dict | None, overlay: dict | None) -> dict | None:
    if not existing and not overlay:
        return None
    out = dict(existing or {})
    if overlay:
        out.update(overlay)
    return out if out else None


def _post_optional_uuid_str(raw: str | None) -> str | None:
    """Empty / missing optional FK from POST → None for JSON (never the string 'None' from str(None))."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.lower() in ("none", "null"):
        return None
    return s


def _product_form_dimension_cm(raw: str | None) -> str | None:
    """Optional L/W/D in centimetres; returns string for API JSON or None if empty."""
    v = (raw or "").strip()
    if not v:
        return None
    try:
        d = Decimal(v)
    except InvalidOperation as e:
        raise ValueError("Length, width, and depth must be valid numbers (centimetres).") from e
    if d < 0:
        raise ValueError("Dimensions cannot be negative.")
    return str(d)


def _product_draft_from_post(request) -> dict:
    """Repopulate product form after validation/API errors (file inputs cannot be restored by browsers)."""
    post = request.POST
    return {
        "title": (post.get("title") or "").strip(),
        "description": post.get("description") or "",
        "condition": (post.get("condition") or "new").strip(),
        "brand_id": (post.get("brand_id") or "").strip() or None,
        "category_id": (post.get("category_id") or "").strip() or None,
        "model": (post.get("model") or "").strip() or "",
        "colour": (post.get("colour") or "").strip() or "",
        "length_cm": (post.get("length_cm") or "").strip(),
        "width_cm": (post.get("width_cm") or "").strip(),
        "depth_cm": (post.get("depth_cm") or "").strip(),
        # NEW FIELDS START
        "weight_kg": (post.get("weight_kg") or "").strip(),
        "cost_price": (post.get("cost_price") or "").strip(),
        "barcode": (post.get("barcode") or "").strip(),
        "hs_code": (post.get("hs_code") or "").strip(),
        "allow_oversell": post.get("allow_oversell") == "1",
        # NEW FIELDS END
        "weight_kg": (post.get("weight_kg") or "").strip(),
        "base_price": (post.get("base_price") or "0").strip(),
        "currency_code": normalize_currency_code(post.get("currency_code")),
        "compare_at_price": (post.get("compare_at_price") or "").strip(),
        "quantity": (post.get("quantity") or "1").strip(),
        "status": (post.get("status") or "active").strip(),
        "active": post.get("active") == "1",
        "cover_index": (post.get("cover_index") or "0").strip(),
        "image_url": (post.get("image_url") or "").strip(),
        "image_url_is_cover": post.get("image_url_is_cover") == "1",
        "cover_first_new": post.get("cover_first_new") == "1",
        "listing_readiness": (post.get("listing_readiness") or "draft").strip(),
    }


def _product_edit_overlay_post(product: dict, request) -> dict:
    """After a failed edit save, show what the user submitted while keeping API-only fields (e.g. images, id)."""
    d = _product_draft_from_post(request)
    out = dict(product)
    for k in (
        "title",
        "description",
        "condition",
        "brand_id",
        "category_id",
        "model",
        "colour",
        "length_cm",
        "width_cm",
        "depth_cm",
        # NEW FIELDS START
        "weight_kg",
        "cost_price",
        "barcode",
        "hs_code",
        "allow_oversell",
        # NEW FIELDS END
        "base_price",
        "currency_code",
        "compare_at_price",
        "quantity",
        "status",
        "active",
        "cover_index",
        "image_url",
        "image_url_is_cover",
        "cover_first_new",
        "listing_readiness",
    ):
        out[k] = d[k]
    return out


def _marketplace_listing_items_from_post(request, listing_rows: list) -> list[dict]:
    items: list[dict] = []
    for cl in listing_rows:
        if not isinstance(cl, dict):
            continue
        mid = cl.get("marketplace_id")
        if not mid:
            continue
        ms = str(mid)
        items.append(
            {
                "marketplace_id": ms,
                "enabled": request.POST.get(f"marketplace_{ms}") == "on",
                "mark_refreshed": request.POST.get(f"marketplace_refresh_{ms}") == "on",
            }
        )
    return items


def _org_id(request):
    v = request.session.get("organisation_id")
    return str(v) if v else None


def _org_default_currency(request) -> str:
    oid = _org_id(request)
    if not oid:
        return "AUD"
    try:
        o = api_get(f"/organisations/{oid}", _token(request), organisation_id=oid)
        if isinstance(o, dict) and o.get("currency_code"):
            return normalize_currency_code(str(o.get("currency_code")))
    except ApiError:
        pass
    return "AUD"


def _require_workspace(request):
    """Signed-in users must confirm workspace (org picker) when required; members need an org scope."""
    if not _token(request):
        return redirect("login")
    if needs_workspace_selection(request):
        return redirect("select_organisation")
    if not request.session.get("is_platform_user"):
        if not request.session.get("organisation_id"):
            return redirect("select_organisation")
    return None


def _include_inactive_from_request(request) -> bool:
    if request.method == "POST":
        return request.POST.get("include_inactive") == "on"
    return request.GET.get("include_inactive") == "on"


def _redirect_preserve_include(name: str, request):
    u = reverse(name)
    if _include_inactive_from_request(request):
        u += "?include_inactive=on"
    return redirect(u)


_PRODUCT_LIST_QS_ALLOW = frozenset(
    {"q", "status", "listing_readiness", "page_size", "page", "include_inactive"}
)


def _redirect_product_list(request):
    """After bulk actions, return to the product list with the same filters when possible."""
    u = reverse("product_list")
    raw = (request.POST.get("return_qs") or "").strip()
    if raw:
        # Accept only whitelisted query keys (return_qs is generated server-side in product_list).
        qd = parse_qsl(urlsplit("?" + raw).query, keep_blank_values=True)
        filt = [(k, v) for k, v in qd if k in _PRODUCT_LIST_QS_ALLOW]
        if filt:
            return redirect(u + "?" + urlencode(filt))
    if _include_inactive_from_request(request):
        u += "?include_inactive=on"
    return redirect(u)


def _safe_json_for_script(obj) -> str:
    return json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c")


def _render_product_form(
    request,
    *,
    categories,
    brands,
    product,
    title: str,
    taxonomy_include_inactive: bool,
):
    all_marketplaces: list = []
    try:
        all_marketplaces = api_get("/marketplaces", _token(request), params={"include_inactive": "true"}, organisation_id=_org_id(request)) or []
    except ApiError:
        all_marketplaces = []
    if product is None:
        default_currency = _org_default_currency(request)
    else:
        default_currency = normalize_currency_code(product.get("currency_code"))
    return render(
        request,
        "catalog/product_form.html",
        {
            "categories": categories,
            "brands": brands,
            "product": product,
            "title": title,
            "categories_json": _safe_json_for_script(categories),
            "taxonomy_include_inactive": taxonomy_include_inactive,
            "is_add_product": title == "Add product",
            "all_marketplaces": all_marketplaces,
            "currency_codes": CURRENCY_CHOICES,
            "default_currency": default_currency,
        },
    )


def _wants_json(request) -> bool:
    return request.headers.get("Accept", "").startswith("application/json") or request.GET.get("format") == "json"


def _taxonomy_xhr(request) -> bool:
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _err_msg(e: ApiError) -> str:
    d = e.detail
    if isinstance(d, dict):
        if "detail" in d:
            return str(d["detail"])
        return str(d)
    if isinstance(d, list):
        return "; ".join(str(x) for x in d)
    return str(d or e.message)


def _upload_product_media_files(
    token: str,
    product_id,
    files,
    *,
    cover_index: int | None,
    organisation_id: str | None,
) -> None:
    """POST each file to the API. cover_index: index of file that is cover, or None = no upload marked cover."""
    for i, f in enumerate(files):
        data = f.read()
        ct = f.content_type or "application/octet-stream"
        is_cover = cover_index is not None and i == cover_index
        api_post_multipart(
            f"/products/{product_id}/images",
            token,
            {"file": (f.name, data, ct)},
            data={"is_cover": "true" if is_cover else "false"},
            organisation_id=organisation_id,
        )


def _apply_product_cover_from_form(token: str, product_id, request, *, skip_patch: bool) -> None:
    """Set cover to selected existing media (radio), unless skip_patch (e.g. first new file is already cover)."""
    if skip_patch:
        return
    cmd = (request.POST.get("cover_media_id") or "").strip()
    if cmd:
        api_patch_json(
            f"/products/{product_id}/images/{cmd}",
            token,
            {"is_cover": True},
            organisation_id=_org_id(request),
        )


def _import_product_image_from_url(
    token: str,
    product_id,
    url: str,
    *,
    is_cover: bool,
    organisation_id: str | None,
) -> None:
    """POST /products/{id}/images/from-url — empty url is a no-op."""
    u = (url or "").strip()
    if not u:
        return
    api_post_json(
        f"/products/{product_id}/images/from-url",
        token,
        {"url": u, "is_cover": is_cover},
        organisation_id=organisation_id,
    )


# Landing page: marketplaces (full product vision — integrations ship over time)
LANDING_MARKETPLACES = [
    {"code": "amz", "name": "Amazon", "blurb": "Marketplace listings, Buy Box, FBA & merchant-fulfilled orders."},
    {"code": "ebay", "name": "eBay", "blurb": "Auction & fixed-price, item specifics, and multi-site listings."},
    {"code": "shop", "name": "Shopify", "blurb": "Sync products, inventory, and orders with your storefront."},
    {"code": "meta", "name": "Facebook Marketplace", "blurb": "Reach local buyers with Meta commerce workflows."},
    {"code": "gum", "name": "Gumtree", "blurb": "Classified-style listings for AU and regional markets."},
    {"code": "ucg", "name": "Used Coffee Gear", "blurb": "Specialty marketplace for used equipment and parts."},
]

# Capability areas (full platform vision; MVP may implement a subset)
LANDING_CAPABILITY_GROUPS = [
    {
        "title": "Product master",
        "items": [
            "Single source of truth for SKU, title, description, condition, brand & category",
            "Rich attributes (JSON/specs) for coffee machines and accessories",
            "Multiple images and videos per product; cover media for listings and marketplaces",
            "Enable/disable catalog rows without deleting history",
        ],
    },
    {
        "title": "Multi-marketplace listing",
        "items": [
            "Choose which marketplaces each product lists to",
            "Per-marketplace overrides for title, price, compare-at, and description",
            "Draft → publish → update → end listing lifecycle",
            "Marketplace category / collection mapping",
            "Listing job queue with durable status & retries",
        ],
    },
    {
        "title": "Inventory & availability",
        "items": [
            "Locations (warehouse, FBA, default) and per-SKU stock levels",
            "Reserved quantity for open orders — avoid overselling",
            "Low-stock thresholds and alerts",
            "Near-real-time sync targets across connected marketplaces",
        ],
    },
    {
        "title": "Orders & fulfillment",
        "items": [
            "Import orders from every connected marketplace into one dashboard",
            "Preserve marketplace source id + external_order_id for audit and sync-back",
            "Fulfillment states, packing notes, tracking, and carrier events",
            "Partial and line-level fulfillment",
        ],
    },
    {
        "title": "Operations & trust",
        "items": [
            "Role-based access (admin, operator, viewer)",
            "App login with email/password or enterprise SSO (OAuth)",
            "Encrypted or vault-referenced marketplace credentials",
            "Audit log for product, override, and listing changes after go-live",
            "Notifications via email, SMTP, or webhooks for key events",
        ],
    },
    {
        "title": "Configuration & scale",
        "items": [
            "Marketplace registry: add new integrations without schema migrations",
            "Per-marketplace API config, rate limits, and feature flags",
            "App & system settings; per-user preferences",
            "Reporting hooks and export-friendly APIs",
        ],
    },
]


def landing(request):
    """Public marketing home — no workspace stats (see dashboard when signed in)."""
    return render(
        request,
        "landing.html",
        {
            "marketplaces": LANDING_MARKETPLACES,
            "capability_groups": LANDING_CAPABILITY_GROUPS,
        },
    )


# Demo-only dashboard metrics (replace with live queries / APIs in future MVPs)
DEMO_DASHBOARD_KPIS = [
    {"id": "products", "label": "Active products", "value": "128", "delta": "+12% vs last month"},
    {"id": "listings", "label": "Live listings", "value": "342", "delta": "Across 6 marketplaces"},
    {"id": "orders_open", "label": "Open orders", "value": "47", "delta": "Awaiting fulfillment"},
    {"id": "orders_today", "label": "Orders today", "value": "23", "delta": "Imported from marketplaces"},
    {"id": "low_stock", "label": "Low-stock SKUs", "value": "8", "delta": "Below threshold"},
    {"id": "sync_jobs", "label": "Sync jobs (24h)", "value": "156", "delta": "96% succeeded"},
]

DEMO_DASHBOARD_MARKETPLACES = [
    {"name": "Amazon", "status": "Connected", "listings": "89", "demo": True},
    {"name": "eBay", "status": "Connected", "listings": "112", "demo": True},
    {"name": "Shopify", "status": "Sync delayed", "listings": "76", "demo": True},
    {"name": "Facebook", "status": "Not connected", "listings": "—", "demo": True},
]

DEMO_DASHBOARD_ACTIVITY = [
    {"time": "09:14", "text": "Price sync completed for 24 SKUs on eBay", "demo": True},
    {"time": "08:51", "text": "Order #AU-9921 imported from Amazon", "demo": True},
    {"time": "Yesterday", "text": "3 products moved to low stock", "demo": True},
]


def dashboard(request):
    if red := _require_workspace(request):
        return red
    try:
        stats = api_get("/stats/summary", _token(request), organisation_id=_org_id(request)) or {}
        active_products = str(int(stats.get("active_products", 0)))
    except ApiError:
        active_products = "—"
    kpis = []
    for k in DEMO_DASHBOARD_KPIS:
        row = dict(k)
        if row["id"] == "products":
            row["value"] = active_products
            row["delta"] = (
                "In the selected organisation"
                if _org_id(request)
                else "Across all organisations (system workspace)"
            )
        kpis.append(row)
    return render(
        request,
        "dashboard.html",
        {
            "demo_banner": True,
            "kpis": kpis,
            "marketplace_rows": DEMO_DASHBOARD_MARKETPLACES,
            "activity": DEMO_DASHBOARD_ACTIVITY,
        },
    )


_PRODUCT_PAGE_SIZES = (10, 20, 50, 100)
_DEFAULT_PAGE_SIZE = 20


def product_list(request):
    if red := _require_workspace(request):
        return red
    q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip() or None
    include_inactive = request.GET.get("include_inactive") == "on"
    try:
        page = max(1, int(request.GET.get("page") or 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.GET.get("page_size") or _DEFAULT_PAGE_SIZE)
    except (TypeError, ValueError):
        page_size = _DEFAULT_PAGE_SIZE
    if page_size not in _PRODUCT_PAGE_SIZES:
        page_size = _DEFAULT_PAGE_SIZE

    listing_rf = request.GET.get("listing_readiness", "").strip() or None
    params = {"page": page, "page_size": page_size}
    if q:
        params["q"] = q
    if status_filter:
        params["status_filter"] = status_filter
    if listing_rf:
        params["listing_readiness_filter"] = listing_rf
    if include_inactive:
        params["include_inactive"] = "true"
    try:
        body = api_get("/products", _token(request), params=params, organisation_id=_org_id(request)) or {}
    except ApiError as e:
        messages.error(request, _err_msg(e))
        body = {}
    products = body.get("items", []) if isinstance(body, dict) else []
    pg = body.get("page", page) if isinstance(body, dict) else page
    total = body.get("total", 0) if isinstance(body, dict) else 0
    total_pages = body.get("total_pages", 1) if isinstance(body, dict) else 1
    page_size = body.get("page_size", page_size) if isinstance(body, dict) else page_size

    base_params = {}
    if q:
        base_params["q"] = q
    if status_filter:
        base_params["status"] = status_filter
    if listing_rf:
        base_params["listing_readiness"] = listing_rf
    if include_inactive:
        base_params["include_inactive"] = "on"
    base_params["page_size"] = str(page_size)
    preserve_params = {**base_params, "page": str(pg)}
    preserve_qs = urlencode(preserve_params)

    def page_url(p: int) -> str:
        return "?" + urlencode({**base_params, "page": str(p)})

    pagination = {
        "page": pg,
        "total_pages": total_pages,
        "total": total,
        "page_size": page_size,
        "prev_url": page_url(max(1, pg - 1)) if pg > 1 else None,
        "next_url": page_url(min(total_pages, pg + 1)) if pg < total_pages else None,
    }
    bulk_marketplaces: list = []
    try:
        bulk_marketplaces = api_get("/marketplaces", _token(request), organisation_id=_org_id(request)) or []
    except ApiError:
        bulk_marketplaces = []
    return render(
        request,
        "catalog/product_list.html",
        {
            "products": products,
            "q": q,
            "status_filter": status_filter or "",
            "listing_readiness_filter": listing_rf or "",
            "include_inactive": include_inactive,
            "page_sizes": _PRODUCT_PAGE_SIZES,
            "pagination": pagination,
            "bulk_marketplaces": bulk_marketplaces,
            "preserve_qs": preserve_qs,
        },
    )


@require_http_methods(["GET", "POST"])
def product_create(request):
    if red := _require_workspace(request):
        return red
    try:
        categories = api_get("/categories", _token(request), organisation_id=_org_id(request)) or []
        brands = api_get("/brands", _token(request), organisation_id=_org_id(request)) or []
    except ApiError:
        categories = []
        brands = []
    if request.method == "POST":
        try:
            payload = {
                "title": request.POST.get("title", "").strip(),
                "description": request.POST.get("description") or None,
                "condition": request.POST.get("condition", "new"),
                "brand_id": _post_optional_uuid_str(request.POST.get("brand_id")),
                "model": request.POST.get("model") or None,
                "category_id": _post_optional_uuid_str(request.POST.get("category_id")),
                "colour": (request.POST.get("colour") or "").strip() or None,
                "length_cm": _product_form_dimension_cm(request.POST.get("length_cm")),
                "width_cm": _product_form_dimension_cm(request.POST.get("width_cm")),
                "depth_cm": _product_form_dimension_cm(request.POST.get("depth_cm")),
                # NEW FIELDS START (Using existing helper for decimal)
                "weight_kg": _product_form_dimension_cm(request.POST.get("weight_kg")),
                "cost_price": request.POST.get("cost_price") or None,
                "barcode": (request.POST.get("barcode") or "").strip() or None,
                "hs_code": (request.POST.get("hs_code") or "").strip() or None,
                "allow_oversell": request.POST.get("allow_oversell") == "1",
                # NEW FIELDS END
                "base_price": str(Decimal(request.POST.get("base_price", "0"))),
                "currency_code": normalize_currency_code(request.POST.get("currency_code")),
                "compare_at_price": request.POST.get("compare_at_price") or None,
                "quantity": int(request.POST.get("quantity", "1") or 1),
                "status": request.POST.get("status", "active"),
                "listing_readiness": (request.POST.get("listing_readiness") or "draft").strip(),
                "active": request.POST.get("active") == "1",
            }
            if payload["listing_readiness"] not in ("draft", "ready_to_post"):
                payload["listing_readiness"] = "draft"
        except ValueError as e:
            messages.error(request, str(e))
            return _render_product_form(
                request,
                categories=categories,
                brands=brands,
                product=_product_draft_from_post(request),
                title="Add product",
                taxonomy_include_inactive=False,
            )
        if payload["compare_at_price"]:
            payload["compare_at_price"] = str(Decimal(payload["compare_at_price"]))
        merged_attrs = _parse_import_attributes_json(request)
        if merged_attrs:
            payload["attributes"] = merged_attrs
        created_pid = None
        try:
            created = api_post_json("/products", _token(request), payload, organisation_id=_org_id(request))
            created_pid = created["id"]
            files_list = request.FILES.getlist("media")
            tok = _token(request)
            if files_list:
                try:
                    ci = int(request.POST.get("cover_index") or 0)
                except (TypeError, ValueError):
                    ci = 0
                ci = max(0, min(ci, len(files_list) - 1))
                _upload_product_media_files(
                    tok, created_pid, files_list, cover_index=ci, organisation_id=_org_id(request)
                )
            image_url = (request.POST.get("image_url") or "").strip()
            if image_url:
                _import_product_image_from_url(
                    tok,
                    created_pid,
                    image_url,
                    is_cover=request.POST.get("image_url_is_cover") == "1",
                    organisation_id=_org_id(request),
                )
            messages.success(request, "Product created.")
            return redirect("product_edit", product_id=created_pid)
        except ApiError as e:
            if created_pid is not None:
                messages.warning(
                    request,
                    "This product was already saved. Continue below to add or fix images — "
                    "do not use “Add product” again for the same item, or you will create a duplicate.",
                )
                messages.error(request, _err_msg(e))
                return redirect("product_edit", product_id=created_pid)
            messages.error(request, _err_msg(e))
            return _render_product_form(
                request,
                categories=categories,
                brands=brands,
                product=_product_draft_from_post(request),
                title="Add product",
                taxonomy_include_inactive=False,
            )
    return _render_product_form(
        request,
        categories=categories,
        brands=brands,
        product=None,
        title="Add product",
        taxonomy_include_inactive=False,
    )


@require_http_methods(["GET", "POST"])
def product_edit(request, product_id: UUID):
    if red := _require_workspace(request):
        return red
    try:
        inc = {"include_inactive": "true"}
        categories = api_get("/categories", _token(request), params=inc, organisation_id=_org_id(request)) or []
        brands = api_get("/brands", _token(request), params=inc, organisation_id=_org_id(request)) or []
        product = api_get(f"/products/{product_id}", _token(request), organisation_id=_org_id(request))
    except ApiError as e:
        messages.error(request, _err_msg(e))
        return redirect("product_list")
    if request.method == "POST":
        try:
            payload = {}
            if request.POST.get("title"):
                payload["title"] = request.POST.get("title", "").strip()
            payload["description"] = request.POST.get("description") or None
            payload["condition"] = request.POST.get("condition", product["condition"])
            payload["brand_id"] = _post_optional_uuid_str(request.POST.get("brand_id"))
            payload["model"] = request.POST.get("model") or None
            payload["category_id"] = _post_optional_uuid_str(request.POST.get("category_id"))
            payload["colour"] = (request.POST.get("colour") or "").strip() or None
            payload["length_cm"] = _product_form_dimension_cm(request.POST.get("length_cm"))
            payload["width_cm"] = _product_form_dimension_cm(request.POST.get("width_cm"))
            payload["depth_cm"] = _product_form_dimension_cm(request.POST.get("depth_cm"))
            # NEW FIELDS START
            payload["weight_kg"] = _product_form_dimension_cm(request.POST.get("weight_kg"))
            payload["cost_price"] = request.POST.get("cost_price") or None
            payload["barcode"] = (request.POST.get("barcode") or "").strip() or None
            payload["hs_code"] = (request.POST.get("hs_code") or "").strip() or None
            payload["allow_oversell"] = request.POST.get("allow_oversell") == "1"
            # NEW FIELDS END
            payload["base_price"] = str(Decimal(request.POST.get("base_price", "0")))
            payload["currency_code"] = normalize_currency_code(request.POST.get("currency_code"))
            cap = request.POST.get("compare_at_price")
            payload["compare_at_price"] = None if not cap else str(Decimal(cap))
            payload["quantity"] = int(request.POST.get("quantity", "1") or 1)
            payload["status"] = request.POST.get("status", "active")
            payload["listing_readiness"] = (request.POST.get("listing_readiness") or "draft").strip()
            if payload["listing_readiness"] not in ("draft", "ready_to_post"):
                payload["listing_readiness"] = "draft"
            payload["active"] = request.POST.get("active") == "1"
            merged_attrs = _parse_import_attributes_json(request)
            if merged_attrs:
                ex = product.get("attributes") if isinstance(product.get("attributes"), dict) else {}
                payload["attributes"] = _merge_product_attributes(ex, merged_attrs)
        except ValueError as e:
            messages.error(request, str(e))
            return _render_product_form(
                request,
                categories=categories,
                brands=brands,
                product=_product_edit_overlay_post(product, request),
                title="Edit product",
                taxonomy_include_inactive=True,
            )
        try:
            token = _token(request)
            product = api_patch_json(
                f"/products/{product_id}",
                token,
                payload,
                organisation_id=_org_id(request),
            )
            ch_rows = product.get("marketplace_listings") or []
            if ch_rows and (product.get("listing_readiness") or "draft") == "ready_to_post":
                try:
                    api_patch_json(
                        f"/products/{product_id}/marketplace-listings",
                        token,
                        {"items": _marketplace_listing_items_from_post(request, ch_rows)},
                        organisation_id=_org_id(request),
                    )
                except ApiError as e:
                    messages.warning(request, f"Product saved, but marketplace flags: {_err_msg(e)}")
            files_list = request.FILES.getlist("media")
            cover_first_new = request.POST.get("cover_first_new") == "1"
            existing_images = product.get("images") or []
            oid = _org_id(request)
            if files_list:
                if existing_images and cover_first_new:
                    _upload_product_media_files(
                        token, str(product_id), files_list, cover_index=0, organisation_id=oid
                    )
                elif existing_images:
                    _upload_product_media_files(
                        token, str(product_id), files_list, cover_index=None, organisation_id=oid
                    )
                else:
                    try:
                        ci = int(request.POST.get("cover_index") or 0)
                    except (TypeError, ValueError):
                        ci = 0
                    ci = max(0, min(ci, len(files_list) - 1))
                    _upload_product_media_files(
                        token, str(product_id), files_list, cover_index=ci, organisation_id=oid
                    )
            image_url = (request.POST.get("image_url") or "").strip()
            url_as_cover = request.POST.get("image_url_is_cover") == "1"
            if image_url:
                _import_product_image_from_url(
                    token,
                    str(product_id),
                    image_url,
                    is_cover=url_as_cover,
                    organisation_id=oid,
                )
            skip_cover_patch = (
                (bool(files_list) and cover_first_new and bool(existing_images)) or url_as_cover
            )
            _apply_product_cover_from_form(token, str(product_id), request, skip_patch=skip_cover_patch)
            messages.success(request, "Product saved.")
            return redirect("product_edit", product_id=product_id)
        except ApiError as e:
            messages.error(request, _err_msg(e))
            return _render_product_form(
                request,
                categories=categories,
                brands=brands,
                product=_product_edit_overlay_post(product, request),
                title="Edit product",
                taxonomy_include_inactive=True,
            )
    return _render_product_form(
        request,
        categories=categories,
        brands=brands,
        product=product,
        title="Edit product",
        taxonomy_include_inactive=True,
    )


@require_http_methods(["GET", "POST"])
def product_comments_api(request, product_id: UUID):
    if not _token(request):
        return JsonResponse({"detail": "Unauthorized"}, status=401)
    if needs_workspace_selection(request):
        return JsonResponse({"detail": "Workspace not selected"}, status=403)
    token = _token(request)
    oid = _org_id(request)
    if request.method == "GET":
        try:
            data = api_get(f"/products/{product_id}/comments", token, organisation_id=oid)
        except ApiError as e:
            return JsonResponse({"detail": _err_msg(e)}, status=e.status_code or 400)
        return JsonResponse(data, safe=False)
    try:
        body = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)
    try:
        data = api_post_json(
            f"/products/{product_id}/comments",
            token,
            body,
            organisation_id=oid,
        )
    except ApiError as e:
        return JsonResponse({"detail": _err_msg(e)}, status=e.status_code or 400)
    return JsonResponse(data)


@require_http_methods(["POST"])
def product_scrape_preview(request):
    if not _token(request):
        return JsonResponse({"detail": "Unauthorized"}, status=401)
    if needs_workspace_selection(request):
        return JsonResponse({"detail": "Workspace not selected"}, status=403)
    try:
        payload = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)
    url = (payload.get("url") or "").strip()
    source = (payload.get("source") or "shopify").strip().lower()
    if source not in ("shopify", "ebay"):
        source = "shopify"
    if not url:
        return JsonResponse({"detail": "url is required"}, status=400)
    try:
        data = api_post_json(
            "/products/scrape-preview",
            _token(request),
            {"url": url, "source": source},
            organisation_id=_org_id(request),
        )
    except ApiError as e:
        return JsonResponse({"detail": _err_msg(e)}, status=e.status_code or 502)
    return JsonResponse(data, safe=False)


def product_delete(request, product_id: UUID):
    if red := _require_workspace(request):
        return red
    if request.method != "POST":
        return redirect("product_list")
    try:
        api_delete(f"/products/{product_id}", _token(request), organisation_id=_org_id(request))
        messages.success(request, "Product deleted.")
    except ApiError as e:
        messages.error(request, _err_msg(e))
    return redirect("product_list")


@require_http_methods(["GET", "POST"])
def category_list(request):
    if red := _require_workspace(request):
        return red
    include_inactive = request.GET.get("include_inactive") == "on"
    sort = (request.GET.get("sort") or "sort_order").strip()
    order = (request.GET.get("order") or "asc").strip().lower()
    if order not in ("asc", "desc"):
        order = "asc"
    params = {"sort": sort, "order": order}
    if include_inactive:
        params["include_inactive"] = "true"
    try:
        categories = api_get("/categories", _token(request), params=params, organisation_id=_org_id(request)) or []
    except ApiError as e:
        if _wants_json(request) or (
            request.method == "POST"
            and request.content_type
            and "application/json" in request.content_type
        ):
            return JsonResponse({"error": _err_msg(e)}, status=502)
        messages.error(request, _err_msg(e))
        categories = []

    if request.method == "POST" and request.content_type and "application/json" in request.content_type:
        try:
            body = json.loads(request.body.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        name = (body.get("name") or "").strip()
        if not name:
            return JsonResponse({"error": "Name is required"}, status=400)
        payload = {
            "name": name,
            "description": (body.get("description") or "").strip() or None,
            "active": bool(body.get("active", True)),
        }
        so = body.get("sort_order")
        if so is not None and str(so).strip() != "":
            payload["sort_order"] = int(so)
        else:
            payload["sort_order"] = None
        pid = body.get("parent_id")
        if pid:
            payload["parent_id"] = str(pid)
        else:
            payload["parent_id"] = None
        try:
            created = api_post_json("/categories", _token(request), payload, organisation_id=_org_id(request))
            return JsonResponse({"ok": True, "item": created})
        except ApiError as e:
            return JsonResponse({"error": _err_msg(e)}, status=400)

    if _wants_json(request) and request.method == "GET":
        return JsonResponse({"items": categories, "sort": sort, "order": order})

    return render(
        request,
        "catalog/category_list.html",
        {
            "categories": categories,
            "include_inactive": include_inactive,
            "sort": sort,
            "order": order,
            "items_json": _safe_json_for_script(categories),
        },
    )


@require_http_methods(["GET", "POST"])
def category_edit(request, category_id: UUID):
    if red := _require_workspace(request):
        return red
    inc = {"include_inactive": "true"}
    include_inactive = request.GET.get("include_inactive") == "on" or (
        request.method == "POST" and request.POST.get("include_inactive") == "on"
    )
    try:
        category = api_get(f"/categories/{category_id}", _token(request), organisation_id=_org_id(request))
        all_categories = api_get("/categories", _token(request), params=inc, organisation_id=_org_id(request)) or []
    except ApiError as e:
        messages.error(request, _err_msg(e))
        return redirect("category_list")
    parent_choices = [c for c in all_categories if str(c.get("id")) != str(category_id)]
    if request.method == "POST":
        payload: dict = {
            "name": request.POST.get("name", "").strip(),
            "sort_order": int(request.POST.get("sort_order", "0") or 0),
            "active": request.POST.get("active") == "1",
        }
        slug = (request.POST.get("slug") or "").strip()
        payload["slug"] = slug if slug else None
        parent = (request.POST.get("parent_id") or "").strip()
        payload["parent_id"] = str(parent) if parent else None
        desc_raw = request.POST.get("description", "")
        payload["description"] = desc_raw.strip() if desc_raw.strip() else None
        try:
            api_patch_json(
                f"/categories/{category_id}",
                _token(request),
                payload,
                organisation_id=_org_id(request),
            )
            messages.success(request, "Category saved.")
            q = "?include_inactive=on" if include_inactive else ""
            return redirect(f"{reverse('category_edit', args=[category_id])}{q}")
        except ApiError as e:
            messages.error(request, _err_msg(e))
    return render(
        request,
        "catalog/category_form.html",
        {
            "category": category,
            "parent_choices": parent_choices,
            "include_inactive": include_inactive,
        },
    )


@require_http_methods(["GET", "POST"])
def brand_list(request):
    if red := _require_workspace(request):
        return red
    include_inactive = request.GET.get("include_inactive") == "on"
    sort = (request.GET.get("sort") or "sort_order").strip()
    order = (request.GET.get("order") or "asc").strip().lower()
    if order not in ("asc", "desc"):
        order = "asc"
    params = {"sort": sort, "order": order}
    if include_inactive:
        params["include_inactive"] = "true"
    try:
        brands = api_get("/brands", _token(request), params=params, organisation_id=_org_id(request)) or []
    except ApiError as e:
        if _wants_json(request) or (
            request.method == "POST"
            and request.content_type
            and "application/json" in request.content_type
        ):
            return JsonResponse({"error": _err_msg(e)}, status=502)
        messages.error(request, _err_msg(e))
        brands = []

    if request.method == "POST" and request.content_type and "application/json" in request.content_type:
        try:
            body = json.loads(request.body.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        name = (body.get("name") or "").strip()
        if not name:
            return JsonResponse({"error": "Name is required"}, status=400)
        payload = {
            "name": name,
            "description": (body.get("description") or "").strip() or None,
            "active": bool(body.get("active", True)),
        }
        so = body.get("sort_order")
        if so is not None and str(so).strip() != "":
            payload["sort_order"] = int(so)
        else:
            payload["sort_order"] = None
        try:
            created = api_post_json("/brands", _token(request), payload, organisation_id=_org_id(request))
            return JsonResponse({"ok": True, "item": created})
        except ApiError as e:
            return JsonResponse({"error": _err_msg(e)}, status=400)

    if _wants_json(request) and request.method == "GET":
        return JsonResponse({"items": brands, "sort": sort, "order": order})

    return render(
        request,
        "catalog/brand_list.html",
        {
            "brands": brands,
            "include_inactive": include_inactive,
            "sort": sort,
            "order": order,
            "items_json": _safe_json_for_script(brands),
        },
    )


def _taxonomy_include_inactive_params(request) -> dict:
    if request.GET.get("include_inactive") == "on":
        return {"include_inactive": "true"}
    return {}


@require_http_methods(["POST"])
def category_reorder(request):
    if red := _require_workspace(request):
        return red
    try:
        body = json.loads(request.body.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    ids = body.get("ordered_ids")
    if not isinstance(ids, list) or not ids:
        return JsonResponse({"error": "ordered_ids is required"}, status=400)
    try:
        items = api_post_json(
            "/categories/reorder",
            _token(request),
            {"ordered_ids": ids},
            params=_taxonomy_include_inactive_params(request),
            organisation_id=_org_id(request),
        )
        return JsonResponse({"ok": True, "items": items})
    except ApiError as e:
        return JsonResponse({"error": _err_msg(e)}, status=400)


@require_http_methods(["POST"])
def category_sort_by_name(request):
    if red := _require_workspace(request):
        return red
    try:
        items = api_post_json(
            "/categories/sort-by-name",
            _token(request),
            {},
            params=_taxonomy_include_inactive_params(request),
            organisation_id=_org_id(request),
        )
        return JsonResponse({"ok": True, "items": items})
    except ApiError as e:
        return JsonResponse({"error": _err_msg(e)}, status=400)


@require_http_methods(["POST"])
def brand_reorder(request):
    if red := _require_workspace(request):
        return red
    try:
        body = json.loads(request.body.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    ids = body.get("ordered_ids")
    if not isinstance(ids, list) or not ids:
        return JsonResponse({"error": "ordered_ids is required"}, status=400)
    try:
        items = api_post_json(
            "/brands/reorder",
            _token(request),
            {"ordered_ids": ids},
            params=_taxonomy_include_inactive_params(request),
            organisation_id=_org_id(request),
        )
        return JsonResponse({"ok": True, "items": items})
    except ApiError as e:
        return JsonResponse({"error": _err_msg(e)}, status=400)


@require_http_methods(["POST"])
def brand_sort_by_name(request):
    if red := _require_workspace(request):
        return red
    try:
        items = api_post_json(
            "/brands/sort-by-name",
            _token(request),
            {},
            params=_taxonomy_include_inactive_params(request),
            organisation_id=_org_id(request),
        )
        return JsonResponse({"ok": True, "items": items})
    except ApiError as e:
        return JsonResponse({"error": _err_msg(e)}, status=400)


@require_http_methods(["GET", "POST"])
def brand_edit(request, brand_id: UUID):
    if red := _require_workspace(request):
        return red
    include_inactive = request.GET.get("include_inactive") == "on" or (
        request.method == "POST" and request.POST.get("include_inactive") == "on"
    )
    try:
        brand = api_get(f"/brands/{brand_id}", _token(request), organisation_id=_org_id(request))
    except ApiError as e:
        messages.error(request, _err_msg(e))
        return redirect("brand_list")
    if request.method == "POST":
        payload: dict = {
            "name": request.POST.get("name", "").strip(),
            "sort_order": int(request.POST.get("sort_order", "0") or 0),
            "active": request.POST.get("active") == "1",
        }
        slug = (request.POST.get("slug") or "").strip()
        payload["slug"] = slug if slug else None
        desc_raw = request.POST.get("description", "")
        payload["description"] = desc_raw.strip() if desc_raw.strip() else None
        try:
            api_patch_json(
                f"/brands/{brand_id}",
                _token(request),
                payload,
                organisation_id=_org_id(request),
            )
            messages.success(request, "Brand saved.")
            q = "?include_inactive=on" if include_inactive else ""
            return redirect(f"{reverse('brand_edit', args=[brand_id])}{q}")
        except ApiError as e:
            messages.error(request, _err_msg(e))
    return render(
        request,
        "catalog/brand_form.html",
        {"brand": brand, "include_inactive": include_inactive},
    )


@require_http_methods(["POST"])
def category_set_active(request, category_id: UUID):
    if red := _require_workspace(request):
        return red
    next_url = request.POST.get("next") or reverse("category_list")
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = reverse("category_list")
    active = request.POST.get("active") == "true"
    xhr = _taxonomy_xhr(request)
    try:
        api_patch_json(
            f"/categories/{category_id}",
            _token(request),
            {"active": active},
            organisation_id=_org_id(request),
        )
        if xhr:
            return JsonResponse({"ok": True})
        messages.success(request, "Category updated.")
    except ApiError as e:
        if xhr:
            return JsonResponse({"error": _err_msg(e)}, status=400)
        messages.error(request, _err_msg(e))
    return redirect(next_url)


@require_http_methods(["POST"])
def brand_set_active(request, brand_id: UUID):
    if red := _require_workspace(request):
        return red
    next_url = request.POST.get("next") or reverse("brand_list")
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = reverse("brand_list")
    active = request.POST.get("active") == "true"
    xhr = _taxonomy_xhr(request)
    try:
        api_patch_json(
            f"/brands/{brand_id}",
            _token(request),
            {"active": active},
            organisation_id=_org_id(request),
        )
        if xhr:
            return JsonResponse({"ok": True})
        messages.success(request, "Brand updated.")
    except ApiError as e:
        if xhr:
            return JsonResponse({"error": _err_msg(e)}, status=400)
        messages.error(request, _err_msg(e))
    return redirect(next_url)


def redirect_legacy_channel_list(request):
    """Legacy path `/channels/` redirects to marketplace management."""
    return redirect("marketplace_list")


def redirect_legacy_channel_edit(request, channel_id: UUID):
    """Legacy path `/channels/<uuid>/` redirects to marketplace edit."""
    return redirect("marketplace_edit", marketplace_id=channel_id)


def marketplace_list(request):
    if red := _require_workspace(request):
        return red
    include_inactive = request.GET.get("include_inactive") == "on"
    params: dict = {}
    if include_inactive:
        params["include_inactive"] = "true"
    try:
        marketplaces = api_get("/marketplaces", _token(request), params=params, organisation_id=_org_id(request)) or []
    except ApiError as e:
        messages.error(request, _err_msg(e))
        marketplaces = []
    return render(
        request,
        "catalog/marketplace_list.html",
        {"marketplaces": marketplaces, "include_inactive": include_inactive},
    )


@require_http_methods(["GET", "POST"])
def marketplace_edit(request, marketplace_id: UUID):
    if red := _require_workspace(request):
        return red
    try:
        marketplace = api_get(f"/marketplaces/{marketplace_id}", _token(request), organisation_id=_org_id(request))
    except ApiError as e:
        messages.error(request, _err_msg(e))
        return redirect("marketplace_list")
    if request.method == "POST":
        raw_req = (request.POST.get("integration_requirements_json") or "").strip()
        integ: dict | None = None
        if raw_req:
            try:
                integ = json.loads(raw_req)
                if not isinstance(integ, dict):
                    raise ValueError("Integration requirements must be a JSON object.")
            except (json.JSONDecodeError, ValueError) as e:
                messages.error(request, str(e))
                return render(
                    request,
                    "catalog/marketplace_form.html",
                    {
                        "marketplace": marketplace,
                        "title": marketplace.get("name", "Marketplace"),
                        "integration_json": raw_req or "{}",
                    },
                )
        payload: dict = {
            "name": (request.POST.get("name") or "").strip() or marketplace["name"],
            "description": (request.POST.get("description") or "").strip() or None,
            "active": request.POST.get("active") == "1",
        }
        try:
            so = (request.POST.get("sort_order") or "").strip()
            payload["sort_order"] = int(so) if so else marketplace.get("sort_order", 0)
        except ValueError:
            messages.error(request, "Sort order must be a number.")
            return render(
                request,
                "catalog/marketplace_form.html",
                {
                    "marketplace": marketplace,
                    "title": marketplace.get("name", "Marketplace"),
                    "integration_json": (request.POST.get("integration_requirements_json") or "").strip() or "{}",
                },
            )
        if integ is not None:
            payload["integration_requirements"] = integ
        elif raw_req == "":
            payload["integration_requirements"] = marketplace.get("integration_requirements") or {}
        try:
            marketplace = api_patch_json(
                f"/marketplaces/{marketplace_id}",
                _token(request),
                payload,
                organisation_id=_org_id(request),
            )
            messages.success(request, "Marketplace saved.")
            return redirect("marketplace_list")
        except ApiError as e:
            messages.error(request, _err_msg(e))
            integ_err = request.POST.get("integration_requirements_json") or "{}"
            return render(
                request,
                "catalog/marketplace_form.html",
                {
                    "marketplace": {
                        **marketplace,
                        "name": payload.get("name", marketplace.get("name")),
                        "description": payload.get("description"),
                    },
                    "title": marketplace.get("name", "Marketplace"),
                    "integration_json": integ_err,
                },
            )
    title = marketplace.get("name", "Marketplace")
    integ = marketplace.get("integration_requirements") or {}
    try:
        integration_json = json.dumps(integ, indent=2, ensure_ascii=False) if isinstance(integ, dict) else str(integ)
    except TypeError:
        integration_json = "{}"
    return render(
        request,
        "catalog/marketplace_form.html",
        {"marketplace": marketplace, "title": title, "integration_json": integration_json},
    )


@require_http_methods(["POST"])
def product_bulk_listings(request):
    if red := _require_workspace(request):
        return red
    action = (request.POST.get("bulk_action") or "").strip()
    raw_ids = request.POST.getlist("product_ids")
    try:
        uuids = [UUID(x) for x in raw_ids if x.strip()]
    except ValueError:
        messages.error(request, "Invalid product selection.")
        return _redirect_product_list(request)
    if not uuids:
        messages.error(request, "Select at least one product.")
        return _redirect_product_list(request)
    tok = _token(request)
    oid = _org_id(request)
    try:
        if action == "bulk_ready":
            api_post_json(
                "/products/bulk-listing-readiness",
                tok,
                {"product_ids": [str(u) for u in uuids], "listing_readiness": "ready_to_post"},
                organisation_id=oid,
            )
            messages.success(request, f"Marked {len(uuids)} product(s) as ready to post.")
        elif action == "bulk_draft":
            api_post_json(
                "/products/bulk-listing-readiness",
                tok,
                {"product_ids": [str(u) for u in uuids], "listing_readiness": "draft"},
                organisation_id=oid,
            )
            messages.success(request, f"Moved {len(uuids)} product(s) to draft (marketplace flags cleared).")
        elif action.startswith("bulk_marketplace:"):
            cid = action.split(":", 1)[1]
            try:
                UUID(cid)
            except ValueError:
                messages.error(request, "Invalid marketplace.")
                return _redirect_product_list(request)
            api_post_json(
                "/products/bulk-marketplace-flags",
                tok,
                {"product_ids": [str(u) for u in uuids], "marketplace_id": cid, "enabled": True},
                organisation_id=oid,
            )
            messages.success(request, f"Enabled marketplace for {len(uuids)} ready product(s) (skipped drafts).")
        elif action.startswith("bulk_marketplace_off:"):
            cid = action.split(":", 1)[1]
            try:
                UUID(cid)
            except ValueError:
                messages.error(request, "Invalid marketplace.")
                return _redirect_product_list(request)
            api_post_json(
                "/products/bulk-marketplace-flags",
                tok,
                {"product_ids": [str(u) for u in uuids], "marketplace_id": cid, "enabled": False},
                organisation_id=oid,
            )
            messages.success(request, f"Disabled marketplace for {len(uuids)} ready product(s) (skipped drafts).")
        else:
            messages.error(request, "Unknown bulk action.")
    except ApiError as e:
        messages.error(request, _err_msg(e))
    return _redirect_product_list(request)


def privacy_policy(request):
    return render(request, "pages/privacy_policy.html")


def terms_of_service(request):
    return render(request, "pages/terms_of_service.html")


def contact(request):
    return render(request, "pages/contact.html")
