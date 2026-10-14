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


# PHẦN THÊM cho `docs/GATE_CANDIDATES.md` — 2026-08-09

*Nối vào cuối file, TRƯỚC mục "ƯU TIÊN NẾU LÀM TIẾP". Rồi cập nhật danh sách ưu tiên theo bản ở cuối tài liệu này.*

---

## NHÓM G — TỪ LOẠT THÍ NGHIỆM 09/08

*Ba thí nghiệm, đều đo trên dữ liệu thật của 4 phim. Không cái nào đã implement.*

### G-SNAP. Lưới snap từ cú cắt hình ⭐ đã chứng minh, rẻ nhất

**Là gì:** dùng PySceneDetect quét `source.mp4` một lần, cache danh sách cú cắt vào `_cuts.json`. Gate cảnh báo khi biên một shot trong catalogue cách mọi cú cắt quá ~2 giây.

**Bằng chứng (Shutter Island, 62 mốc tay vs 1906 cú cắt):**

| khoảng cách tới cú cắt gần nhất | số mốc |
|---|---|
| < 1s | 39% |
| 1–3s | 48% |
| 3–10s | 13% |
| > 10s | **0%** |

Lệch lớn nhất 6.6s. **Máy không bỏ sót cảnh nào** — 8 mốc bị coi là "máy trượt" ở lần đo đầu thực ra chỉ là mốc tay ước chừng lệch vài giây.

**Vì sao đáng làm:** 87% mốc đã sát cú cắt sẵn, nên snap **không làm méo catalogue** — nó chỉ nắn 13% còn lệch. Rủi ro gần bằng không.

**Nó sửa được gì:** một cửa sổ bắt đầu lệch 6 giây so với cú cắt nghĩa là **6 giây đầu clip vẫn đang chiếu cảnh trước**. Ca tệ nhất đo được là `clip:01:52:40.0` (line 37 — Chuck xưng tên thật), lệch 6.0s ở start và 6.6s ở end, ngay trên một reveal. Đây là drift nhẹ, không ai để ý, và hoàn toàn chặn được bằng máy.

**Lợi ích kèm theo:** cả 5 beat rỗng của Shutter Island đều có 23–54 cú cắt ứng viên nằm trong khoảng. Khi `CATALOGUE-DENSITY` báo beat rỗng, người mở rộng catalogue sẽ có sẵn danh sách biên hợp lệ thay vì phải tự bịa mốc.

**Chi phí:** quét ~11 phút mỗi phim, một lần, có cache. `pip install scenedetect`.

**Trạng thái:** sẵn sàng code. Script đo đã có: `diag_scenedetect.py`, `diag_snapgrid.py`.

---

### G-AXIS. `shots.json` đang trộn hai trục thông tin ⭐ phát hiện có giá trị nhất

**Là gì:** hai trường `depicts` và `chars` mỗi trường đang gánh **hai loại thông tin khác hẳn nhau** — thứ máy nhìn thấy được, và thứ chỉ người biết truyện mới biết.

| trường | trục NHÌN THẤY (máy làm được) | trục TRUYỆN (người quyết) |
|---|---|---|
| `depicts` | `dialogue`, `action`, `establishing`, `montage` | `emotion`, `reveal`, `setup`, `aftermath`, `discovery` |
| `chars` | ai đang trên khung hình (theo mặt) | người đó **là ai** tại thời điểm đó trong truyện |

**Bằng chứng — `depicts`:** 20 shot chấm mù, chỉ 4 khớp hoàn toàn nhưng 13 có chung ≥1 tag. Trong 12 lần nhầm, **6 lần có `emotion` ở phía người tag**. `emotion` không nằm trong pixel — một người đàn ông hút thuốc trong phòng đỏ là `emotion` với ai biết đó là Dolores đã chết, và là `dialogue` với ai chỉ thấy hai người đang nói chuyện.

**Bằng chứng — `chars`, và đây là ca minh hoạ hoàn hảo:**

```
shot17   người tag: andrew laeddis, dr. cawley, dr. sheehan
         model:     teddy daniels,  dr. cawley, chuck aule
```

`Andrew Laeddis` **là** `Teddy Daniels`. `Dr. Sheehan` **là** `Chuck Aule`. Sau mốc reveal, người tag chuyển sang tên thật; model nhìn mặt nên dùng tên trước reveal. Cả hai đều đúng.

Soi hết 11 ca bị chấm là "bịa thêm": **không có ca nào là bịa.** 7 ca là cùng người khác tên vì twist (bị phạt hai lần — vừa "bịa" vừa "sót"), 2 ca là nhân vật có mặt thật mà người tag chỉ ghi nhân vật trọng tâm. Độ chính xác thật gần 100%, không phải 67% như script chấm báo.

**Vì sao quan trọng:** việc chọn gọi "Teddy" hay "Laeddis" ở một thời điểm **chính là quyết định biên tập về việc khán giả đã biết tới đâu** — đúng thứ reveal-map sinh ra để quản. Không vision model nào đoán được, và không nên đoán.

**Đề xuất:** tách `chars` thành hai tầng.

- **Tầng mặt** — ai có mặt trên khung hình. Máy tag, chính xác cao. Đây là nền để `binding_audit` cuối cùng chạy được thật: so **mặt** với **lời**, không đòi model biết cú lật.
- **Tầng truyện** — gọi họ là gì tại thời điểm đó. Người quyết, gắn với reveal-map.

Tương tự với `depicts`: máy đề xuất trục nhìn thấy, người xác nhận và thêm trục chức năng.

**Trạng thái:** cần thiết kế. Chạm schema `shots.json`, nên phải qua quy trình duyệt như BINDING-INTEGRITY.

---

### G-CAST. `names.json` vứt mất tên diễn viên

**Là gì:** rule A7 bảo đọc mục **Cast** trên Wikipedia — mục đó có ánh xạ *"Leonardo DiCaprio as Teddy Daniels"*. Nhưng `names.json` chỉ giữ tên nhân vật + vai trò, bỏ phần tên diễn viên.

**Hệ quả:** pipeline đọc rồi ném đi đúng mẩu dữ liệu duy nhất cho phép nhận mặt. Vòng 2 thí nghiệm cho model đọc `names.json` — nó không giúp được gì, vì biết "McPherson là phó quản giáo hộ tống hai marshal" vẫn không cho biết mặt ông ấy trông thế nào.

**Đo được:** thêm `cast.json` (diễn viên↔nhân vật) ở vòng 3 giúp model đặt tên được thêm 2 shot. Ít, nhưng đúng hướng — và bị che bởi lỗi bộ đề ở G-AXIS nên chưa đo được mức thật.

**Đề xuất:** thêm trường `actor` vào `names.json`. Thay đổi schema nhỏ, dữ liệu đã có sẵn ở bước A7, chỉ là chưa lưu.

