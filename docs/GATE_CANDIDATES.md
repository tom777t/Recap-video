# Gate & Rule Candidates — Recap Vid (linear pipeline)

**Cập nhật: 2026-08-08** — sau buổi sửa gate + render QA Shutter Island. Nhóm D (gate đang sai) đã xử xong và chuyển lên mục ĐÃ LÀM; thêm hai gate mới; thêm hai lớp lỗi chưa từng có tên.

> **Không áp dụng bất cứ mục nào trong file này trừ khi được bảo rõ.** Đây là ứng viên chưa chốt. Luật đang chạy nằm ở `docs/RULES.md` Phần A.

---

## ĐÃ LÀM RỒI (không còn là ứng viên)

- **Gate beat-coverage** — implement cùng Outline/Script split. Điều kiện: "không có ≥2 beat liên tiếp bị bỏ trống" (không phải % thô). Tự tìm ra JW ending gap. Chạy mỗi draft, mọi stage. ✅
- **Drift-tagging (B1 cũ)** — đã thành rule A5 + A6. Kiểm chứng: 3 Peter không lẫn. ✅
- **Outline/Script stage machine** — `pipeline/state.py` + `outline_ready()`, promote một chiều qua `--promote`. Zero regression. ✅
- **A1. Gate REVEAL-TIMING** — ✅ **đã implement**. Đọc reveal-map trong `beats_proposal.md`, check không term reveal nào xuất hiện trước beat landing của nó. Luôn chạy (spoiler là sai kể cả trong outline). **Kiểm chứng Shutter Island: 0 hit qua 6 reveal — phim khó nhất về spoiler tới giờ.** ⚠️ Giới hạn đã biết: gate đếm **term**, không bắt được **ám chỉ** — xem `RULES.md` B11.
- **BINDING-INTEGRITY** — ✅ **đã implement 2026-08-08**, bậc 1 (report-only). Đếm line có `clip_start` không ứng với mục nào trong catalogue. Đo được: interstellar 0/106, johnwick 0/91, spiderman 19/76, shutterisland 27/58. Line `pool`/`montage` được miễn (label đã là id). ⚠️ Bậc 2 (chặn promote) và bậc 3 (fail cứng, chỉ cho project mới) CHƯA bật — chờ một phim chạy trọn bậc 1. Thiết kế đầy đủ: `docs/DESIGN_binding_integrity.md`
- **CATALOGUE-DENSITY** — ✅ **đã implement 2026-08-08**. Đếm shot trong catalogue theo TỪNG BEAT; báo beat không có shot nào (không thể kể) và beat chỉ có 1 shot. Đo được beat rỗng: interstellar 0, johnwick 2 (B29, B30), spiderman 2 (B04, B17), shutterisland 5. **Tìm ra nguyên nhân gốc của John Wick ending gap**: B29/B30 bị beat-coverage báo hụt bấy lâu không phải vì draft quên viết mà vì không có footage nào được catalogue. ⚠️ Dải ngưỡng tỉ lệ shot/beat đã bị BỎ có chủ ý — 3.07 có beat rỗng còn 2.97 thì không, tức con số tổng không mang thông tin. Chỉ danh sách per-beat là tín hiệu
- **Sửa audit báo xanh giả** — ✅ 2026-08-08. `load_shots` cô lập từng entry hỏng thay vì abort (trước: một tag sai ⇒ mất sạch 31 shot ⇒ mọi audit chạy trên dict rỗng ⇒ in "clean"); caller in `[FOOTAGE-DROPPED]` đỏ và tuyên bố audit DEGRADED; `binding_audit` không còn in "all visual lines verified" khi verified = 0; id trùng fail cứng ở cả `draft` lẫn `render`
- **D1 timestamp beat map** — ✅ 2026-08-08. Quy ước khai trong header `ts_format:`, không đoán nữa; beat map được validate (đơn điệu tăng + không vượt runtime) trước khi ba gate dùng; map hỏng chặn promote
- **D2 ACTION-SETUP** — ✅ 2026-08-08 sau 4 vòng. `_ACTION_FAMILIES` match theo token thay vì tên riêng từng phim; đọc `depicts: action`; kiểm theo RUN chứ không theo line; cue list hẹp. ⚠️ **Nhánh SCRIPT stage chưa validate trên phim nào** — 3/4 project ở outline, Shutter Island không có action. Chờ phim action tiếp theo
- **A-NEW. Gate SET-PIECE COVERAGE** — ✅ **đã implement** 2026-07-21. Trong mỗi range set-piece người đã xác nhận + dense-verify, không gap nào giữa hai line liên tiếp được vượt max-gap. Chỉ chạy ở stage SCRIPT, soft-only. Bài học chính: ngưỡng cố định copy từ phim này sẽ false-fire ở phim khác (90s đúng cho John Wick, sai cho Spider-Man) → chuyển sang tier-relative. Range không đánh dấu thì không bao giờ bị đo. ⚠️ **v1 PROVISIONAL** — xem F1 bên dưới.

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

## NHÓM D — LỚP LỖI MỚI, CHƯA CÓ GATE

*Phát hiện 2026-08-08. Không phải bug lẻ — là hai khoảng trống mà mọi gate hiện tại đều không phủ.*

### D-GREEN. Audit mất input rồi báo "clean"

