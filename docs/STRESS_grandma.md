# STRESS TEST — Gia Tài Của Ngoại (2024), phim Thái / cảm xúc

*Chặng 3 của `docs/ROADMAP_automation.md`. Gộp hai biến: **không nói tiếng Anh** và **cảm xúc làm động cơ chính**.*
*Trạng thái: **ĐÃ ĐÓNG**. Bốn bản render, đã xem cả bốn.*

**Nguồn:** 1280×690 (720p). Chấp nhận vì là phim để đo.
**Runtime:** 126.8 phút tổng, nhưng **chỉ 119.1 phút là mạch truyện** — phần còn lại là credits chữ. Mọi phép tính dùng 126.8 đều lệch 7.7 phút.

---

## Kết luận một dòng

**Recap phim cảm xúc làm được** — người xem nói *"cảm động thật"*. Nhưng chỉ sau khi đổi **đăng ký kể chuyện**, không phải sau khi chậm lại. Bảy rule mới (`RULES.md` Phần I), bốn khoảng trống từ vựng chưa implement, và ba bug kỹ thuật có trong cả tám phim trước.

---

## Bốn bản — A/B trong nội bộ một phim

Cùng catalogue, cùng shot, mỗi lần đổi một biến. Đây là dữ liệu mạnh nhất dự án từng có.

| # | bản | biến đổi | người xem |
|---|---|---|---|
| 1 | 223 line, cửa sổ 6.5s, 4 silence | — | "không xúc động lắm, nhiều chỗ bị giục" |
| 2 | 129 line, cửa sổ 45.9s, 15 silence | chậm lại | "chạm hơn một chút" |
| 3 | 129 line, viết theo quan hệ | + đăng ký kể chuyện | **"chạm hơn nhiều"** |
| 4 | + cửa sổ vừa lời + lead-in 0.5s | + hai sửa kỹ thuật | **"cảm động thật"** |

**Nhịp đóng góp ít nhất. Đăng ký kể chuyện đóng góp nhiều nhất.** Hai sửa kỹ thuật ở bước cuối là phần còn lại.

Bằng chứng phụ mạnh: ở bản 1, **bốn chỗ im lặng là bốn chỗ duy nhất người xem thấy chạm** — và đó là bốn chỗ duy nhất recap cho phép mình dừng.

---

## Số liệu catalogue

| | Gia Tài | Superbad | John Wick | Interstellar | Spider-Man | Shutter Island |
|---|---|---|---|---|---|---|
| shot | **280** | 183 | 92 | 101 | 69 | 31 |
| beat | 57 | 59 | 30 | 34 | 26 | 28 |
| độ phủ mạch truyện | 98.2% | 77% | 48% | 17% | 9% | 7% |
| cú cắt / phút | **5.6** | 16.3 | — | — | — | 14.8 |
| trung vị cửa sổ | **27.1s** | 30.0s | 28.0s | 9.0s | 24.0s | 18.0s |

**616 cú cắt trong 127 phút — một phần năm nhịp cắt của Superbad.** Phim dựng bằng cú máy giữ dài, và đó là gốc của gần như mọi thứ khác trong sổ này.

Catalogue làm trong **6 pass**, mỗi pass một phiên OpenCode. Sản lượng sụp theo context: 11 trang → 11 → 3 → 1, rồi phiên mới lại về 10 trang. **Giới hạn context được đo, không còn là lý thuyết** — một agent tương tác không catalogue nổi một phim trong một phiên.

---

## 1. Gate nào KHÔNG nổ

**`parse_beats()` trả về 0 beat suốt NĂM pass.** `catalogue.py:265` đòi dòng mở đầu bằng beat id; beat map phim này viết dạng bảng markdown bắt đầu bằng `|`. Depth gate không có gì để duyệt, **và in "Depth gates clean"**.

Nghĩa là beat-coverage, REVEAL-TIMING và mọi depth gate là no-op — **kỷ luật reveal của phim này chưa từng được máy kiểm**.

