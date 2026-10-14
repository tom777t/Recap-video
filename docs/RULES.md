# MASTER LIST — Rules & Lessons (Recap Vid / linear pipeline)

*Nguồn: 4 phim linear — Interstellar, John Wick, Spider-Man NWH, Shutter Island.*
*(Các phim trước linear — IT 2017, Prisoners, Gone Girl, Joker — nằm trong `docs/lessons.md`.)*

**Cập nhật: 2026-08-04** — pass reconcile sau khi file được đưa vào git. Bản trước đứng ở mốc "sau vòng sửa action-coverage Spider-Man", thiếu toàn bộ phiên Shutter Island.

**Quy ước trạng thái:**
`✅ kiểm chứng` = đã thấy hoạt động đúng trên phim thật, đã hoàn thành.
`🔄 đã áp dụng` = đã sửa theo rule và ship, nhưng chưa có phim thứ hai đối chiếu.
`⏳ chờ` = chưa có bằng chứng.

**Quan hệ với các file khác:**
`docs/RULES.md` (file này) = luật + quyết định. `docs/GATE_CANDIDATES.md` = ứng viên chưa chốt, **không được áp dụng nếu chưa được bảo**. `docs/lessons.md` = nhật ký kỹ thuật chi tiết theo phiên. `prompts/style_linear_vn.md` = nơi rule Phần A thật sự được thi hành.

---

# PHẦN A — ĐÃ GHI vào `prompts/style_linear_vn.md` (đang chạy)

| # | Rule | Nguồn | Trạng thái |
|---|------|-------|-----------|
| A1 | **Act-by-act enrichment** khi draft under-target (không enrich cả phim một lần) | Interstellar | ✅ kiểm chứng |
| A2 | **Đừng nén chuỗi nhân-quả** / **đừng bịa** cái phim cố tình bỏ trống | Interstellar | ✅ kiểm chứng |
| A3 | **CLIP ANCHORING** — anchor `clip_start` vào khoảnh khắc narration mô tả, KHÔNG vào shot-start. Dịch cả window (start+end), không co. Shift >3-4s phải frame-check. | John Wick | ✅ kiểm chứng |
| A4 | **+ RULE 2 (bổ sung A3)** — fast-cut sequence: anchor vào đúng SUB-MOMENT, không vào đầu sequence | Spider-Man | 🔄 đã áp dụng (dense scan tìm ra lệch 2 phút, đã sửa + ship) |
| A5 | **DRIFT TAGGING** — tag nhân vật CỤ THỂ, không generic. Cue hierarchy: mặt lộ → đồ khi sáng → thoại đặc trưng. **Admit uncertainty + flag** khi mờ, không đoán. | John Wick + Spider-Man | ✅ kiểm chứng (3 Peter không lẫn) |
| A6 | **+ RULE 3 (bổ sung A5)** — mở rộng sang **mọi NHÓM intercut** (villain, đội, ê-kíp), không chỉ look-alike. "Even when they look different." | Spider-Man (Sandman/Electro lẫn) | 🔄 đã áp dụng |
| A7 | **PRE-CATALOGUE: đọc Wikipedia** (Plot + Cast) trước catalogue. Chỉ plot+cast, KHÔNG review/rating. **Frames win** khi mâu thuẫn. | Spider-Man | ✅ kiểm chứng (dùng lại ở Shutter Island) |
| A8 | **SPOILER DISCIPLINE** — setup-zone/reveal-zone split; biết twist ≠ được kể; đọc trước = trách nhiệm CAO hơn; nghi thì giấu. **Per-reveal beat-map** ghi vào beats_proposal, hold theo map — KHÔNG dựa vào "kể đúng thứ tự". Kể cảnh sớm bằng con mắt người xem lần đầu. | Spider-Man | ✅ kiểm chứng (trọn 5 act; Shutter Island giữ trọn 6 reveal, gate 0 hit) |
| A9 | **RULE 1 — Under-fill: TRỐNG Ở ĐÂU quan trọng hơn trống bao nhiêu.** Trống ở action = honest. Trống ở dialogue/closing = coverage gap, phải lấp. "Fill thấp vì phim action" chỉ đúng cho action shot — KHÔNG áp blanket. **⚠️ ĐÃ THU HẸP 2026-09-05 — xem A9/I2 ở cuối Phần A.** Phạm vi giờ là **action và dialogue**. Với shot mà nội dung là QUAN HỆ chứ không phải SỰ KIỆN, **I2 cầm quyền**, không phải A9. | Spider-Man (cảnh kết 3 phút bị nén còn 24s) | 🔄 đã áp dụng, đã thu hẹp |
| A10 | **+ RULE 1 correction** — "Don't pad the fights" ≠ "let the fights be unfollowable". Không tường thuật từng cú = đúng; kể STAGE của trận đánh = BẮT BUỘC. **Test: người xem lần đầu có theo được trận đánh không?** Nếu không → under-covered, bất kể fill. | Spider-Man (Statue 13.5 phút / 5 window = 14% coverage) | 🔄 đã áp dụng → sau đó được hoá thành gate SET-PIECE COVERAGE |
| A11 | ~~**TIER FOLLOWS THE FILM — cả hai chiều.**~~ **⛔ NGHỈ HƯU 2026-09-05 — xem "A11 nghỉ hưu" cuối Phần A.** Quan sát gốc vẫn đúng và vẫn đáng đọc; cái sai là **thứ nó quản lý lẽ ra không bao giờ nên là gate**. | Shutter Island | ⛔ superseded |

---

## A11 NGHỈ HƯU (2026-09-05) — rule đúng, nhưng nó quản một cái lẽ ra không phải gate

**Không xoá.** Nguyên văn A11 giữ lại ở đây vì nó ghi một quan sát THẬT:

> *Phim có thể **từ chối** lên tier: enrich trung thực rồi đo, nếu con số dừng ở đáy band thấp thì giữ tier thấp, không kéo dài để chạm band trên.*

Và lần dùng đầu tiên — **Shutter Island tụt xuống đáy `recap`, không kéo lên `fuller_recap`** — là một quyết định **đúng**. Quan sát đó vẫn nên đọc trước khi ai đó cố kéo dài một phim không chịu dài.

### Vì sao nghỉ hưu

Vấn đề không nằm ở rule. Nằm ở chỗ **tier là một cái ngưỡng, mà người phải vượt ngưỡng cũng chính là người chọn tier.**

Đó là **nước đi đỏ-sang-xanh rẻ nhất trong cả repo**: `DRAFT-UNDER-TARGET` kêu → sửa một chữ trong `beats_proposal.md` → hết kêu. Không cần viết thêm một câu nào.

Và nó **đã xảy ra thật**, 2026-09-04, trên `badgenius2017`: tụt `video_essay → fuller_recap`, kèm **ba đoạn biện minh**, mà con số nền (`68% fill`) sau đó hoá ra là **artefact của một mẫu số hỏng** — số thật là 41%. Cú tụt tier đó đã bị rút lại.