**Trạng thái:** rẻ, làm được ngay, nhưng nên làm CÙNG G-AXIS vì cả hai đụng cùng chỗ.

---

### G-FRAME. Lấy mẫu 3 frame là chưa đủ

**Là gì:** bộ đề trích đúng 3 frame mỗi shot ở vị trí cố định (đầu +0.5s, giữa, cuối −0.5s).

**Vấn đề đo được:** phần lớn ca "sót" là nhân vật xuất hiện ở giữa cửa sổ 20–30 giây mà không rơi vào frame nào. Và bốn ca model giữ `(khong ro)` đều cùng lý do — mặt tối, quay đi, ánh lửa — chứ không phải thiếu dữ liệu.

**Đề xuất:** trích 8–10 frame rồi chọn frame sáng nhất / rõ mặt nhất, thay vì lấy vị trí cố định.

**Trạng thái:** chỉ là chuyện của công cụ thí nghiệm, chưa đụng pipeline. Làm khi nào chạy vòng đo tiếp.

---

### Bài học về CÁCH ĐO, đáng nhớ hơn cả ba mục trên

Cả ba vòng thí nghiệm đều cho số thấp (`depicts` 20% khớp hẳn, `chars` 67% chính xác) và cả ba lần con số đó **sai** — vì ground truth thô hơn thứ đang được chấm, chứ không phải vì model kém.

Chỉ khi in ra **từng ca lệch cụ thể** mới thấy được. Số tổng hợp giấu mất chuyện `Laeddis = Teddy`.

> **Trước khi tin một điểm số, hãy đọc mấy ca mà nó cho là sai.** Một thước đo không giải thích được cái nó phạt là một thước đo chưa dùng được.

---

# PHẦN THÊM — 2026-08-31 (từ Bad Genius)

---

## ĐÃ LÀM RỒI: bỏ trần shot của DEPTH-TOTAL

**Trạng thái: ✅ ĐÃ SỬA 2026-08-31.** Không còn là ứng viên. Ghi lại vì phép tính buộc phải sửa là thứ đáng giữ.

### Mâu thuẫn số học

`DEPTH_TIERS` cũ khai đồng thời hai thứ không thể cùng đúng:

```
video_essay:  shots (110, 130),  per_beat (3, 4)
```

`DEPTH-UNDER` đòi **mỗi beat được đánh số** phải có ≥ `per_beat[0]` shot. Với bản đồ N beat, sàn của nó là **N × per_beat[0]** shot. Trần `shots[1]` chặn đúng cái catalogue đó.

Hai gate chỉ cùng thoả được khi:

| tier | trần | per_beat sàn | **số beat tối đa còn nhất quán** |
|---|---|---|---|
| `recap` | 80 | 2 | **40** |
| `fuller_recap` | 110 | 3 | **36** |
| `video_essay` | 130 | 3 | **43** |

Bad Genius có **80 beat**. `DEPTH-UNDER` đòi 240 shot; trần cho 130. Ở 126 shot: qua DEPTH-TOTAL, trượt DEPTH-UNDER trên **51 beat**. Muốn DEPTH-UNDER về 0 thì cần ~240 shot, vượt trần **85%**. Không có giá trị nào thoả cả hai.

### Trần đã sai theo CẢ HAI chiều trên phim đã ship

| phim | shot | trần tier | |
|---|---|---|---|
| Superbad | **183** | 130 | vượt **41%** |
| Gia Tài Của Ngoại | **280** | 130 | vượt **115%** |
| Shutter Island | 31 | 110 | dưới sàn, ship vẫn tốt |

Hai phim đã ship vượt trần mà không ai coi đó là lỗi — tức trần chưa bao giờ thật sự được thi hành, chỉ ngồi đó phát cảnh báo sai.

### Lý do gốc

**Số shot trong catalogue không quyết định độ dài recap — số LINE mới quyết định.** Catalogue là một **thực đơn**, và `BINDING-INTEGRITY` bắt mọi line phải đáp xuống một shot có thật. Vậy nhiều shot hơn = **nhiều lựa chọn hơn**, không phải nhiều nghĩa vụ hơn. Một catalogue không thể "quá đầy".

Đúng meta-pattern B5: *rule đúng, áp sai phạm vi*. `per_beat` hiệu chỉnh trên phim 26–34 beat; đem áp cho phim 80 beat thì gãy.

### Đã đổi gì

- `config.py`: `shots` thành `(sàn, None)` cho cả ba tier. Không còn trần.
- `catalogue.py`: DEPTH-TOTAL chỉ cảnh báo khi **dưới sàn**; đo theo `shot_lo`; báo cáo in `floor N+ shots (no ceiling)` và `[at/above floor]` / `[UNDER floor]`.
- Hồi quy 17 project: không project nào hỏng thêm. Superbad và Gia Tài Của Ngoại chuyển từ "over target" sang "at/above floor".

⚠️ **Còn treo, KHÔNG sửa trong lần này:** `SCRIPTING_CHECKLIST.md` C12 vẫn viết *"within the declared tier's band"*. Câu đó giờ không còn nghĩa. Chưa sửa vì checklist là tài liệu người dùng ký, không phải code — cần bạn duyệt câu chữ mới.

---

## NHÓM H — TỪ BAD GENIUS

### H-REVEAL. Reveal được bảo vệ có thể BIẾN MẤT mà mọi gate vẫn xanh ⭐ ứng viên chính

**Là gì:** hiện không có gì kiểm tra rằng một reveal đã khai trong `reveal-map` **thật sự được kể**.

**Cách nó lọt qua toàn bộ hàng rào:**

| hàng rào | vì sao không bắt được |
|---|---|
| `REVEAL-TIMING` | quét **chuỗi ký tự**, tìm term xuất hiện **quá sớm**. Một draft **không bao giờ nhắc** reveal thì nó không có gì để quét → xanh tuyệt đối |
| `C1` / binding audit | kiểm clip **đã được catalogue chưa**, không kiểm clip **có chiếu cái reveal không** |
| `BEAT-COVERAGE` | đếm beat có line, nhưng beat landing có thể chưa từng có shot nào để mà thiếu |
| `DEPTH-UNDER` | kêu về beat 0 shot — nhưng lẫn trong 51 cảnh báo khác, không phân biệt beat landing với beat phụ |

**Ca thật (chính là phim này):** R1 đáp ở B48, R2 đáp ở B77. Cả hai beat có **0 shot**. Một draft viết từ 41 beat có footage sẽ **im lặng bỏ cả hai cú lật** — và chạy qua sạch mọi gate. Kịch bản mất luôn: ai trả tiền cho vụ đánh, và Bank trở thành cái gì.

Đây là B11 lặp lại ở chiều ngược: B11 nói gate xanh không chứng minh **không rò rỉ**; cái này nói gate xanh không chứng minh **có kể**.

**Đề xuất kiểm (dữ liệu đã có sẵn, không cần thêm gì):**