Cùng lớp với Superbad (thiếu `beats_proposal.md` → `style: review` → tắt hết gate), cơ chế khác: file **có**, parser không đọc được.

Và đáng chú ý: **cùng một agent viết beat map cho hai phim ra hai định dạng khác nhau.** Superbad ra `B01 | 00:04:12 | ...` (đọc được), phim này ra bảng markdown (không đọc được). Đó là mục 4 sổ Superbad — *LLM phải đoán định dạng file* — giờ có hậu quả cụ thể.

**Đã sửa:** parser nhận cả ba dạng, định dạng ghi vào `TAGGING_GUIDE.md`, và **mọi gate duyệt beat giờ in `NOT MEASURED` khi 0 đơn vị, không bao giờ in `clean`**.

**`DEPTH-MOTIF` — đã BỎ.** Bằng chứng:
- chạy trên **1 phim trên 10** (9 proposal thiếu dòng `MOTIF TRACKING:`)
- ở đúng phim nó chạy được, nó cũng **đo thiếu**: khai báo của Interstellar vắt qua ba dòng, regex `MULTILINE` nhưng `.` không qua xuống dòng → đọc dòng đầu, lấy 3/5 motif, **bỏ 2 cái còn lại không nói gì, rồi in pass**
- **không bắt được lỗi nó tưởng bắt được**: `pomegranate` xuất hiện trong 4 shot nên gate pass, trong khi lỗi thật là **plant thiếu, chỉ có payoff**. Nó đo *sự hiện diện*, cần đo *vị trí*
- mù với thoại (xem I4)

---

## 2. Gate nào nổ OAN

**`DRAFT-UNDERFILL`** — nổ ở 13% rồi 21%. Xem I3: fill mù với nhịp phim. Bỏ qua có chủ ý.

**`BEAT-COVERAGE`** — nổ ở 4 beat bị bỏ. Bỏ có chủ ý để giữ nhịp.

**`SNAP-GRID` — 34.8% biên lệch, gấp đôi hai phim kia. Không phải lỗi catalogue.**

Đo theo pass: 30.7% → 30.4% → 62.0% → 35.0% → 32.5% → 36.5%. Pass 3 là ngoại lệ cục bộ, không phải xu hướng cuối phim — pass 4 báo "late-film elevated ~1.8×" trên 20 biên rồi **bị pass 5 (200 biên) bác bỏ**.

Hai quan sát ngược trực giác:
- **Mật độ cắt không giải thích được biến thiên** — pass 5 có ít cắt/phút nhất mà off-cut lại thấp
- **Off-cut dồn cục chứ không rải đều** — riêng B42 (phòng bệnh trống, hành lang vắng) đóng 10 trong 65

> **Giới hạn của `SNAP-GRID`:** nó đo **khoảng cách tới cú cắt gần nhất**, nên không phân biệt được *"bỏ lỡ một cú cắt có sẵn"* với *"không có cú cắt nào để trúng"*. Báo kèm **mật độ cắt cục bộ** sẽ tách được, và gate thôi phạt phim giữ cú máy dài. *(ứng viên, chưa implement)*

**`DRAFT-TARGET` đếm silence SAI CHỖ.** Renderer đọc silence từ `draft.json`; gate đọc từ `shots.json`. Bản chậm giữ **243 giây** im lặng qua 15 line, gate đếm **0** — nó đếm 29 giây từ bốn shot tag hồi pass 1-2, hai trong bốn cái đó bản này còn không dừng ở.

Comment trong `draft.py` **nói ngược C1**. Mọi draft viết đúng theo S9/C1 có silence vô hình với gate và bị bảo thêm chữ cho runtime nó đã có. Sai số tỉ lệ với lượng silence — nên 4 silence không lộ, 15 silence thì lộ. **Chưa sửa.**

---

## 3. Rule nào phải BỎ QUA

