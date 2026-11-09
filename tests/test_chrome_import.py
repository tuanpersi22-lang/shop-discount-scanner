from chrome_import import load_chrome_export


def test_load_chrome_export_recalculates_discount_from_observed_prices():
    data = (
        "Shop,Sản phẩm,Giá niêm yết,Giá bán,Tỷ lệ giá bán (%),Chiết khấu (%),URL sản phẩm\n"
        "mcbookssaigon,Sách mẫu,100000,70000,,,https://shopee.vn/product/1/2\n"
    ).encode("utf-8")
    rows = load_chrome_export(data)
    assert len(rows) == 1
    assert rows[0]["Giá niêm yết"] == 100000
    assert rows[0]["Giá bán"] == 70000
    assert rows[0]["Tỷ lệ giá bán (%)"] == 70
    assert rows[0]["Chiết khấu (%)"] == 30
    assert rows[0]["Trạng thái"] == "Có chiết khấu"


def test_load_chrome_export_keeps_missing_list_price_unknown():
    data = (
        "Shop,Sản phẩm,Giá bán,Chiết khấu (%),URL sản phẩm\n"
        "shop,Sách chỉ có giá bán,70000,,https://shopee.vn/product/1/3\n"
    ).encode("utf-8")
    rows = load_chrome_export(data)
    assert rows[0]["Giá niêm yết"] is None
    assert rows[0]["Chiết khấu (%)"] is None
    assert rows[0]["Trạng thái"] == "Thiếu giá niêm yết"


def test_load_chrome_export_rejects_unrecognized_csv():
    try:
        load_chrome_export(b"hello,world\n1,2\n")
    except ValueError as exc:
        assert "thiếu cột" in str(exc).lower()
    else:
        raise AssertionError("Expected invalid CSV to be rejected")
