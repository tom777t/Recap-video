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
