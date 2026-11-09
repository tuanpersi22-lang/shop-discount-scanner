from __future__ import annotations

import ipaddress
import json
import re
import socket
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urldefrag, urlencode, urljoin, urlparse
import uuid
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

USER_AGENT = "ShopDiscountScanner/1.0 (public product-price audit; respects robots.txt)"
TIMEOUT = 12
MAX_REDIRECTS = 4


def parse_money(value):
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    raw = re.sub(r"[^0-9,.\-]", "", str(value).replace("\xa0", " ").strip())
    if not raw or raw in {"-", ".", ","}:
        return None
    if "," in raw and "." in raw:
        sep = max(raw.rfind(","), raw.rfind("."))
        tail = raw[sep + 1:]
        normalized = re.sub(r"[,.]", "", raw[:sep]) + ("." + tail if len(tail) in (1, 2) else tail)
        if len(tail) not in (1, 2):
            normalized = re.sub(r"[,.]", "", raw)
    elif "," in raw or "." in raw:
        sep = "," if "," in raw else "."
        parts = raw.split(sep)
        if len(parts) > 2 or len(parts[-1]) == 3:
            normalized = "".join(parts)
        elif len(parts[-1]) in (1, 2):
            normalized = parts[0] + "." + parts[-1]
        else:
            normalized = "".join(parts)
    else:
        normalized = raw
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def calculate_discount(list_price, sale_price):
    listed, sale = parse_money(list_price), parse_money(sale_price)
    if listed is None or sale is None or listed <= 0:
        return None, None
    ratio = sale / listed * Decimal("100")
    discount = (Decimal("1") - sale / listed) * Decimal("100")
    return round(ratio, 2), round(discount, 2)


def _normal_url(url):
    if not isinstance(url, str):
        return None
    value = urldefrag(url.strip())[0]
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    if parsed.username or parsed.password or (port is not None and port not in (80, 443)):
        return None
    if parsed.scheme == "http" and port == 443 or parsed.scheme == "https" and port == 80:
        return None
    return value


def _public_host(host):
    if not host or host.lower() == "localhost" or host.lower().endswith((".localhost", ".local", ".internal")):
        return False
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            addresses = [ipaddress.ip_address(x[4][0]) for x in socket.getaddrinfo(host, None)]
        except (OSError, ValueError):
            return False
    return bool(addresses) and all(address.is_global for address in addresses)


def _host_key(url):
    parsed = urlparse(url)
    return (parsed.hostname or "").lower().removeprefix("www.")


def _safe_get(session, url, robots=None, extra_headers=None):
    current = _normal_url(url)
    if not current:
        return None
    original_host = _host_key(current)
    for _ in range(MAX_REDIRECTS + 1):
        parsed = urlparse(current)
        if _host_key(current) != original_host or not _public_host(parsed.hostname):
            return None
        if robots is not None:
            try:
                if not robots.can_fetch(USER_AGENT, current):
                    return None
            except Exception:
                return None
        try:
            headers = {"User-Agent": USER_AGENT}
            if extra_headers:
                headers.update(extra_headers)
            response = session.get(current, timeout=TIMEOUT, allow_redirects=False,
                                   headers=headers)
        except requests.RequestException:
            return None
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location")
            if not location:
                return None
            current = _normal_url(urljoin(current, location))
            if not current or _host_key(current) != original_host:
                return None
            continue
        return response if response.status_code == 200 else None
    return None



