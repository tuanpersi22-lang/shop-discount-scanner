# SHOP DISCOUNT SCANNER

Công cụ quét giá niêm yết và giá bán công khai của nhiều shop, sau đó tính tỷ lệ giá bán và chiết khấu từng sản phẩm.

## Công thức

- **Tỷ lệ giá bán (%)** = Giá bán / Giá niêm yết × 100%.
- **Chiết khấu (%)** = (1 − Giá bán / Giá niêm yết) × 100%.

Ví dụ: giá niêm yết 1.000.000đ, giá bán 700.000đ:
- Tỷ lệ giá bán: 70%.
- Chiết khấu thực tế: 30%.

Nếu không tìm thấy giá niêm yết, công cụ không tự đoán mức giảm mà ghi `Thiếu giá niêm yết`.

## Chạy trên Windows

1. Cài Python 3.10 trở lên: https://www.python.org/downloads/
2. Giải nén file ZIP.
3. Mở thư mục `shop_discount_scanner`.
4. Mở Command Prompt/PowerShell tại thư mục đó và chạy:

```bash
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

5. Trình duyệt sẽ mở giao diện công cụ. Dán URL shop (mỗi dòng một URL), rồi bấm **QUÉT VÀ LẬP BÁO CÁO**.
6. Tải báo cáo Excel hoặc CSV.

Có thể chạy nhanh bằng cách mở `start_windows.bat` sau khi đã cài Python.

## Loại website được hỗ trợ

- Shopify: thử đọc catalogue công khai qua `/products.json`.
- Shopee: hỗ trợ thử đọc URL bộ sưu tập trong shop có tham số `shopCollection`, thông qua endpoint danh sách công khai của Shopee khi `robots.txt` cho phép.
- Website có dữ liệu Product JSON-LD.
- Một số website WooCommerce/HTML có giá trong các thẻ phổ biến như `del`, `ins`, `price`, `sale-price`, `compare-at-price`.
- Trang danh mục có liên kết sản phẩm theo các đường dẫn phổ biến như `/product/`, `/products/`, `/item/`.

## Giới hạn quan trọng

- Đây là bản nền tảng đa shop, không thể cam kết đọc chính xác 100% mọi website.
- Nên nhập URL trang danh mục/collection sản phẩm; nhập trang chủ vẫn có thể không tìm thấy danh sách sản phẩm ở một số shop.
- Website tải dữ liệu bằng JavaScript, yêu cầu đăng nhập, CAPTCHA, chặn bot hoặc có API riêng có thể cần adapter riêng. Riêng Shopee có thể thay đổi API hoặc giới hạn truy cập tự động; bộ quét không vượt CAPTCHA, đăng nhập hay quy tắc `robots.txt`.
- Công cụ tôn trọng `robots.txt`, có thời gian nghỉ giữa các request, chỉ truy cập host công khai và không đi theo redirect sang host khác.
- Công cụ không tìm cách vượt đăng nhập/CAPTCHA hoặc truy cập mạng nội bộ/private IP.
- Chỉ lấy dữ liệu giá công khai tại thời điểm chạy; giá/khuyến mại có thể thay đổi theo tài khoản, khu vực, mã giảm giá, số lượng hoặc phương thức thanh toán.
- Hãy kiểm tra mẫu một vài sản phẩm trước khi dùng báo cáo cho quyết định kinh doanh.

## Cấu trúc

- `app.py`: giao diện Streamlit.
- `scanner.py`: logic đọc dữ liệu shop và tính toán.
- `tests/test_scanner.py`: kiểm thử công thức và bộ đọc giá.
