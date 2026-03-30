"""Best-effort scraping of public Shopify / eBay listing pages for product form prefill.

Shopify: prefers the storefront ``/products/{handle}.json`` endpoint when available.
eBay: parses Open Graph and common price/title patterns from HTML (fragile by nature).
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from app.models.product import ProductCondition

_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def _http_client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(45.0),
        follow_redirects=True,
        headers={"User-Agent": _DEFAULT_UA, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"},
    )


def _shopify_json_url(page_url: str) -> str:
    p = urlparse(page_url.strip())
    path = p.path.split("?")[0].rstrip("/")
    if path.endswith(".json"):
        json_path = path
    else:
        json_path = f"{path}.json"
    return urlunparse((p.scheme or "https", p.netloc, json_path, "", "", ""))


def scrape_shopify(url: str) -> dict[str, Any]:
    json_url = _shopify_json_url(url)
    with _http_client() as client:
        r = client.get(json_url)
        if r.status_code != 200:
            raise ValueError(f"Could not load Shopify product JSON ({r.status_code}). Try the product page URL.")
        data = r.json()
    product = data.get("product") if isinstance(data, dict) else None
    if not isinstance(product, dict):
        raise ValueError("Unexpected Shopify JSON shape.")
    title = (product.get("title") or "").strip() or None
    body_html = (product.get("body_html") or "").strip() or None
    vendor = (product.get("vendor") or "").strip() or None
    product_type = (product.get("product_type") or "").strip() or None
    variants = product.get("variants") or []
    base_price = None
    compare_at = None
    if isinstance(variants, list) and variants:
        v0 = variants[0] if isinstance(variants[0], dict) else {}
        raw_price = v0.get("price")
        raw_compare = v0.get("compare_at_price")
        if raw_price is not None:
            try:
                base_price = str(Decimal(str(raw_price)))
            except (InvalidOperation, ValueError):
                base_price = None
        if raw_compare is not None:
            try:
                c = Decimal(str(raw_compare))
                if c > 0:
                    compare_at = str(c)
            except (InvalidOperation, ValueError):
                pass
    desc_parts = []
    if body_html:
        desc_parts.append(body_html)
    if product_type and product_type.lower() not in (body_html or "").lower():
        desc_parts.append(f"<p><strong>Type:</strong> {product_type}</p>")
    description = "\n".join(desc_parts) if desc_parts else None
    return {
        "title": title,
        "description": description,
        "condition": ProductCondition.new,
        "base_price": base_price or "0",
        "compare_at_price": compare_at,
        "quantity": 1,
        "model": None,
        "colour": None,
        "suggested_brand_name": vendor,
        "data_origin": "shopify",
        "import_source_url": url.strip(),
    }


def _ebay_item_id(url: str) -> str | None:
    m = re.search(r"/itm/(?:[^/]+/)?(\d{6,})", url)
    if m:
        return m.group(1)
    m = re.search(r"itm=(\d{6,})", url)
    if m:
        return m.group(1)
    return None


def _parse_money(s: str | None) -> str | None:
    if not s:
        return None
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    try:
        return str(Decimal(s.replace(",", "")))
    except (InvalidOperation, ValueError):
        return None


def scrape_ebay(url: str) -> dict[str, Any]:
    with _http_client() as client:
        r = client.get(url.strip())
        if r.status_code != 200:
            raise ValueError(f"Could not load eBay page ({r.status_code}).")
        html = r.text
    soup = BeautifulSoup(html, "html.parser")
    title = None
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = og["content"].strip()
    if not title:
        h = soup.find("h1", class_=re.compile(r"x-item-title", re.I))
        if h:
            title = h.get_text(strip=True)
    desc = None
    ogd = soup.find("meta", property="og:description")
    if ogd and ogd.get("content"):
        desc = ogd["content"].strip()
    if not desc:
        d2 = soup.find("meta", attrs={"name": "description"})
        if d2 and d2.get("content"):
            desc = d2["content"].strip()
    price = None
    pr_el = soup.find("meta", attrs={"itemprop": "price"})
    if pr_el and pr_el.get("content"):
        price = _parse_money(pr_el["content"])
    if not price:
        for selector in (
            '[data-testid="x-price-primary"] span',
            ".x-price-primary span",
            ".x-bin-price",
        ):
            for node in soup.select(selector):
                t = node.get_text(strip=True)
                p = _parse_money(t)
                if p:
                    price = p
                    break
            if price:
                break
    # JSON-LD
    if not title or not price:
        for script in soup.find_all("script", type="application/ld+json"):
            raw_js = (script.string or script.get_text() or "").strip()
            if not raw_js:
                continue
            try:
                j = json.loads(raw_js)
            except (json.JSONDecodeError, TypeError):
                continue
            items = j if isinstance(j, list) else [j]
            for block in items:
                if not isinstance(block, dict):
                    continue
                if block.get("@type") in ("Product", "IndividualProduct"):
                    if not title:
                        title = (block.get("name") or "").strip() or None
                    off = block.get("offers")
                    if isinstance(off, dict) and not price:
                        p = off.get("price")
                        if p is not None:
                            price = _parse_money(str(p))
    condition = ProductCondition.used
    tlow = (title or "").lower()
    dlow = (desc or "").lower()
    if "new" in tlow or "brand new" in dlow:
        condition = ProductCondition.new
    elif "refurb" in tlow or "refurb" in dlow:
        condition = ProductCondition.refurbished
    item_id = _ebay_item_id(url)
    extra = f"<p><em>Imported from eBay listing{item_id and f' #{item_id}' or ''}.</em></p>"
    description = desc
    if description:
        description = f"<div>{description}</div>\n{extra}"
    else:
        description = extra
    return {
        "title": title or "eBay listing",
        "description": description,
        "condition": condition,
        "base_price": price or "0",
        "compare_at_price": None,
        "quantity": 1,
        "model": item_id,
        "colour": None,
        "suggested_brand_name": None,
        "data_origin": "ebay",
        "import_source_url": url.strip(),
    }
