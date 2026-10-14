# STRESS TEST — Bad Genius (2017), chính kịch học đường / heist, tiếng Thái

*Mục đích: đo xem `RULES.md` gãy ở đâu với phim KHÔNG nói tiếng Anh, và với phim dựng nhanh.*
*Trạng thái: **ĐANG MỞ** — mới xong catalogue, chưa có draft, chưa render.*

**Nguồn:** `source.mp4` 7793.06s (129.9 phút container). Phần tự sự **7353s = 122.5 phút** (00:01:22 → 02:03:55; 82s ident đầu, credit cuối). Mọi con số phủ sóng dưới đây tính trên 122.5 phút.

---

## Kết luận một dòng

Không rule nào gãy. Nhưng phim này đưa ra **bằng chứng mạnh nhất từ trước tới nay cho B10**: lưới 5 giây không làm mờ một cú máy — nó **đánh rơi hẳn một nút thắt cốt truyện**, và khi kiểm lại thì **7 trên 9 shot cũ ghi sai**.

---

## 1. Con số: lưới 5s bỏ sót bao nhiêu

`_cuts.json` — 1814 cut, 1813 shot đo được:

| | giá trị |
|---|---|
| trung bình | 4.30s |
| **trung vị** | **3.00s** |
| p25 | 1.88s |
| p90 | 8.25s |

Với lưới đều bước `s`, một shot dài `d` bị bỏ qua hoàn toàn với xác suất `max(0, 1 − d/s)`. Cộng trên cả phim:

| bước lưới | shot ngắn hơn bước | **kỳ vọng số shot KHÔNG BAO GIỜ được lấy mẫu** |
|---|---|---|
| **5.0s** (pass 1) | 1346 / 74% | **670 / 37%** |
| **2.0s** (pass 2–4) | 508 / 28% | 172 / 9% |
| 0.75s (zoom) | 32 / 2% | 3 / 0% |

> Đây mới là con số phải trích, không phải "74%". **74% là shot ngắn hơn bước lưới; 37% là shot lưới không hề chạm vào.** Với 1813 shot, lưới 5s được kỳ vọng bỏ trắng khoảng **670 cú máy**.

---

## 2. Bằng chứng B10: một nút thắt bị đánh rơi, không phải một cú máy bị mờ

Trong SP5 (chiến dịch STIC, 01:21–01:49), giữa **01:26:48 và 01:28:12**, Bank — đang khoá trong buồng vệ sinh giữa giờ thi — **đòi thêm tiền**. Bangkok trả. Có insert app ngân hàng đọc rõ **485,000.00**.

- **Ở lưới 5s:** bốn frame insert điện thoại không đọc được. Pass 1 ghi **không có gì**. Beat map 79 beat không có beat này.
- **Ở lưới 2s:** đọc được toàn bộ, kể cả con số.
- **Hệ quả:** chèn beat mới **B58**, dồn số B58–B79 cũ thành B59–B80. Beat map thành 80 beat.

Đây không phải "shot bị mờ nên mô tả kém". Đây là **một hành động của nhân vật chính, có hệ quả tiền bạc, biến mất khỏi bản đồ truyện**. Nếu draft đã viết trên beat map 79 beat, khán giả sẽ không bao giờ biết Bank tống tiền chính đồng đội của mình giữa kỳ thi — mà đó chính là bước đầu của R2 (Bank trở về hỏng, 01:58:45).

**B10 trước đây chỉ có lập luận. Giờ nó có một ca cụ thể.**

---

## 3. Kiểm lại 9 shot `[grid 5s]` còn sót — 7/9 phải sửa

Sau khi catalogue xong, 9 shot từ pass 1 vẫn mang nhãn `[grid 5s]`. Chúng được chọn *vì* tĩnh và dài — tức đúng điều kiện lưới thô còn hợp lệ. Vẫn kiểm lại toàn bộ ở 2s:

| shot | phán quyết | sai ở đâu |
|---|---|---|
| B01 01:25 gương | **ĐÚNG** | — |
| B01 01:40 túi tang vật | **SAI NẶNG** | 5s ghi "bút chì và tẩy" — ở 2s lẫn 0.75s đều KHÔNG phân giải được vật gì. Và ghi sai thứ tự: túi được đẩy sang *sau* khi cô nhìn, không phải trước. |
| B03 02:55 phỏng vấn | **SAI NẶNG** | Cảnh đọc hồ sơ nằm ở 02:28–02:48, *trước* cửa sổ shot. Ở 02:55 hồ sơ đã đóng. Và trong phòng có **hai** cán bộ, không phải một "giám hiệu". |
| B04 03:35 "120,000" | nhẹ | Con số đúng tuyệt đối. Nhưng quy cho "giám hiệu" là sai, và motif chữ số còn chạy tiếp tới 150,000 khoanh tròn ở 04:18. |
| B06 05:15 tường đỏ | **SAI NẶNG** | Đó là **buổi chụp ảnh thẻ** — tường đỏ là phông, có máy ảnh trên chân. Pass 1 bỏ sót hoàn toàn, mà đó mới là lý do Grace sửa tóc cho Lynn. |
| B07 07:40 phiếu hồng | nhẹ | Phiếu hồng + biểu đồ Venn đúng. Nhưng "ngồi bệt sàn thư viện" nằm ở 07:16–07:26, ngoài cửa sổ shot. |
| B35 46:15 bàn tròn | **ĐÚNG** | Người cha đứng suốt, không ngồi lần nào. Đúng nguyên văn. |
| B52 01:18:30 vòm đá | nhẹ | Khung hình đúng. "Ngày hôm trước" là suy diễn — phim có title SYDNEY ở 18:14 nhưng không hề định ngày so với kỳ thi. |
| B74 01:53:35 sân bay | **SAI NẶNG ×2** | 5s ghi ôm là "việc đầu tiên cô làm". Thực tế hai cha con **đứng nói chuyện gần nửa phút** rồi mặt cô mới vỡ. Và "Don Mueang" không hề xuất hiện trong khung hình. |

**2 đứng, 3 sai nhẹ, 4 sai nặng.** Cả 9 đã viết lại theo đúng frame 2s và gắn nhãn `[grid 2s, re-verified]`. `shots.json` hiện **không còn shot `[grid 5s]` nào**.

> Điểm đáng chú ý nhất: 9 shot này là những shot **dễ nhất** — tĩnh, dài, được chọn có chủ đích để lưới thô vẫn đúng. Tỉ lệ sai vẫn là 7/9. Sai số của lưới 5s không nằm ở shot khó; nó nằm ở khắp nơi.

---

## 4. Ba dạng sai, không phải một

Tách ra thì lỗi lưới thô có ba kiểu khác hẳn nhau:

1. **Bỏ trắng** — beat B58. Lưới không chạm vào, nên không có gì để ghi.
2. **Đoán chi tiết không nhìn thấy** — "bút chì và tẩy", "Don Mueang", "ngày hôm trước". Lưới thô chừa khoảng trống, và người viết lấp bằng suy luận hợp lý. **Đây là dạng nguy hiểm nhất**, vì kết quả đọc trôi chảy và không có dấu hiệu gì là bịa.
3. **Lệch cửa sổ** — B03, B07. Nội dung mô tả có thật, nhưng nằm ngoài đoạn clip đã ghi. Draft sẽ nói một đằng, hình chạy một nẻo.

Dạng 3 là dạng `binding_audit` bắt được. Dạng 1 và 2 thì **không máy nào bắt được** — chỉ có nhìn lại ở lưới mịn hơn.

---

## 5. Số liệu catalogue

| | pass 1 (5s) | hiện tại (2s + 0.75s) |
|---|---|---|
| shot | 21 | **126** |
| shot `[grid 5s]` | 21 | **0** |
| shot `[grid 2s]` | 0 | 108 |
| shot `[dense 0.75s]` | 0 | 18 |
| footage đã buộc | 269s / 3.7% | **1330s = 22.2 phút / 18.1%** |
| beat chạm tới | 16 / 79 | **41 / 80 = 51%** |
| shot có ≥3 tag | 0 | 0 |

Set-piece SP5 (01:21–01:49): **70 shot, 719s / 42% độ dài chuỗi**, phủ trọn B53–B72.