> Với mỗi dòng `land:` trong khối ```reveal-map```:
> 1. **Stage 2 (catalogue):** beat landing phải có **≥1 shot**. Không có → `REVEAL-UNCATALOGUED`.
> 2. **Stage 3 (draft):** phải có **≥1 line bind vào trong** cửa sổ beat landing. Không có → `REVEAL-UNNARRATED`.
>
> `land:` đã hỗ trợ beat id / `HH:MM:SS` / `mid-credits` / `none`. Hai dạng sau miễn kiểm (1) — không phải beat.

**Vì sao rẻ:** reveal-map đã parse được, beat đã resolve ra thời gian, shot đã có trường `beat`, draft line đã có `clip_start`. Không cần cấu trúc mới.

**Độ nặng đề xuất:** `REVEAL-UNCATALOGUED` **hard** ở Stage 2 (không thể viết cái chưa nhìn thấy). `REVEAL-UNNARRATED` **soft** ở Stage 3 — có thể có lý do chính đáng để một reveal đáp bằng hình mà không có lời, và gate không phân biệt được.

⚠️ **Giới hạn tự khai:** kiểm này chứng minh **có line ở đúng chỗ**, không chứng minh line đó **kể đúng cái reveal**. Nó là sàn, giống REVEAL-TIMING. Người duyệt draft vẫn là chốt chặn.

---

### H-REVEAL-B. Reveal do THOẠI mang thì KHÔNG kiểm được bằng bất kỳ gate hình nào ⭐ phát hiện riêng

*Đây không phải chú thích của H-REVEAL. Đây là một giới hạn tách bạch, và phải biết TRƯỚC khi ai đó bắt tay implement H-REVEAL.*

Bad Genius có đúng hai reveal được bảo vệ, và chúng **thuộc hai loại khác hẳn nhau**:

| | R2 — reveal do HÌNH mang | R1 — reveal do THOẠI mang |
|---|---|---|
| đáp ở | 01:57:40 | 01:10:40 |
| phim tiết lộ bằng | tấm biển **`มิสเตอร์ แบงค์ / Mister BANK`** trên nóc tiệm, dàn máy giặt mới còn nguyên bọc xốp, chiếc xe máy mới — **tất cả trước khi Bank mở miệng** | Pat nói ra, trong phòng thẩm vấn |
| frame cho thấy gì | **chính nội dung reveal** | chỉ **cách nó được nói**: Pat ngồi một mình, bắt đầu bằng cười, rồi hai tay bưng mặt; cắt sang xưởng in đứng hình; giữ lâu trên mặt Bank |
| catalogue ghi được | nội dung | **chỉ ghi được sự truyền đạt, không ghi được nội dung** |
| H-REVEAL bắt được không | **có** | **không** |

**Hệ quả cho thiết kế:**

> Với reveal do thoại mang, **không có shot nào tồn tại để mà show cái reveal**. Một kiểm kiểu "beat landing phải có ≥1 shot" sẽ **PASS** bằng những shot chỉ quay người đang nói. Một kiểm kiểu "phải có ≥1 line bind vào beat landing" cũng sẽ **PASS** bằng một line không hề nhắc tới reveal — vì frame không cho line ấy cái gì để nhắc.

Nói cách khác: với R1, **cả hai bậc của H-REVEAL đều xanh trên một draft đã bỏ rơi hoàn toàn cú lật**. Chính xác cùng lỗ hổng mà H-REVEAL sinh ra để vá, chỉ là gate mới không với tới.

> **H-REVEAL là sàn cho reveal do HÌNH mang, và MÙ HOÀN TOÀN với reveal do THOẠI mang.**

**Vì sao không sửa được bằng cách siết gate:** thứ phân biệt hai loại nằm ở *âm thanh*, mà cả pipeline này không đọc audio ở tầng nghĩa (I4 đã nói transcript dịch máy chỉ dùng để định vị). Không có dữ liệu nào trong repo phân biệt được "shot quay người đang tiết lộ" với "shot quay người đang nói chuyện phiếm".

**Đề xuất kèm theo — rẻ, và là thứ duy nhất khả thi:**

> Thêm cột thứ tư cho mỗi dòng `reveal-map`: `carried: image | dialogue`. **Người khai**, giống `land:` và `hold:` — dumb gate + explicit human intent, đúng triết lý đã thắng ở reveal-map và set-piece.
> - `carried: image` → H-REVEAL chạy đủ hai bậc.
> - `carried: dialogue` → H-REVEAL **tự khai là không đo được**, in ra một dòng nhắc người duyệt draft phải đọc tay beat đó. Không giả vờ xanh.

Điều này giữ đúng bài học D-GREEN: **một audit thiếu input phải nói là nó thiếu, không được báo "clean"**.

**Ghi cho Bad Genius:** shot của B48 đã được catalogue kèm cảnh báo ghi thẳng trong `action` rằng frame KHÔNG mang nội dung reveal, để người viết draft không tưởng nhầm là có.

---

### L-FAMILY-SEMANTICS. `family` mang hai nghĩa khác nhau — đã thử nối, đã lùi lại

**2026-09-05. Đã implement, đã revert trong cùng ngày. Ghi lại vì cái sai đáng giá hơn cái đúng.**

`[VISUAL-REPEAT]` đọc family từ **`broll.json`** (pool metadata) và tag `visual` ở cấp line. Nó **không** đọc `family` trên `shots.json` — 463 tag ở hai project. Có vẻ như một lỗ hổng phạm vi, và đã nối vào.

**Nối xong thì `superbad2007` — phim ĐÃ SHIP, ĐÃ XEM — nổ 22 family vượt cap**, cao nhất `cop_car_night` **8x**, `mall_coda` 7x, `cops_at_store` 5x.

Không phải recap lặp. Là gate **đo sai thứ**:

| | `broll.json` pool `family` | `shots.json` `family` |
|---|---|---|
| nghĩa | **B-roll thay thế lẫn nhau được** | **nhãn CẢNH / ĐỊA ĐIỂM** |
| dùng 3 cái liên tiếp | đúng là "vừa thấy cái này rồi" | là **phủ một cảnh**, chuyện bình thường |
| superbad | — | 69 family / 183 shot, trung bình 2.65 |

`cap = 2` được hiệu chỉnh cho nghĩa thứ nhất. Bind 8 line vào 8 shot khác nhau của cảnh xe cảnh sát là **kể tuyến truyện phụ**, không phải lặp hình.

**Đã lùi.** Nếu quay lại ý này thì nó cần **cap riêng và tên gate riêng**, không dùng chung bộ đếm này. Spec test vẫn nằm trong `tools/gate_selftest.py` (`test_visual_repeat_shots`, KHÔNG đăng ký) để khỏi phải viết lại.

