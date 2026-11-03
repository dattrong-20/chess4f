# Ảnh minh họa cho báo cáo Trực quan hóa dữ liệu

Thư mục này chứa các ảnh cần chèn vào báo cáo, đặt tên theo số hình và nội dung.

| Tệp | Hình | Nội dung / cấu hình |
|---|---|---|
| `hinh-01-kien-truc-he-thong.png` | Hình 1 | Sơ đồ kiến trúc Chess4F: nguồn dữ liệu, Bronze–Silver–Gold, MinIO, Trino, FastAPI, Streamlit; Dagster điều phối và Spark kiểm chứng. |
| `hinh-02-pham-vi-du-lieu-lichess.png` | Hình 2 | Phạm vi dữ liệu Lichess: 100.000 ván từ 10 tệp tháng, 10 ván đồng bộ tài khoản và 1 ván quan sát trực tiếp; tổng 100.011 ván, lưu ý mẫu tập trung ngày đầu tháng. |
| `hinh-03-nhan-dien-khai-cuoc.png` | Hình 3 | Quy trình nhận diện khai cuộc: PGN/nước đi → tái tạo bàn cờ → khóa vị trí → đối chiếu danh mục trong 36 ply → giữ nhãn gần nhất và mã ECO. |
| `hinh-04-cac-lop-du-lieu.png` | Hình 4 | Các lớp Bronze, Silver, Gold, Quarantine; bước kiểm chứng và công bố release trước khi dashboard đọc. |
| `hinh-05-tong-quan-dashboard.png` | Hình 5 | Tổng quan dashboard: thẻ chỉ số, bộ lọc nguồn/thể thức, biểu đồ khai cuộc phổ biến, cơ cấu kết quả và bảng số liệu. |
| `hinh-06-c1-khai-cuoc-pho-bien.png` | Hình 6 | C1 — Top 5 khai cuộc phổ biến, Lichess Blitz tháng 01–10/2026, ngưỡng 200 ván; mẫu 74.934 ván, top 5 chiếm 37,91%. |
| `hinh-07-c2-ty-trong-theo-thang.png` | Hình 7 | C2 — Tỷ trọng top 5 khai cuộc theo tháng; tháng thiếu quan sát không được thay bằng 0. |
| `hinh-08-c3-co-cau-ket-qua.png` | Hình 8 | C3 — Cơ cấu thắng/hòa/thua của top 5 khai cuộc (tỷ lệ % xếp chồng). |
| `hinh-09-c4-ty-le-diem-theo-elo.png` | Hình 9 | C4 — Ma trận điểm Trắng theo nhóm khai cuộc và nhóm Elo, 7 nhóm khai cuộc, thang màu 40–60%, ngưỡng 200 ván. |
| `hinh-10-c5-pho-bien-va-diem.png` | Hình 10 | C5 — Tương quan giữa tỷ trọng sử dụng và điểm Trắng; kích thước điểm biểu diễn số ván, đường nét đứt 50%. |
| `hinh-11-c6-bien-the-sicilian.png` | Hình 11 | C6 — So sánh biến thể Sicilian Defense ở nhóm Elo 1600–1999 (thắng/hòa/thua). |
| `hinh-12-c7-ket-qua-theo-thang.png` | Hình 12 | C7 — Điểm Trắng theo tháng của top 5 khai cuộc, nhóm Elo 1600–1999, ngưỡng 200 ván; điểm dưới ngưỡng được để trống. |
| `hinh-13-ho-so-nguoi-choi.png` | Hình 13 | Hồ sơ người chơi Chess.com — hikaru: tổng kết thắng/hòa/thua, khai cuộc thường dùng, đối thủ gặp nhiều nhất và diễn biến Elo. |
| `hinh-14-xem-lai-van.png` | Hình 14 | Xem lại ván Lichess wGPgx5tW: bàn cờ, điều khiển ⏮ ◀ ▶ ⏭, danh sách ply và thanh đánh giá từ bình luận PGN. |
| `hinh-14b-quan-sat-live.png` | Hình 14b | Live observer ván eRIlxQlE: trạng thái luồng, thời điểm nhận, nhãn khai cuộc, bàn cờ và thông báo ván đã kết thúc được xếp hàng nhập. |
| `hinh-15-tinh-huong-phan-tich.png` | Hình 15 | Tình huống phân tích: C1 với ngưỡng 200 ván, mở bảng số liệu và nút tải CSV để kiểm tra/tái lập. |

## Ghi chú kỹ thuật

- Ảnh 01–04 là sơ đồ được vẽ lại từ mô tả trong báo cáo (Pillow, font Segoe UI).
- Ảnh 05–15 là ảnh chụp dashboard thật bằng Playwright trên release `r_e3f3e2f2603b487d89a35c656adb5557` (107.155 ván; Lichess 100.011, Chess.com 7.144).
- C1–C7 dùng cấu hình Lichess + Blitz, tháng 01–10/2026, ngưỡng 200 ván; C1 và C2 dùng top 5, C4 dùng top 7.
- Ảnh C4 có thang màu 40–60% để nhìn rõ khác biệt quanh mốc 50%.
- Ảnh 14 dùng ván Lichess có bình luận `[%eval]`; ván Chess.com không có eval nên thanh đánh giá bị ẩn.