Kiểm máy: `load_shots` 126/126, `problems: 0`, không chồng lấn, sắp xếp tăng dần theo `clip_start`.

---

## 6. Rule: có gì gãy không

**Không.** Không rule nào phải phá, uốn hay lách trong cả bốn pass.

Ba ghi nhận:

- **A5 chạy đúng 3 lần và giữ được cả 3.** Vật trong ủng Lynn (B63) không nhìn thấy được kể cả ở 0.75s → ghi hành động, không đặt tên vật. Cô gái cười ở 00:39:06 quá nhỏ để đối chiếu `names.json` → để `chars: []`. Túi tang vật ở 01:40 → ghi "vật nhỏ sẫm màu", không đoán.
- **S10 chạy đúng theo cả hai chiều trong cùng một pass.** `DEPTH-REACTION` nổ ở B54 → xem lại thì frame 0.75s đúng là có shot còn thiếu (01:21:39, mặt Lynn phản chiếu trong hộp tường) → thêm. Nổ ở B59 → beat đó *là* cái máy in, không có khoảnh khắc phản ứng sạch → **giữ nguyên 1 shot, để cảnh báo đứng**, ghi vào `beats_proposal.md`. Hiếm khi có ví dụ sạch cho cả hai chiều trong một lượt.
- **P1 (mới, trong `TAGGING_GUIDE.md`) áp được cho cả người, không chỉ parser.** Nhãn `[grid 2s]` / `[dense 0.75s]` / `[grid 5s]` chính là "tự khai đã khớp bằng hình dạng nào". Chính nhãn đó khiến việc kiểm lại mục 3 khả thi. Nếu pass 1 không ghi nhãn, sẽ không có cách nào biết shot nào cần kiểm lại.

**Ứng viên sửa rule duy nhất còn treo** vẫn là **H1 thiếu phép thử thứ ba** — nhưng đó là câu hỏi tầng viết lời, không tầng catalogue, nên chưa thể trả lời cho tới khi có draft.

---

## 7. Đề xuất (chưa áp dụng)

Không đề xuất gate mới. Đề xuất **một dòng trong quy trình**, vì nó rẻ và đã tự chứng minh:

> Trước khi catalogue, chạy `_cuts.json` ra trung vị độ dài shot. **Bước lưới phải ≤ trung vị.** Ghi bước lưới vào từng shot. Nếu về sau bước lưới đổi, mọi shot mang bước cũ phải kiểm lại trước khi vào draft — kể cả shot "dễ".

Con số biện minh (đã tính, không ước): ở bước = trung vị (3.0s), kỳ vọng bỏ trắng **20%**; ở bước 5s là **37%**; Bad Genius chạy 2s, ra **9%**.

⚠️ Lưu ý: "bước ≤ trung vị" vẫn để lọt 20%. Nếu muốn xuống dưới 10% thì phải là **≈ ⅔ trung vị**, tức 2.0s cho phim này. Ngưỡng đúng là ⅔ trung vị, không phải trung vị — con số ban đầu viết trong bản nháp mục này là "~17%" và đã sai; sửa sau khi tính.

**Chưa đề xuất thành rule** vì mới đo trên **một** phim. Cần ít nhất một phim nữa có `_cuts.json` để biết trung vị 3.0s là bất thường hay bình thường.

---

## 8. Câu hỏi còn mở

1. 39/80 beat vẫn chưa có shot nào — phần lớn nằm ở 00:08–00:21, 00:40–01:18, 01:50–02:04. Có cần phủ hết không, hay 126 shot đã đủ cho 18–22 phút?
2. Whisper `--translate` dịch Thái→Anh; transcript gọi nhân vật chính là "Lin", `names.json` ghi **Lynn**. Đã theo `names.json` (I4 + S5). Nhưng chưa có rule nào nói rõ ai thắng khi transcript và `names.json` lệch tên riêng.
3. Hai cán bộ trong phòng giám hiệu (một nam một nữ) đều không có tên trong phim. S5 buộc mô tả theo vai trò — nhưng cả hai cùng vai "cán bộ nhà trường", nên không phân biệt được trong lời dẫn. Chưa có cách xử lý.