⚠️ **Bài học về cách đo, lặp lại lần thứ ba:** phép đo đầu tiên (khớp `clip_start` chính xác) báo `WOULD_EXCEED=0` và **sai** — hai trong ba line neo *bên trong* cửa sổ theo A3. Phép đo thứ hai (window containment) báo 1 finding và **cũng sai** — công cụ snapshot cắt ở dòng đầu vì rich wrap. Chỉ đến lần đọc thứ ba mới thấy 22. *Trước khi tin một con số, đọc mấy ca nó cho là sai* — và kiểm luôn cả công cụ đang đếm.

---

### K-OVERFILL. Gone Girl 109% fill — con số thật, hay ngưỡng sai? *(chỉ ghi, chưa đụng)*

**Phát hiện 2026-09-05, lộ ra sau khi vá capacity basis.** `gonegirl2014` báo **fill 109%** với **20 line vượt trần** — trên ngưỡng `DRAFT_FILL_OVER_WARN = 0.90`. Trước đây bị che vì trần bị đọc từ trường tự khai.

**Chưa xử lý, có chủ ý:** phim đã ship và đã được xem; nó là **review mode**, khác nhánh với toàn bộ công việc linear đang làm; và cắt ngang chuỗi việc tốn hơn là được.

⚠️ **Điểm đáng ghi hơn con số:** `DRAFT-OVERFILL` nổ trên **một phim đã ship và người xem đã duyệt**. Nghĩa là gate này **cũng chưa từng được kiểm chứng**. Hai khả năng, chưa phân biệt được:

- 109% là thật → phim đó thực sự nhồi chữ, và người xem vẫn thấy ổn, tức **ngưỡng 0.90 quá chặt**;
- hoặc 109% là artefact của một khâu khác chưa soi tới.

> Đây **đúng câu hỏi mà `CAPACITY-WORDS` vừa tự trả lời cho chính nó**: nó nổ trên 12 project, hoá ra 10 là báo động giả do mẫu số sai. `DRAFT-OVERFILL` đang ở đúng vị trí đó — nổ trên dữ liệu đã ship, chưa ai kiểm mẫu số.

Không sửa cho tới khi có người xem lại Gone Girl với con số này trong tay.

---

### J-SPEECH-CONTENT. Quét transcript trong cửa sổ của một claim `speech` — CHỈ GHI, KHÔNG LÀM

**Trạng thái: ứng viên. KHÔNG implement.** n=1, và ngưỡng "khớp nghĩa" chưa có nghĩa gì cho tới khi có phim thứ hai nhiều thoại.

#### GIỚI HẠN ĐẶT TRƯỚC, không phải chú thích cuối trang

`I4` nói thẳng: transcript của phim ngoại ngữ làm bằng Whisper `--translate` **không dùng để suy ra chuyện gì xảy ra**. Bad Genius là `lang: th`, `model: medium`, dịch thẳng Thái→Anh. Mọi thứ dưới đây phải đọc với giả định đó còn nguyên hiệu lực.

> **Hệ quả thiết kế: gate chỉ được KHẲNG ĐỊNH ở trạng thái IM LẶNG. Hai trạng thái còn lại là gợi ý cho người, không bao giờ là "pass".**

#### Ý tưởng

`H-REVEAL-B` kết luận reveal do thoại mang thì không kiểm được, vì *"không gate nào trong pipeline đọc thoại ở tầng nghĩa"*. Đúng về **audio**, nhưng **thiếu**: `transcript.json` là **văn bản, và có timestamp**. Nó đang nằm sẵn trong mọi project và chưa gate nào đụng tới.

Với line mang `claim.type: "speech"`, quét các segment transcript giao với cửa sổ `[clip_start, clip_end)`:

| trạng thái | nghĩa | gate làm gì |
|---|---|---|
| **im lặng** trong cửa sổ | line khẳng định một câu thoại **không tồn tại** | **KHẲNG ĐỊNH — lỗi thật.** Đây là trạng thái duy nhất đáng assert |
| có thoại, **khớp nghĩa** | bằng chứng yếu | báo là **yếu**, không tính là verified |
| có thoại, **không khớp** | có thể lệch, có thể do dịch máy, có thể do intercut | **cờ cho Stage-7**, không chặn |

#### Đo thử trên Bad Genius (chưa implement, chỉ chạy tay)

Transcript: 1472 segment, 56.7s → 7785.3s, mật độ ~1 segment / 5.3 giây.

Đối chiếu với các mốc **đã xác minh bằng frame**, độ khớp thời gian rất tốt:

| mốc (frame-verified) | transcript trong cửa sổ |
|---|---|
| B04 03:35 khoản phí | *"60,000 baht per semester. \| 2 semesters is 120,000 baht."* |
| B25 32:05 hai đề | *"Teacher, what should we do with the 40th question \| There are two sets of the question."* |
| B55 82:36 vào giờ thi | *"Starting now,"* |
| B80 123:24 lời khai | *"We're here to record"* |

**Nhưng ba cửa sổ của chính ba line `speech` trong draft thì KHÔNG khớp:**

    01:10:48-53  (R1, Pat)   -> "You really | want to get caught."
    01:10:58-11:07 (R1, Pat) -> "The last question. | Are you ready?"
    01:50:38-51  (Bank khai) -> "What's up?"

⚠️ **Và đây là phần đáng giá nhất của mục này.** Đọc ba dòng đó, phản xạ đầu tiên là kết luận *"transcript lệch thời gian"*. **Sai.** Bốn spot-check ở trên chứng minh time base khớp. Lý do thật là **cửa sổ được bind theo SHOT, mà trong đoạn intercut thì cửa sổ của một shot chứa thoại của phía bên kia** — và trong đoạn thẩm vấn này, phim còn cắt qua lại giữa hai dòng thời gian.

> Nghĩa là trạng thái **"không khớp" sẽ xảy ra RẤT thường xuyên vì lý do vô hại**, và bất kỳ ai xây gate này mà coi "không khớp" là lỗi sẽ tạo ra một biển cờ sai. Đúng như trực giác ban đầu: chỉ **im lặng** mới assert được.

Tự ghi nhận cách đo: kết luận sai ban đầu được sửa **bằng cách đối chiếu với mốc đã xác minh bằng frame**, không bằng cách nhìn kỹ hơn vào transcript. Lặp lại bài học ở cuối NHÓM G: *trước khi tin một điểm số, hãy đọc mấy ca mà nó cho là sai*.

#### Nó chạm vào hai chỗ khác

**1. `H-REVEAL-B`** — reveal `carried: dialogue` hiện **không có sàn nào**. Cái này cho nó một cái sàn: không phải xác minh đầy đủ, nhưng *"phim CÓ nói gì đó ở chỗ đó"* thì hơn là không có gì. Nếu cửa sổ landing của một reveal do thoại mang mà **im lặng**, thì hoặc bind sai, hoặc reveal không nằm ở đó.

