from decimal import Decimal
from unittest.mock import Mock, patch
from urllib.parse import urlparse
from scanner import calculate_discount, parse_money, _normal_url, _public_host


def test_parse_vietnamese_thousands():
    assert parse_money("1.299.000₫") == Decimal("1299000")


def test_parse_us_price():
    assert parse_money("$1,299.00") == Decimal("1299.00")


def test_calculate_discount():
    ratio, discount = calculate_discount("1000000", "700000")
    assert ratio == Decimal("70.00")
    assert discount == Decimal("30.00")


def test_missing_list_price():
    ratio, discount = calculate_discount(None, "700000")
    assert ratio is None
    assert discount is None


def test_reject_private_and_nonstandard_hosts():
    assert _public_host("127.0.0.1") is False
    assert _normal_url("http://example.com:8080") is None
    assert _normal_url("file:///etc/passwd") is None


def test_shopee_collection_prices_are_scaled_and_discount_is_calculated():
    from scanner import _shopee_product_objects, _shopee_product_row

    payload = {
        "data": {
            "items": [{
                "itemid": 123,
                "shopid": 456,
                "name": "Laptop mẫu",
                "price": 7000000000,
                "price_before_discount": 10000000000,
            }]
        }
    }
    items = _shopee_product_objects(payload)
    assert len(items) == 1

    row = _shopee_product_row(
        items[0],
        "shopee.vn",
        "https://shopee.vn",
        "https://shopee.vn/shop?shopCollection=999",
    )
    assert row["Giá bán"] == 70000
    assert row["Giá niêm yết"] == 100000
    assert row["Chiết khấu (%)"] == 30
    assert row["URL sản phẩm"] == "https://shopee.vn/product/456/123"


def test_shopee_nested_item_card_uses_display_name_and_price():
    from scanner import _shopee_product_objects, _shopee_product_row

    payload = {
        "data": {
            "item_cards": [{
                "item_data": {
                    "itemid": 789,
                    "shopid": 456,
                    "item_card_display_price": {"price": 8000000000},
                    "price_before_discount": 10000000000,
                },
                "item_card_displayed_asset": {"name": "Máy tính mẫu"},
            }]
        }
    }
    items = _shopee_product_objects(payload)
    assert len(items) == 1
    row = _shopee_product_row(items[0], "Shop mẫu", "https://shopee.vn", "https://shopee.vn/shop")
    assert row["Sản phẩm"] == "Máy tính mẫu"
    assert row["Giá bán"] == 80000
    assert row["Giá niêm yết"] == 100000
    assert row["Chiết khấu (%)"] == 20


def test_shopee_collection_queries_collection_id_without_resolving_shop_id():
    from scanner import _scan_shopee_collection

    class FakeResponse:
        def json(self):
            return {
                "data": {
                    "items": [{
                        "itemid": 123,
                        "shopid": 456,
                        "name": "Sách mẫu",
                        "price": 7000000000,
                        "price_before_discount": 10000000000,
                    }]
                }
            }

    url = "https://shopee.vn/mcbookssaigon?shopCollection=261476905#product_list"
    with patch("scanner._safe_get", return_value=FakeResponse()) as mocked_get:
        rows, errors = _scan_shopee_collection(
            Mock(),
            url,
            urlparse(url),
            "shopee.vn",
            None,
            50,
        )

    assert errors == []
    assert len(rows) == 1
    assert rows[0]["Sản phẩm"] == "Sách mẫu"
    assert rows[0]["Chiết khấu (%)"] == 30
    requested_url = mocked_get.call_args.args[1]
    assert "/api/v4/collection/get_items?" in requested_url
    assert "collection_id=261476905" in requested_url


def test_shopee_shop_card_discount_is_used_when_list_price_is_not_in_card():
    from scanner import _shopee_product_objects, _shopee_product_row

    payload = {
        "data": {
            "items": [{
                "itemid": 123,
                "shopid": 456,
                "item_data": {
                    "item_card_display_price": {
                        "price": 7000000000,
                        "discount": 30,
                    }
                },
                "item_card_displayed_asset": {"name": "Sách mẫu"},
            }]
        }
    }
    items = _shopee_product_objects(payload)
    assert len(items) == 1
    row = _shopee_product_row(items[0], "MCBOOKS", "https://shopee.vn", "https://shopee.vn/mcbookssaigon")
    assert row["Sản phẩm"] == "Sách mẫu"
    assert row["Giá bán"] == 70000
    assert row["Giá niêm yết"] == 100000
    assert row["Chiết khấu (%)"] == 30


def test_shopee_shop_home_resolves_username_then_searches_shop_items():
    from scanner import _scan_shopee_shop
    from urllib.parse import urlparse
    from unittest.mock import Mock, patch

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    url = "https://shopee.vn/mcbookssaigon"
    detail_response = FakeResponse({"data": {"shopid": 456, "name": "MCBOOKS"}})
    items_response = FakeResponse({
        "data": {
            "items": [{
                "itemid": 123,
                "shopid": 456,
                "item_data": {
                    "item_card_display_price": {"price": 7000000000, "discount": 30}
                },
                "item_card_displayed_asset": {"name": "Sách mẫu"},
            }]
        }
    })
    with patch("scanner._safe_post", return_value=detail_response) as mocked_post, \
         patch("scanner._safe_get", return_value=items_response) as mocked_get:
        rows, errors = _scan_shopee_shop(
            Mock(), url, urlparse(url), "shopee.vn", None, 30
        )

    assert errors == []
    assert len(rows) == 1
    assert rows[0]["Shop"] == "MCBOOKS"
    assert rows[0]["Chiết khấu (%)"] == 30
    assert "get_shop_base_v2" in mocked_post.call_args.args[1]
    assert "/api/v4/search/search_items?" in mocked_get.call_args.args[1]
    assert "match_id=456" in mocked_get.call_args.args[1]