⚠️ **Điểm đáng sợ nhất:** một cú tụt tier *đúng* (Shutter Island) và một cú tụt tier *do đo sai* (Bad Genius) **nhìn giống hệt nhau** — cả hai đều đến kèm lý lẽ tự tin, viết cẩn thận, dẫn đúng rule. Không có cách nào phân biệt từ bên ngoài. Và trong vòng lặp tự động, người viết luôn đọc được luật.

A11 đứng **số 1** trong danh sách "rule nguy hiểm nếu tự động hoá" của chính bản audit 2026-09-05.

### Thay bằng gì

| bỏ | thay bằng |
|---|---|
| `DRAFT-UNDER-TARGET` (sàn runtime theo tier) | **bỏ hẳn.** `DRAFT-TARGET` vẫn in runtime real-rate — **so với không gì cả**. Thông tin, không phải phán quyết |
| `DEPTH-TOTAL` (sàn số shot theo tier) | **bỏ hẳn.** Số shot vẫn được in |
| tier là ngưỡng | tier là **nhãn mô tả**. `recap` / `fuller_recap` / `video_essay` vẫn dùng để nói "phim này thuộc loại đó" trong một từ. Không mang ngưỡng nào |
| — | **`target_minutes`**: tác giả khai độ dài mong muốn. Engine ghim vào `state.json` lần đầu; đổi về sau thì `[TARGET-LOCK]` nêu **cả hai giá trị**. Là **đầu vào**, không phải ngưỡng — không gì so runtime với nó |

### Nguyên tắc rút ra (rộng hơn A11)

> **Một ngưỡng mà người bị đo cũng là người đặt, thì không đo gì cả.** Nó đo cái nhãn.
>
> Khi gặp hình dạng đó, cách sửa không phải siết ngưỡng — mà là **biến nó thành đầu vào**, rồi kiểm rằng đầu vào ấy không bị đổi lặng lẽ.

Áp cho các trường hợp còn lại có cùng hình dạng: `reveal-map` (người viết tự khai alias), `set-pieces` (tự khai range), `claim.type: speech` (tự chọn subject + binding), `DEPTH-*` (tự viết beat map làm mẫu số). Chưa cái nào được xử lý.

---

## A9 ↔ I2 — RANH GIỚI (sửa 2026-09-05, gỡ một mâu thuẫn sống)

Trước ngày này, `A9` và `I2` đưa ra **chỉ dẫn ngược nhau trên cùng một loại shot**, và cả hai đều đang ở trạng thái 🔄:

- **A9** viết: *"Trống ở dialogue/**emotional**/closing = coverage gap, **phải lấp**."*
- **I2** viết: *"Với đoạn mà nội dung là quan hệ chứ không phải sự kiện: **ít line hơn, cửa sổ dài hơn, nhiều silence hơn**."*

Một shot `emotion` rơi vào cả hai. Người viết đọc file này hôm nay không có cách nào biết cái nào thắng.

### Ranh giới

> **A9 quản `action` và `dialogue`.** Ở đó, capacity chưa dùng trên shot dialogue/closing là **lỗ hổng phủ sóng** và phải lấp.
>
> **I2 quản shot mà nội dung là QUAN HỆ chứ không phải SỰ KIỆN** — mặt người giữ lâu, silence có chủ ý, hai người ngồi với nhau mà không có gì "xảy ra". Ở đó capacity chưa dùng là **đúng**, và lấp nó là nói đè lên chính cái shot đang có tác dụng.

### Vì sao A9 chịu thu hẹp chứ không phải I2

**Chính câu đầu của A9 chưa bao giờ là lệnh lấp đầy.** Nguyên văn: *"TRỐNG Ở ĐÂU quan trọng hơn trống bao nhiêu"* — nó là rule về **chẩn đoán**, không phải về hạn ngạch. Nó ra đời từ Spider-Man, nơi một cảnh kết ba phút bị nén còn 24 giây; hỏng ở đó là **bỏ sót sự kiện**, không phải bỏ sót lời. Đem nó áp lên một khuôn mặt giữ hai mươi giây là mở rộng quá phạm vi nó được đo — đúng meta-pattern **B5**: *rule đúng, áp quá rộng*.

`emotional` bị gỡ khỏi danh sách "phải lấp" của A9 vì lý do đó, không phải vì I2 mạnh hơn.

### Cách phân loại khi không chắc

Hỏi: **nếu bỏ shot này đi, người xem có mất một SỰ KIỆN không?**
- Có → A9. Lấp.
- Không, chỉ mất *cảm giác về việc đã ngồi lại trong khoảnh khắc đó* → I2. Để yên.

Nhãn `depicts` là gợi ý, **không phải phán quyết**: một shot `dialogue` cũng có thể là quan hệ thuần (hai người nói mà không trao đổi thông tin gì), và một shot `emotion` cũng có thể mang một sự kiện (một người vừa hiểu ra điều gì).

### Ca thật đã dùng ranh giới này

Bad Genius, vòng enrich 2026-09-05: `emotion` ở 62% fill (số đo lúc đó), còn `dialogue`/`reaction` thấp hơn. Quyết định để yên phần `emotion` và lấp `dialogue` là **đúng theo ranh giới này**.

⚠️ Nhưng lưu ý: chính lần đó cả hai con số đều **sai** vì mẫu số hỏng (xem Phần K / capacity basis). Ranh giới A9↔I2 đúng; **số liệu đem áp vào nó thì không**. Hai lỗi khác nhau, đừng gộp.

### Trạng thái

Cả hai vẫn **🔄** — cần một phim thứ hai có cả đoạn action nặng lẫn đoạn quan hệ nặng để xác nhận ranh giới cắt đúng chỗ. Cái đã đổi hôm nay là **hết mâu thuẫn**, chưa phải hết nghi ngờ.

---

# PHẦN B — BÀI HỌC (ghi chép, không phải luật)

*Chi tiết đầy đủ nằm trong `docs/lessons.md` theo ngày; đây là bản rút gọn.*

