# Kế hoạch giai đoạn 2: nhanh hơn, chính xác hơn, ít vòng sửa hơn

Soạn ngày 30/10/2026, dựa trên bốn hướng rà soát: kiến trúc pipeline (đọc code ở commit `ea67a43`), tăng tốc render và tính toán, tính năng mới của Claude, và công cụ AI mới. Các con số thời gian là **ước lượng từ code và tốc độ máy thông thường**, chưa đo trên máy của bạn. Mỗi mục đều có cách đo lại.

## Tóm tắt

Phim Tokyo Drift tốn khoảng **20 tiếng** từ đầu tới cuối. Thứ ăn thời gian nhiều nhất **không phải AI**, mà là **vòng render, vấp, sửa, render lại** (khoảng 1/3). Mỗi lần render lại, kể cả khi mọi clip đã lưu sẵn, vẫn mã hoá lại cả phim 3–4 lần, mất 30–35 phút.

Giai đoạn 2 nên làm theo thứ tự này:

1. **Sửa các lỗi vừa tìm ra trong code.** Ví dụ: bước kiểm độ to của nhạc chèn và thoại **không bao giờ chạy** trong render bình thường, đúng chỗ bạn nghe thấy vấn đề.
2. **Render chỉ mã hoá phim một lần, dùng chip Intel có sẵn.** Render lại sau khi sửa vài câu: từ 30–35 phút còn khoảng 3–5 phút.
3. **Bắt lỗi trước khi render**, để render không còn là nơi phát hiện lỗi.
4. **Chuyển bước tag hình sang API (Haiku 5.5), trả bằng tín dụng API đi kèm gói Max.** Khoảng 1–2 USD mỗi phim, xong trong chưa tới một tiếng thay vì vài tiếng.
5. **Tự khớp lời với hình bằng "dấu vân tay" hình ảnh**, mỗi shot dùng một lần. Đây là cách xử lý thẳng 87 chỗ hình không khớp lời và lỗi lặp cảnh.

Mục tiêu (ước lượng): **khoảng 20 tiếng còn 5–7 tiếng mỗi phim**, phần lớn là máy tự chạy, bạn chỉ dừng ở ba chỗ (duyệt draft, xem video, kiểm duyệt).

---

## 1. Thời gian hiện tại đi đâu (Tokyo Drift)

| Phần việc | Tỉ lệ (ước lượng) | Ghi chú |
|---|---|---|
| ~9 lần render lại | ~33% | Mỗi lần 30–75 phút, mã hoá cả phim 3–4 lần |
| Beat map + 3 vòng viết draft | ~22% | Agent viết, gate chấm, sửa |
| Tag hình (~2.600 shot) | ~20% | Subagent xem từng ảnh, vài tiếng |
| Nhận dạng giọng (2 lần) | ~9% | Lần 2 để sửa lỗi lẫn tiếng Nhật |
| Các vòng kiểm tra làm tay | ~7% | Kiểm sự thật, tone, payload |
| Tách tiếng (Demucs) | ~3,5% | |

**Bài học lớn nhất:** vòng sửa lỗi tốn nhiều hơn toàn bộ thời gian máy chạy lần đầu. Muốn nhanh, phải giảm số vòng và làm mỗi vòng rẻ đi, chứ không chỉ làm từng bước nhanh hơn.

## 2. Ba nguyên tắc cho giai đoạn 2

1. **Một việc, một chỗ trong code.** Gần như mọi lỗi khó tìm vừa qua đều cùng một dạng: hai đoạn code làm cùng một việc theo hai cách (intro với render, bước kiểm trước với bước dựng clip, cách tính độ dài câu). Hợp nhất trước rồi mới tối ưu.
2. **Kiểm trên file thật, không kiểm trên sổ sách.** Đã bắt đầu làm (probe, audio_check, dupe_check), giờ phải đảm bảo chúng **thật sự chạy**.
3. **Phát hiện lỗi càng sớm càng rẻ.** Lỗi bắt được lúc viết draft tốn vài giây. Bắt được lúc render tốn cả tiếng.

---

## Pha 0: Sửa ngay các lỗi tìm được khi đọc code (1 phiên)

Những lỗi này tìm ra bằng cách đọc code. Cần OpenCode xác nhận rồi sửa:

| Lỗi | Chỗ trong code | Hậu quả |
|---|---|---|
| Bước kiểm nhạc chèn và độ rõ của thoại **không chạy**: file cần đọc bị xoá cùng thư mục tạm ngay trước đó | `render.py:2182` so với `2442` | Gate "xanh" trong khi nhạc chèn và thoại không nghe được, đúng như bạn thấy |
| Lệnh chạy tiếp sau duyệt draft là `-From render`, **bỏ qua** bước chọn thoại gốc | `run.ps1:474` | Draft có thể ra không có thoại nhân vật nào |
| Agent viết draft vẫn dùng **giới hạn kéo chậm cũ 1,4 lần**, trong khi giờ là 1,1–1,15 | `act_payload.py:141` | Gây hàng loạt câu vượt hình lúc render |
| Hướng zoom tính theo **số thứ tự câu**, và nằm trong khoá lưu clip | `render.py:1142` | Thêm hay xoá một câu là mọi clip phía sau phải dựng lại |
| Intro và phần chính dùng **cài đặt mã hoá khác nhau** rồi ghép không mã hoá lại | `intro.py:599/624` | Có thể là nguồn gốc lỗi hình mất từ 4:15. Kiểm bằng `ffmpeg -v error -i final.mp4 -f null -` |
| Các bản sửa nhận dạng giọng (VAD, nhận diện ngôn ngữ từng đoạn) **chưa được gộp vào bước chính** | `transcribe.py:197` | Phim nói lẫn hai thứ tiếng sẽ phải chạy lại lần hai |
| Tách tiếng **cả phim** khi draft không có câu nào cần tiếng phim | `stems.py:452` | Có thể tốn ~2,7 tiếng vô ích (hai project gonegirl2014 và prisoners2013 đang ở trạng thái này) |
| Kiểm hình đứng **chạy hai lần** trên cùng một file | `motion_check.py:248`, `render.py:2674` | Phí 2–5 phút mỗi lần render |

## Pha 1: Render nhanh (2–3 phiên)

| Thay đổi | Lợi ích (ước lượng) |
|---|---|
| **Mã hoá mỗi clip một lần ở chất lượng cuối**, chỉ mã hoá riêng đoạn chuyển cảnh 0,28 giây, rồi **ghép bằng copy** (không mã hoá lại). Tiếng trộn riêng một lượt. Intro dùng **chung code** với phần chính. | Render lần đầu: 65–75 phút còn ~10–12 phút. Render lại sau khi sửa vài câu: ~3–5 phút |
| **Dùng chip Intel Quick Sync để mã hoá** (`h264_qsv`), tự dò xem có không, không có thì quay về libx264. Hiệu chỉnh mức chất lượng bằng đo VMAF so với CRF 20. | Bước mã hoá cuối: ~16 phút còn ~3–5 phút |
| ~~**Chế độ xem nháp** 540p, mã hoá nhanh, cùng mốc thời gian~~ — **ĐÃ BỎ** | **Bỏ ngày 31/10/2026.** Người xem chỉ duyệt bản render cuối, không ai xem bản nháp, nên một bản render thứ hai ở chất lượng thấp chỉ thêm chi phí và thêm một đường tính thời gian nữa phải giữ cho khớp với bản chính. Đã xoá hẳn: `DRAFT_WIDTH`/`DRAFT_HEIGHT` trong `config.py`, tier `"draft"` trong `pipeline/encoder.py`, cờ `--draft-mode` trong `tools/bench_render.py`. |
| **Dựng clip song song** (3–4 luồng), **gọi giọng đọc song song** | Lần đầu nhanh hơn 8–13 phút |
| **Khoá lưu ổn định:** khoá theo nội dung, không theo số thứ tự câu hay giờ sửa file | Sửa một câu chỉ dựng lại đúng câu đó |

**Kiểm tra trước khi tin:** chạy ba lệnh này trên máy bạn để biết ffmpeg có Quick Sync không:

```powershell
ffmpeg -hide_banner -encoders | findstr /i qsv
ffmpeg -hide_banner -f lavfi -i testsrc2=s=1920x1080:r=30:d=10 -c:v h264_qsv -preset veryslow -global_quality 20 -y qsv.mp4
ffmpeg -hide_banner -f lavfi -i testsrc2=s=1920x1080:r=30:d=10 -c:v libx264 -preset medium -crf 20 -y x264.mp4
```

Lệnh thứ hai chạy được, và nhanh hơn rõ rệt lệnh thứ ba, là có Quick Sync.

## Pha 2: Bắt lỗi trước khi render (1–2 phiên)