def _safe_post(session, url, payload, robots=None, extra_headers=None):
    current = _normal_url(url)
    if not current or not _public_host(urlparse(current).hostname):
        return None
    if robots is not None:
        try:
            if not robots.can_fetch(USER_AGENT, current):
                return None
        except Exception:
            return None
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json, text/plain, */*"}
    if extra_headers:
        headers.update(extra_headers)
    try:
        response = session.post(
            current,
            json=payload,
            timeout=TIMEOUT,
            allow_redirects=False,
            headers=headers,
        )
    except requests.RequestException:
        return None
    return response if response.status_code == 200 else None


def _get_robots(session, base_url):
    response = _safe_get(session, urljoin(base_url, "/robots.txt"))
    if response is None:
        return None
    parser = RobotFileParser()
    parser.set_url(urljoin(base_url, "/robots.txt"))
    parser.parse(response.text.splitlines())
    return parser


def _product_row(html, page_url, shop):
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("h1")
    name = heading.get_text(" ", strip=True) if heading else ""
    list_price = sale_price = None
    currency = ""
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text())
        except (ValueError, TypeError):
            continue
        objects = data if isinstance(data, list) else [data]
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            if isinstance(obj.get("@graph"), list):
                objects.extend(obj["@graph"])
            kind = obj.get("@type", [])
            if isinstance(kind, str):
                kind = [kind]
            if not any(str(x).lower() in ("product", "productgroup") for x in kind):
                continue
            name = obj.get("name") or name
            offers = obj.get("offers") or {}
            if isinstance(offers, list):
                offers = next((x for x in offers if isinstance(x, dict)), {})
            if isinstance(offers, dict):
                sale_price = parse_money(offers.get("price") or offers.get("lowPrice"))
                currency = offers.get("priceCurrency", "")
                specs = offers.get("priceSpecification") or obj.get("priceSpecification") or []
                if isinstance(specs, dict):
                    specs = [specs]
                for spec in specs if isinstance(specs, list) else []:
                    if isinstance(spec, dict) and any(t in str(spec.get("priceType", "")).lower() for t in ("listprice", "regular", "strikethrough")):
                        list_price = parse_money(spec.get("price"))
                        break
            break
        if sale_price is not None:
            break

    def first_price(selectors):
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                raw = element.get("content") or element.get("data-price") or element.get_text(" ", strip=True)
                value = parse_money(raw)
                if value is not None:
                    return value
        return None

    if list_price is None:
        list_price = first_price([".price del .amount", ".price del", ".price s", ".compare-at-price", ".old-price", "[data-compare-at-price]"])
    if sale_price is None:
        sale_price = first_price([".price ins .amount", ".price ins", ".sale-price", ".special-price", "[data-sale-price]", "meta[property='product:price:amount']", "meta[itemprop='price']", ".product-price", ".price .amount", ".price"])
    if not name and sale_price is None and list_price is None:
        return None
    if not currency:
        text = soup.get_text(" ", strip=True)
        currency = "VND" if "₫" in text or "đ" in text.lower() else ""
    ratio, discount = calculate_discount(list_price, sale_price)
    return {
        "Shop": shop, "Sản phẩm": name or "(Chưa đọc được tên sản phẩm)",
        "Biến thể": "", "SKU": "", "Giá niêm yết": float(list_price) if list_price is not None else None,
        "Giá bán": float(sale_price) if sale_price is not None else None,
        "Tỷ lệ giá bán (%)": float(ratio) if ratio is not None else None,
        "Chiết khấu (%)": float(discount) if discount is not None else None,
        "Tiền tệ": currency, "Trạng thái": "Thiếu giá niêm yết" if list_price is None else ("Có chiết khấu" if discount is not None and discount > 0 else "Không giảm giá"),
        "URL sản phẩm": page_url, "Nguồn giá": "JSON-LD/HTML",
        "Thời điểm quét": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
    }



def _shopee_price(value):
    """Shopee v4 price fields are integer amounts scaled by 100,000."""
    amount = parse_money(value)
    if amount is None or amount <= 0:
        return None
    return amount / Decimal("100000")


def _shopee_product_objects(payload):
    """Find product-card dictionaries across known Shopee response envelopes."""
    found, seen = [], set()

    def walk(node, depth=0):
        if depth > 12:
            return
        if isinstance(node, dict):
            containers = [node]
            nested_keys = (
                "item_basic", "item_data", "item_card_display_price",
                "item_card_displayed_price", "item_card_display_asset",
                "item_card_displayed_asset",
            )
            index = 0
            while index < len(containers):
                parent = containers[index]
                for key in nested_keys:
                    nested = parent.get(key)
                    if isinstance(nested, dict) and nested not in containers:
                        containers.append(nested)
                index += 1
            item_id = next(
                (
                    container.get("itemid") or container.get("item_id")
                    for container in containers
                    if container.get("itemid") is not None or container.get("item_id") is not None
                ),
                None,
            )
            has_price = any(
                key in container
                for container in containers
                for key in (
                    "price", "price_min", "price_before_discount",
                    "price_min_before_discount", "current_price",
                )
            )
            if item_id is not None and has_price:
                key = str(item_id)
                if key not in seen:
                    seen.add(key)
                    found.append(node)
            for value in node.values():
                walk(value, depth + 1)
        elif isinstance(node, list):
            for value in node:
                walk(value, depth + 1)

    walk(payload)
    return found


def _shopee_product_row(item, shop, base_url, collection_url):
    containers = [item]
    nested_keys = (
        "item_basic", "item_data", "item_card_display_price",
        "item_card_displayed_price", "item_card_display_asset",
        "item_card_displayed_asset",
    )
    index = 0
    while index < len(containers):
        parent = containers[index]
        for key in nested_keys:
            nested = parent.get(key)
            if isinstance(nested, dict) and nested not in containers:
                containers.append(nested)
        index += 1

    def first(keys):
        for container in containers:
            for key in keys:
                value = container.get(key)
                if value not in (None, ""):
                    return value
        return None

    def first_price(keys):
        for container in containers:
            for key in keys:
                value = _shopee_price(container.get(key))
                if value is not None:
                    return value
        return None

    item_id = first(("itemid", "item_id"))
    shop_id = first(("shopid", "shop_id"))
    name = first(("name", "title", "item_name"))
    sale_price = first_price(("price_min", "price", "current_price"))
    list_price = first_price(("price_min_before_discount", "price_before_discount"))

    if not name:
        name = "(Shopee chưa trả tên sản phẩm)"
    if item_id and shop_id:
        product_url = f"{base_url}/product/{shop_id}/{item_id}"
    else:
        product_url = collection_url

    ratio, discount = calculate_discount(list_price, sale_price)
    return {
        "Shop": shop,
        "Sản phẩm": str(name),
        "Biến thể": "",
        "SKU": str(first(("item_sku", "sku")) or ""),
        "Giá niêm yết": float(list_price) if list_price is not None else None,
        "Giá bán": float(sale_price) if sale_price is not None else None,
        "Tỷ lệ giá bán (%)": float(ratio) if ratio is not None else None,
        "Chiết khấu (%)": float(discount) if discount is not None else None,
        "Tiền tệ": str(first(("currency",)) or "VND"),
        "Trạng thái": (
            "Thiếu giá niêm yết" if list_price is None
            else ("Có chiết khấu" if discount is not None and discount > 0 else "Không giảm giá")
        ),
        "URL sản phẩm": product_url,
        "Nguồn giá": "Shopee collection API",
        "Thời điểm quét": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _scan_shopee_collection(session, normalized_url, parsed, shop, robots, max_products):
    query = parse_qs(parsed.query)
    collection_id = (
        (query.get("shopCollection") or query.get("collection_id") or [None])[0]
    )
    if not collection_id or not str(collection_id).isdigit():
        return None

    base_url = f"{parsed.scheme}://{parsed.netloc}"
    path_parts = [part for part in parsed.path.split("/") if part]
    shop_id = None
    shop_slug = path_parts[0] if path_parts else ""
    if shop_slug.lower() == "shop" and len(path_parts) > 1 and path_parts[1].isdigit():
        shop_id = path_parts[1]
    elif shop_slug.isdigit():
        shop_id = shop_slug
    if query.get("shopid"):
        shop_id = query["shopid"][0]

    shop_name = shop_slug or shop
    if not shop_id and shop_slug:
        detail_url = f"{base_url}/api/v4/shop/get_shop_base_v2"
        detail_payload = {
            "request_source": "mobile_shop_home_page",
            "livestream_params": {},
            "username": shop_slug,
        }
        detail_response = _safe_post(
            session,
            detail_url,
            detail_payload,
            robots,
            extra_headers={
                "Referer": normalized_url,
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        if detail_response is not None:
            try:
                detail_data = detail_response.json().get("data") or {}
                shop_id = str(detail_data.get("shopid") or detail_data.get("shop_id") or "") or None
                shop_name = detail_data.get("name") or shop_name
            except (ValueError, AttributeError):
                pass

    # Older Shopee shop URLs sometimes contain the numeric shop id in the path.
    # For username URLs, Shop Detail V2 above resolves it without login.
    if not shop_id:
        legacy_detail_url = f"{base_url}/api/v4/shop/get_shop_base?username={shop_slug}"
        legacy_response = _safe_get(
            session,
            legacy_detail_url,
            robots,
            extra_headers={"Referer": normalized_url, "X-Requested-With": "XMLHttpRequest"},
        )
        if legacy_response is not None:
            try:
                detail_data = legacy_response.json().get("data") or {}
                shop_id = str(detail_data.get("shopid") or detail_data.get("shop_id") or "") or None
                shop_name = detail_data.get("name") or shop_name
            except (ValueError, AttributeError):
                pass

    if not shop_id or not shop_id.isdigit():
        return [], [
            "Không lấy được mã gian hàng Shopee từ đường link này. "
            "Hãy thử URL có dạng /shop/MA_GIAN_HANG hoặc kiểm tra lại tên shop."
        ]

    limit = min(max(int(max_products), 1), 50)
    common_params = {
        "by": "pop",
        "limit": limit,
        "match_id": shop_id,
        "newest": 0,
        "order": "desc",
        "page_type": "shop",
        "shop_categoryids": str(collection_id),
        "version": 2,
    }
    api_candidates = [
        (
            f"{base_url}/api/v4/search/search_items?"
            + urlencode({**common_params, "scenario": "PAGE_SHOP_SEARCH"})
        ),
        f"{base_url}/api/v2/search_items/?{urlencode(common_params)}",
    ]

    last_error = None
    for api_url in api_candidates:
        if robots is not None:
            try:
                if not robots.can_fetch(USER_AGENT, api_url):
                    last_error = "robots.txt không cho phép truy cập endpoint danh sách sản phẩm này."
                    continue
            except Exception:
                return [], ["Không xác minh được robots.txt của Shopee; đã bỏ qua yêu cầu quét."]

        response = _safe_get(
            session,
            api_url,
            robots,
            extra_headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": normalized_url,
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        if response is None:
            last_error = "Shopee không trả phản hồi từ API danh sách sản phẩm."
            continue

        try:
            payload = response.json()
        except ValueError:
            last_error = "Shopee trả về dữ liệu không phải JSON."
            continue

        if isinstance(payload, dict) and payload.get("error") not in (None, 0, "", False):
            last_error = str(payload.get("error_msg") or payload.get("error"))
            continue

        items = _shopee_product_objects(payload)
        if items:
            rows = [
                _shopee_product_row(item, shop_name, base_url, normalized_url)
                for item in items[:limit]
            ]
            return rows, []

        last_error = "API có phản hồi nhưng không chứa danh sách sản phẩm phù hợp."

    return [], [
        "Chưa đọc được sản phẩm trong bộ sưu tập Shopee này. "
        + (last_error or "Shopee có thể đã thay đổi API hoặc giới hạn truy cập tự động.")
        + " Công cụ không vượt CAPTCHA, đăng nhập hoặc quy tắc robots.txt."
    ]

def scan_shop(shop_url, max_products=30, max_category_pages=3, delay=1.5):
    normalized = _normal_url(shop_url)
    if not normalized:
        return [], [f"URL không hợp lệ hoặc cổng truy cập không được hỗ trợ: {shop_url}"]
    parsed = urlparse(normalized)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    shop = parsed.netloc.lower().removeprefix("www.")
    session = requests.Session()
    robots = _get_robots(session, base_url)
    rows, errors = [], []

    # Shopee collection URLs use a separate public listing endpoint.
    if parsed.hostname and (parsed.hostname.lower() == "shopee.vn" or parsed.hostname.lower().endswith(".shopee.vn")):
        shopee_result = _scan_shopee_collection(
            session, normalized, parsed, shop, robots, max_products
        )
        if shopee_result is not None:
            return shopee_result

    # Shopify public catalogue endpoint.
    response = _safe_get(session, urljoin(base_url, "/products.json?limit=50"), robots)
    if response is not None:
        try:
            products = response.json().get("products", [])
        except (ValueError, AttributeError):
            products = []
        for product in products:
            for variant in product.get("variants") or [{}]:
                listed, sale = parse_money(variant.get("compare_at_price")), parse_money(variant.get("price"))
                ratio, discount = calculate_discount(listed, sale)
                handle = product.get("handle") or ""
                rows.append({
                    "Shop": shop, "Sản phẩm": product.get("title") or "(Không có tên)",
                    "Biến thể": variant.get("title") or "", "SKU": variant.get("sku") or "",
                    "Giá niêm yết": float(listed) if listed is not None else None,
                    "Giá bán": float(sale) if sale is not None else None,
                    "Tỷ lệ giá bán (%)": float(ratio) if ratio is not None else None,
                    "Chiết khấu (%)": float(discount) if discount is not None else None,
                    "Tiền tệ": "", "Trạng thái": "Thiếu giá niêm yết" if listed is None else ("Có chiết khấu" if discount is not None and discount > 0 else "Không giảm giá"),
                    "URL sản phẩm": urljoin(base_url, f"/products/{handle}"),
                    "Nguồn giá": "Shopify products.json",
                    "Thời điểm quét": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                })
                if len(rows) >= min(int(max_products), 50):
                    return rows, errors
        if rows:
            return rows[:50], errors

    queue, visited, links = [normalized], set(), []
    while queue and len(visited) < min(int(max_category_pages), 3):
        page = queue.pop(0)
        if page in visited:
            continue
        visited.add(page)
        response = _safe_get(session, page, robots)
        if response is None:
            errors.append(f"Không truy cập được trang danh mục: {page}")
            continue
        row = _product_row(response.text, response.url, shop)
        if row and row["URL sản phẩm"] not in links:
            rows.append(row)
            links.append(row["URL sản phẩm"])
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.find_all("a", href=True):
            candidate = _normal_url(urljoin(response.url, anchor["href"]))
            if candidate and _host_key(candidate) == _host_key(base_url) and re.search(r"/(products?|p|item|items)/[^/]+", urlparse(candidate).path, re.I) and candidate not in links:
                links.append(candidate)
                if len(links) >= min(int(max_products), 50):
                    break
        nxt = soup.select_one('a[rel~="next"][href]')
        if nxt:
            next_url = _normal_url(urljoin(response.url, nxt["href"]))
            if next_url and _host_key(next_url) == _host_key(base_url) and next_url not in visited:
                queue.append(next_url)
        time.sleep(max(1.0, float(delay)))

    for product_url in links:
        if len(rows) >= min(int(max_products), 50):
            break
        if any(r["URL sản phẩm"] == product_url for r in rows):
            continue
        response = _safe_get(session, product_url, robots)
        if response is None:
            errors.append(f"Không đọc được trang sản phẩm: {product_url}")
            continue
        row = _product_row(response.text, response.url, shop)
        if row:
            rows.append(row)
        else:
            errors.append(f"Không tìm thấy tên/giá sản phẩm: {product_url}")
        time.sleep(max(1.0, float(delay)))

    if not rows and not errors:
        errors.append("Không tìm thấy sản phẩm. Hãy thử URL trang danh mục/collection; website có thể tải dữ liệu bằng JavaScript hoặc chặn truy cập tự động.")
    return rows, errors
