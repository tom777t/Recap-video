# STRESS TEST — Superbad (2007), phim hài

*Chặng 2 của `docs/ROADMAP_automation.md`. Mục đích: tìm chỗ `RULES.md` gãy với thể loại khác.*
*Rules hiện rút từ 8 phim CÙNG một họ — chính kịch / giật gân / hành động — và nhiều rule ngầm giả định phim CÓ twist và CÓ set-piece.*
*Trạng thái: **ĐÃ ĐÓNG**. Đã render, đã xem.*

**Nguồn:** 1280×692 (không phải 1080p). Chấp nhận, vì đây là phim để ĐO. Hình mềm ở bản render là do nguồn.

---

## Kết luận một dòng

Recap phim hài **làm được** — người xem thấy cuốn, hiểu hết, có buồn cười. Nhưng nó chỉ tải được **hài tình huống**; hài ngôn ngữ thì không, và không có cách nào. Ba chỗ `RULES.md` cần bổ sung, không chỗ nào phải bỏ.

---

## Số liệu catalogue

| | Superbad | John Wick | Interstellar | Spider-Man | Shutter Island |
|---|---|---|---|---|---|
| shot | **183** | 92 | 101 | 69 | 31 |
| shot/beat | 3.1 | 3.07 | 2.97 | 2.65 | 1.11 |
| độ phủ phim | **77%** | 48% | 17% | 9% | 7% |
| trung vị cửa sổ | 30.0s | 28.0s | 9.0s | 24.0s | 18.0s |
| drift (lời↔hình) | **0** | 0/20 | 2/18 | 1/16 | 2/20 |

Catalogue dày nhất từ trước tới nay. Kiểm máy sạch cả sáu: id không trùng, `depicts` đúng vocab, cửa sổ không hỏng, thứ tự tăng dần, `chars` khớp `names.json`.

**Phim đầu tiên `binding_audit` thật sự chạy** — 133 verified, 0 mismatch. Bốn phim trước claim = 0% nên nó chưa từng kiểm gì.
⚠️ Nhưng OpenCode viết cả tag lẫn claim, nên đây là máy kiểm tính nhất quán của chính nó. Đúng B4 — bắt được lỗi cẩu thả, không bắt được hiểu sai có hệ thống.

---

## 1. Gate nào KHÔNG nổ lần nào

**`ACTION-SETUP` từ 10 → 0 sau vòng SCRIPT — nhưng bằng cách đáng ngờ.**

OpenCode khai thẳng: *"I read `_SETUP_CUES` in the source so the cues match what the gate actually scans."* Nó **đọc danh sách cue rồi viết cho khớp**.

Đây là gate đã mất **bốn vòng** hiệu chỉnh, kết luận cuối: *setup là NGHĨA, không phải chuỗi ký tự*. Giờ nó qua bằng chuỗi ký tự.

> **Bài học cấu trúc, không phải chuyện thể loại: gate dựa trên khớp chữ sẽ bị tối ưu ngược khi người viết đọc được luật.** Với mục tiêu tự động hoá — nơi LLM vừa viết vừa đọc được repo — đây là vấn đề thiết kế, không phải sự cố một lần.

Người xem xác nhận mười beat đó hiểu được, nên lần này không hại. Nhưng `ACTION-SETUP: 0` **không còn là bằng chứng** về chất lượng.

---

## 2. Gate nào nổ OAN

**`DEPTH-REACTION` — 12 lần, chưa kết luận.** Trong phim hài, "action" thường là gag vật lý và **phản ứng chính là cú chốt**, nên gate có thể đang đúng. Ba ca đáng soi: B21, B37, B51.

**`DEPTH-UNDER` — 13 lần. Để nguyên**, đã ghi lý do trong `_depth_note`. Chạy theo cảnh báo để làm đẹp con số là đúng cái B9 cấm.

**`DRAFT-UNDERFILL` báo sai.** Draft 3743 từ mà fill tính `356/1362`, và dòng `Most room to enrich: ?` có dấu `?` chỗ đáng ra là tên act. **Đừng tin chỉ số này khi viết.**

**`[CAPACITY-WORDS]` và `[BINDING-VIOLATION]` mâu thuẫn nhau** — một cái nói mọi line thoải mái trong trần từ, cái kia nói line 27 tràn. Một cái đếm từ theo hiệu chỉnh, một cái đo thời lượng TTS thật. Họ D4 trong `GATE_CANDIDATES.md`.

---

## 3. Rule nào phải BỎ QUA

Không rule nào phải bỏ. Nhưng **ba chỗ thiếu** — xem `RULES.md` Phần H.

---

## 4. Reveal-map có RỖNG không

**KHÔNG.** Dự đoán ban đầu (phim hài không có reveal) **sai**.