| # | Bài học | Nguồn |
|---|---------|-------|
| B1 | **Tier phải khớp độ-THOẠI của phim**, không chỉ shot-count. Action ít thoại → tier thấp. | John Wick |
| B2 | **Đừng khóa tier giữa chừng.** Enrich trung thực → đo → RỒI gắn tier. | John Wick (9.9→19 min→cắt về 15) |
| B3 | **Tier fits the film, not the film fits the tier.** Vượt band vì lý do thật (comprehension) → đổi tier lên, không cắt. | Spider-Man (→ video_essay) |
| B4 | **Tự-check là FILTER, không phải DUYỆT.** Tìm được 14/16 mismatch, nhưng sót Sandman/Electro + đánh giá nhẹ L59. Mắt người tìm ra cả hai. **RENDER QA bắt buộc.** | Spider-Man |
| B5 | **META-PATTERN: mọi lỗi đều là "rule ĐÚNG áp quá HẸP hoặc quá RỘNG."** Drift áp cho look-alike nhưng không cho nhóm; action-underfill áp cho cả draft thay vì chỉ action shot; clip-anchoring áp shot-start thay vì sub-moment; self-check tin là duyệt thay vì lọc. **Fix luôn là: nới đúng phạm vi.** | Spider-Man |
| B6 | Shift/nudge lớn (>3-4s) đáng nghi — dễ vượt scene cut thành drift. | John Wick (id22 +9s) |
| B7 | OpenCode hay **chốt pattern từ mẫu nhỏ** rồi tự tin (action-only, 6-vs-rest, 12/91 line). Ép check HẾT, không sample. | Cả 3 phim |
| B8 | **Đừng làm bẩn names.json** bằng danh từ thường/chữ đầu câu để dọn lint. *(quan sát gốc, Interstellar + John Wick — vẫn đúng: không bao giờ sửa data để dọn gate.)* **CẬP NHẬT 2026-08-19 — phần "lint `[NAME]` giả vô hại, kệ" đã HẾT HIỆU LỰC.** Lý do gate kêu bừa là lỗi thật, không phải bản chất: `known` so khớp CẢ CHUỖI, nên names.json có "Dr. John Cawley" mà narration viết "Cawley" thì bị gắn cờ. Đo trên hai phim đã xong: Shutter Island 11/14 và Superbad 12/13 cờ là **tên có thật**. Sau khi tokenise (+ gộp actor/alias, + lớp loại trừ rank/place/title): còn **0 và 1** cờ, sai chính tả tiêm vào vẫn bắt **10/10**. **Một cờ `[NAME]` giờ đáng đọc.** Cờ còn lại là danh từ thường / chức danh / địa danh / tên phim — không phải tên nhân vật. Đánh đổi đã biết: tên ghép chéo ("Rachel Daniels") không còn bắt được. | Interstellar, John Wick; đo lại trên Shutter Island + Superbad |
| B9 | **FILL LÀ CHỈ SỐ MÙ với comprehension — không bao giờ dùng làm mục tiêu.** Bằng chứng cứng: trước 9 stage-line = 62% (2821/4574), sau = 62% (2821/4574). Cùng con số, một bản climax không hiểu nổi, một bản kể được. Thêm line mở window mới (mẫu số) song song thêm chữ (tử số) → tỷ lệ đứng yên. *(là C1 cũ — đã ghi vào `lessons.md` 2026-07-18)* | Spider-Man |
| B10 | **Frame-verify bằng SAMPLING không đủ ở fast-cut sequence.** Vài frame trong window 20s bắt trúng một frame khớp rồi kết luận cả window — trong khi 20s đó cắt qua 8–12 cảnh. Cú bắt MJ lệch **2 phút** qua *hai* vòng "frame-verified". Phải dense-scan 1–2s/frame, đọc window từ đầu đến cuối. | Spider-Man |
| B11 | **Gate xanh ≠ nội dung đúng.** Reveal-timing gate đếm term, không bắt được ám chỉ. Ở Shutter Island, một câu chủ đề vô hại ("the stories people tell themselves to survive") ám chỉ chính twist mà gate không thấy — chỉ hand-audit từng line pre-reveal mới gỡ ra được. | Shutter Island |
| B12 | **Không đánh bóng metric mình đã kết luận là không đáng tin.** shots.json còn 31 shot trong khi draft có 56 line → fill hiển thị lệch. Đã quyết KHÔNG tidy-up: binding vẫn sạch (mọi line trên footage thật), và fill vốn là chỉ số phụ (xem B9). Sửa catalogue để làm đẹp một con số mù = thêm rủi ro đổi lấy không gì. | Shutter Island |
| B13 | **Render bằng PowerShell, KHÔNG để OpenCode render.** Nó timeout ở khâu mux → file hỏng, `moov atom not found`. | (pipeline) |

---

# PHẦN C — CHỜ DỮ LIỆU

| # | Ứng viên | Trạng thái |
|---|----------|-----------|
| C3 | **Quy trình mấy vòng là đủ?** xem → tự-check → sửa → xem lại. Đủ hay cần vòng 3? | ⏳ chờ |

*C1 → đã thành B9. C2 (ngưỡng coverage set-piece) → đã thành gate SET-PIECE COVERAGE, xem Phần D.*

---

# PHẦN D — Ý TƯỞNG CẤU TRÚC

## D1. Tách Stage 3a (OUTLINE) / 3b (SCRIPT) — ✅ ĐÃ LÀM

**Vấn đề gốc:** pass đầu LUÔN mỏng ở cả 3 phim (Interstellar 11.8min/54%, John Wick 9.9/23%, Spider-Man 8.5/31%). Ta cứ coi đó là lỗi và hoảng.

**Nhận ra:** pass đầu *thực chất LÀ outline* — nó dựng khung, phủ beat, bind shot, thấy toàn cảnh. Mỏng là ĐÚNG. Còn act-by-act enrich *thực chất LÀ viết script*.

**Đã implement:** `pipeline/state.py` giữ stage per-project trong `projects/<n>/state.json`, engine sở hữu, không sửa tay. `outline_ready()` trong `draft.py` tính điều kiện, promote một chiều qua `recap.py draft --promote`. DRAFT-TARGET và SET-PIECE chỉ áp ở stage SCRIPT; beat-coverage và REVEAL-TIMING luôn chạy (một lỗ hổng / một spoiler là sai kể cả trong outline).

**Kết quả:** zero regression. Tự tìm ra JW ending gap ngay lần chạy đầu. Shutter Island đi trọn outline → promote → script sạch.

## D2. Gate ứng viên
→ chuyển hết sang `docs/GATE_CANDIDATES.md`.

---

# PHẦN E — QUYẾT ĐỊNH CÒN TREO

| # | Vấn đề | Trạng thái |
|---|--------|-----------|
| E1 | **Git** — repo nào, khi nào | ✅ XONG: `github.com/tom777t/Recap-video`, remote `origin`, working tree sạch |
| E2 | **Vá gate ở repo nào** | ✅ XONG (hệ quả của E1): chỉ Recap-video |
| E3 | **Review vid giờ là gì** | ✅ XONG: `Review-video` là bản chết, deprecated. Không dùng song song, không backport |
| E4 | **ElevenLabs** — sẽ phá calibration 3.50 w/s, phải re-calibrate | ⏳ để CUỐI, sau khi pipeline ổn |
| E5 | **Commercial/bản quyền** | ngoài phạm vi (có người hỗ trợ riêng) |
| E6 | **Repo visibility** — MỚI. Repo đang Public. Nó chứa toàn bộ tiêu chuẩn biên tập (file này), tên kênh, và hướng dẫn ingest từ site lậu trong README | ⏳ CẦN QUYẾT SỚM |

---

# PHẦN F — BA CHECKPOINT NGƯỜI KHÔNG BỎ ĐƯỢC

