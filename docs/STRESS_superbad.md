# STRESS TEST — Superbad (2007), phim hài

*Chặng 2 của `docs/ROADMAP_automation.md`. Mục đích: tìm chỗ `RULES.md` gãy với thể loại khác.*
*Rules hiện rút từ 8 phim CÙNG một họ — chính kịch / giật gân / hành động — và nhiều rule ngầm giả định phim CÓ twist và CÓ set-piece.*

**Nguồn:** 1280×692 (không phải 1080p). Chấp nhận, vì đây là phim để ĐO, không phải để lên kênh. Hình mềm ở bản render là do nguồn, đừng ghi nhầm thành lỗi pipeline.

---

## Số liệu catalogue

| | Superbad | John Wick | Interstellar | Spider-Man | Shutter Island |
|---|---|---|---|---|---|
| shot | **181** | 92 | 101 | 69 | 31 |
| shot/beat | 3.1 | 3.07 | 2.97 | 2.65 | 1.11 |
| độ phủ phim | **77%** | 48% | 17% | 9% | 7% |
| trung vị cửa sổ | 30.0s | 28.0s | 9.0s | 24.0s | 18.0s |
| drift (lời↔hình) | ? | 0/20 | 2/18 | 1/16 | 2/20 |

Catalogue dày nhất từ trước tới nay — hơn John Wick (phim sạch tuyệt đối) một nửa nữa. Kiểm máy: id không trùng, `depicts` không sai vocab, cửa sổ không hỏng, thứ tự tăng dần, `chars` khớp `names.json` — sạch cả sáu.

---

## 1. Gate nào KHÔNG nổ lần nào

*Gate chết trong im lặng với thể loại này. ACTION-SETUP từng 0 cảnh báo trên 4 phim và hoá ra là CHẾT, không phải sạch.*

- (chờ điền sau khi chạy `draft` ở stage SCRIPT)

---

## 2. Gate nào nổ OAN

**DEPTH-REACTION — 12 lần.** Chưa kết luận được là oan hay đúng.

Lý do chưa quyết: trong phim hài, "action" thường là gag vật lý, và **phản ứng chính là cú chốt** — nên gate có thể đang đúng. Ba ca đáng soi vì là bản lề cảm xúc: B21 (Seth bị xe tông, không có shot phản ứng của Evan), B37 (cãi nhau, 4 shot không cái nào tag reaction/emotion), B51 (bị bắt).

**DEPTH-UNDER — 13 lần. Để nguyên.** Đã xem xét và ghi lý do trong `_depth_note` của `shots.json`. Chạy theo cảnh báo để làm đẹp con số là đúng cái B9 cấm.

---

## 3. Rule nào phải BỎ QUA

Không rule nào phải bỏ. Nhưng hai chỗ **đẩy sai hướng** — xem mục 6.

---

## 4. Reveal-map có RỖNG không

**KHÔNG.** Dự đoán ban đầu (phim hài không có reveal) **sai**.

- **R1 — 01:38:50**, hai viên cảnh sát thừa nhận họ biết từ đầu. Reveal cấu trúc đúng nghĩa: thông tin bị giấu có chủ ý, biết rồi thì hiểu lại toàn bộ 90 phút trước đó — cái trông như bất tài hoá ra là tử tế có tính toán.
- **R2 — 01:45:04**, lời thú nhận của Seth. Yếu hơn (là thú nhận, không phải phim lột mặt nạ), tag `discovery`.

### Khoảng trống mới trong `RULES.md`: "reveal cơ học nhưng KHÔNG cần bảo vệ"

Hai thứ là reveal về mặt cấu trúc mà giấu đi là **hiểu sai phim**:

- **Vụ McLovin (00:27:25)** — danh tính giả lộ ra, cơ học là reveal. Nhưng đó là hình quảng cáo của phim và cả act giữa giả định khán giả đã biết. Bảo vệ nó là hiểu sai.
- **Fogell bước ra khỏi xe tuần (01:17:45)** — reveal với Seth và Evan, không phải với khán giả, người đã xem tuyến cảnh sát nửa tiếng. Kể như hội tụ, không phải bất ngờ.

Hệ thống hiện **không có khái niệm này**. Nó phải tự nghĩ ra. Với mục tiêu tự động hoá, đây là thứ phải viết thành rule — không thể trông chờ mỗi lần model lại tự suy ra.

### Và một phát hiện ngược: kỷ luật hold quan trọng HƠN trong phim hài

R1 chỉ hoạt động nếu mọi cảnh cảnh sát trước đó được kể **thuần là bất tài**. Việc của recap ở đây là **không được hài sớm**, để sự chân thành ở cuối có chỗ đáp xuống. Ngược với vấn đề thường gặp, và không rule nào nói điều đó.

---

## 5. Tier có VỪA không

**Không.** 181 shot vượt band `video_essay` (110–130), và độ phủ 77% nằm ngoài toàn bộ vùng có bằng chứng.

Nhưng nghi **band mới là cái sai**: band rút từ những phim phủ 7–48%, mà ba trong bốn phim đó có drift. Đặt mục tiêu theo mẫu có lỗi thì mục tiêu thừa hưởng lỗi. Số shot không quyết định độ dài recap — số **line** mới quyết định; nhiều shot là nhiều chỗ để bind, không phải nhiều nghĩa vụ.

Lý do 181 kiểm chứng được: từ 00:48 đến 01:41 phim chạy **ba tuyến song song** và cắt qua lại, nên một beat thường chứa hai ba khoảnh khắc không dùng chung cửa sổ được.

