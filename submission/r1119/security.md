# Bảo mật khi làm việc

> Gắn với lô `lab250_` của seed 1119 (250 ảnh, 10 job J01–J10, người gán A01–A05, người kiểm Q01–Q03).

## 1. Ca USB: hết giờ, muốn chép lô về nhà làm tiếp
Không chép. Lô này có ảnh người thật (ví dụ 000000004395, 000000001296) và nhãn của dự án; ra khỏi máy công ty là mất kiểm soát: USB rơi, máy nhà không mã hoá, không có log ai mở. Gửi qua email cá nhân hay nhờ người khác làm hộ cũng sai vì đều đưa dữ liệu ra ngoài kênh được duyệt và người kia không có quyền với job. Cách đúng: dừng ở job đang mở, lưu trên CVAT, báo trưởng nhóm xin thêm thời gian hoặc xin truy cập từ xa qua VPN/máy được cấp; dữ liệu luôn nằm trên hạ tầng của dự án.

## 2. Năm việc: được hay không
- Mở job được giao trên máy công ty: **được**, đúng quyền, đúng máy, có log.
- Chụp màn hình gửi người quen: **không**, ảnh chụp chứa ảnh gốc và nhãn, ra ngoài kênh dự án, không thu hồi được.
- Chép lô ra USB: **không**, như ca 1; muốn chuyển dữ liệu thì qua kho lưu trữ của dự án có phân quyền.
- Dán nhãn thật lên chatbot: **không**, dữ liệu dự án thật gửi lên dịch vụ ngoài có thể bị lưu hoặc dùng để train. (Trong lab chỉ ảnh COCO công khai mới được hỏi AI, và phải ghi vào prompts.md.)
- Đưa tài khoản CVAT cho đồng nghiệp: **không**, mất truy vết ai gán/kiểm (truyvet.csv và rework_queue dựa vào mã người), và đồng nghiệp có thể không có quyền với job đó; nhờ trưởng nhóm giao job cho họ.

## 3. Ca khuôn mặt: thấy mặt người rõ trong lô, guideline yêu cầu làm mờ
Ví dụ trong lô: `000000004395` (nam mặc sơ mi, cà vạt, mặt nhìn thẳng rõ), `000000001296` (cô gái cầm điện thoại, mặt rõ), `000000016598` (người tóc xanh chụp selfie trước gương, mặt rõ). Kết luận: **Hold** lô (không Release, không giao cho team AI) và **báo người phụ trách** dữ liệu/bảo mật của dự án kèm danh sách ảnh. Không tự làm mờ hay xoá ảnh: tự sửa ảnh là ghi đè v1 (hash đổi, mất truy vết), có thể làm sai nhãn (box quanh mặt), và việc làm mờ phải theo quy trình thống nhất có người duyệt; xoá ảnh thì mất bằng chứng và lệch số liệu. Người phụ trách quyết định làm mờ ở bản mới (v2) bằng quy trình chuẩn, rồi mới đóng gói lại.
