# Burner-probe protocol — kiểm tra claim behavior trước khi cam kết

Mục tiêu: biết chính xác hành vi Content ID của các rights-holder trong lane
mình chọn (web film iQIYI/Youku, short-drama ReelShort/DramaBox) **trước** khi
dồn ngân sách — bằng 1 kênh vứt, ~15 phút prep + 3 ngày đợi.

## Chuẩn bị (15 phút)

1. Tạo Google account mới (hoặc tài khoản dự phòng), tạo kênh YouTube, KHÔNG
   gắn branding gì. Tên kiểu "test upload 8472".
2. Chuẩn bị 4 clip, mỗi clip 30 giây, 1080p, **không nhạc gốc phủ lên** (giữ
   nguyên audio của phim trong 2 clip đầu để test cả audio fingerprint; nếu
   muốn tách riêng thì làm 5 clip):
   - **Clip A** — footage + audio từ `Qi Men Dun Jia (2020)` (web film iQIYI,
     lane P2). nguồn: bản Viki/iQIYI International.
   - **Clip B** — footage + audio từ một title DramaBox (kênh YouTube chính
     thức của DramaBox, lane P1). ví dụ *No Escape From The Mafia King's
     Embrace*.
   - **Clip C** — footage + audio từ một title ReelShort (kênh chính thức
     ReelShort). ví dụ *The Double Life of My Billionaire Husband*.
   - **Clip D (control dương)** — 30 giây từ một blockbuster Mỹ bất kỳ (Disney
     chẳng hạn). clip này **phải** dính claim — nếu không dính thì cách upload
     hoặc cấu hình có vấn đề, kết quả cả lô bỏ.
3. Upload cả 4 ở chế độ **Unlisted**, không title keyword, không tag.

## Đọc kết quả (sau 24–72 giờ)

YouTube Studio → Content → cột **Restrictions** → "Copyright claim":

| Kết quả | Nghĩa | Quyết định lane |
|---|---|---|
| Không claim | rights-holder không đăng ký reference (hoặc clip dưới ngưỡng khớp) | xanh nhất — lane phim dựng footage mở |
| Claim → **Monetize** (biểu tượng $) | video sống, họ lấy tiền | cơ bản của kế hoạch — đúng mid-case $1–2 RPM |
| Claim → **Track** | họ chỉ theo dõi | tốt như không claim |
| Claim → **Block** (video ẩn) | rights-holder chặn | lane đó chuyển hoàn toàn sang narration-forward, không footage |

Ghi mỗi kết quả vào `projects/<film>/claims.json` (schema mục 6 advisory) —
dù là kênh burner, dữ liệu vẫn là dữ liệu.

## Dọn dẹp

Xóa 4 video + kênh burner sau khi chốt. KHÔNG dispute claim nào trên burner —
kênh này sinh ra để đo, không phải để cãi.

## Kịch bản trục vẽ quyết định

- **A/B/C đều monetize/track/không claim** → GO đầy đủ cho P1 (narration) +
  P2 (footage recap). D vẫn claim-monetize thì control hoạt động tốt.
- **B hoặc C block** → P1 giữ nguyên (narration-forward vốn không cần footage
  của họ), P2 xem A thế nào mới quyết.
- **A block** → web film iQIYI cũng phải narration-forward; cân nhắc pillar
  xianxia suy giảm, tăng C-drama anchor đã probe riêng.
- **D không claim** → lỗi phương pháp, làm lại trước khi kết luận gì.