*(kết luận xuyên suốt — nền cho mọi kế hoạch auto hóa)*

1. **Duyệt draft** — soi spoiler/hindsight mà audit chữ mù (xem B11).
2. **RENDER QA (xem video)** — bắt drift, mismatch, action không hiểu được, cảnh bị nén. **Ba lần bạn xem = ba loại lỗi mới mà gate + tự-check đều sót.**
3. **Censor review** — phán đoán cảnh nào cần mờ (chưa có dữ liệu, mọi phim tới giờ = "censor: none").

**Kiến trúc auto hóa thật: máy làm → người xem → máy sửa.** Không phải "máy làm hết".

---

# PHẦN G — ỨNG VIÊN RULE TỪ SHUTTER ISLAND

*Cả hai mới xuất hiện trên MỘT beat của MỘT phim. Rule là giả thuyết cho tới khi phim thật xác nhận. Điều kiện chốt: (1) Shutter Island render QA xong và xác nhận hai chỗ này xử đúng thật, (2) có phim thứ hai với beat tương tự để đối chiếu.*

> **Ghi chú lịch sử:** phần này từng được note trong một phiên chat nhưng KHÔNG lọt vào file, và đã mất khi file được đưa vào git. Được khôi phục ngày 2026-08-04 từ log chat gốc. Đây chính là lý do file này phải nằm trong repo.

## G1. Kể bi kịch nặng — kiềm chế *(ứng viên rule, → style guide)*

**Nguồn:** Shutter Island id38 / beat B26 — cái chết của ba đứa con.

**Cách xử đúng đã quan sát được:** nói bi kịch **một lần**, một mệnh đề trần, không chi tiết graphic, không dừng lâu — rồi **xoay ngay sang cơ chế tâm lý / hệ quả cốt truyện**. Điểm của beat là *tại sao anh dựng nhân cách Teddy*, không phải cái chết. Cảnh nặng đi kèm `blur_heavy` (imply-not-show).

**Rule đề xuất:**
> Beat bi kịch nặng (chết chóc thương tâm, trẻ em, bạo lực với người yếu thế) — kể kiềm chế: nêu một lần, không chi tiết graphic, không dừng lâu, xoay ngay sang ý nghĩa tâm lý/cốt truyện của beat. Cảnh nặng đánh imply-not-show. Bi kịch phục vụ câu chuyện, không phải để khai thác.

**Vì sao generalize được:** áp cho mọi phim (phim nào cũng có thể có beat nặng); là quyết định biên tập chứ không phụ thuộc phim cụ thể; và bền — kể cả khi model xem được video, "kể bi kịch cho phải đạo" vẫn là lựa chọn nghệ thuật, không phải cái nhìn thấy được.

**Không gate được.** Đây là hướng dẫn viết, thuộc `docs/STYLE_GUIDE.md` + `prompts/style_linear_vn.md`.

## G2. Ambiguity-hold — bảo vệ sự KHÔNG-biết *(ứng viên gate hẹp)*

**Nguồn:** Shutter Island id42-43 / reveal R6 — câu kết mơ hồ ("sống như quái vật hay chết như người tốt"). Narration trích câu rồi **dừng**, không diễn giải là tái phát hay lựa chọn tỉnh táo. Sự mơ hồ được tái tạo nguyên vẹn.

**⚠️ Cái KHÔNG được làm — và đây là phần quan trọng nhất của mục này:**

Đừng ra rule chung kiểu *"đừng diễn giải ending mơ hồ"*. Nghe hợp lý nhưng nguy hiểm, vì **máy không tự phân biệt được cái gì cố-ý-mơ-hồ với cái gì cần-làm-rõ**. Cả pipeline này dạy OpenCode làm rõ — kể mạch lạc, đừng để người xem lẫn — và điều đó đúng 95% thời gian. R6 là trường hợp ngược. Một rule chung sẽ khiến máy để mơ hồ những chỗ đáng ra phải rõ, làm recap khó hiểu. Đúng bẫy B5: rule đúng áp quá rộng.

**Cái ra được rule — một tầng cao hơn:**
> Xác định TRƯỚC (ở bước Wikipedia / reveal-map) xem phim có điểm cố-ý-mơ-hồ nào không — ending mở, câu hỏi không lời đáp, sự thật để ngỏ. Nếu có, đánh dấu như một **"reveal ngược"**: narration phải TÁI TẠO sự mơ hồ, cấm giải quyết. Giống spoiler discipline, nhưng bảo vệ sự KHÔNG-biết thay vì sự bất ngờ.

**Khác biệt then chốt:** không bắt máy tự nhận ra lúc draft (nó không làm được) — mà **người đánh dấu ở bước reveal-map, máy tuân theo cái đánh dấu**. Dumb gate + explicit human intent — đúng triết lý đã thắng ở reveal-map và set-piece.

**Hướng implement:** thêm cột/loại `ambiguity-hold` vào reveal-map trong `beats_proposal.md`, kèm range. Chi tiết gate ở `GATE_CANDIDATES.md` mục A-AMB.


# PHẦN H — RULE TỪ PHIM HÀI (Superbad 2007)

*Nối vào cuối `docs/RULES.md`, sau Phần G.*
*Nguồn: chặng 2 của `ROADMAP_automation.md`. Chi tiết đầy đủ ở `docs/STRESS_superbad.md`.*
*Cả ba đều **🔄 đã áp dụng** — dùng khi làm Superbad, chưa có phim thứ hai đối chiếu.*

---

## H1. Reveal cơ học ≠ reveal cần bảo vệ

**Nguồn:** Superbad — vụ McLovin (00:27:25) và Fogell bước khỏi xe tuần (01:17:45).

Một beat có thể là reveal **về mặt cấu trúc** — danh tính giấu kín lộ ra — mà vẫn **không được đưa vào reveal-map**. Hai trường hợp:

- **Khán giả đã biết trước khi xem.** Vụ McLovin là hình quảng cáo của phim, và cả act giữa giả định người xem đã ở trong cuộc. Bảo vệ nó là hiểu sai phim.
- **Reveal với NHÂN VẬT, không phải với khán giả.** Fogell bước ra khỏi xe tuần làm Seth và Evan sững sờ; khán giả đã theo tuyến cảnh sát nửa tiếng. Kể như **hội tụ**, không phải bất ngờ.

**Rule:**
> Ở bước reveal-map, với mỗi ứng viên hỏi thêm một câu: **khán giả chưa xem phim có biết điều này trước khi bấm play không, và họ có biết trước nhân vật không?** Nếu có ở câu nào, nó không vào reveal-map. Ghi vào `beats_proposal.md` dưới mục "DELIBERATELY NOT PROTECTED" kèm lý do, để người sửa sau không "giúp" thêm nó vào.

**Vì sao cần thành rule:** hệ thống không có khái niệm này. Phải tự nghĩ ra mỗi lần, và tự động hoá thì không trông chờ được như vậy.

---

