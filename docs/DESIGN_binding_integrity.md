# THIẾT KẾ — BINDING-INTEGRITY + CATALOGUE-DENSITY

*Trạng thái: **bản thảo, chờ duyệt**. Chưa code dòng nào.*
*Ngày: 2026-08-08. Theo khuôn quy trình đã dùng cho Outline/Script split: thiết kế → duyệt → code → regression 4 phim → ghi lessons.*

---

## 1. Vấn đề, bằng chứng đo được

Một line trong `draft.json` được phép mang `clip_start`/`clip_end` trỏ tới **bất kỳ đâu** trong phim. Không có ràng buộc nào buộc nó tương ứng với một mục đã catalogue.

Đo trên cả bốn phim linear (`diag_catalogue.py`, 2026-08-08):

| Phim | shot | line | shot/line | line ở đầu shot | trong shot | **free** |
|---|---|---|---|---|---|---|
| John Wick | 92 | 91 | 1.01 | 66 | 25 | **0 (0%)** |
| Interstellar | 101 | 106 | 0.95 | 106 | 0 | **0 (0%)** |
| Spider-Man NWH | 69 | 76 | 0.91 | 54 | 3 | **19 (25%)** |
| Shutter Island | 31 | 58 | 0.53 | 30 | 1 | **27 (47%)** |

Hai điều rút ra:

**(a) Line free là line không kiểm được, do cấu tạo.** Không có mục catalogue nào đứng sau nó, nên `binding_audit`, `continuity_check`, `tag_audit` đều không có gì để đối chiếu. Đây là lý do sâu xa vì sao audit footage bất lực với drift — không phải vì gate hỏng.

**(b) Mật độ catalogue dự đoán được tỉ lệ line free.** Tương quan xếp hạng hoàn hảo trên cả bốn phim. Cơ chế: catalogue thưa thì vòng enrich act-by-act (rule A1) không có chỗ bind, nên nó bịa cửa sổ. Shutter Island có 31 shot cho phim 2h09 và bị viết thành 58 line — 27 line thừa ra chính là 27 line free.

**Giả thuyết bị bác bỏ, ghi lại để không thử lại:** ban đầu nghi catalogue được cắt theo mốc thoại (transcript) chứ không theo hình, dựa trên ghi chú `~833s` ở một shot của Shutter Island. Đo ra: biên shot trùng biên segment transcript chỉ 5–31% ở cả bốn phim. **Catalogue cắt theo hình.** Kết luận cũ là suy rộng từ n=1.

---

## 2. BINDING-INTEGRITY — ràng buộc

### 2.1 Thay đổi schema

Thêm vào mỗi line của `draft.json`:

```
shot_id: str        # id của một mục trong shots.json hoặc broll.json pool
```

`clip_start` / `clip_end` **giữ nguyên** — rule A3 (anchor vào đúng khoảnh khắc narration mô tả, không vào đầu shot) vẫn sống. Chỉ thêm một điều kiện:

> Nếu line có `clip_start`, nó phải nằm trong `[shot.clip_start, shot.clip_end]` của chính `shot_id` đó. Tương tự `clip_end`.

Line dùng `pool` / `montage` / silence không đổi gì — chúng vốn đã trỏ vào pool label, tức đã có `shot_id` dưới dạng khác.

### 2.2 Khi cần hình chưa có trong catalogue

Không được bịa timestamp. Hai đường hợp lệ:

- **Tách shot**: một mục catalogue chứa hai khoảnh khắc thì tách thành hai mục, mỗi mục một `depicts` chính. (Đây cũng là cách sửa đúng cho line 8 của Shutter Island.)
- **Thêm mục mới**: catalogue thêm shot mới, qua frame-verify như mọi shot khác.

Nghĩa là vòng enrich từ nay gồm hai phần: viết thêm lời **và** mở rộng catalogue. Đó là công thật, và là công đã bị bỏ qua âm thầm cho tới giờ.

### 2.3 Lộ trình — bắt buộc theo bậc

| Bậc | Hành vi | Áp dụng khi |
|---|---|---|
| 1 | **Report-only**: in `[BINDING-INTEGRITY] N/M line không trỏ vào shot nào: <ids>`. Không chặn gì | ngay sau khi code xong |
| 2 | **Chặn promote**: line free làm `outline_ready` fail, giống `beat_map_trusted` | sau khi một phim mới chạy trọn bậc 1 |
| 3 | **Hard fail** ở `validate_draft` | chỉ cho project tạo mới sau ngày bật |