Không rule nào phải bỏ, nhưng **A2 suýt cấm đúng cái phim này cần** — xem I1. Và **bảy rule mới** phải thêm.

---

## 4. Reveal-map có RỖNG không

**Không rỗng, nhưng gần** — đúng một reveal đáng bảo vệ, và nó không mang tính cấu trúc.

**R1 — sổ tiết kiệm.** Bà để dành tiền đứng tên M từ hồi cậu còn nhỏ, từ lúc cậu nói muốn mua cho bà căn nhà mới. Khán giả không biết, M không biết, nó rơi ở cuối, và nó viết lại toàn bộ tiền đề của phim.

⚠️ **R1 không phải cuộc gọi.** Trên màn hình là **cuốn sổ đọc được số tài khoản** và một hồi tưởng bà dắt thằng bé mặc đồng phục. Cuộc gọi chỉ là phần nối. Một line viết *"rồi ngân hàng gọi cho cậu"* **tả một thứ phim không chiếu** — vi phạm S4 ở beat quan trọng nhất của cả recap.

Mục R1 ban đầu viết từ plot summary **trước khi có footage**, và đã sửa lại theo hình.

**R2 — bà từng chăm cha mẹ mình tới lúc mất và không được hưởng gì.** Bảo vệ *vị trí*, không bảo vệ *sự thật*.

### Hai ca H1 — reveal cơ học, KHÔNG bảo vệ

- **Chẩn đoán ung thư.** Về cấu trúc là reveal sách vở: sự thật bị giấu, gia đình chủ động che, tiết lộ sau cho chính người đó. Nhưng **tên phim nói ra trước khi khán giả bấm play**, và nó là reveal với *nhân vật*, không phải với khán giả — ta được biết trước cả bà.
- **Cái chết của bà.** Cùng lý do, thẳng hơn. Phim không hỏi liệu bà có chết.

Cả hai ghi dưới **DELIBERATELY NOT PROTECTED** kèm lý do.

**Hệ quả cho H2:** sức hút không phải bất ngờ, nên hook phải nói thẳng tiền đề chứ đừng ép vào khuôn thriller.

**A8 zone split bất thường:** ~95% thời lượng là SETUP zone, kể thẳng được. REVEAL zone hẹp — sổ tiết kiệm và sau đó.

---

## 5. Tier có VỪA không

**Không, và band vô nghĩa với phim này.** 280 shot so với band `video_essay` 110–130.

Hai cách tính lệch nhau bốn lần: theo **shot/phút** ra ~219; theo **tỉ lệ shot-trên-cú-cắt** của Superbad ra ~60. Band rút từ phim có nhịp cắt gấp ba.

**Số shot trong catalogue không quyết định độ dài recap — số line mới quyết định.** Catalogue là thực đơn, không phải nghĩa vụ. `BINDING-INTEGRITY` đòi mọi line đáp xuống một shot, nên nhiều shot là **nhiều lựa chọn**.

Không xoá coverage đã verify để cho vừa một con số.

---

## 6. Xem xong: CÓ XÚC ĐỘNG KHÔNG

**Có** — ở bản thứ tư. Xem bảng bốn bản ở đầu sổ.

Và ba chi tiết từ lần xem đầu chỉ về cùng một chỗ: *không xúc động lắm* + *nhiều chỗ bị giục* + **nhưng bốn chỗ im lặng thì có chạm**. Bốn chỗ đó là bốn chỗ duy nhất recap dừng lại.

Người xem cũng **không để ý** hai câu phá `STYLE_GUIDE` §3 (nói thẳng với người xem: *"để ý đôi chân bà trong cảnh này"*). Chúng bị cuốn trôi trong nhịp chung — nên chuyện phá rule hoá ra không phải vấn đề, vì không ai kịp nhận ra.

---

## 7. Whisper dịch tiếng Thái ra sao