1. **Thêm bước "giọng đọc" ngay sau duyệt draft:** đọc bằng Warren, kiểm độ dài, tự nắn câu (`fit_narration`), tất cả **trước khi** dựng clip. Render chỉ còn là bước lắp ráp.
2. **Người viết dùng đúng ngân sách chữ** từ `preflight.budget_words()`, tức là cùng công thức với lúc render.
3. **Đưa các bước đang làm tay vào `run.ps1` và `/film`:** góc nhìn (angle), thông tin phim, tách tiếng, các vòng kiểm sự thật, tone, payload, nắn câu, nhạc intro. Hiện chúng chưa có trong quy trình nên phim sau sẽ bị quên.
4. **Một danh sách gate duy nhất** kèm mức độ (chặn hay cảnh báo), và **một lệnh chạy toàn bộ bài kiểm tra**. Hiện có 81 gate và khoảng 175 bài tự kiểm tra rải rác. Ít nhất 10 bài đang đọc chữ trong code thay vì chạy thử code. Ngoài ra có 62 chỗ "bắt lỗi rồi im lặng" trong phần draft và render, cần rà để không còn gate nào hỏng mà không báo.

## Pha 3: Dùng các tính năng mới của Claude (1–2 phiên, cần bạn quyết)

**Tín dụng API đi kèm gói Max (đã kiểm trên trang chính thức):** gói Max 5x có **100 USD/tháng**, Max 20x có **200 USD/tháng** tín dụng API. Nhận bằng cách vào claude.ai, **Settings > Billing**, mục **API credits**, rồi liên kết một tổ chức trên Claude Console. Lưu ý:

- Tín dụng **không cộng dồn**, hết tháng là mất.
- Dùng được cho Claude API, Agent SDK, Managed Agents. **Không** dùng cho Claude Code chạy bằng gói.
- Không làm thay đổi giới hạn sử dụng của gói.

**Chuyển bước tag hình sang API với Haiku 5.5, chạy theo lô (Message Batches, giảm 50% giá):**

| Ảnh mỗi shot | Haiku 5.5 (theo lô) | Sonnet 5.5 (theo lô) |
|---|---|---|
| 768×432 | ~0,57 USD/phim | ~11 USD/phim |
| 1280×720 | ~0,86 USD/phim | ~17 USD/phim |

Lợi ích: xong trong chưa tới một tiếng thay vì vài tiếng, và **không tiêu vào giới hạn gói** mà các bước viết cần. Nên chạy thử 20 shot trước để đo chi phí thật (Haiku có phần "suy nghĩ" chưa đo được). Gợi ý thêm: gửi **lưới nhiều khung hình trong một ảnh** thay vì từng ảnh, và mỗi yêu cầu chỉ 10–20 shot (vượt 100 nghìn token thì Haiku tính giá gấp 5).

**Gợi ý chia model theo việc:** tag hình dùng Haiku (shot nào không chắc thì Sonnet xem lại); beat map và các vòng kiểm dùng Sonnet; viết draft và punch-up dùng Opus.

**Tự động hoá vòng agent bằng Claude Code:**

- `claude -p ... --output-format json --json-schema ...` trả về JSON đã kiểm cấu trúc, nên script có thể **tự xử lý danh sách việc mà không phải dừng chờ**.
- Mỗi bước đóng gói thành một **Skill**, kèm luôn script gate.
- **Hooks** tự chạy gate sau mỗi lần ghi draft, thay vì trông vào việc agent nhớ chạy.
- **Dynamic workflows** chạy song song tới 16 agent, có kiểm cấu trúc đầu ra, tạm dừng khi hết hạn mức rồi chạy tiếp sau khi hạn mức được làm mới (khi chạy tương tác).

**Một vấn đề cần bạn kiểm tra (quan trọng):** theo điều khoản của Anthropic, đăng nhập bằng gói Claude chỉ dành cho Claude Code và các ứng dụng chính thức của Claude. Báo chí đưa tin OpenCode đã bỏ kiểu đăng nhập bằng gói từ tháng 3/2026 (mình chưa kiểm được từ nguồn chính thức). Có hai hướng hợp lệ:

- (a) Dùng **Claude Code** làm môi trường chính (chạy được trên Windows), vẫn bằng gói Max.
- (b) Giữ OpenCode nhưng dùng **API key** từ tổ chức Console đã liên kết, trả bằng tín dụng API. Lưu ý 100 USD/tháng có thể không đủ cho các phiên code dài bằng Opus.

Hướng (a) cho phần code và điều phối, cộng API cho bước tag hình, là cách chia gọn nhất.

## Pha 4: Chính xác hơn (2–4 phiên)