**2. Lỗ hổng plant-audit của Gia Tài Của Ngoại (`I4`, nửa sau).** Pass 5 kết luận motif "bán nhà" không có plant nào, sau khi grep toàn bộ `action` text. Sai — plant nằm ở **thoại** lúc 01:14:10, người mua tới cổng hỏi thăm. `I4` đã ghi: *"một plant audit chỉ quét `action` sẽ trả về âm tính giả với sự tự tin tuyệt đối"*.

> **Cùng một nguồn dữ liệu chưa dùng, hai lỗ hổng khác nhau.** Một cái làm claim `speech` không kiểm được; một cái làm plant-audit mù với mọi thứ phim gieo bằng lời. Nếu có ngày đọc transcript, nên thiết kế cho cả hai cùng lúc chứ không vá riêng.

#### Vì sao CHƯA làm

- **n=1.** Một phim, một ngôn ngữ, một model.
- **Ngưỡng "khớp nghĩa" chưa định nghĩa được.** So khớp thế nào giữa *"He wanted Bank with nothing left to say no with"* và một transcript dịch máy? Cần ít nhất một phim nhiều thoại nữa mới biết ngưỡng nào không vô nghĩa.
- **Trạng thái im lặng cũng cần hiệu chỉnh.** Mật độ ~1 segment/5.3s là của phim này. Phim ít thoại hơn sẽ có khoảng lặng thật, và "im lặng = lỗi" sẽ bắn nhầm.

---

# NHÓM M — PHÁT HIỆN TRÊN PHIM ĐÃ SHIP *(chưa sửa, cố ý)*

**Bối cảnh.** Ngày 2026-09-05, ba gate `BINDING-INTEGRITY`, `CATALOGUE-DENSITY`,
`BEAT-COVERAGE` được đưa ra khỏi `if style == "linear":` vì cả ba đo thuộc tính
**không phụ thuộc mode**. Ngay lần chạy đầu, chúng bắn trên **năm phim
review đã ship**. Dưới đây là toàn bộ số liệu, **chưa sửa gì**.

| project | BEAT-COVERAGE | beat KHÔNG có shot nào | density | BINDING-INTEGRITY |
|---|---|---|---|---|
| gonegirl2014 | 32/36 — thiếu **B02, B21, B23, B28** (run ≥2: `B21,B23`) | B02, B21, B23, B28 | **1.64** | sạch 67/67 |
| joker2019 | 32/37 — thiếu **B08, B11, B18, B25, B27** | **B08, B11, B12, B18, B25, B27** | **1.76** | sạch 73/73 |
| parasite2019 | 26/28 — thiếu **B27, B28** (run ≥2) | B27, B28 | 3.93 | sạch 114/114 |
| howtomakemillions2024 | 54/57 — thiếu **B14, B26, B32** | (không) | 4.91 | sạch 129/129 |
| interstellar2014 | **34/34** | (không) | 2.97 | sạch 91/91 |

`unplaceable = 0` ở cả năm — không phim nào dùng pool line, nên con số coverage
không bị nhiễu bởi lỗ hổng pool đã vá khi chuyển gate.

## M1 — `gonegirl2014`: beat map KHÔNG tăng dần theo thời gian phim ⚠️ **ưu tiên cao nhất**

```
B21 | 01:24:28 | Media frenzy / Nick prime suspect
B22 | 01:34:27 | Motel robbery - Greta + Jeff take cash
B23 | 01:26:09 | Amy turns to Desi for refuge        <-- sớm hơn B22
```

