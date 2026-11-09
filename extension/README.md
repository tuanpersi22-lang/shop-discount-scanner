# Tiện ích Chrome — SHOP DISCOUNT SCANNER

Tiện ích đọc các sản phẩm và mức giá đang được hiển thị trên trang Shopee.vn trong trình duyệt của bạn. File CSV được tạo cục bộ trên máy; tiện ích không gửi dữ liệu sang máy chủ tiện ích.

## Cài đặt

1. Mở repository GitHub, chọn Code → Download ZIP.
2. Giải nén ZIP vừa tải.
3. Mở Chrome và truy cập chrome://extensions.
4. Bật Developer mode / Chế độ dành cho nhà phát triển.
5. Chọn Load unpacked / Tải tiện ích đã giải nén.
6. Chọn thư mục extension nằm bên trong thư mục vừa giải nén.
7. Mở hoặc tải lại trang Shopee.vn.

## Cách sử dụng

1. Mở trang shop hoặc bộ sưu tập Shopee cần quét.
2. Nếu trang tải sản phẩm khi cuộn, chờ trang tải xong hoặc cuộn xuống một lần.
3. Bấm biểu tượng tiện ích SHOP DISCOUNT SCANNER.
4. Bấm Quét trang Shopee. Tiện ích tự cuộn trang trong giới hạn tối đa 18 lượt và đọc tối đa 300 sản phẩm.
5. Bấm Tải CSV sản phẩm.
6. Mở https://shop-discount-scanner.onrender.com, tải file vào mục Nhập CSV từ tiện ích Chrome, rồi bấm LẬP BÁO CÁO.

## Lưu ý

- Tiện ích đọc DOM đang hiển thị trong tab Shopee; không gọi API riêng, không vượt CAPTCHA, không lấy dữ liệu sau đăng nhập nếu trang không hiển thị cho bạn.
- Sản phẩm tải động hoặc bị ẩn khỏi DOM có thể không được thu thập.
- Giá niêm yết chỉ được ghi khi có giá gạch ngang/giá gốc hiển thị hoặc có nhãn giảm giá rõ ràng. Nếu không, báo cáo ghi Thiếu giá niêm yết.
- Kiểm tra mẫu một số sản phẩm trước khi dùng kết quả cho quyết định kinh doanh.
