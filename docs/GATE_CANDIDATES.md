# Gate & Rule Candidates — Recap Vid (linear pipeline)

**Cập nhật: 2026-08-04** — pass reconcile sau Shutter Island. Hai ứng viên lớn của bản trước (reveal-timing, set-piece coverage) nay đã implement xong và được chuyển ra khỏi danh sách.

> **Không áp dụng bất cứ mục nào trong file này trừ khi được bảo rõ.** Đây là ứng viên chưa chốt. Luật đang chạy nằm ở `docs/RULES.md` Phần A.

---

## ĐÃ LÀM RỒI (không còn là ứng viên)

- **Gate beat-coverage** — implement cùng Outline/Script split. Điều kiện: "không có ≥2 beat liên tiếp bị bỏ trống" (không phải % thô). Tự tìm ra JW ending gap. Chạy mỗi draft, mọi stage. ✅
- **Drift-tagging (B1 cũ)** — đã thành rule A5 + A6. Kiểm chứng: 3 Peter không lẫn. ✅
- **Outline/Script stage machine** — `pipeline/state.py` + `outline_ready()`, promote một chiều qua `--promote`. Zero regression. ✅
- **A1. Gate REVEAL-TIMING** — ✅ **đã implement**. Đọc reveal-map trong `beats_proposal.md`, check không term reveal nào xuất hiện trước beat landing của nó. Luôn chạy (spoiler là sai kể cả trong outline). **Kiểm chứng Shutter Island: 0 hit qua 6 reveal — phim khó nhất về spoiler tới giờ.** ⚠️ Giới hạn đã biết: gate đếm **term**, không bắt được **ám chỉ** — xem `RULES.md` B11.
- **A-NEW. Gate SET-PIECE COVERAGE** — ✅ **đã implement** 2026-07-21. Trong mỗi range set-piece người đã xác nhận + dense-verify, không gap nào giữa hai line liên tiếp được vượt max-gap. Chỉ chạy ở stage SCRIPT, soft-only. Bài học chính: ngưỡng cố định copy từ phim này sẽ false-fire ở phim khác (90s đúng cho John Wick, sai cho Spider-Man) → chuyển sang tier-relative. Range không đánh dấu thì không bao giờ bị đo. ⚠️ **v1 PROVISIONAL** — xem D3 bên dưới.

---

## NHÓM A — ĐÁNG LÀM, SẴN SÀNG

### A-AMB. Gate ambiguity-hold ⭐ ứng viên số 1 hiện tại

- **Là gì:** thêm loại `ambiguity-hold` vào reveal-map (kèm range). Người đánh dấu chỗ phim **cố ý để mở**; gate quét các line bind vào range đó và cảnh báo khi thấy cấu trúc diễn giải — `as if`, `meaning`, `in other words`, `which means`, `he chose to`, `he had finally`, `we realize`.
- **Bằng chứng:** Shutter Island R6 (câu kết). Xử đúng tay, nhưng gate hiện tại hoàn toàn mù với nó.
- **Đo được?** CÓ — trong phạm vi hẹp. Term-matching giống REVEAL-TIMING, chỉ khác là bảo vệ sự KHÔNG-biết thay vì sự bất ngờ.
- **Tại sao an toàn:** chỉ chạy trong range người đã đánh dấu, y hệt cách SET-PIECE chỉ đo range người xác nhận. Ngoài range không đụng gì. Đây là điều kiện bắt buộc — xem cảnh báo ở `RULES.md` G2 về vì sao rule chung "đừng diễn giải cái mơ hồ" là nguy hiểm.
- **Trạng thái:** chờ Shutter Island render QA xác nhận R6 xử đúng thật, rồi mới formalize.

---

## NHÓM B — RULE ĐÁNG GHI (không phải gate)

### B2. Rule: bản mở rộng / special edition
- **Là gì:** với extended cut, xác định + LOẠI phần bonus không thuộc narrative TRƯỚC catalogue.
- **Bằng chứng:** Spider-Man extended intro có cả 3 Peter = lộ R4 nếu không cắt.
- **Trạng thái:** ĐỦ dữ liệu, SẴN SÀNG ghi. **Vẫn chưa ghi.**