## H2. Hook không nhất thiết là cú sốc

**Nguồn:** Superbad — `recap_style.md` đòi một "shock" mở màn.

Công thức hook hiện tại xây cho phim mà sức hút là **twist hoặc cảnh hoành tráng**. Có thể loại kéo người xem bằng thứ khác:

- **Sự nhận ra** — người ta xem Superbad vì nhớ mình từng là mấy đứa đó, không phải vì chưa biết chuyện gì xảy ra
- **Hình ảnh sai chỗ** — đưa ra một khoảnh khắc muộn trông vô lý, để khoảng trống nhân quả tự kéo *(Superbad dùng cái xe cảnh sát đang cháy)*

**Rule:**
> Trước khi viết hook, hỏi phim này kéo người xem bằng gì. Nếu không phải bất ngờ, đừng nặn một hook hình-thriller lên nó. Hook kiểu hài: **đây là quyết định tệ nhất, giờ xem nó lan ra**.

---

## H3. Hài ngôn ngữ không sống sót qua recap

**Nguồn:** Superbad — B12/B26 (cái tên McLovin), B31 (độc thoại mở màn), B29 (thoại ở bữa tiệc).

Recap kể **cấu trúc**, và hài tình huống *là* cấu trúc — kế hoạch sụp đổ, ba tai hoạ hội tụ. Cái đó tải được gần như miễn phí.

Nhưng hài **ngôn ngữ** — nhịp, cách đọc, khoảng lặng trước câu chốt — chỉ tồn tại trong khoảnh khắc nó được nói. Diễn giải là giết. Trích nguyên văn vào lời kể còn tệ hơn: cú đùa nổ hai lần, lần đầu ở giọng đọc và chết ở đó.

**Rule:**
> **Tả tình huống, để clip tự diễn.** Không bao giờ đưa câu chốt vào voiceover. Với beat mà cái hài thuần là lời, cho nó ít line và đi tiếp — đừng cố bù bằng độ dài.

**Ngoại lệ có thật:** cú đùa **có nền cốt truyện** thì recap kể được, và kể tốt. Superbad B08 (hồi tưởng vẽ tranh) là gag nhưng phim cài nó làm tính cách — để gag đáp xuống một line, rồi dùng line sau nói ý nghĩa. Đó là chỗ "kể chuyện gì xảy ra" phục vụ cú đùa thay vì làm nhụt nó.

---

## H4. Kỷ luật hold quan trọng HƠN trong phim hài *(phát hiện ngược)*

**Nguồn:** Superbad R1 — hai viên cảnh sát thừa nhận họ biết từ đầu.

Cú lật chỉ hoạt động vì **90 phút trước đó được kể thuần là bất tài**. Việc của recap ở đây là **không được hài sớm**, để sự chân thành ở cuối có chỗ đáp xuống.

Ngược với vấn đề thường gặp: A8 chống rò rỉ *thông tin*; cái này chống rò rỉ **tông**.

**Rule:**
> Khi phim hài có một beat lật sang chân thành hoặc ấm áp, mọi line trước đó về cùng chủ đề phải giữ **đúng cách khán giả đang đọc nó lúc ấy** — kể cả khi biết thừa là hiểu vậy sai. Một câu nháy mắt sớm là đủ giết cú lật.

**Kiểm chứng:** người xem xác nhận cú lật đọng lại được sau khi giữ trọn 14 line cảnh sát ở tông bất tài.


# PHẦN I — RULE TỪ PHIM CẢM XÚC / KHÔNG NÓI TIẾNG ANH
### (Gia Tài Của Ngoại — How to Make Millions Before Grandma Dies, 2024)

*Nối vào cuối `docs/RULES.md`, sau Phần H.*
*Nguồn: chặng 3 của `ROADMAP_automation.md`. Chi tiết đầy đủ ở `docs/STRESS_grandma.md`.*

**Bằng chứng: bốn bản render của cùng một phim, cùng một catalogue, tách bạch từng biến.** Đây là dữ liệu mạnh nhất mà bất kỳ Phần nào trong file này từng có.

| bản | biến đổi | người xem nói |
|---|---|---|
| 223 line, cửa sổ 6.5s | — | "không xúc động lắm, nhiều chỗ bị giục" |
| 129 line, cửa sổ 45.9s | chậm lại | "chạm hơn một chút" |
| 129 line, viết theo quan hệ | + đăng ký kể chuyện | **"chạm hơn nhiều"** |
| 129 line, cửa sổ vừa lời, lead-in 0.5s | + hai sửa kỹ thuật | **"cảm động thật"** |

**Nhịp đóng góp ít nhất. Đăng ký kể chuyện đóng góp nhiều nhất.**

---

## I1. Đăng ký kể chuyện: SỰ KIỆN vs QUAN HỆ ⭐ rule chính

**Nguồn:** cả phim. Áp cho **mọi phim**, không riêng thể loại này.

`style_linear_vn.md` được xây quanh việc kể **chuyện gì xảy ra**, và nó đúng cho tám phim cùng họ — ở đó sự kiện *là* nội dung. Nhưng nó ngầm đòi mỗi hành động phải mang **hệ quả hoặc động cơ**.

Đưa nguyên tắc đó vào một bộ phim mà hành động không có cả hai — nơi ý nghĩa nằm ở **sự tích luỹ** chứ không ở từng lần — thì nó rút gọn thành tường thuật trần trụi. Tệ hơn: nó trượt xuống **chú thích khung hình**.

### Dấu hiệu nhận biết: câu không có chủ ngữ

Bản đầu tiên của phim này viết ra những dòng như:

> *"Bốn giờ sáng. Con hẻm, đường ray, một con mèo."*
> *"Đêm. Một bãi xe, và Amah đứng một mình giữa những chiếc ô tô."*

Đó là **danh sách danh từ** — không chủ ngữ, không động từ, không ai làm gì với ai. Chúng đọc y hệt một dòng `action` trong `shots.json`, **vì chúng được viết ra từ đó**.

Đối chiếu với Superbad, nơi mỗi câu có chủ ngữ, động từ, và một mệnh đề nói *vì sao*: *"vì duyên rõ ràng không có tác dụng, cậu quyết định bỏ qua hẳn"*.

**Rule:**
> **Viết câu, không viết chú thích.** Mỗi line cần chủ ngữ và động từ. **Đừng đọc `action` text làm nguồn cho văn xuôi** — dùng nó để biết trong khung có gì, rồi viết về *cái đang xảy ra giữa những người trong đó*.
>
> Khi phim không cho nhân quả để kể, hãy kể **trạng thái giữa hai người**: ai đang gánh ai, điều gì đang được hỏi mà không nói ra, cái gì đã lặng lẽ đổi kể từ lần trước ta thấy cảnh này. Đó là thứ có thật mà shot đang chiếu, và tường thuật nó **không phải là bịa**.

### Ví dụ đo được

Cùng một shot, cùng cửa sổ, chỉ đổi văn xuôi:

