# Gate & Rule Candidates — Recap Vid (linear pipeline)
*Cập nhật SAU Spider-Man + SAU khi làm Outline/Script split. Trạng thái đã thay đổi nhiều so với bản cũ.*

---

## ĐÃ LÀM RỒI (không còn là ứng viên)
- **Gate beat-coverage** — ĐÃ implement trong Outline/Script split. Tự tìm ra JW ending gap. Chạy mỗi draft. ✅
- **Drift-tagging (B1 cũ)** — ĐÃ viết rule (+ mở rộng nhóm intercut). Kiểm chứng: 3 Peter không lẫn. ✅
- **Outline/Script stage machine** — ĐÃ làm, zero regression. ✅

---

## NHÓM A — ĐÁNG LÀM, SẴN SÀNG (đo được, đã có bằng chứng)

### A1. Gate reveal-timing (spoiler audit tự động) ⭐ ứng viên số 1
- **Là gì:** dựa reveal-map trong beats_proposal, check tự động: không term reveal (tên villain, twist) xuất hiện trong shot/draft TRƯỚC beat landing của nó.
- **Bằng chứng:** Spider-Man — OpenCode tự chế reveal-timing audit, giữ trọn 7 reveal qua 5 act. ĐÃ THẤY CHẠY.
- **Đo được?** CÓ (term-matching theo timestamp). Rất khả thi.
- **Trạng thái:** SẴN SÀNG formalize thành gate thật (giống cách làm Outline/Script). Cần reveal-map làm input → đi cùng Wikipedia step.
- **Cách làm:** giao OpenCode thiết kế trước (như Outline/Script), duyệt, code, regression test 3 phim, ghi.

### A-NEW. Gate set-piece coverage
- **Là gì:** đo screen-time mỗi sequence action / số window phủ → cảnh báo khi dưới ngưỡng (bắt "action không theo được").
- **Bằng chứng:** Spider-Man — Statue 13.5min/5win=14%, Highway 21%, Apartment 16%, tất cả không theo được. Dưới ~25% = fail.
- **Đo được?** CÓ (screen-time / window count). Khả thi.
- **Lưu ý:** ngưỡng chính xác cần thêm dữ liệu vài phim. Nhưng "no ≥2 consecutive uncovered beats" (như beat-coverage) có thể tái dùng cho action stage.

---

## NHÓM B — RULE ĐÁNG GHI (không phải gate, chưa ghi)

### B2. Rule: bản mở rộng / special edition
- **Là gì:** với extended cut, xác định + LOẠI phần bonus không thuộc narrative TRƯỚC catalogue.
- **Bằng chứng:** Spider-Man extended intro có cả 3 Peter = lộ R4 nếu không cắt.
- **Trạng thái:** ĐỦ dữ liệu, SẴN SÀNG ghi. Chưa ghi.

### B-NEW. Bắt OpenCode khai PHƯƠNG PHÁP frame-verify
- **Là gì:** khi OpenCode báo "frame-verified" ở fast-cut sequence, bắt nó nói rõ DÀY hay MẪU trước khi tin.
- **Bằng chứng:** cú bắt MJ lệch 2 phút qua 2 vòng "frame-verified" vì cả hai đều sampling.
- **Trạng thái:** ĐÃ ghi vào lessons (bài học 2026-07-18). Có thể nâng thành rule cứng trong style guide.

---

## NHÓM C — KHÔNG VÁ ĐƯỢC BẰNG CHỮ (cần vision/mắt người)
- **DRIFT thật (bind nhầm cảnh)** — cần vision model. Chấp nhận cần RENDER QA. Rule "admit uncertainty + flag" giảm rủi ro, không diệt.
- **Censor/blur** — phán đoán chủ quan. Chưa có dữ liệu (mọi phim = "censor: none"). Chờ phim có cảnh máu.

---

## ĐÃ BỎ (không còn cần)
- ~~A2 Gate clip-reuse~~ — clip-anchoring đã tự chặn reuse (Spider-Man cũng 1:1). KHÔNG cần.
- ~~A3 VISUAL-MEMORY re-weight~~ — cùng lý do A2. KHÔNG cần.

---

## ƯU TIÊN NẾU LÀM TIẾP
1. **A1 (reveal-timing gate)** — sẵn sàng nhất, giá trị cao (spoiler = lỗi nghiêm trọng), đã có bằng chứng chạy.
2. **B2 + B-NEW** — rule, ghi nhanh, không đụng engine.
3. **A-NEW (set-piece coverage)** — cần thêm dữ liệu ngưỡng, làm sau vài phim.