### B-NEW. Bắt OpenCode khai PHƯƠNG PHÁP frame-verify
- **Là gì:** khi OpenCode báo "frame-verified" ở fast-cut sequence, bắt nó nói rõ **DÀY hay MẪU** trước khi tin.
- **Bằng chứng:** cú bắt MJ lệch 2 phút qua *hai* vòng "frame-verified" vì cả hai đều sampling.
- **Trạng thái:** đã ghi vào `lessons.md` (2026-07-18) và thành B10 trong RULES. **Đáng nâng thành rule cứng ở Phần A** — nó đang là bài học, chưa phải luật thi hành.

### B-G1. Kể bi kịch nặng — kiềm chế
→ xem `RULES.md` Phần G1. Chờ xác nhận, rồi ghi vào `STYLE_GUIDE.md` + `style_linear_vn.md`.

---

## NHÓM C — CẦN VISION / MẮT NGƯỜI

### C-DRIFT. Drift triage (xếp hạng, KHÔNG phải gate)

Bản trước xếp drift vào "không vá được bằng chữ". Vẫn đúng là **gate chữ không bắt được**, nhưng dense-scan đã chứng minh drift **phát hiện được bằng máy** — báo cáo dense ở Spider-Man tìm ra sai lệch 2 phút mà sampling bỏ sót hai lần.

- **Là gì:** với mỗi line, trích frame dày (1–2s) trong window đã bind, cho vision model chấm độ khớp giữa narration và frame, **xếp hạng từ thấp lên**. Người xem 10 line nghi nhất trước thay vì quét cả 120 line.
- **🚫 TUYỆT ĐỐI KHÔNG biến thành gate pass/fail.** Nó chỉ được phép nói "soi mấy chỗ này trước", không được phép nói "sạch". Lý do: xem SET-PIECE test (d) — một phép đo trên nền tảng không đáng tin còn tệ hơn không đo, vì nó **trấn an sai**. Sampling đã trấn an sai hai lần rồi.
- **Không thay thế RENDER QA** (`RULES.md` Phần F, checkpoint 2). Nó chỉ rút ngắn thời gian quét.

### C-CENSOR. Censor / blur
- Phán đoán chủ quan. Chưa có dữ liệu (mọi phim = `censor: none`, trừ `blur_heavy` ở Shutter Island B26). Chờ phim có cảnh máu.

---

## NHÓM D — GATE ĐÃ CÓ NHƯNG ĐANG SAI

*Phát hiện trong pass đọc code 2026-08-04. Đây không phải ứng viên — là lỗi ở thứ đang chạy. Ưu tiên cao hơn mọi mục ở trên: một gate sai còn tệ hơn không có gate.*

### D1. Hai quy ước timestamp xung khắc trong cùng một file ⚠️ nghiêm trọng nhất

Trong `pipeline/draft.py`:

```python
parse_ts("02:39")          # -> 159.0   (MM:SS)
_beat_ts_seconds("02:39")  # -> 9540.0  (HH:MM)
```

Sai lệch **60 lần** trên hai chuỗi trông giống hệt nhau. Có ghi chú trong docstring, nhưng `beat_coverage()` nuôi thẳng vào `outline_ready()` → `_stage_machine()` → quyết định promote sang SCRIPT. Một beat map viết nhầm quy ước sẽ báo coverage sai mà không có gì kêu.

**Fix:** bắt buộc `HH:MM:SS` đủ 3 phần ở mọi nơi; reject chuỗi 2 phần thay vì đoán.

### D2. `_ACTION_FAMILIES` hardcode tên family của từng phim

```python
"pennywise_attack", "pennywise_climax", "losers_fight", "bowers_bully"
```

Đây là family của IT 2017 nằm trong hằng số toàn cục. Phim mới tag family là `warehouse_shootout` → `_is_action()` trả False → gate `[ACTION-SETUP]` **im lặng hoàn toàn** (chỉ còn fallback `hold>=5s`). Gate trông như đang chạy mà không chạy.