| trước | sau |
|---|---|
| "Bốn giờ sáng. Con hẻm, đường ray, một con mèo." | "Bốn giờ sáng bà đã dậy được một tiếng, và giờ cậu dậy cùng bà. Họ cùng làm nồi cháo trong bóng tối — và một tháng trước, đây là người không ai gọi dậy nổi trước trưa." |
| "bà đã đoán ra" | "Bà đã biết cậu đến vì cái gì. Biết từ lâu. Và vẫn để cậu ở lại." |

Câu thứ hai của cặp dưới **kể lại cả bộ phim trong một dòng**. Câu đầu chỉ là một sự kiện.

### Quan hệ với A2, và giới hạn

A2 cấm bịa cái phim cố tình bỏ trống. Rule đó **giữ nguyên**. Nhưng ở phim loại này, khoảng trống thường *chính là* nội dung — nên:

> Đừng bịa **sự kiện**. Nhưng đừng coi một khoảnh khắc không lời là **không có gì để tường thuật**.

Ranh giới: một quan hệ đang đổi là thứ shot chiếu ra và người xem thấy được. Một sự kiện không có trên màn hình thì không.

### Nó cũng gỡ được một xung đột rule

Shot trả nghĩa của cây lựu có `chars: []` (không ai nhận diện được trong khung), nên **S5 cấm** nói "cậu đang tưới cây". Bản đầu ship *"có ai đó đang tưới nó"* — đúng sự thật, không mang gì cả.

Đăng ký quan hệ gỡ được mà không phá S5: **báo trạng thái thay vì báo tác nhân** — *"có ai đó đang đứng đó giữ cho nó sống"*.

---

## I2. Thứ sống trong THỜI GIAN thì không sống sót qua NÉN *(gộp với H3)*

**Nguồn:** phim này + Superbad H3.

Superbad: hài ngôn ngữ không sống sót vì nó nằm ở **nhịp**.
Phim này: sự day dứt không sống sót vì nó nằm ở **thời lượng**.

Cùng một gốc:

> **Recap nén 127 phút còn 20, và thời gian là thứ nó lấy đi trước tiên.** Với đoạn phim mà tác dụng nằm ở việc *được ngồi lại trong một khoảnh khắc*, độ phủ mua bằng nhịp là mua nhầm thứ.

**Bằng chứng trực tiếp:** ở bản 223 line, **bốn chỗ im lặng là bốn chỗ duy nhất người xem thấy chạm** — và chúng là bốn chỗ duy nhất recap cho phép mình dừng lại.

**Rule:**
> Với đoạn mà nội dung là quan hệ chứ không phải sự kiện: **ít line hơn, cửa sổ dài hơn, nhiều silence hơn**, và chấp nhận bỏ beat để giữ nhịp. `DRAFT-UNDERFILL` và `BEAT-COVERAGE` sẽ kêu — bỏ qua chúng **có chủ ý và ghi lại**.

**⚠️ ĐÃ LÀM RÕ PHẠM VI 2026-09-05.** Rule này **cầm quyền trên shot quan-hệ**, kể cả khi `A9` nói ngược lại — A9 đã được thu hẹp về `action` + `dialogue` cho đúng câu mở đầu của chính nó (*"trống Ở ĐÂU quan trọng hơn trống bao nhiêu"* là chẩn đoán, không phải hạn ngạch). Ranh giới đầy đủ + phép thử "bỏ shot này thì mất SỰ KIỆN hay chỉ mất thời gian ngồi lại?" nằm ở mục **A9 ↔ I2** cuối Phần A. I2 không được nới rộng: nó **không** cấp phép viết mỏng cho shot action hay shot mang sự kiện.

⚠️ Nhưng **nhịp một mình không đủ**: bản chậm với văn xuôi cũ chỉ "chạm hơn một chút". Cho một câu tường thuật hành động nhiều thời gian hơn thì nó vẫn là câu tường thuật hành động. **I1 phải đi kèm.**

---

## I3. Fill là chỉ số MÙ với nhịp phim *(mở rộng B9)*

B9 nói fill mù với comprehension. Đo trên năm phim thì nó còn mù với nhịp dựng:

| phim | độ dài shot trung bình | fill |
|---|---|---|
| Gone Girl | 5.5s | 109% |
| Interstellar | 9.7s | 71% |
| Shutter Island | 17.4s | 73% |
| Superbad | 21.7s | 27% |
| Gia Tài Của Ngoại | **27.1s** | **13%** |

`fill = từ ÷ (giây đã bind × 3.5)` là **mật độ từ trên giây phim**, nên nó tụt đơn điệu khi phim giữ cú máy lâu. Đạt 65% ở phim này cần ~14.700 từ — bảy mươi phút nói liên tục.

> **Đừng bao giờ dùng fill làm mục tiêu.** Với phim cú máy dài, con số đó không thể thoả mãn mà không nói đè lên phim.

---

## I4. Transcript dịch máy: dùng để ĐỊNH VỊ, không dùng để HIỂU

**Nguồn:** phim Thái, ingest bằng `--translate`.

Whisper dịch thẳng từ âm thanh sang tiếng Anh (`task="translate"`) cho ra transcript đọc được nhưng **kém xa chép âm rồi dịch riêng**. Có chỗ hallucinate — một đoạn lặp cùng một câu bảy lần dưới nền im lặng.

> Transcript của phim ngoại ngữ dùng để **tìm cảnh** và **biết ai đang nói**. Không dùng để suy ra chuyện gì xảy ra.
>
> Hệ quả: **PRE-CATALOGUE (A7) nặng ký hơn hẳn** — Wikipedia Plot thành nguồn chính chứ không phải bản đồ hỗ trợ. A7 vẫn đúng ("frame thắng khi mâu thuẫn"), nhưng thêm một vế: **transcript thua cả hai**.

### Và audit plant bằng grep chỉ tìm được plant BẰNG HÌNH

Pass 5 kết luận motif "bán nhà" không có plant nào, sau khi grep toàn bộ `action` text. **Sai.** Plant nằm ở 01:14:10 trong **thoại** — người mua tới cổng hỏi thăm.

> Một plant audit chỉ quét `action` sẽ trả về **âm tính giả với sự tự tin tuyệt đối** cho mọi thứ phim gieo bằng lời. Grep cả transcript.

---

## I5. Bốn khoảng trống của từ vựng catalogue *(ghi lại, CHƯA implement)*

Phát hiện lúc catalogue, xác nhận lúc viết draft. **Không thêm tag** — n=1, theo đúng tiền lệ G-AXIS.

**(a) Không có nhãn cho "chăm sóc như việc thường ngày".** Động cơ của phim là chuỗi phục vụ lặp lại — đút ăn, tắm rửa, ngồi canh đêm. Không phải `action` (định nghĩa đòi hệ quả, không có), không phải `dialogue` (thường không lời), không phải `emotion` (định nghĩa là *không có hành động*, mà ở đây luôn có ai đó đang làm gì), không phải `montage` (rời rạc, không nén). Chỉ còn `setup` — mà nhãn đó khẳng định **thứ thật sự vẫn đang tới**. Nó không bao giờ tới, vì nó đã xảy ra bốn mươi lần trong im lặng.

