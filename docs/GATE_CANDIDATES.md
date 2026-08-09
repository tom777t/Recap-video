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

## ƯU TIÊN NẾU LÀM TIẾP *(thay cho danh sách cũ)*

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