Gate tự đề xuất một cách giải thích khác (*"nếu map viết bằng MM:SS thì khai
`ts_format: MM:SS`"*). **Đã kiểm: không phải.** Cả ba mốc đều là ba thành phần
`HH:MM:SS` và đều nằm đúng dải thời gian phim. Đây là **lỗi dữ liệu thật**.

Thứ tự *kể chuyện* B22 → B23 mới là đúng (Amy bị cướp ở motel **rồi** mới tìm
đến Desi), nên nhiều khả năng **mốc của B23 sai**, chứ không phải xếp sai thứ tự.

**Vì sao nó là ưu tiên số một:** `beat_coverage` sắp xếp lại theo *thời gian*
(`bt["ordered"]`), nên cửa sổ của B23 thành `[01:26:09, 01:34:27)` và của B22
thành `[01:34:27, …)`. **Mọi cửa sổ beat quanh đó đều lệch khỏi beat mà nó đại
diện.** Nghĩa là con số `32/36` ở trên — và cả danh sách beat rỗng của chính
phim này — **không đáng tin trên chính phim này**. Sửa M1 trước, rồi mới đọc lại
M3; đọc M3 trước khi sửa M1 là đọc số vô nghĩa.

## M2 — `joker2019`: 6/37 beat không có shot nào được catalogue

`B08, B11, B12, B18, B25, B27` — **16% nội dung tác giả tự khai là có trong
phim, không thể trình bày được bằng footage đã catalogue.**

Một chi tiết chỉ lộ ra khi đọc đủ hai danh sách: **B12 rỗng nhưng vẫn "covered"**
(nó có trong danh sách beat-rỗng mà không có trong danh sách uncovered). Không
mâu thuẫn — `CATALOGUE-DENSITY` đếm shot **bắt đầu** trong cửa sổ beat, còn
`BEAT-COVERAGE` đếm line có `clip_start` trong cửa sổ đó. B12 được kể bằng một
shot bắt đầu từ beat liền trước tràn sang. Đáng ghi vì nó cho thấy hai gate này
**không thừa nhau**: một cái hỏi *"có đủ footage không"*, cái kia hỏi *"có kể
đến không"*, và chúng lệch nhau ở đúng những ca như B12.

## M3 — `gonegirl2014`: density 1.64, bốn beat rỗng

`B02, B21, B23, B28` rỗng; thêm **16 beat chỉ có đúng một shot**. 1.64 shot/beat
nằm giữa Shutter Island (1.11, sau đó chạy 47% line tự do) và Spider-Man (2.65,
25% line tự do) — nhưng **`BINDING-INTEGRITY` của Gone Girl lại sạch 67/67**.

> Tự ghi nhận: đây là phản ví dụ cho giả thuyết trong docstring của
> `catalogue_density` rằng catalogue mỏng **đẩy** pass enrichment đi bịa cửa sổ.
> Gone Girl mỏng mà không bịa dòng nào. Băng "PROVISIONAL (4 films)" vẫn đúng là
> provisional, và giờ có một ca ngược. **Không sửa băng vội — n vẫn quá nhỏ.**

---

## Lần thứ BA một gate bắn vào sản phẩm người đã duyệt

Ba lần, và **ba nguyên nhân khác hẳn nhau**. Đây mới là điều đáng ghi, không
phải bản thân con số:

| # | ca | nguyên nhân | ai sai |
|---|---|---|---|
| 1 | `CAPACITY-WORDS` bắn 12/17 project | **mẫu số hỏng** — ceiling đọc từ field tự khai, drift 0.58–0.80 lần giá trị suy ra | **gate sai.** Sửa mẫu số → còn 2 project |
| 2 | M1/M2/M3 ở trên | **lỗi dữ liệu thật** — mốc sai, catalogue thiếu | **gate đúng.** Dữ liệu cần sửa |
| 3 | Superbad `convenience_store` | **chưa xác định** | chưa biết — chưa đủ dữ kiện để kết luận bên nào |

> **Không có luật nào nói rằng gate sai khi nó bắn vào sản phẩm đã ship.** Cũng
> không có luật ngược lại. Ca 1 là gate sai và việc sửa gate là đúng; ca 2 là gate
> đúng và việc sửa dữ liệu mới là đúng; ca 3 vẫn mở. **Mỗi ca phải đọc riêng** —
> và phản xạ "đã ship rồi thì chắc gate quá nghiêm" chính là thứ đã suýt làm hỏng
> A11 (drop tier Bad Genius dựa trên mẫu số hỏng, sau phải rút lại).

**Vì sao CHƯA sửa M1–M3.** Đây là phim đã ship; phát hiện lúc này đáng giá hơn
bản vá. Ba mục này là **bằng chứng đầu tiên** rằng default `style:` im lặng đã
che mất lỗi dữ liệu thật chứ không chỉ gây lộn xộn — và giá trị đó chỉ còn
nguyên khi chúng còn nằm đây chưa sửa. Sửa xong thì không ai kiểm chứng lại được
là gate có thật sự bắt được gì không.

**Chưa đánh giá:** `SNAP-GRID` vẫn nằm trong `if style == "linear":`. Nhiều khả
năng nó cũng không phụ thuộc mode, và dry-run cho thấy nó **sẽ** đo được thật
trên `howtomakemillions2024`. Cố ý không chuyển cùng đợt — chuyển vì *nằm cạnh*
đúng là cách mà `if style == "linear":` phình ra quá rộng ngay từ đầu.

---

# NHÓM N — CATALOGUE ĐÃ SHIP THIẾU DỮ LIỆU, Ở HAI TRƯỜNG *(đo 2026-09-05)*

## N1. Catalogue thiếu ở CẢ `depicts` LẪN `chars` — cùng một hình dạng

### N1a. 39% shot không có nhãn VISIBLE nào

```
badgenius2017: 231 shot
  khong co nhan truc-NHIN : 91  (39%)
  khong co depicts nao ca :  0
  dem nhan: action 52 | setup 36 | dialogue 32 | reaction 32 |
            discovery 27 | emotion 27 | establishing 17 | montage 7 | reveal 1
```

`VISIBLE = {action, dialogue, establishing, montage, reaction, transition}`
`STORY   = {aftermath, discovery, emotion, reveal, setup}`

91 shot chỉ mang nhãn **STORY** — `setup` một mình, `discovery` một mình,
`emotion` một mình. Đây là **G-AXIS**, nhưng lần này nằm trong **dữ liệu đã
ship**, không phải trong phiếu eval.

### Hệ quả: mọi điểm số chấm theo catalogue này đều PHẠT câu trả lời đầy đủ hơn

Ví dụ thật, `shot030`:

| | depicts |
|---|---|
| catalogue (người) | `['setup']` |
| agent | `['establishing', 'setup']` |

Agent **đúng hơn** — nó thêm một nhãn trục-nhìn mà người bỏ sót. Chấm theo
catalogue thì nó **mất điểm vì đã đúng**.

> **Điều này định nghĩa lại con số 76% của hôm nay.** `VISIBLE-AXIS 13/17 = 76%`
> đo trên phiếu Shutter Island là một **SÀN, không phải TRẦN**. Phần "sai" bao
> gồm cả những ca mà đáp án tham chiếu thiếu nhãn chứ không phải agent thiếu.
> Không biết phần đó lớn bao nhiêu — nhưng biết chắc nó **khác 0**.

### Chưa làm gì, và vì sao

Không sửa 91 shot. Ba lý do:

1. **Chưa biết nhãn đúng là gì** nếu không xem lại frame từng shot — đúng bằng
   khối lượng của một pass catalogue mới.
2. **Sửa xong thì mất mốc so sánh.** Hiện có một catalogue người-viết và một
   bộ tag máy-viết trên cùng 231 cửa sổ; đó là dữ liệu A/B hiếm.
3. Theo tiền lệ **NHÓM M**: phát hiện trên phim đã ship đáng giá hơn bản vá,
   và chỉ còn nguyên giá trị khi chưa sửa.

### Việc cần làm TRƯỚC khi tin bất kỳ điểm số tag nào

Bất kỳ eval nào chấm `depicts` theo catalogue có sẵn **phải** báo riêng:
- số shot mà đáp án tham chiếu **không có** nhãn trục-nhìn (mẫu số không hợp lệ)
- điểm tính **chỉ trên** phần mẫu số hợp lệ

`tools/score_vision_eval.py` đã tách hai trục (`VISIBLE_AXIS` / `STORY_AXIS`,
dòng 34-36) nhưng **chưa** báo cáo cỡ mẫu số hợp lệ. Đó là lỗ hổng nhỏ nhất và
đáng vá nhất trong nhóm này.

### N1b. `chars` rỗng KHÔNG phải vì không nhìn thấy mặt — **28/30**

`badgenius2017` có **55 shot** mà người viết catalogue để `chars` trống. Lấy 30
shot trong số đó (những shot mà máy có gán tên), mở **toàn bộ 86 frame** mà
tagger được đưa, chấm theo chuẩn ghim sẵn trong `docs/FACE_STANDARD.md`:

```
FACE 26 | AMBIG 2 | NO-FACE 2   (trên 30 shot)
```

**28/30 có mặt người nhìn rõ.** `shot034` là ví dụ sạch nhất: bốn học sinh đứng
tạo dáng nhìn thẳng ống kính, bốn khuôn mặt sắc nét, và catalogue ghi `chars: []`.

> **Trường `chars` trống không phải vì người không nhìn thấy mặt.** Cùng một
> hình dạng với N1a, ở trường thứ hai: catalogue đã ship **thiếu dữ liệu**, và
> bản tag máy **đầy đủ hơn** bản người.
>
> Ghi thêm: cả hai lần đọc lần đầu của tôi đều nhầm "đầy đủ hơn" thành "bịa".
> Xem `docs/FACE_STANDARD_RESULT.md` và mục ngày 2026-09-05 trong `lessons.md`.

### Hệ quả cho MỌI điểm số đã đo hôm nay

Hai con số của phiếu Shutter Island:

```
VISIBLE-AXIS    13/17 = 76%    (baseline agent 50%)
CHARS precision 28/38 = 74%    (baseline 77%)
```

Cả hai đều chấm theo một **tham chiếu thiếu ở CẢ HAI trường**: `depicts` thiếu
nhãn trục-nhìn (N1a), `chars` thiếu tên người có mặt rõ (N1b).

> **Cả 76% lẫn 74% đều là SÀN, không phải TRẦN, và khoảng cách tới sự thật là
> KHÔNG BIẾT** — không phải nhỏ, không phải lớn, mà *chưa đo được*. Một phần
> của phần "sai" là tham chiếu thiếu chứ không phải câu trả lời sai. Không được
> trích dẫn hai số này như thể chúng là độ chính xác.

### N1c. Hai người chấm, 61% chồng lấn, **1% trùng khớp** *(đo 2026-09-06, n=231)*

Chạy máy tag **toàn bộ 231 shot** `badgenius2017` rồi chấm theo chính catalogue
người viết:

```
TRUC NHIN THAY        : 95/140  = 68%    cham 140/231 | LOAI TRU 91 (39%)
CHARS precision       : 161/197 = 82%    cham 203/231 | LOAI TRU 28 (12%)
CHARS recall          :           67%

co chung >=1 tag bat ky : 142/231  (61%)
  trong do KHOP HAN     :   2/231  ( 1%)   <-- con so dang chu y
```

**Trùng khớp hoàn toàn 2/231.** Hai bên cùng nhìn một cửa sổ, chồng lấn 61%,
nhưng gần như **không bao giờ** đưa ra cùng một tập nhãn.

Bảng nhầm lẫn (tay → máy) **bị chi phối bởi các cặp XUYÊN TRỤC**:

```
action -> reaction   x12     discovery -> setup    x11
setup  -> reaction   x10     reaction  -> setup    x9
discovery -> action  x8      action    -> emotion  x7
setup  -> dialogue   x5      reaction  -> dialogue x5
```

`action/reaction/dialogue` là **trục NHÌN**; `discovery/setup/emotion` là **trục
TRUYỆN**. Sáu trong tám cặp dẫn đầu bắc cầu giữa hai trục. Đây không phải hai
bên nhìn khác nhau — là hai bên **trả lời hai câu hỏi khác nhau** bằng cùng một
từ vựng.

### Hệ quả cho con số 68%

> Con số `VISIBLE-AXIS 68%` đo trên **140 shot mà đáp án tham chiếu có nhãn
> trục-nhìn**. Nhưng ngay trong 140 shot đó, hai bên vẫn trộn trục. Nghĩa là
> **68% đo phần từ vựng mà hai bên CÙNG hiểu giống nhau — và phần đó NHỎ HƠN
> toàn bộ từ vựng.**
>
> Nó không phải "độ chính xác của máy". Nó là độ đồng thuận trên một tập con
> chưa được định nghĩa rõ ranh giới.

### ⛔ KHÔNG hành động — có chủ ý

Đây là **bằng chứng mạnh nhất từ trước tới nay** cho `G-AXIS` (ghi từ Shutter
Island, xem NHÓM G). Nhưng:

- G-AXIS đã được ghi và **cố ý chưa implement ở n=1**. Giờ có n=231 trên phim
  thứ hai — mạnh hơn nhiều, nhưng vẫn **không phải giấy phép** để thiết kế lại
  `depicts` **giữa một tác vụ chấm điểm**.
- Sửa từ vựng lúc này làm hỏng luôn cặp A/B hiếm: một catalogue người-viết và
  một bộ tag máy-viết trên **cùng 231 cửa sổ**. Đó là dữ liệu chưa từng có.
- Theo tiền lệ NHÓM M và N1a/N1b: phát hiện trên dữ liệu đã ship đáng giá hơn
  bản vá, và chỉ còn nguyên giá trị khi chưa sửa.

Dữ liệu để xem lại: `projects/badgenius2017/shots_tagged.json` (231 shot máy),
`projects/badgenius2017/shots.json` (231 shot người, **không đụng tới**,
sha1 `e8ce90043b07382e63fed00d1f154f6d7719ffc1`).

---

### N1d. `censor` — trường thứ BA, và lần thứ ba catalogue là bên thiếu

`badgenius2017` ghi `censor: none` trên **cả 231 shot**. Chạy máy gán `censor`
trên 130 shot đầu (tuần tự, `00:01:22` → `01:11:58`, 72/124 phút — bao gồm trọn
đoạn bạo lực duy nhất của phim):

```
shot102  00:58:28  may = blur_heavy   nguoi = none
  note may: "mat bi danh, mau tuoi, mot mat sung hup va mui chay mau, can canh
             lap day khung hinh; thuong tich CHINH LA diem cua shot"
shot103  00:58:36  may = blur_light   nguoi = none
  note may: "vet mau kho tren mat va ao dong phuc rach, nguoi chiem khoang 1/5
             khung rong, khong ve thuong nao doc duoc o kich thuoc do"
```

### Bằng chứng nằm ngay trong chính catalogue

Trường `action` **do người viết** cho `shot102`:

> *"Daylight, and a close-up of what it cost: **one eye swollen shut, dried
> blood across his face**"*

Người viết đã **mô tả đúng thương tích** — rồi đặt `censor: none` cho chính shot
đó. Hai trường trong cùng một bản ghi mâu thuẫn nhau, và không gate nào bắt được
vì không gate nào đối chiếu `action` với `censor`.

### Đáng chú ý: máy phân MỨC đúng

`blur_heavy` cho cận cảnh lấp đầy khung, `blur_light` cho **cùng nhân vật đó**
trong cảnh rộng nơi không vết thương nào đọc được. Đó chính là suy luận theo
**độ phủ + độ đọc được** mà S7.1 yêu cầu — và cũng chính là thứ `shot114`
(superbad) đã KHÔNG làm. Năng lực có; độ tin cậy thì không.

⚠️ **Đây là phép đo EXTRAS, không phải miss.** `badgenius2017` không có shot
`censor` dương nào, nên một miss là **bất khả về mặt cấu trúc** ở phim này.
Không được trích con số này như một tỉ lệ bỏ sót. Phạm vi: 130/231 shot.

---

## Hệ quả CHUNG của N1a + N1b + N1d — cho mọi lần chấm điểm về sau

| trường | catalogue người thiếu | đo được |
|---|---|---|
| `depicts` | 91/231 (39%) không có nhãn trục-nhìn | N1a |
| `chars` | 28/30 shot `chars` rỗng VẪN có mặt người nhìn rõ | N1b |
| `censor` | ≥2 shot bạo lực để `none`, dù `action` tự mô tả thương tích | N1d |

> **Ba trường, ba lần catalogue đã ship là bên KÉM ĐẦY ĐỦ hơn.**
>
> Nghĩa là: **catalogue người viết KHÔNG phải là đáp án tham chiếu ở bất kỳ
> trường nào trong ba trường đó.** Mọi điểm số chấm máy theo nó đều **kế thừa
> phần thiếu ấy** và sẽ **phạt câu trả lời đầy đủ hơn**.
>
> Điều này không nói máy đúng. Nó nói **chưa bên nào là tham chiếu**, và bất kỳ
> con số nào được tính như thể có tham chiếu đều phải kèm cảnh báo này. Các con
> số hôm nay (`VISIBLE-AXIS 68%`, `CHARS precision 82%`) là **SÀN**, khoảng cách
> tới sự thật **chưa đo được**.

Dữ liệu A/B còn nguyên để đọc lại: `shots.json` (người, 231, **không đụng tới**,
sha1 `e8ce90043b07382e...`), `shots_tagged.json` (máy, 231),
`tags_censor/` (máy, 130, chỉ trường censor).

---

## N2. `FACE-AVAILABILITY` — ĐÃ THỬ, ĐÃ ĐO, **BÁC BỎ** ⛔

*Gate đề xuất:* trước khi chấp nhận một tên trong `chars`, kiểm tra có ít nhất
một frame chứa khuôn mặt nhận dạng được. Không có mặt → không được gán tên.

**Không xây. Không phải vì yếu — vì SAI DỤNG CỤ.**

### Chuẩn đã dùng (ghim trong `docs/FACE_STANDARD.md` TRƯỚC khi mở frame nào)

Một frame có "mặt nhận dạng được" khi đủ **cả bốn**: (1) có mặt người, không
phải tay/lưng/thân; (2) đầu chiếm **≳10% chiều cao khung**; (3) nét, không nhoè;
(4) vùng mắt-mũi-miệng nhìn thấy đáng kể. Shot đạt nếu **≥1 frame** thoả.
`AMBIG` là kết quả hạng nhất, không được ép về `FACE`/`NO-FACE`.

### Kết quả: 30 shot, 86 frame

```
FACE 26 | AMBIG 2 | NO-FACE 2
gán tên khi KHÔNG có mặt nhận dạng được: 2/30 (7%)
  shot098 -> Bank  : phố đêm, người đi xe máy đội mũ bảo hiểm ở xa, rồi một ô tô
  shot110 -> Lynn  : hội trường tối, người thuyết trình nhỏ xíu ngược sáng
AMBIG: shot029 (đầu ~8-10% khung), shot032 (quay lưng 3/4 nặng)
```

Ranh giới kích thước/độ nét **đứng vững** — chỉ 2 ca rơi vào `AMBIG`.

### Vì sao vẫn bác bỏ

```
shot163 -> Bank      FACE (sạch: mặt to, nét, không che)
shot165 -> Pat       FACE (sạch)
```

Hai khuôn mặt đó là **hai người đàn ông phương Tây mặc vest** — giám thị kỳ thi
ở nước ngoài. `Bank` và `Pat` là học sinh Thái tuổi teen.

**Chúng ĐẠT bài kiểm tra này, và chúng SAI.**

| nhóm | số ca | gate face-availability bắt được? |
|---|---|---|
| gán tên khi không có mặt | 2 | **có** |
| gán tên lên mặt của người KHÁC | ≥2 | **không** |
| gán tên đúng | ≤26 | — |

> Gate này bắt **2 trong ≥4** lỗi chứng minh được, và cho ≥2 lỗi còn lại đi qua
> **kèm tín hiệu sạch**. Như vậy **tệ hơn là không có gate**: nó sẽ đóng dấu
> "đã xác minh" lên `shot163`.
>
> **Sai dụng cụ, không phải dụng cụ yếu.** Câu hỏi là *"có phải mặt NGƯỜI ĐÓ
> không"*; phép đo trả lời *"có phải MỘT khuôn mặt không"*. Tăng ngưỡng, thêm
> frame, siết `AMBIG` — không cái nào thu hẹp được khoảng cách đó.

Con số 26 là **cận trên**. Đã xác minh *có mặt* cho cả 26; **chưa xác minh
*mặt ai*** cho ca nào, và việc đó cố ý nằm ngoài phạm vi vì không thể làm bằng
mắt nếu không mở phim ra đối chiếu.

**Không kết luận bỏ `names.json`.** 28/30 có sẵn mặt để nhận dạng, và nhánh đối
chứng không tạo ra phỏng đoán tốt hơn — nó tạo ra `(khong ro)` mọi lần.

### Vấn đề gốc vẫn MỞ

`chars` và `claim.subject` do **cùng một agent** viết, nên `binding_audit` đem
một điều bịa ra so với chính nó và cho qua. `shot163` chính là lỗi đó, lại còn
có một khuôn mặt trong khung để trông có vẻ vững. **Cần dụng cụ khác và một
session khác.**

Chi tiết đầy đủ: `docs/FACE_STANDARD.md` + `docs/FACE_STANDARD_RESULT.md`.

---

## ƯU TIÊN NẾU LÀM TIẾP *(thay cho danh sách cũ)*

0⁻. **M1 (`gonegirl2014` beat map sai thứ tự)** — MỚI, rẻ nhất trong nhóm M và chặn việc đọc nhầm M3. Không phải gate, là **dữ liệu**. Phải làm trước M3.
0. **H-REVEAL** — MỚI, ưu tiên cao nhất trong nhóm gate. Dữ liệu đã đủ, lỗ hổng đã có ca thật, và hậu quả là mất hẳn cú lật chứ không phải lệch một chút.
0b. **J-SPEECH-CONTENT** — ghi nhận, chưa làm. Chờ phim thứ hai nhiều thoại. Nếu làm, làm cùng lúc với lỗ hổng plant-audit của I4 (cùng một nguồn dữ liệu).
1. **F4 (README)** — rẻ nhất, chặn hiểu nhầm cho mọi session sau.
2. **G-SNAP** — đã chứng minh trên dữ liệu thật, rủi ro gần bằng không, đóng được một nguồn drift.
3. **D-RENDER** — lớp kiểm sau render (đếm audio/clip/runtime). Rẻ, phủ cả một lớp lỗi.
4. **E1 `timeline.json`** — ~5 dòng, cho QA nói được "line 36" thay vì "khoảng phút 7".
5. **G-AXIS + G-CAST** — đi cùng nhau. Đây là thứ mở khoá tag máy VÀ làm `binding_audit` có nghĩa. Cần thiết kế trước.
6. **A-AMB** — sau khi có nhận định về câu kết Shutter Island.
7. **BINDING-INTEGRITY bậc 2** — sau khi một phim mới chạy trọn bậc 1.
8. **F5 (id sub-line)** — sửa gốc, không chỉ chốt lưới.
9. **B2 + B-NEW** — rule, ghi nhanh, không đụng engine.
10. **F1, F2, F3** — cần phim thứ hai / cần calibrate thêm.

**Chưa validate được, đừng quên:** nhánh SCRIPT stage của ACTION-SETUP (chờ phim action), và bậc 2/3 của BINDING-INTEGRITY.
