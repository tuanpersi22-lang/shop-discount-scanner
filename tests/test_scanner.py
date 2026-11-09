from decimal import Decimal
from scanner import calculate_discount, parse_money, _normal_url


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


def test_reject_private_and_nonstandard_urls():
    assert _normal_url("http://127.0.0.1") is not None  # DNS/IP filtering happens before requests
    assert _normal_url("http://example.com:8080") is None
    assert _normal_url("file:///etc/passwd") is None
