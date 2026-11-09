from io import BytesIO
from datetime import datetime
import pandas as pd
import streamlit as st

from scanner import scan_shop

st.set_page_config(
    page_title="Shop Discount Scanner",
    page_icon="🛍️",
    layout="wide",
)

st.title("🛍️ SHOP DISCOUNT SCANNER")
st.caption("Quét giá niêm yết, giá bán và tỷ lệ chiết khấu của nhiều shop trong một lần chạy.")
st.info("Bản dùng chung miễn phí: tối đa 5 shop/lần, 50 sản phẩm/shop và 3 trang danh mục/shop để hạn chế tải lên máy chủ.")

with st.expander("Công thức tính và cách đọc báo cáo", expanded=True):
    st.markdown(
        """
        - **Tỷ lệ giá bán (%)** = Giá bán / Giá niêm yết × 100%.
        - **Chiết khấu (%)** = (1 − Giá bán / Giá niêm yết) × 100%.
        - Ví dụ: giá niêm yết 1.000.000đ, giá bán 700.000đ → tỷ lệ giá bán 70%, chiết khấu 30%.
        - Nếu shop không công bố giá niêm yết/giá gạch ngang, công cụ sẽ ghi **Thiếu giá niêm yết** và không tự suy đoán mức giảm.
        """
    )

st.subheader("1. Danh sách shop cần quét")
urls_text = st.text_area(
    "Dán URL shop hoặc URL trang danh mục sản phẩm (mỗi dòng một URL)",
    height=160,
    placeholder=(
        "https://shop-a.vn/collections/all\n"
        "https://shop-b.vn\n"
        "https://shop-c.vn/danh-muc-san-pham"
    ),
)

uploaded = st.file_uploader("Hoặc tải lên file TXT/CSV chứa danh sách URL", type=["txt", "csv"])
if uploaded is not None:
    try:
        uploaded_text = uploaded.getvalue().decode("utf-8-sig")
        st.caption("Đã nhận file danh sách URL; nội dung file sẽ được cộng với các URL ở ô phía trên.")
    except Exception:
        uploaded_text = ""
        st.warning("Không đọc được file. Hãy dùng UTF-8.")

col_a, col_b, col_c = st.columns(3)
with col_a:
    max_products = st.number_input("Số sản phẩm tối đa mỗi shop", min_value=10, max_value=50, value=30, step=10)
with col_b:
    max_pages = st.number_input("Số trang danh mục tối đa mỗi shop", min_value=1, max_value=3, value=3, step=1)
with col_c:
    delay = st.number_input("Nghỉ giữa các lần truy cập (giây)", min_value=1.0, max_value=5.0, value=1.5, step=0.5)

run = st.button("🔎 QUÉT VÀ LẬP BÁO CÁO", type="primary", use_container_width=True)


def extract_urls(*texts):
    found = []
    seen = set()
    for text in texts:
        for line in (text or "").splitlines():
            value = line.strip().strip('"').strip("'")
            if not value:
                continue
            if "," in value and not value.lower().startswith(("http://", "https://")):
                value = value.split(",")[0].strip().strip('"')
            if value.startswith(("http://", "https://")) and value not in seen:
                found.append(value)
                seen.add(value)
    return found


if run:
    urls = extract_urls(urls_text, uploaded_text if uploaded is not None else "")
    if not urls:
        st.warning("Bạn cần nhập ít nhất một URL shop.")
    elif len(urls) > 5:
        st.error(f"Mỗi lượt chỉ quét tối đa 5 shop. Bạn đang nhập {len(urls)} URL; hãy chia thành nhiều lượt.")
    else:
        all_rows = []
        all_errors = []
        progress = st.progress(0)
        status = st.empty()

        for index, shop_url in enumerate(urls, start=1):
            status.write(f"Đang quét shop {index}/{len(urls)}: {shop_url}")
            try:
                rows, errors = scan_shop(
                    shop_url,
                    max_products=int(max_products),
                    max_category_pages=int(max_pages),
                    delay=float(delay),
                )
                all_rows.extend(rows)
                for error in errors:
                    all_errors.append({"Shop URL": shop_url, "Lỗi/Ghi chú": error})
            except Exception as exc:
                all_errors.append({"Shop URL": shop_url, "Lỗi/Ghi chú": f"Lỗi ngoài dự kiến: {exc}"})
            progress.progress(index / len(urls))

        status.write("Hoàn tất quét.")
        st.session_state["discount_rows"] = all_rows
        st.session_state["discount_errors"] = all_errors
        st.session_state["discount_scanned_at"] = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")