**(b) Không có chỗ ghi một shot mang HAI NGHĨA cùng lúc.** M đút cho bà ăn vừa là chăm sóc thật vừa là nước cờ giành thừa kế. `claim.type` là số ít, `depicts` ép chọn một nghĩa trội. Rule "một clip = một khoảnh khắc chính" đúng cho **các giai đoạn nối tiếp**; đây là **một khoảnh khắc với hai nghĩa đồng thời** — thứ khác hẳn.

*(a) và (b) thực ra là một: **một hành động bình thường mà toàn bộ sức nặng nằm ở nghĩa thứ hai của nó.***

**(c) Không có liên kết trả nghĩa — và trường `pays_off` khai xuôi KHÔNG dùng được.** Đôi dép ở 00:31:55 là một cutaway phụ, không gì trong khung/transcript/plot đánh dấu nó; payoff cách 32 phút. **Plant vô hình tại thời điểm gieo.**

> Một liên kết giữa hai khoảnh khắc phải được khai **từ đầu nào đọc được**, và cấu trúc gieo-trả chỉ đọc được **từ phía trả**.

⚠️ **Rủi ro kèm theo, chưa có cách chặn:** `MAX_REUSE` có thể âm thầm tiêu hết plant trước khi payoff được catalogue. Draft viết theo act tiêu hợp lệ cả hai lượt của shot gieo trong Act 1, vì tiệm giày chưa tồn tại. Mọi gate xanh — reuse cap thấy số hợp lệ, `DEPTH-MOTIF` quét chữ mà "dép" không có trong entry nào, binding audit cho cả hai qua. **Chỉ mất cái vần, và không gì đọc vần.**

**(d) `aftermath` nói về SỰ KIỆN, không nói về SỰ VẮNG MẶT.** Trạng thái phim kết thúc là *một người không còn ở đó nữa*. Và nó có hệ quả kỹ thuật: `aftermath` **không có `ClaimType` tương ứng**, nên những line đó mang `requires_visual: false` và **binding audit bỏ qua** — 30 line miễn kiểm, 12 nằm trong 25 phút cuối, tức đúng đoạn mọi thứ dồn về.

---

## I6. Cửa sổ dài hơn lời quá nhiều thì phim chạy quá nhanh để đọc

**Nguồn:** bản 129 line, trước khi trim.

`render.py` đặt `clip_len = max(narr_dur + GAP, hold)` — **cửa sổ không đóng góp vào runtime**. Một cửa sổ 136 giây với 10 giây lời không làm clip dài ra; nó **nhồi 136 giây phim vào 9.4 giây, chạy ở 14.5×**, lao qua 23 cú cắt.

Người xem thấy đó là drift. Nó không phải bind sai.

> Cửa sổ của một line không nên dài quá **khoảng hai lần** thời lượng đọc của nó. Snap `clip_end` vào cú cắt thật khi có; không thì cắt thẳng tới mốc.
>
> Silence beat giữ nguyên toàn bộ hold — việc dừng lại chính là mục đích.

**Ứng viên gate:** `BINDING-SLOWDOWN` bắt **lời dài hơn shot**. Không gì bắt chiều ngược lại — **shot chạy nhanh hơn tốc độ đọc được**. Dữ liệu đã có sẵn (`clip_len` vs độ dài cửa sổ, `_cuts.json` cho số cú cắt bị nhồi). Chưa implement.

⚠️ **Trim tạo ra lỗi ngược:** 50 line merge sau khi trim kết thúc **trước** shot mà mệnh đề cuối của chúng đang tả — một vi phạm S4 do chính việc trim sinh ra. Sửa bằng cách cắt lời cho khớp cửa sổ, hoặc nới cửa sổ khi mệnh đề cuối *chính là* beat.

---

## I7. `NARRATION_LEAD_IN` — nửa giây, và nó đổi cả bộ phim

**Nguồn:** người xem báo *"cảm giác cả video narration đi trước scene"*. Không phải drift, không phải desync — đo lại thì lệch timeline chỉ 0.15s và `verify` sạch 114/114.

Nguyên nhân nằm trong code: `clip_len = max(narr_dur + GAP, hold)` đặt `GAP` ở **cuối**, và comment trong `render.py` nói thẳng *"narration starts at clip start"*.

> **Mọi clip đều bắt đầu bằng giọng đọc, ngay khung hình đầu tiên.** Mắt chưa kịp nhận ra cảnh mới thì tai đã bị bảo cảnh đó là gì.

Có trong **cả tám phim trước**. Không ai để ý vì phim cắt nhanh thì mắt đọc hình kịp. Với phim giữ cú máy lâu, hiệu ứng cộng dồn qua 114 line.

**Sửa:** `config.NARRATION_LEAD_IN`, mặc định 0.5s. Dải hiệu chỉnh **theo thể loại**: 0.3–0.5 cho phim cắt nhanh, **0.6–1.0 cho phim giữ cú máy dài**.

⚠️ **Lead phải CO LẠI cho vừa, không được phá binding.** Bản đầu cộng lead phẳng vào mọi line đẩy Interstellar 0 → 8 vi phạm, Parasite 0 → 12, Gone Girl 49 → 52 — ba phim đang render được sẽ dừng hẳn. Lead-in là tính năng dễ chịu; binding contract là tính đúng đắn. Lead co xuống tới 0 chứ không bao giờ phá render.

⚠️ **Silence clip KHÔNG nhận lead-in.** Nó không có narration để trễ; thêm vào sẽ **âm thầm kéo dài mọi silence beat quá mức draft yêu cầu**.

---

## Ghi chú về mẫu dữ liệu

Phần này rút từ **một phim**, nhưng I1, I2, I6 và I7 đều có bằng chứng A/B trong nội bộ phim đó — bốn bản, cùng catalogue, mỗi lần đổi một biến. I3 có năm điểm dữ liệu chéo phim.

I5 là **n=1 và chưa implement gì**, đúng tiền lệ G-AXIS.

**Điều kiện dừng chưa đạt:** Superbad thêm bốn rule, phim này thêm bảy. Mốc vẫn là **hai phim liên tiếp chạy qua mà không phải thêm rule nào**.


# PHẦN J — RULE TỪ PHIM CÓ CỐT TRUYỆN NẰM TRONG THOẠI
### (Bad Genius / ฉลาดเกมส์โกง, 2017 — chính kịch heist, tiếng Thái)

*Nguồn: chặng 4 của `ROADMAP_automation.md`. Chi tiết ở `docs/STRESS_badgenius.md`.*
*Bốn pass catalogue KHÔNG tìm ra rule nào. Rule này lộ ra ở **pass viết draft đầu tiên**, đúng chỗ Superbad lộ H3 và Gia Tài lộ I1.*
*Trạng thái: **🔄 đã áp dụng** — đã implement và có test âm, chưa có phim thứ hai đối chiếu.*