**Dùng được để định vị, không dùng được để hiểu.** `--translate` (`task="translate"`) cho transcript tiếng Anh, 1456 segment / 127 phút — **mật độ thoại bằng nửa Superbad** (2663 / 113).

Hallucinate: đúng **một** chỗ, lặp cùng một câu 7 lần dưới nền im lặng. Cục bộ, không phải mẫu chung — Claude đã suy rộng từ một đoạn nhìn thấy và bị OpenCode đo lại rồi đính chính.

Xem I4.

---

## 8. `recap.py names` với phim Thái

**Loại nhầm 5 nhân vật chính, gồm cả hai vai chính.** Tên Thái viết kèm biệt danh trong ngoặc kép — `Putthipong "Billkin" Assaratanakul`.

Claude chẩn đoán sai lần đầu: đổ cho giới hạn 4 từ. Mấy tên đó **chỉ ba từ**. Thủ phạm là `w.strip("'\u2019.-")` **không strip dấu ngoặc kép**, nên ký tự đầu của `"Billkin"` là dấu nháy và phép kiểm chữ hoa trượt.

*Hai lỗi khác nhau cần hai phép thử khác nhau — nới trần từ theo lời Claude thì cả năm tên vẫn bị loại.*

**Đã sửa:** strip nickname trước khi đếm, giữ làm `actor_alias`; chỉ strip nháy kép để `O'Brien` sống sót; trần lên 6 với phép kiểm mệnh đề gánh phần nặng.

### `M` — nhân vật một ký tự, và guard KHÔNG thể an toàn

Đo cả hai chiều: scanner đòi `[A-Z][a-z]{2,}` nên `M` **vô hình** — không validate, không gắn cờ. Nhưng nới ra để thấy `M` thì **mọi chữ cái viết hoa đơn lẻ đều được chấp nhận**, và gate hợp thức hoá đúng thứ nó sinh ra để bắt.

> **Mù thành thật tốt hơn mù giả.** Loại một-ký-tự khỏi guard, và `draft` giờ **cảnh báo nêu đích danh** khi `names.json` có mục như vậy.

### Phát hiện lớn hơn: `[NAME]` guard xưa nay gần như toàn nhiễu

Shutter Island 11/14 cờ là **tên thật nó lẽ ra phải biết**; Superbad 12/13. Nguyên nhân: whole-string membership nên họ đứng một mình không bao giờ khớp mục nhiều từ, và `load_names` vứt tên diễn viên đi.

**Đã sửa bằng tokenise + gộp diễn viên:** 14 → 4 và 13 → 3, phát hiện lỗi chính tả giữ nguyên 5/5, phát hiện tên bịa 5/5. Thêm loại trừ theo **lớp** (quân hàm, địa danh, tên phim đọc từ metadata) → còn 0 và 1.

Cái mất: phát hiện ghép nhầm (`Rachel Daniels` từ hai tên có thật) về 0. Gate cũ cũng chỉ bắt 1/5, chôn giữa 11 cờ nhiễu.

**B8 đã viết lại, không xoá** — quan sát gốc giữ nguyên kèm ngày, chỉ mệnh đề *"kệ lint [NAME]"* đánh dấu superseded. Điều kiện sinh ra B8 hết đúng.

---

## Bug pipeline gặp trong chặng này

1. **`parse_beats` không đọc bảng markdown** → 5 pass không gate nào chạy. **Đã sửa.**
2. **Depth gate in "clean" trên 0 beat** → mọi gate duyệt beat giờ in `NOT MEASURED`. **Đã sửa.**
3. **`DEPTH-MOTIF` chạy 1/10 phim, và đo thiếu ở phim đó.** **Đã bỏ.**
4. **`names.json` loại 5 nhân vật chính** (nickname trong ngoặc kép). **Đã sửa.**
5. **`[NAME]` guard gần như toàn nhiễu.** **Đã sửa** bằng tokenise.
6. **`DRAFT-TARGET` đếm silence từ `shots.json` thay vì `draft.json`.** **Chưa sửa.**
7. **`NARRATION_LEAD_IN` — giọng đọc vào ngay khung hình đầu.** Có trong cả 8 phim trước. **Đã sửa** (xem I7).
8. **`diag_offset.py` báo sai 22.3s** — công cụ chẩn đoán của Claude quét cả transcript không giới hạn vùng và giữ match sớm nhất; Whisper nghe khác draft đủ để một cửa sổ vắt qua khoảng lặng thắng. Render đúng, tool sai. **Chưa sửa** (cần ràng buộc locality).
9. **`skeleton` chỉ validate, không sinh** — nên `skeleton.json` và `draft.json` đều phải viết từ đầu.