if "discount_rows" in st.session_state:
    rows = st.session_state["discount_rows"]
    errors = st.session_state.get("discount_errors", [])
    scanned_at = st.session_state.get("discount_scanned_at", "")

    st.divider()
    st.subheader("2. Báo cáo kết quả")
    st.caption(f"Thời điểm quét: {scanned_at}")

    if rows:
        df = pd.DataFrame(rows)
        total = len(df)
        with_list = int(df["Giá niêm yết"].notna().sum())
        discounts = pd.to_numeric(df["Chiết khấu (%)"], errors="coerce").dropna()
        avg_discount = float(discounts.mean()) if not discounts.empty else 0.0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Tổng sản phẩm", f"{total:,}")
        m2.metric("Có giá niêm yết", f"{with_list:,}")
        m3.metric("Có dữ liệu chiết khấu", f"{len(discounts):,}")
        m4.metric("Chiết khấu trung bình", f"{avg_discount:.2f}%")

        summary = (
            df.groupby("Shop", dropna=False)
            .agg(
                **{
                    "Số sản phẩm": ("Sản phẩm", "count"),
                    "Có giá niêm yết": ("Giá niêm yết", "count"),
                    "Chiết khấu trung bình (%)": ("Chiết khấu (%)", "mean"),
                    "Chiết khấu cao nhất (%)": ("Chiết khấu (%)", "max"),
                }
            )
            .reset_index()
        )
        st.markdown("**Tổng hợp theo shop**")
        st.dataframe(summary, use_container_width=True, hide_index=True)

        shops = ["Tất cả"] + sorted(df["Shop"].dropna().unique().tolist())
        f1, f2 = st.columns([2, 1])
        with f1:
            selected_shop = st.selectbox("Lọc theo shop", shops)
        with f2:
            min_discount = st.number_input("Chiết khấu tối thiểu (%)", min_value=-100.0, max_value=100.0, value=-100.0, step=5.0)

        view = df.copy()
        if selected_shop != "Tất cả":
            view = view[view["Shop"] == selected_shop]
        view["Chiết khấu (%)"] = pd.to_numeric(view["Chiết khấu (%)"], errors="coerce")
        view = view[
            view["Chiết khấu (%)"].isna()
            | (view["Chiết khấu (%)"] >= min_discount)
        ]
        view = view.sort_values(
            by="Chiết khấu (%)",
            ascending=False,
            na_position="last",
        )

        st.markdown("**Chi tiết từng sản phẩm**")
        st.dataframe(view, use_container_width=True, hide_index=True)

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Chi tiet san pham", index=False)
            summary.to_excel(writer, sheet_name="Tong hop shop", index=False)
            if errors:
                pd.DataFrame(errors).to_excel(writer, sheet_name="Loi va ghi chu", index=False)
        output.seek(0)

        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                "⬇️ Tải báo cáo Excel",
                data=output.getvalue(),
                file_name=f"bao_cao_chiet_khau_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with d2:
            csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇️ Tải báo cáo CSV",
                data=csv_bytes,
                file_name=f"bao_cao_chiet_khau_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
    else:
        st.warning("Chưa thu thập được sản phẩm nào từ các URL đã nhập.")

    if errors:
        st.markdown("**Lỗi và ghi chú khi quét**")
        st.dataframe(pd.DataFrame(errors), use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Lưu ý: Công cụ chỉ đọc dữ liệu công khai, không đăng nhập, không vượt CAPTCHA/paywall. "
    "Kết quả phụ thuộc cấu trúc website, robots.txt và cơ chế chống bot của từng shop. "
    "Nên ưu tiên URL trang danh mục sản phẩm; website tải giá hoàn toàn bằng JavaScript có thể cần bộ kết nối riêng."
)