---

## J1. Bằng chứng bằng LỜI là một loại claim riêng ⭐ rule chính

**Nguồn:** Bad Genius R1 (01:10:40, Pat khai đã trả tiền cho vụ đánh) và lời chối của Bank (01:50:38).

### Vấn đề

`S4` / `C4` viết: *"mọi claim của narration phải mô tả cái footage CHO THẤY"*. `G4` viết: *"ở cao trào, narration phải nhỏ tiếng lại và để hình gánh"*.

**Cả hai đều ngầm giả định bằng chứng nằm ở HÌNH.**

Với phim mà nút thắt được **nói ra**, giả định đó sai. R1 của phim này không có một frame nào chứa nội dung của nó — catalogue đã ghi rõ điều đó trong shot note của B48. Khi viết draft, ba lựa chọn đều hỏng:

| lựa chọn | hỏng ở đâu |
|---|---|
| bỏ hẳn reveal | mất nút thắt trung tâm — đúng lỗ hổng H-REVEAL, và **mọi gate vẫn xanh** |
| bind vào shot Pat đang nói *trước* mốc đáp | phá **A8** (spoiler discipline) |
| khẳng định đè lên shot phản ứng | phá **S4** — footage chỉ cho thấy một căn phòng đứng hình |

Bản outline đầu tiên chọn cách thứ ba và tự khai. Đó là rule đầu tiên bị phá sau bốn pass.

### Rule

> **Một claim mà bằng chứng là LỜI NÓI là một loại claim riêng, không phải claim hình.** Khai bằng `claim.type: "speech"` kèm `claim.subject` là người nói.
>
> **Dạng chặt, và chỉ dạng chặt:** người nói phải **đang nói và nhìn thấy được TRONG CHÍNH shot được bind**.
>
> **Dạng lỏng — người nói được xác lập bởi line liền trước — đã bị BÁC BỎ.** Nó cho claim trôi một shot khỏi bằng chứng của nó, và một chuỗi line như vậy đi xa tuỳ ý khỏi bất kỳ ai đang có mặt. Đã có test âm cho đúng ca này.

### Gate phải nói ra giới hạn của chính nó (D-GREEN)

`binding_audit` coi `speech` là **kiểm được, nhưng kiểm thứ khác**:

- kiểm `claim.subject` có nằm trong `chars` của shot không → `SPEAKER_ABSENT`;
- kiểm subject có được nêu tên và có trong `names.json` không → `SPEAKER_UNNAMED`;
- **KHÔNG** kiểm `depicts` (`speech` không phải giá trị depicts; shot tương ứng thường tag `dialogue`);
- **KHÔNG** kiểm nội dung — không gate nào trong pipeline đọc thoại ở tầng nghĩa (I4).

Đếm riêng thành `speaker_verified`, **không gộp vào `verified_match`**, và báo cáo luôn in kèm:

    Speaker verified:    3 speech line(s) - speaker present in the bound shot
    LIMIT: a `speech` claim is checked for SPEAKER PRESENCE ONLY. Nothing here
    confirms WHAT was said - no gate in this pipeline reads dialogue. These
    lines need the Stage-7 watch.

Gộp vào `verified_match` sẽ để một con số nghĩa là *"hình cho thấy điều này"* nuốt mất những dòng mà hình **không** cho thấy. Đó đúng là D-GREEN.

### Phát hiện quan trọng nhất: THIẾU TỪ VỰNG GÂY CHẨN ĐOÁN SAI

Session trước kết luận R1 buộc phải phá S4, và lời chối của Bank là **không thể viết được**.

**Cả hai kết luận đều sai**, và chỉ lộ ra sau khi có khái niệm `speech`:

| | tưởng là | thật ra là |
|---|---|---|
| R1 | phải phá S4 | **lỗ hổng catalogue.** Pat nhìn thấy rõ đang nói ở **01:10:48–01:10:53** và **01:10:58–01:11:07**, cả hai **SAU** mốc đáp 01:10:40. Chưa từng được catalogue vì cửa sổ intercut bị tag sai. |
| lời chối của Bank | không quay, mất luôn | **lỗ hổng catalogue.** Bank nhìn thấy rõ đang khai ở **01:50:38–01:50:51** (trang 093). B72 không có shot nào ở đó. |

> **Không có tên cho một loại bằng chứng thì sẽ không đi tìm nó.** Bốn pass catalogue đọc frame để tìm *hành động*; không pass nào hỏi "ai đang nói ở đây". Cái thiếu không phải footage — là **từ vựng**.

Kèm theo, cùng lúc phát hiện một lỗi tag thật: hai cửa sổ B48 (`01:10:54`, `01:11:20`) được tag như thể mỗi cửa sổ một nhân vật, trong khi đó là đoạn **intercut nhanh** giữa Pat và xưởng in. Đúng **A6** ("mở rộng sang mọi NHÓM intercut"). Đã cắt lại thành các cửa sổ một-nhân-vật.

### Quan hệ với H-REVEAL-B

`GATE_CANDIDATES.md` mục **H-REVEAL-B** nói: reveal do thoại mang thì **không kiểm được**. J1 nói: nó cũng **không viết được** nếu không phá S4. Cùng một lỗ hổng, hai đầu — và `claim.type: "speech"` vá cả hai:

- phía **viết**: cho phép nêu điều được nói mà không phải giả vờ là hình cho thấy;
- phía **kiểm**: cho gate khẳng định người nói có mặt, và **tự khai** là không kiểm được nội dung.

Cột `carried: image | dialogue` đề xuất ở H-REVEAL-B vẫn nên làm: nó cho reveal-map biết reveal nào **cần** một line `speech`.

### Giới hạn còn lại (chưa vá)

`speech` chứng minh **ai đang nói**, không chứng minh **họ nói gì**. Với phim ngoại ngữ, nội dung vẫn đến từ A7 (Wikipedia Plot) và transcript — mà I4 đã nói transcript không dùng để suy ra chuyện gì xảy ra. **Chốt chặn vẫn là người duyệt draft và Stage-7 render QA.** Gate là sàn, không phải trần.

---

## Ghi chú về mẫu dữ liệu (Phần J)

n=1. Nhưng lỗ hổng là **cấu trúc, không phải đặc thù phim**: bất kỳ phim nào có nút thắt nằm trong lời thoại đều gặp — và với phim không nói tiếng Anh thì đó là phần lớn nội dung. Test âm 4/4 (sai người nói, thiếu subject, người nói không có trong names.json, và đúng dạng-lỏng-đã-bác-bỏ).

**Điều kiện dừng vẫn chưa đạt.** Superbad +4, Gia Tài +7, Bad Genius +1. Chuỗi "hai phim liên tiếp không thêm rule nào" **chưa bắt đầu**.