---

## Lớp lỗi lặp lại — nay là MƯỜI LĂM lần

**Một thành phần mất một phần input, rồi đưa ra kết luận trên phần còn lại.**

Chặng 2 đã đếm tám. Chặng 3 thêm:

9. `censor` tra khoá chính xác vs anchor A3 → **9 line lẽ ra mờ, chỉ 1 mờ**
10. `schemas.py` thiếu `import re` → token loader ném `NameError` vào `except` trả set rỗng *(OpenCode tự bắt trước khi ship)*
11. `parse_beats` 0 beat → depth gate in "clean"
12. `DEPTH-MOTIF` chạy 1/10 phim, chưa từng pass — chưa từng chạy
13. `DEPTH-MOTIF` regex không qua xuống dòng → đo 3/5 đơn vị rồi in pass
14. `DRAFT-TARGET` đếm silence sai file
15. `diag_offset` không giới hạn vùng tìm → báo sai 22.3s

> **Rỗng thì luôn qua mọi kiểm tra.**
>
> Và câu sắc nhất của cả loạt, từ `lessons.md`: **một phép tra cứu mà nhánh miss trả về một giá trị mặc định hợp lý thì không phân biệt được với phép tra cứu thành công.** `.get(key, "none")` không nói được *"shot này sạch"* khác *"tôi không tìm thấy shot này"*.

---

## Bài học về phương pháp

**Kỷ luật catalogue theo pass đã trả công.** OpenCode dừng ở pass 3 và 4 thay vì lấp nốt bằng Wikipedia plot, với lý do đúng: *một entry suy từ plot không phân biệt được với entry đã verify*. Nếu nó lấp, catalogue sẽ trông hoàn chỉnh và sai ở nửa sau.

**`--zoom` phải chạy TRƯỚC, không phải sau.** Một người bị đọc nhầm là "bạn ăn cùng M" hoá ra là **nhân viên đứng quầy** — và **không gate nào kiểm quan hệ**: `binding_audit` so `claim.subject` với `chars`, cả hai do cùng người viết. Hiểu sai ai với ai thì hai bên khớp nhau hoàn hảo và cùng sai.

**Cờ giữ lại kèm lời giải thích, không dập.** B54 (sổ tiết kiệm) thiếu reaction shot vì phim cắt thẳng ra đường ray — phản ứng nằm trọn ở B55. Tách cửa sổ làm hai sẽ dập được cờ, nhưng *"cái tách đó tồn tại để thoả mãn gate, không phải để mô tả phim"*. Đối lập hẳn với `ACTION-SETUP` ở Superbad, nơi gate qua được bằng cách đọc danh sách cue.

**Bốn lần một kết luận bị chính người đưa ra rút lại:** Claude đổ lỗi giới hạn 4 từ (sai); Claude nói hallucination là mẫu chung (sai, một chỗ); Claude nói cửa sổ dài làm hình chạy tiếp sau khi nói xong (sai, cửa sổ không đóng góp runtime); OpenCode báo late-film off-cut cao 1.8× trên 20 biên rồi tự bác bỏ bằng 200 biên.

> Cách duy nhất phân biệt được giả thuyết đúng với giả thuyết nghe-có-lý là **cô lập thành phần ra và đo trực tiếp.**
