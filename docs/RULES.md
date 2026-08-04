# MASTER LIST — Rules & Lessons (Recap Vid / linear pipeline)
*Tổng hợp toàn bộ từ 3 phim: Interstellar, John Wick, Spider-Man NWH.*
*Cập nhật: sau vòng sửa action-coverage của Spider-Man, TRƯỚC khi xem bản mới.*

---

# PHẦN A — ĐÃ GHI vào `prompts/style_linear_vn.md` (đang chạy)

| # | Rule | Nguồn | Trạng thái |
|---|------|-------|-----------|
| A1 | **Act-by-act enrichment** khi draft under-target (không enrich cả phim một lần) | Interstellar | ✅ kiểm chứng |
| A2 | **Đừng nén chuỗi nhân-quả** / **đừng bịa** cái phim cố tình bỏ trống | Interstellar | ✅ kiểm chứng |
| A3 | **CLIP ANCHORING** — anchor `clip_start` vào khoảnh khắc narration mô tả, KHÔNG vào shot-start. Dịch cả window (start+end), không co. Shift >3-4s phải frame-check. | John Wick | ✅ kiểm chứng |
| A4 | **+ RULE 2 (bổ sung A3)** — fast-cut sequence: anchor vào đúng SUB-MOMENT, không vào đầu sequence | Spider-Man | ⏳ chờ xem |
| A5 | **DRIFT TAGGING** — tag nhân vật CỤ THỂ, không generic. Cue hierarchy: mặt lộ → đồ khi sáng → thoại đặc trưng. **Admit uncertainty + flag** khi mờ, không đoán. | John Wick + Spider-Man | ✅ kiểm chứng (3 Peter không lẫn) |
| A6 | **+ RULE 3 (bổ sung A5)** — mở rộng sang **mọi NHÓM intercut** (villain, đội, ê-kíp), không chỉ look-alike. "Even when they look different." | Spider-Man (Sandman/Electro lẫn) | ⏳ chờ xem |
| A7 | **PRE-CATALOGUE: đọc Wikipedia** (Plot + Cast) trước catalogue. Chỉ plot+cast, KHÔNG review/rating. **Frames win** khi mâu thuẫn. | Spider-Man | ✅ kiểm chứng |
| A8 | **SPOILER DISCIPLINE** — setup-zone/reveal-zone split; biết twist ≠ được kể; đọc trước = trách nhiệm CAO hơn; nghi thì giấu. **Per-reveal beat-map** ghi vào beats_proposal, hold theo map — KHÔNG dựa vào "kể đúng thứ tự". Kể cảnh sớm bằng con mắt người xem lần đầu. | Spider-Man | ✅ kiểm chứng (trọn 5 act, phim twist gắt nhất) |
| A9 | **RULE 1 — Under-fill: TRỐNG Ở ĐÂU quan trọng hơn trống bao nhiêu.** Trống ở action = honest. Trống ở dialogue/emotional/closing = coverage gap, phải lấp. "Fill thấp vì phim action" chỉ đúng cho action shot — KHÔNG áp blanket. | Spider-Man (cảnh kết 3 phút bị nén còn 24s) | ⏳ chờ xem |
| A10 | **+ RULE 1 correction** — "Don't pad the fights" ≠ "let the fights be unfollowable". Không tường thuật từng cú = đúng; kể STAGE của trận đánh = BẮT BUỘC. **Test: người xem lần đầu có theo được trận đánh không?** Nếu không → under-covered, bất kể fill. | Spider-Man (Statue 13.5 phút / 5 window = 14% coverage) | ⏳ chờ xem |

---

# PHẦN B — ĐÃ GHI vào `docs/lessons.md` (ghi chép, không phải luật)

| # | Bài học | Nguồn |
|---|---------|-------|
| B1 | **Tier phải khớp độ-THOẠI của phim**, không chỉ shot-count. Action ít thoại → tier thấp. | John Wick |
| B2 | **Đừng khóa tier giữa chừng.** Enrich trung thực → đo → RỒI gắn tier. | John Wick (9.9→19 min→cắt về 15) |
| B3 | **Tier fits the film, not the film fits the tier.** Vượt band vì lý do thật (comprehension) → đổi tier lên, không cắt. | Spider-Man (→ video_essay) |
| B4 | **Tự-check là FILTER, không phải DUYỆT.** Tìm được 14/16 mismatch, nhưng sót Sandman/Electro + đánh giá nhẹ L59. Mắt người tìm ra cả hai. **RENDER QA bắt buộc.** | Spider-Man |
| B5 | **META-PATTERN: mọi lỗi đều là "rule ĐÚNG áp quá HẸP hoặc quá RỘNG."** Drift áp cho look-alike nhưng không cho nhóm; action-underfill áp cho cả draft thay vì chỉ action shot; clip-anchoring áp shot-start thay vì sub-moment; self-check tin là duyệt thay vì lọc. **Fix luôn là: nới đúng phạm vi.** | Spider-Man |
| B6 | Shift/nudge lớn (>3-4s) đáng nghi — dễ vượt scene cut thành drift. | John Wick (id22 +9s) |
| B7 | OpenCode hay **chốt pattern từ mẫu nhỏ** rồi tự tin (action-only, 6-vs-rest, 12/91 line). Ép check HẾT, không sample. | Cả 3 phim |
| B8 | **Đừng làm bẩn names.json** bằng danh từ thường/chữ đầu câu để dọn lint. Lint [NAME] giả vô hại — kệ. | Interstellar, John Wick |

