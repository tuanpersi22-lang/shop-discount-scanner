from io import BytesIO

import pandas as pd


COLUMNS = [
    "Shop", "Sản phẩm", "Biến thể", "SKU", "Giá niêm yết", "Giá bán",
    "Tỷ lệ giá bán (%)", "Chiết khấu (%)", "Tiền tệ", "Trạng thái",
    "URL sản phẩm", "Nguồn giá", "Thời điểm quét",
]


def load_chrome_export(file_bytes):
    """Validate and normalize the CSV exported by the SHOP DISCOUNT SCANNER Chrome extension."""
    try:
        frame = pd.read_csv(BytesIO(file_bytes))
    except Exception as exc:
        raise ValueError(f"Không đọc được CSV: {exc}") from exc

    if frame.empty:
        raise ValueError("File CSV không có sản phẩm nào.")

    frame.columns = [str(column).strip() for column in frame.columns]
    aliases = {
        "Tên sản phẩm": "Sản phẩm",
        "Giá gốc": "Giá niêm yết",
        "Giá hiện tại": "Giá bán",
        "Giảm giá (%)": "Chiết khấu (%)",
        "Product URL": "URL sản phẩm",
    }
    frame = frame.rename(columns={key: value for key, value in aliases.items() if key in frame.columns})

    if "Sản phẩm" not in frame.columns or "Giá bán" not in frame.columns:
        raise ValueError("CSV thiếu cột 'Sản phẩm' hoặc 'Giá bán'. Hãy xuất file từ tiện ích SHOP DISCOUNT SCANNER.")

    for column in COLUMNS:
        if column not in frame.columns:
            frame[column] = None

    for column in ("Giá niêm yết", "Giá bán", "Tỷ lệ giá bán (%)", "Chiết khấu (%)"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame["Sản phẩm"] = frame["Sản phẩm"].fillna("").astype(str).str.strip()
    frame = frame[(frame["Sản phẩm"] != "") & frame["Giá bán"].notna()].copy()
    if frame.empty:
        raise ValueError("Không tìm thấy dòng nào có tên sản phẩm và giá bán hợp lệ.")

    has_list = frame["Giá niêm yết"].notna() & (frame["Giá niêm yết"] > 0)
    frame.loc[has_list, "Tỷ lệ giá bán (%)"] = (
        frame.loc[has_list, "Giá bán"] / frame.loc[has_list, "Giá niêm yết"] * 100
    ).round(2)
    frame.loc[has_list, "Chiết khấu (%)"] = (
        1 - frame.loc[has_list, "Giá bán"] / frame.loc[has_list, "Giá niêm yết"]
    ).mul(100).round(2)

    frame.loc[~has_list, "Trạng thái"] = "Thiếu giá niêm yết"
    frame.loc[has_list & frame["Chiết khấu (%)"].gt(0), "Trạng thái"] = "Có chiết khấu"
    frame.loc[has_list & frame["Chiết khấu (%)"].le(0), "Trạng thái"] = "Không giảm giá"
    frame["Nguồn giá"] = frame["Nguồn giá"].fillna("Chrome extension (Shopee DOM)")
    frame["Tiền tệ"] = frame["Tiền tệ"].fillna("VND")
    return frame[COLUMNS].where(pd.notna(frame[COLUMNS]), None).to_dict(orient="records")