1. **Tự khớp lời với hình (ưu tiên số một về chất lượng):**
   - Mỗi shot lấy 3 khung, tính "dấu vân tay" hình ảnh **một lần** bằng model mã nguồn mở (Meta PE-Core-B/16 hoặc SigLIP 2, chạy trên CPU, ước tính 3–8 phút cho 2.600 shot).
   - AI viết lại mỗi câu kể thành mô tả hình ảnh. Máy chấm điểm theo độ giống hình, cộng vị trí thời gian trong phim, cộng thoại của shot đó.
   - Gán shot theo thứ tự, **mỗi shot dùng tối đa một lần**.
   - Dò cảnh gần giống nhau bằng mã hash ảnh (chênh từ 5 bit trở xuống coi là trùng), cộng độ giống dấu vân tay cho các shot cùng góc máy.
2. **Tách tiếng đúng loại cho phim:** Demucs được huấn luyện để tách **bài hát**, nên để lại tiếng rác. Có những model huấn luyện riêng để tách **thoại, nhạc, tiếng động** trong phim (BandIt Plus; TIGER-DnR nhỏ và nhanh, giấy phép Apache-2.0). Chỉ tách ở đoạn hành động có tiếng phim, có fade. Phải kiểm **giấy phép** từng model trước khi dùng.
3. **Nhận dạng giọng:**
   - Gộp các bản sửa VAD và nhận diện ngôn ngữ vào bước chính.
   - **Ghép các đoạn ngắn** trước khi đưa vào Whisper: hiện mỗi đoạn trung bình 1,7 giây, chỉ lấp 9% khung 30 giây của Whisper.
   - Nhận diện ngôn ngữ bằng model nhỏ, và **đưa danh sách tên nhân vật** cho Whisper (hotwords) để bớt nghe sai tên.
   - Ước tính tiết kiệm 20–30 phút mỗi phim.
4. **Dò cảnh cắt nhanh hơn:** giải mã bằng ffmpeg ở độ phân giải thấp rồi đưa vào bộ dò sẵn có: ~11 phút còn ~3–4 phút, chạy song song với Whisper. Muốn chính xác hơn (bắt được cả chuyển cảnh mờ dần) thì thử TransNetV2.

## Pha 5: Tính năng mới (sau khi các pha trên ổn định)

Theo phân tích đối thủ, xếp theo giá trị:

1. **Render xong thì AI nhìn lại hình:** lấy khung hình từ video thành phẩm, so với từng câu kể, đưa ra danh sách chỗ nghi ngờ kèm số phút để bạn xem nhanh.
2. **Cắt Shorts 9:16** từ mỗi video dài (3–5 cái), đây là cách kênh mới được tìm thấy.
3. **Tự tạo thumbnail và mô tả video**, theo công thức tiêu đề đã có.
4. **Xuất timeline sang Premiere hoặc CapCut**, để sửa tay vài phút thay vì render lại.
5. Dò khung đen hoặc nháy ở chỗ ghép, nhận diện phụ đề cứng dính trên hình (bản vietsub).

## Không nên làm

- **Phóng to bằng AI** (Real-ESRGAN): trên chip Iris Xe ước tính 4–8 tiếng cho 10 phút video, và còn tự bịa chi tiết da, vải. Giữ lanczos cộng làm nét nhẹ. Muốn hình đẹp hơn thì tìm **bản phim gốc 1080p**.
- **Đưa thẳng cả video vào Claude:** chưa có tài liệu chính thức nào nói Claude nhận video, nên vẫn dùng khung hình.

---

## Thứ tự và cách đo thành công

| Pha | Đo bằng gì | Mục tiêu (ước lượng) |
|---|---|---|
| 0 | Các gate nhạc và thoại thật sự chạy; `ffmpeg -v error` sạch | Không còn gate "xanh mà hỏng" |
| 1 | Thời gian render lần đầu và render lại | ≤12 phút và ≤5 phút |
| 2 | Số lần render phải chạy lại cho một phim | ≤2 |
| 3 | Thời gian và chi phí tag hình | <1 tiếng, <2 USD |
| 4 | Số chỗ VOICE-VISUAL; số cảnh lặp; bạn chấm khi xem | 87 → dưới 15; 0 lặp |
| 5 | Shorts và thumbnail tự ra cùng video | Có |

## Prompt cho OpenCode

Gửi **từng pha một**, mỗi pha một phiên mới. Đặt file này vào `docs/STAGE2_PLAN.md` trước.

**Pha 0:**