---

# PHẦN C — CHỜ GHI (sau khi xem bản Spider-Man mới)

| # | Ứng viên | Trạng thái |
|---|----------|-----------|
| C1 | **Fill là chỉ số MÙ với comprehension — không bao giờ dùng làm mục tiêu.** Bằng chứng cứng: trước 9 stage-line = 62% (2821/4574), sau = 62% (2821/4574). Cùng số, một bản climax không hiểu nổi, một bản kể được. Thêm line mở window mới (mẫu số) song song thêm chữ (tử số) → tỷ lệ đứng yên. | ✅ **Ghi được NGAY** — không cần xem |
| C2 | **Ngưỡng coverage cho set-piece.** Dữ liệu: dưới 25% = không theo được (Statue 13.5min/5win=14%, Highway 5.8/3=21%, Apartment 4.9/2=16%). John Wick house fight (theo được) = 5 stage/pha. Ước: **1 line mỗi ~60-90s footage, hoặc 1 line mỗi stage thật — cái nào nhiều hơn.** | ⏳ Chờ xem 9 line đủ chưa |
| C3 | **Quy trình mấy vòng là đủ?** xem → tự-check → sửa → xem lại. Đủ hay cần vòng 3? | ⏳ Chờ xem |

---

# PHẦN D — Ý TƯỞNG LỚN chưa làm (cải tiến CẤU TRÚC, không phải vá lỗi)

## D1. Tách Stage 3a (OUTLINE) / 3b (SCRIPT) ⭐ ý của bạn
**Vấn đề:** pass đầu LUÔN mỏng ở cả 3 phim (Interstellar 11.8min/54%, John Wick 9.9/23%, Spider-Man 8.5/31%). Ta cứ coi đó là lỗi và hoảng.
**Nhận ra:** pass đầu *thực chất LÀ outline* — nó dựng khung, phủ beat, bind shot, thấy toàn cảnh. Mỏng là ĐÚNG. Còn act-by-act enrich *thực chất LÀ viết script*.
**Đề xuất:**
- **Stage 3a — OUTLINE:** viết 1 lần cả phim, cố ý mỏng. Gate CHỈ kiểm coverage/binding. **KHÔNG bật DRAFT-TARGET** (outline mỏng không phải lỗi).
- **Stage 3b — SCRIPT:** viết dày act-by-act dựa outline. Lúc này DRAFT-TARGET mới có nghĩa.
**Lợi:** giữ được cả tầm nhìn tổng thể (outline) lẫn độ dày (act-by-act). Hết cảnh 3 phim liền báo đỏ giả. Đổi *cách nghĩ về quy trình*, không phải vá lỗi.

## D2. Gate ứng viên (chưa implement — xem file gate_candidates.md)
- **A1: Gate reveal-timing** (spoiler audit tự động dựa reveal-map) — OpenCode tự chế được, chạy ngon. Đo được. **Ứng viên số 1.**
- **A2/A3: Gate clip-reuse** — ⚠️ có thể KHÔNG cần: clip-anchoring đã vô tình chặn reuse (John Wick sau sửa = 1:1 window).
- **MỚI: Gate set-piece coverage** — đo screen-time sequence / số window phủ → cảnh báo dưới ngưỡng. Bắt đúng cái fill mù. Cần dữ liệu nhiều phim để chốt ngưỡng.
- **KHÔNG vá được:** DRIFT thật (cần vision), censor (phán đoán chủ quan).

---

# PHẦN E — QUYẾT ĐỊNH CÒN TREO

1. **Git** — bạn nói "add vô git" rồi hoãn. Ba lựa chọn: (a) git riêng cho Recap Vid, (b) gộp về 1 repo với Review vid, (c) chưa git. → Nên làm SAU khi Spider-Man xong (commit trạng thái sạch).
2. **Vá gate ở repo nào?** — Recap Vid / cả hai / gộp. CHƯA QUYẾT.
3. **Review vid giờ là gì?** — nếu linear là hướng chính thức, Review vid (thiếu hết 10 rule mới) là bản dự phòng? bản chết? dùng song song?
4. **ElevenLabs** — sẽ phá calibration 3.50 w/s, phải re-calibrate. Để CUỐI, sau khi pipeline ổn.
5. **Commercial/bản quyền** — bạn nói có người hỗ trợ riêng. Ngoài phạm vi.

---

# PHẦN F — BA CHECKPOINT NGƯỜI KHÔNG BỎ ĐƯỢC
*(kết luận xuyên suốt — nền cho mọi kế hoạch auto hóa)*

1. **Duyệt draft** — soi spoiler/hindsight mà audit chữ mù.
2. **RENDER QA (xem video)** — bắt drift, mismatch, action không hiểu được, cảnh bị nén. **Ba lần bạn xem = ba loại lỗi mới mà gate + tự-check đều sót.**
3. **Censor review** — phán đoán cảnh nào cần mờ (chưa có dữ liệu, mọi phim tới giờ = "censor: none").

**Kiến trúc auto hóa thật: máy làm → người xem → máy sửa.** Không phải "máy làm hết".