- **R1 — 01:38:50**, hai viên cảnh sát thừa nhận họ biết từ đầu. Reveal cấu trúc đúng nghĩa: 90 phút trông như bất tài hoá ra là tử tế có tính toán.
- **R2 — 01:45:04**, lời thú nhận của Seth. Yếu hơn, tag `discovery`.

**Người xem xác nhận: cú lật đọng lại được.** Kỷ luật hold hoạt động.

### Phát hiện ngược: hold quan trọng HƠN trong phim hài

R1 chỉ hoạt động vì mọi cảnh cảnh sát trước đó được kể **thuần là bất tài**. Việc của recap ở đây là **không được hài sớm**, để sự chân thành ở cuối có chỗ đáp. Ngược với vấn đề thường gặp.

### Khoảng trống: "reveal cơ học nhưng KHÔNG cần bảo vệ"

Vụ McLovin (00:27:25) là reveal về cấu trúc nhưng là **hình quảng cáo của phim**; cả act giữa giả định khán giả đã biết. Fogell bước khỏi xe tuần (01:17:45) là reveal với nhân vật, không phải với khán giả.

Hệ thống **không có khái niệm này** — OpenCode phải tự nghĩ ra. → thành rule **H1**.

---

## 5. Tier có VỪA không

**Không.** 183 shot vượt band `video_essay` (110–130), độ phủ 77% ngoài mọi vùng có bằng chứng.

Nghi **band mới là cái sai**: nó rút từ những phim phủ 7–48%, mà ba trong bốn phim đó có drift. Số shot không quyết định độ dài recap — số **line** mới quyết định.

Lý do 183 kiểm chứng được: từ 00:48 đến 01:41 phim chạy **ba tuyến song song** và cắt qua lại.

Kết quả cuối: 143 line, real-rate **18.6 phút**, trong band 18–22.

---

## 6. Xem xong: NÓ CÓ BUỒN CƯỜI KHÔNG

**Có.** Người xem: *"rất hay và cuốn luôn, hiểu hết"*, cú lật hiểu được, có buồn cười.

### Nhưng giới hạn thì thật, và không sửa được bằng rule

**Hài tình huống recap tải được gần như miễn phí. Hài ngôn ngữ thì không.**

Recap kể **cấu trúc** — kế hoạch sụp đổ, ba tai hoạ hội tụ — và đó chính là hài tình huống. Cái hài của Superbad phần lớn nằm ở **nhịp và cách đọc thoại**, thứ chỉ tồn tại trong khoảnh khắc nó được nói.

| beat | vấn đề |
|---|---|
| B12/B26 — cái tên McLovin | Gãy nặng nhất. Recap chỉ tả được hình dạng cú đùa, và hình dạng thì không buồn cười |
| B31 — độc thoại mở màn | 90 giây thuần nhịp lời, **không có sự kiện nào**. Cái hài là anh ta không dừng; recap tường thuật nội dung thì đã dừng anh ta |
| B29 — thoại ở bữa tiệc | Cú chốt nằm ở cách đọc từng câu |
| B08 — hồi tưởng vẽ tranh | **Thắng.** Cú đùa có nền cốt truyện, recap kể được ý nghĩa mà không giết nó |
| B53/R1 | Không phải hài đánh nhau với recap, mà **tông** — xem mục 4 |

→ thành rule **H3**.

### Nhạc

`MUSIC_VOLUME` 0.18 → **0.15**, `SILENCE_MUSIC_VOLUME` 0.35 → 0.30. Người xem thấy vừa.

⚠️ **Nhạc có lời hát là sai.** Hai giọng cạnh tranh dưới voiceover; người xem mệt hơn mà không biết vì sao. Voiceover cần nhạc **instrumental**.

---

## Bug pipeline gặp trong chặng này

*Không cái nào thuộc về thể loại.*

1. **`recap.py names` không đi theo redirect Wikipedia** — "Superbad (film)" là trang chuyển hướng. **Đã sửa.** Lộ ra: lệnh này mới chạy đúng một phim trước đó.
2. **Thiếu `beats_proposal.md` → im lặng rơi về `style: review` → TẮT TOÀN BỘ gate linear.** Chưa sửa. *(Có phòng thủ một phần: `_stage_machine` chỉ chạy khi audit trả về dict, nên audit chết không dẫn tới promote nhầm.)*
3. **Dòng "Next:" của `ingest` là hướng dẫn cũ** — bảo nhảy thẳng từ transcript sang `draft.json`, bỏ qua bước 2→6. Chưa sửa.
4. **LLM phải đoán định dạng file ba lần** (`names.json`, `beats_proposal.md`, vị trí reveal-map). Với mục tiêu tự động hoá: pipeline gọi API phải có **schema máy đọc được**.
5. **`load_shots` vứt mất `clip_start`/`clip_end`** — `Shot` có `time_start`/`time_end` nhưng `_drop_unknown` vứt tên khác đi. **Đã sửa.**
6. **Rule A3 xung khắc `binding_audit`** — A3 bảo anchor vào khoảnh khắc, audit tra khoá chính xác theo `clip_start`. Tuân A3 đúng thì audit báo "không kiểm được" (119/140 line), và `no_unverified` chặn promote. **Đã sửa** bằng tra theo khoảng.
7. **`aftermath` là `DepictsType`, không phải `ClaimType`** — hai từ vựng không hoán đổi được. Claim sai giết cả Phase-1 audit.

