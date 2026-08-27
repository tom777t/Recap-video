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
| A9 | **RULE 1 — Under-fill: TRỐNG Ở ĐÂU quan trọng hơn trống bao nhiêu.** Trống ở action = honest. Trống ở dialogue/emotional/closing = coverage gap, phải lấp. "Fill thấp vì phim action" chỉ đúng cho action shot — KHÔNG áp blanket. | Spider-Man (cảnh kết 3 phút bị nén còn 24s) | 🔄 đã áp dụng |
| A10 | **+ RULE 1 correction** — "Don't pad the fights" ≠ "let the fights be unfollowable". Không tường thuật từng cú = đúng; kể STAGE của trận đánh = BẮT BUỘC. **Test: người xem lần đầu có theo được trận đánh không?** Nếu không → under-covered, bất kể fill. | Spider-Man (Statue 13.5 phút / 5 window = 14% coverage) | 🔄 đã áp dụng → sau đó được hoá thành gate SET-PIECE COVERAGE |
| A11 | **TIER FOLLOWS THE FILM — cả hai chiều.** Không chỉ "vượt band thì lên tier". Phim có thể *từ chối* lên tier: enrich trung thực rồi đo, nếu con số dừng ở đáy band thấp thì giữ tier thấp, không kéo dài để chạm band trên. | Shutter Island (9.2 phút, dừng ở đáy `recap`, không lên `fuller_recap`) | 🔄 đã áp dụng |

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