Đồng thời `_SETUP_CUES` rộng đến mức gần như không thể fail: `when`, `once`, `after`, `finds`, `wants`, cộng "chứa bất kỳ tên nào trong names.json" — gần như mọi câu tiếng Anh có tên nhân vật đều pass.

**Chẩn đoán theo B5:** cùng một rule bị áp **quá hẹp** (phát hiện action) và **quá rộng** (công nhận setup) cùng lúc.
**Fix:** đọc `depicts: action` từ `shots.json` thay cho danh sách tên; siết `_SETUP_CUES` lại.

### D3. SET-PIECE max-gap còn tự tham chiếu (v1 provisional)

Ngưỡng = `max(240s, 3 × median gap của chính recap đó)`. Một recap thưa đều sẽ tự đẩy median lên và tự nới lỏng gate. Đã tự flag trong code + `lessons.md` 2026-07-21.

**Hướng chốt:** lấy reference từ **runtime band của tier** thay vì median của chính draft — đó là cách duy nhất phá được self-reference. `min(3×median, ceiling)` chỉ giới hạn thiệt hại. Cần phim thứ hai để chốt số.

### D4. Capacity math dùng sai TTS rate

Cả 4 chỗ gọi `get_profile()` (`draft.py:1214`, `catalogue.py:75/120/146/492`) đều hardcode `DEFAULT_TTS_RATE` = `+22%`. Nhưng line `sad` chạy `+6%`, `mystery` `+10%` — thực tế đọc chậm hơn ước tính ~15%. Line được tính là "vừa khít" shot sẽ **tràn**. Đây đúng loại lỗi `BindingViolation` sinh ra để bắt, nhưng nó đang bắt bằng số liệu sai.

**Fix:** truyền rate thật của từng line; calibrate thêm profile cho `+30%` và `+10%`.

### D5. Giá trị chết trong config

- `TTS_DELIVERY["normal"]["rate"] = "+16%"` không bao giờ dùng — `_delivery_for()` luôn ghi đè bằng `base_rate` (`+22%`). Comment "slowed from +24" đang mô tả một con số không tồn tại.
- `DEFAULT_TARGET_MINUTES = 20` không được tham chiếu ở đâu, và mâu thuẫn với `DEPTH_TIERS` (9–17 phút).

### D6. README.md lỗi thời

Vẫn mô tả flow 3 lệnh `ingest → draft → render`, trong khi thực tế là 9 bước. Cũng ghi "burned-in captions" trong khi `DEFAULT_CAPTIONS = False`. **Đây là file đầu tiên OpenCode đọc** — README sai làm hỏng cả session.

---

## NHÓM E — HẠ TẦNG QA

### E1. `timeline.json` — patch nhỏ, giá trị cao

`render.py` dựng đủ biến `timeline` (start/end mỗi line trên timeline đã xfade) nhưng chỉ ghi ra đĩa khi bật caption, và ghi dưới dạng `.ass` chứa **text**, không chứa **line id**.

Hệ quả: lúc RENDER QA thấy chỗ lệch ở phút 7:32 thì phải mò ngược xem đó là line nào.

**Fix:** luôn ghi `projects/<n>/timeline.json` với `{id, out_start, out_end, clip_start, clip_end}`. QA report thành "line 36 drift" thay vì "khoảng phút 7 có gì đó sai". ~5 dòng code. Điều kiện tiên quyết cho C-DRIFT.

---

## ƯU TIÊN NẾU LÀM TIẾP

1. **D1 + D2** — gate đang cho kết quả sai. Sửa trước mọi thứ khác.
2. **D6** — README, rẻ, chặn hiểu nhầm cho mọi session sau.
3. **E1** — `timeline.json`, ~5 dòng, mở đường cho C-DRIFT.
4. **A-AMB** — sau khi Shutter Island QA xác nhận R6.
5. **B2 + B-NEW** — rule, ghi nhanh, không đụng engine.
6. **C-DRIFT** — khối lớn nhất, nhưng là thứ duy nhất đụng vào nút thắt thật (công người mỗi phim).
7. **D3 + D4** — cần phim thứ hai / cần calibrate thêm.