### 8. A/V DESYNC — có trong CẢ NĂM PHIM đã ship

Nghiêm trọng nhất, và chỉ lộ ra ở chặng này.

Audio narration trôi **muộn dần** so với hình, ~12ms mỗi line: 0.7s trên Shutter Island (58 line), **1.7s** trên Superbad (144 line).

Nguyên nhân: video `xfade` dùng **offset tuyệt đối**; audio `acrossfade` **không có offset**, nối theo độ dài giải mã — và AAC priming làm mỗi clip giải ra dài hơn container khai.

**Đã sửa** bằng `atrim` ghim mỗi input vào đúng độ dài mà cursor đã giả định. Đo sau: **+0.000s** ở line cuối, trên cả hai phim.

Vô hình suốt một năm vì nó **tăng theo số line** và tai người khoan dung với desync nhỏ. Cần đồng thời một phim đủ dài **và** một công cụ đo lời-vs-tiếng (`verify`, mới có).

### 9. `RENDER-CHECK` là hằng đẳng thức — không bao giờ nổ được

Gate này viết ra để bắt lớp lỗi *"render tạo ra thứ khác draft"*. Cả hai vế của phép so 5% đều rút gọn về `sum(clip durations) - XFADE*(n-1)`. Không vế nào quan sát file đã render. **Nó không thể nổ, với bất kỳ bug nào.**

Và kể cả sửa để so với file thật cũng vẫn trượt ca này: tổng đúng trong khi bên trong trôi 1.7s, phần dư bị hấp thụ ở đuôi. **Phép đo thời lượng là sai công cụ cho lớp lỗi này.**

**Đã thay** bằng cross-correlate audio narration với `final.mp4` ở ba vị trí, kiểm **vị trí** thay vì thời lượng.

### 10. `verify` không xác định giữa các lần chạy

Global ASR pass chấm khác nhau qua các lần chạy — Superbad line 26 lúc 0.628, lúc trên ngưỡng. Không phải bug, là bản chất ASR. Nghĩa là **`verify` sạch một lần không đảm bảo lần sau cũng sạch**.

---

## Lớp lỗi lặp lại — TÁM lần trong tuần này

**Một thành phần mất một phần input, rồi đưa ra kết luận trên phần còn lại.**

1. `load_shots` — một tag sai → mất sạch 31 shot → mọi audit in "clean"
2. `known = set()` rỗng → mọi từ viết hoa bị gắn cờ là tên bịa
3. Thiếu `beats_proposal.md` → tắt toàn bộ gate linear
4. Claim sai vocab → chết Phase-1 audit
5. `RENDER-CHECK` — hằng đẳng thức, không bao giờ nổ *(Claude viết)*
6. `_text_in_window` slack 0.25s — cửa sổ hút câu hàng xóm *(Claude viết)*
7. `MIN_AUDIO_COVERAGE` bất khả thi với line ngắn — **một false negative che một false positive** *(OpenCode viết)*
8. Escalation dán lại nhãn MISMATCH → UNMEASURED — **nói gate ra khỏi phát hiện của chính nó** *(OpenCode viết, tìm ra bằng harness ép nhánh chạy)*

> **Rỗng thì luôn qua mọi kiểm tra.** Mọi chỗ đọc dữ liệu đều bọc `try/except` rồi đi tiếp với tập rỗng.

### Và bài về cách chẩn đoán

Cả tuần, cách duy nhất phân biệt được giả thuyết đúng với giả thuyết nghe-có-lý là **cô lập thành phần ra và đo trực tiếp**, không suy từ điểm số.

Claude suy từ điểm số rồi kết luận sai ít nhất năm lần: bộ đề vision, script chấm `(khong ro)`, cửa sổ verify, silence line, và cơ chế frame-quantisation của desync. Lần cuối còn tính ra **bậc độ lớn khớp** (2.4s dự đoán so với 1.7s đo được) và vẫn sai.

> **Bậc độ lớn khớp không phải bằng chứng** — nó chỉ nói giả thuyết chưa bị loại.

Thứ bác bỏ nó là một phép đo cô lập: 8 clip tổng hợp 5.000s chạy qua đúng `_xfade_chain`. OpenCode nghĩ ra, Claude thì không.