⚠️ Chưa biết catalogue dày quá có tác dụng phụ gì không — ví dụ vòng enrich bị cám dỗ viết quá nhiều line vì có sẵn quá nhiều chỗ bind. Câu chờ trả lời ở stage SCRIPT.

---

## 6. Xem xong: NÓ CÓ BUỒN CƯỜI KHÔNG

*(chờ render)*

### Nhưng đã có câu trả lời một phần từ khâu viết draft

**Hài tình huống recap tải được gần như miễn phí. Hài ngôn ngữ thì không, và không có cách nào.**

Recap kể **cấu trúc** — kế hoạch sụp đổ, ba tai hoạ song song hội tụ — và đó chính là hài tình huống. Nhưng cái hài của Superbad phần lớn nằm ở **nhịp và cách đọc thoại**, thứ chỉ tồn tại trong khoảnh khắc nó được nói ra.

Năm beat mà "kể lại" và "cái hài" đánh nhau:

| beat | vấn đề |
|---|---|
| B12/B26 — cái tên McLovin | Gãy nặng nhất. Cả cái hài nằm ở cách Fogell nghiêm túc bảo vệ cái tên đó. Recap chỉ tả được hình dạng của cú đùa, và hình dạng thì không buồn cười |
| B31 — độc thoại mở màn | 90 giây thuần nhịp lời, **không có sự kiện nào**. Cái hài là anh ta không chịu dừng; một recap tường thuật nội dung thì đã dừng anh ta rồi |
| B29 — thoại ở bữa tiệc | Cùng kiểu: cú chốt nằm ở cách đọc từng câu, diễn giải là chết |
| B08 — hồi tưởng vẽ tranh | **Thắng.** Cú đùa có nền cốt truyện bên dưới (Seth cần được yêu quý), nên recap kể được ý nghĩa mà không giết cú đùa |
| B53/R1 | Không phải hài đánh nhau với recap, mà **tông** — xem mục 4 |

**Cách xử đúng đã rút ra:** tả tình huống, để clip tự diễn — **đừng bao giờ đưa câu đùa vào lời kể**, ở đó nó chết.

### Style guide đẩy sai hai chỗ

**(a) Công thức hook giả định có "cú sốc".** `recap_style.md` xây cho phim mà sức hút là twist hoặc cảnh hoành tráng. Sức hút của Superbad là **sự nhận ra** — người ta xem vì nhớ mình từng là mấy đứa đó, không phải vì chưa biết chuyện gì xảy ra. Hook kiểu hài ("đây là quyết định tệ nhất, giờ xem nó lan ra") không có trong từ vựng của guide.

**(b) "Phủ chuỗi nhân quả liền mạch" phục vụ quá đà một phim mà động cơ là sự lạc đề.** Guide giả định đà của phim là tính nhân quả. Nhưng cái thú của Superbad một phần là ngược lại — việc vặt bị chệch hướng bởi những thứ **không liên quan**. Nối chúng thành "dẫn tới, buộc phải" biến một phim lông bông thành phim cướp có kế hoạch. Rule đúng về **cái gì cần đưa vào**, hơi sai về **giọng nối** — vài chỗ chuyển cảnh nghe chủ đích hơn phim xứng đáng.

Cả hai đều không đủ để override guide, và đã không override. Nhưng chúng cho thấy guide đẩy về phía coi phim hài như một cỗ máy chuyển tải cốt truyện.

---

## Ghi chú kỹ thuật từ vòng draft

- 140 line, ~16.6 phút (dưới band 18–22 của `video_essay`) — đúng kỳ vọng ở stage OUTLINE
- **fill 65%, và đều nhau giữa action (66%) và dialogue (69%)** → theo A9, đây là outline mỏng trung thực, không phải hiệu ứng thể loại
- **119 line báo `unverified` trong binding audit** — A3 (anchor vào khoảnh khắc narration tả) xung khắc với cơ chế tra id chính xác của binding_audit. Giữ anchor, vì A3 đã kiểm chứng và `unverified` nghĩa là *không kiểm được*, không phải *sai* (0 mismatch). **Đáng kiểm riêng: đây có phải lần đầu binding_audit thật sự phân loại được gì không**
- 2 set-piece giữ lại đều đánh `verified: sampled` — grid overview là 1 frame/5s, không phải dense scan. Đúng B10. Cảnh báo sẽ nổ và **nên để nổ** cho tới khi ai đó quét dày 01:15:15–01:20:32 và 01:42:15–01:44:35

---

## Bug pipeline gặp trong chặng này (ghi, không sửa giữa chừng)

1. **`recap.py names` không đi theo redirect Wikipedia** — "Superbad (film)" là trang chuyển hướng. Đã sửa tại chỗ vì nó chặn. Lộ ra: lệnh này mới chạy đúng một phim trước đó
2. **Thiếu `beats_proposal.md` → im lặng rơi về `style: review` → TẮT TOÀN BỘ gate linear.** Lần thứ ba cùng một lớp lỗi (`load_shots` mất 31 shot; `known = set()` rỗng): **thiếu dữ liệu bị xử như dữ liệu rỗng, và rỗng thì luôn qua.** Chưa sửa
3. **Dòng "Next:" mà `ingest` in ra là hướng dẫn cũ** — bảo mở `transcript_for_script.txt` rồi viết thẳng `draft.json`, tức nhảy cóc bước 2→6. Cùng họ F4, nguy hiểm hơn vì nó xuất hiện đúng lúc người ta đang tìm bước kế tiếp
4. **LLM phải đoán định dạng file ba lần** (`names.json`, `beats_proposal.md`, và vị trí reveal-map). Với mục tiêu tự động hoá đây là dữ liệu quan trọng: pipeline gọi API phải có **schema máy đọc được**, không thể dựa vào model suy ra từ ví dụ