Một component không đọc được input của nó **không được phép thoái hoá thành một component báo thành công**. Đã sửa hai ca cụ thể (load_shots, binding_audit — xem mục ĐÃ LÀM), nhưng lớp lỗi thì còn: bất kỳ audit nào cũng cần trả lời được "tôi đã kiểm bao nhiêu đơn vị" chứ không chỉ "tôi tìm thấy bao nhiêu lỗi".

**Ứng viên**: mọi audit in ra mẫu số của chính nó. `tag_audit` kiểm N shot, `continuity_check` kiểm N cặp, `beat_coverage` kiểm N beat. Mẫu số = 0 thì không bao giờ được in màu xanh.

### D-RENDER. Gate kiểm draft, render tạo ra thứ khác

**Toàn bộ gate hiện tại đứng TRƯỚC render.** Không cái nào kiểm cái thật sự phát ra loa. Bug id trùng lọt qua đúng khe này: draft.json đúng thứ tự, REVEAL-TIMING xanh, nhưng hai line dùng chung một file audio nên twist lộ ở giây 36.

Đã có hai chốt (fail khi id trùng ở draft và ở render). Còn thiếu một lớp kiểm sau render:

- số file audio == số line có narration
- số clip đã dựng == số line
- tổng runtime khớp ước tính trong khoảng dung sai

Rẻ, và bắt được cả lớp "render lệch draft" chứ không riêng id trùng.

---

## NHÓM E — HẠ TẦNG QA

### E1. `timeline.json` — patch nhỏ, giá trị cao

`render.py` dựng đủ biến `timeline` (start/end mỗi line trên timeline đã xfade) nhưng chỉ ghi ra đĩa khi bật caption, và ghi dưới dạng `.ass` chứa **text**, không chứa **line id**.

Hệ quả: lúc RENDER QA thấy chỗ lệch ở phút 7:32 thì phải mò ngược xem đó là line nào.

**Fix:** luôn ghi `projects/<n>/timeline.json` với `{id, out_start, out_end, clip_start, clip_end}`. QA report thành "line 36 drift" thay vì "khoảng phút 7 có gì đó sai". ~5 dòng code. Điều kiện tiên quyết cho C-DRIFT.

---

## NHÓM F — BUG ENGINE CÒN LẠI (chưa sửa)

*Phát hiện trong pass đọc code 04/08. D1 và D2 đã xong; bốn cái này thì chưa.*

### F1. SET-PIECE max-gap còn tự tham chiếu (D3 cũ)
Ngưỡng = `max(240s, 3 × median gap của chính recap đó)`. Recap thưa đều sẽ tự đẩy median lên và tự nới lỏng gate. Hướng chốt: lấy reference từ **runtime band của tier** thay vì median của chính draft. Cần phim thứ hai để chốt số.

### F2. Capacity math dùng sai TTS rate (D4 cũ)
Bốn chỗ gọi `get_profile()` (`draft.py`, `catalogue.py`) đều hardcode `DEFAULT_TTS_RATE` = `+22%`, nhưng line `sad` chạy `+6%`, `mystery` `+10%` — đọc chậm hơn ước tính ~15%, nên line "vừa khít" sẽ tràn. Fix: truyền rate thật của từng line; calibrate thêm profile cho `+30%` và `+10%`.

### F3. Giá trị chết trong config (D5 cũ)
`TTS_DELIVERY["normal"]["rate"] = "+16%"` không bao giờ dùng (`_delivery_for()` luôn ghi đè bằng `base_rate`). `DEFAULT_TARGET_MINUTES = 20` không được tham chiếu ở đâu và mâu thuẫn với `DEPTH_TIERS`.

### F4. README.md lỗi thời (D6 cũ)
Vẫn mô tả flow 3 lệnh `ingest → draft → render` trong khi thực tế là 9 bước; ghi "burned-in captions" trong khi `DEFAULT_CAPTIONS = False`. **Đây là file đầu tiên OpenCode đọc.**

### F5. Quy ước id sub-line sinh ra va chạm
`<cha><n>` khiến `4` + `1` = `41`, mà `41` cũng là line sau `40`. Đã có chốt fail cứng, nhưng gốc chưa sửa — cần dạng id không thể đụng (`4b`, `4.1`, hoặc id không mang thứ tự).

### F6. `parse_ts` định nghĩa trùng ở 3 nơi
`draft.py`, `catalogue.py`, `schemas.py`. Ba bản có thể lệch nhau lúc nào không biết.

---

## ƯU TIÊN NẾU LÀM TIẾP

1. **F4 (README)** — rẻ nhất, chặn hiểu nhầm cho mọi session sau.
2. **D-RENDER** — lớp kiểm sau render (đếm audio/clip/runtime). Rẻ, phủ cả một lớp lỗi.
3. **E1 `timeline.json`** — ~5 dòng, mở đường cho C-DRIFT và cho QA nói được "line 36" thay vì "khoảng phút 7".
4. **A-AMB** — sau khi có nhận định về câu kết Shutter Island.
5. **BINDING-INTEGRITY bậc 2** — sau khi một phim mới chạy trọn bậc 1.
6. **F5 (id sub-line)** — sửa gốc, không chỉ chốt lưới.
7. **B2 + B-NEW** — rule, ghi nhanh, không đụng engine.
8. **F1, F2, F3** — cần phim thứ hai / cần calibrate thêm.
9. **C-DRIFT** — khối lớn nhất, nhưng là thứ duy nhất đụng vào nút thắt thật (công người mỗi phim).

**Chưa validate được, đừng quên:** nhánh SCRIPT stage của ACTION-SETUP (chờ phim action), và bậc 2/3 của BINDING-INTEGRITY.