Không bật bậc 2/3 ngược lên phim cũ. Shutter Island (27) và Spider-Man (19) sẽ mãi ở bậc 1 — retrofit chúng không đáng, và bậc 1 vẫn cho thấy con số.

### 2.4 Lý do dùng `shot_id` chứ không chỉ kiểm "timestamp có nằm trong shot nào đó không"

Kiểm khoảng thời gian là suy đoán ngược; `shot_id` là **khai báo**. Cùng khuôn đã thắng ở reveal-map và set-piece: người khai ý định, máy tuân. Và nó cho `binding_audit` một ground truth xác định thay vì phải dò xem timestamp rơi vào shot nào.

---

## 3. CATALOGUE-DENSITY — phòng ngừa

### 3.1 Đo cái gì

Ở Stage 2 (sau catalogue, trước khi viết draft):

```
density = số shot / số line mà tier đang nhắm tới
```

Số line mục tiêu suy từ `DEPTH_TIERS` (phút mục tiêu × tốc độ đọc đã calibrate ÷ số từ trung bình mỗi line).

### 3.2 Ngưỡng

Rút từ bốn phim thật:

- `>= 0.90` → đạt (John Wick 1.01, Interstellar 0.95 — cả hai 0% free)
- `0.70 – 0.90` → cảnh báo (Spider-Man 0.91 nằm sát mép và đã có 25% free)
- `< 0.70` → cảnh báo mạnh: *"catalogue quá thưa cho tier này; mở rộng trước khi draft, nếu không vòng enrich sẽ bịa cửa sổ"* (Shutter Island 0.53 → 47% free)

**Ngưỡng này là PROVISIONAL.** Bốn điểm dữ liệu, và Spider-Man ở 0.91 vẫn có 25% free — tức 0.90 có thể còn thấp. Cần thêm hai phim rồi hiệu chỉnh, và gate phải tự khai điều đó mỗi lần chạy (giống cách SET-PIECE khai giới hạn của nó).

### 3.3 No-op khi thiếu dữ liệu

Không có `shots.json`, hoặc chưa chốt tier → **không đo, và nói rõ là không đo**. Không được im lặng bỏ qua.

---

## 4. Cái này KHÔNG giải quyết

Ghi rõ để sáu tháng nữa không ai tưởng đã xong:

- **Line trỏ đúng shot nhưng vẫn là shot SAI.** Cấu trúc không chặn được. Cần `claim` + `binding_audit` chạy thật, hoặc mắt người ở Stage 8.
- **Shot gộp hai khoảnh khắc** (line 8). Ràng buộc `shot_id` không phát hiện được; đó là chất lượng catalogue, thuộc `TAG_TOO_GENEROUS` và vòng frame-verify.
- **RENDER QA vẫn bắt buộc.** Không có gì ở đây thay được checkpoint 2 trong `RULES.md` Phần F.

---

## 5. Regression

Chạy `recap.py draft` trên cả bốn phim, và:

1. Beat-coverage phải **không đổi**: 34/34, 28/30, 24/26, 28/28.
2. `[BINDING-INTEGRITY]` phải ra đúng số đã đo: **0, 0, 19, 27**. Lệch là code sai, không phải phát hiện mới.
3. Không project nào bị chặn ở bậc 1.
4. `[CATALOGUE-DENSITY]` phải phân biệt được: hai phim đạt, hai phim cảnh báo. Nếu cả bốn cùng màu thì gate vô dụng, không ship.

Điều kiện 4 là thứ tôi bỏ qua ở ACTION-SETUP và phải sửa bốn vòng: **đặt trước tiêu chí để biết gate thất bại, rồi mới code.**

---

## 6. Cần bạn quyết

1. **`shot_id` có bắt buộc với line `pool`/`montage` không**, hay chỉ với line explicit window? (Đề xuất: pool label đã là id, nên chỉ cần chuẩn hoá tên trường.)
2. **Bậc 3 (hard fail) áp cho project mới từ khi nào** — ngay phim tới, hay chờ một phim chạy bậc 1 trước? (Đề xuất: chờ một phim.)
3. **Ngưỡng density 0.90/0.70** có hợp trực giác của bạn không? Bạn là người biết một phim cần bao nhiêu shot.
4. Có gộp việc này với quyết định về **`claim`** không? Hai cái bổ trợ nhau: `shot_id` cho biết line trỏ vào đâu, `claim` cho biết nó khẳng định điều gì. Có cả hai thì `binding_audit` mới thật sự bắt được drift.