```
Read docs/STAGE2_PLAN.md. Do PHASE 0 only. For each item, first CONFIRM the defect with a reproduction or a measurement (some were found by reading code, not by running it), then fix it with a regression fixture. Items: audio gates reading a file deleted with the temp dir (render.py ~2182 vs ~2442); run.ps1 resume after draft review skipping the film_speaks stage (run.ps1 ~474) and film_speaks gate ordering (film_speaks.py ~637); act_payload.py word budget still on the 1.4x slowdown (use preflight.budget_words()); zoom direction keyed on line index inside the clip cache key (render.py ~1142); intro vs story encoder mismatch joined by stream copy (intro.py ~599/624, check with `ffmpeg -v error -i final.mp4 -f null -`); VAD/per-chunk-language fixes not merged into transcribe.py (~197); stems.py separating the whole film when no line uses film audio (~452); freezedetect run twice (motion_check.py ~248, render.py ~2674). Commit and push with the guard after each.
```

**Pha 1:**

```
Read docs/STAGE2_PLAN.md. Do PHASE 1. Target design: every clip encoded ONCE at final settings; only the short crossfade transitions encoded separately; everything joined by stream copy; audio mixed in its own pass; the intro built by the SAME code path and settings as the story. Add Intel Quick Sync (h264_qsv) with a runtime capability probe and libx264 fallback, calibrated against CRF 20 by VMAF on a 60s sample. Add a 540p draft mode with identical timing. Parallelize clip builds (3-4 workers) and TTS requests. Make cache keys content-based (no line index, no mtimes). Measure before/after on tokyodrift2006: first render time, re-render after editing 3 lines, and confirm every final-file check still passes. Commit and push with the guard after each step.
```

**Pha 2:**

```
Read docs/STAGE2_PLAN.md. Do PHASE 2. Add a VOICE stage after draft review (synthesize, pre-flight, fit_narration) so render only assembles. Writers get their budget from preflight.budget_words(). Add every ad-hoc stage used on tokyodrift2006 (angle, film facts, stems, fact/tone/payload audits, fit_narration, intro music) to run.ps1 and /film in the right order. Create one gate registry (name, severity, owner module) and one test runner; replace source-text regex tests with behavioural tests; audit the bare except handlers in draft/render so no gate can fail silently. Commit and push with the guard.
```

**Pha 3:** chạy sau khi bạn đã nhận tín dụng API và quyết định giữa Claude Code hay OpenCode.

```
Read docs/STAGE2_PLAN.md. Do PHASE 3. Move span tagging to the Anthropic API: Message Batches, claude-haiku-5-5, frames downscaled to ~768px, 10-20 shots per request, strict JSON output matching the existing tag schema, the cast list in a cached prompt prefix; escalate low-confidence shots to Sonnet 5.5. API key from an environment variable only. First run a 20-shot pilot and report real tokens/cost per shot, then tag one full film and compare against the existing subagent tags on a sample. Keep the subagent path as a fallback.
```

**Pha 4, 5:** sẽ soạn prompt chi tiết khi tới lượt, vì phụ thuộc kết quả đo ở các pha trước.

## Những điều chưa kiểm chứng

- Mọi con số thời gian trên máy bạn: đều là ước lượng, phải đo.
- Ngày ra mắt chính thức của các model mới (trang tin của Anthropic không truy cập được). Bảng giá và tín dụng API thì đã kiểm trên trang tài liệu chính thức.
- OpenCode của bạn đang kết nối với Claude bằng cách nào.
- Giấy phép thương mại của bản trọng số BandIt Plus. Giá Gemini lấy từ trang bên thứ ba.
- Tốc độ thật trên CPU và Iris Xe của các model mã nguồn mở (Whisper turbo, RoFormer, TransNetV2, SigLIP): chưa có số đo công bố, cần thử trên một đoạn 10 phút.

## Nguồn chính

- Claude models và giá: https://platform.claude.com/docs/en/about-claude/models/overview và https://platform.claude.com/docs/en/about-claude/pricing
- Tín dụng API cho gói Max: https://platform.claude.com/docs/en/about-claude/api-credits-for-subscribers
- Claude Code (headless, hooks, skills, workflows): https://docs.claude.com/en/docs/claude-code/overview
- Giới hạn gói Max: https://support.claude.com (bài 11014257, 11145838, 15036540)
- Ghi chú chi tiết của bốn hướng rà soát (đường dẫn file:dòng, nguồn): `pipeline_audit.md`, `speedups.md`, `claude_capabilities.md`, `open_tools.md`
