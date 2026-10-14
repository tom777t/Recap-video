# Xac thuc cho `tools/gemini_vision_eval.py`

Ghi ngay 2026-09-05.

---

# DOC CAI NAY TRUOC: API CHUA BAO GIO CAN THIET CHO KHAU TAG

Ca ngay 2026-09-05 dung de san key Gemini. Ket luan cuoi cung: **van de that
khong phai la thieu API, ma la CONTEXT DECAY** — va cai do co san cach giai
tren chinh may nay, mien phi, tu dau.

**Van de that:** cac pass catalogue kem dan khi context day. Pass 1 doc 11 trang
montage, pass 4 doc 1 trang. Thu mot API mang lai khong phai la "model tot hon"
ma la **moi shot la mot loi goi doc lap, quen sach 249 shot truoc do**.

**Cai da co san:** cong cu `Task` sinh subagent voi **context hoan toan moi**.
Subagent doc frame cua rieng no, tag shot cua rieng no, ghi ra file cua rieng no.
**Frame khong bao gio di vao context cua orchestrator.**

## Do duoc (2026-09-05)

| phep do | ket qua |
|---|---|
| 3 subagent song song | 41.8s |
| 6 subagent song song | **36.2s** (nhanh hon 3 — wall time bi chan boi subagent cham nhat, khong phai boi so luong) |
| 9 va 11 song song | chay het, khong loi |
| **20 shot, cham theo phieu** | **VISIBLE-AXIS 13/17 = 76%** (baseline agent 50%), **CHARS precision 28/38 = 74%** (baseline 77%) |
| du bao 250 shot @10-wide | ~25 lo x ~40s ≈ **17 phut** |

## Cai API VAN mua duoc — va vi sao no khong quan trong o day

1. **Context orchestrator khong tang chut nao.** Voi subagent, *toi* van phai
   phat ra tung prompt. Da giam xuong ~30 token/shot bang cach de lenh trong
   `tools/tag_prompt.md` -> 250 shot ≈ 10K token. Chiu duoc.
2. **Concurrency vuot qua ~10.**

**Ca hai deu khong bi cham o muc 250 shot/phim.** Nen: **API la TIEN LOI, khong
phai CAN THIET.**

---

## Chay that 231 shot (badgenius2017, 2026-09-06)

| do | ket qua | trang thai |
|---|---|---|
| that bai | **0/231** | do duoc |
| context orchestrator | **~14K token** (231 prompt x ~55 + 231 reply x ~8) | do duoc |
| frame di vao context cua toi | **0** | do duoc |
| so LUOT (turn) cua orchestrator | **9** | dem duoc |
| thoi gian TINH TOAN cua subagent | **~8-10 phut** (6 song song = 36s, 9 song song = ~40s, x9 lo) | do duoc |
| **thoi gian dong ho khi co nguoi van hanh** | **CHUA DO DUOC** | — |

Thiet ke file-based giu dung loi hua: khong frame nao vao context orchestrator,
noi dung tung shot ra dia chu khong ve toi. 14K token cho 231 shot, dung nhu du
bao ~10K. **Van de context da duoc giai ma khong can API.**

## ⛔ DA RUT LAI: lap luan "nut co chai la LUOT ORCHESTRATOR"

Ban dau muc nay ghi **11h 33m** dong ho va quy toan bo cho chi phi giua cac
luot, roi ket luan API la **can thiet** cho thong luong va **lat nguoc** ket
luan hom truoc.

**Sai. Rut lai toan bo.**

`11h 33m` la khoang cach giua hai dau doc dong ho, va **may da TAT trong mot
phan khoang do (qua dem)**. Con so ay do **thoi gian troi qua**, khong do
**chi phi luot**. Bien so gay nhieu ro rang nhat — may co bat hay khong — khong
he duoc kiem soat, va toi khong hoi.

> Mot khoang thoi gian chua thoi gian ngung hoat dong **khong phai** mot phep do
> do tre. Toi co the hoi "may co bat suot khong?" truoc khi viet ket luan. Toi
> khong hoi, vi con so da hop voi cau chuyen toi dang dinh ke.

### Ket luan KHOI PHUC

> **API la TIEN LOI, khong phai CAN THIET.**

Lap luan thong luong chong lai cau nay **da bi rut**, vi bang chung dung de dung
no la mot phep do khong kiem soat bien. Dieu do **khong** chung minh dieu nguoc
lai — chi phi luot co the that su dang ke — nhung **hien gio chua ai do no.**

### Neu muon con so chi phi luot THAT

Phai **do co chu y**, khong duoc suy ra tu mot khoang co downtime:

- may **bat lien tuc** suot phep do, xac nhan truoc khi bat dau;
- mot lo nho (vi du 3 lo x 10 shot) de tong thoi gian nam gon trong mot phien;
- ghi dau thoi gian **ngay truoc va ngay sau** moi lo, khong lay hai dau mut;
- tru phan tinh toan subagent da do rieng, phan con lai moi la chi phi luot.

### Cung hinh dang voi loi hom truoc

Giong het vu **lay mau MOT frame** de ket luan tag bia (xem `lessons.md`
2026-09-05): mot con so **trong giong mot phep do**, lay tu du lieu **khong
kiem soat bien hien nhien**, va no da di xa den muc lat nguoc mot ket luan
truoc khi co ai kiem lai.

Khac biet duy nhat: lan truoc bien khong kiem soat la *"cua so gom nhieu frame
va co cat canh"*; lan nay la *"khoang thoi gian co chua luc may tat"*. Ca hai
deu la cau hoi le ra phai hoi **truoc** khi viet ket luan.

> Duoi mot buoi di san key — free tier, Vertex, ADC, gcloud, billing, prepay —
> de giai mot van de ma **cau tra loi mien phi da nam san tren may tu dau**.
> Dieu dang ghi khong phai "da phi mot buoi", ma la: **cau hoi "lam sao co API"
> da thay the cau hoi "van de that la gi"**, va khong ai kiem lai viec thay the
> do cho den tan cuoi.

Cung ho hang voi bon "phep do co hinh dang cua phep do" o duoi: mot cau hoi co
hinh dang cua cau hoi dung.

## Han muc su dung: KHONG do, co chu y

Khong tham do gioi han. Ly do du: **no xuong cap muot** — dinh gioi han giua
chung chi mat MOT LO, khong mat ca lan chay, vi moi shot da doc lap va da ghi
ra dia. Suy ra gioi han tu viec "chua thay loi" chinh la sai lam da lap 4 lan
trong ngay; khong lap lan thu 5.

---

# PHAT HIEN CHINH: free tier BI LOAI khoi khau tag — truoc khi ban ve chat luong

```
GenerateRequestsPerDayPerProjectPerModel-FreeTier   limit = 20 / NGAY / model
```

| project | so shot | so NGAY o muc 20/ngay |
|---|---|---|
| howtomakemillions2024 | 280 | **14.0** |
| badgenius2017 | 231 | **11.6** |
| superbad2007 | 183 | 9.2 |
| **toan bo catalogue** | **1442** | **72.1** |

**Tag mot phim mat 10-14 ngay.** Khong co nguong chat luong nao cuu duoc con so
do. Cau hoi *"model free co du tot cho khau tag khong"* **da co dap an: KHONG**,
va dap an den tu **thong luong**, khong phai tu do chinh xac.

### Dieu dang ghi nhat ve cach phat hien nay

**No den BAT CHAP cau hoi chat luong, khong phai TU cau hoi do.** Ca buoi lam
viec nham vao mot con so (diem visible-axis). Con so do van chua do duoc. Thu
thuc su ket luan duoc van de lai xuat hien nhu mot **chuong ngai** tren duong
di - `429` o shot11 - va chi tro thanh phat hien khi dung lai doc ky
`quotaId` thay vi coi no la loi tam thoi can thu lai.

> Neu coi `429` la "loi ha tang, thu lai sau" - phan xa binh thuong - thi ca
> phat hien nay bien mat, va ta se ket thuc buoi lam voi mot diem so cham cho
> mot phuong an von da bi loai vi ly do khac han.

**Cau hoi chat luong KHONG mat gia - no doi nghia.** Truoc: *"free tier co dung
duoc khong?"*. Sau: *"mot lenh goi Gemini TRA TIEN co dang chon hon mot lenh goi
Anthropic khong?"*. Do la cau hoi khac, va van dang do.

---

# TIER TRA TIEN CUNG BI CHAN — Gemini khong dung duoc o CA HAI muc

Da lam het duong B bang dong lenh (khong can hoi them):

| buoc | ket qua |
|---|---|
| cai gcloud 585.0.0 (zip 98MB, khong admin) | OK |
| dang nhap (1 lan trinh duyet) | OK — `trantridung08082009@gmail.com` |
| project `recap-vid-508719` | **billing DA BAT san**, gan voi `[billing-id da xoa]` (GBP) |
| key cu (`AQ.`) nam o dau? | **KHONG nam trong project nay** — `api-keys list` tra ve 0 items. Day chinh la ly do no chay o free tier |
| bat `apikeys` + `generativelanguage` + `cloudbilling` | OK |
| tao key moi (`AIza`, gioi han dung `generativelanguage`) **trong project co billing** | OK |
| budget alert | **DA TAO**: `recap-vid-alert`, **4 GBP** (~$5), nguong 50/90/100% |
| goi thu bang key moi | **429** |

Nhung thong bao loi **DA DOI**, va do la thong tin:

```
Your prepayment credits are depleted.
Please go to AI Studio at https://ai.studio/projects to manage your project and billing.
```

**Khong con la han muc free tier nua.** Gemini API chay tren mo hinh **tra truoc
(prepay)**, va project nay co 0 credit. Nap credit **chi lam duoc qua AI Studio**.

> ⚠️ **Credit trial £221 cua Google Cloud KHONG dung duoc cho Gemini API.** Day
> la hai he thong thanh toan tach roi. Bat billing tren project **khong** mo
> khoa Gemini API — no chi doi thong bao loi tu "het han muc free" sang "het
> credit tra truoc".

## Ket luan: Gemini bi chan o ca hai tier, vi hai ly do khac nhau

| tier | trang thai | ly do |
|---|---|---|
| free | **loai** | 20 req/ngay/model -> 10-14 ngay cho mot phim |
| tra tien | **chan** | can nap credit qua **AI Studio**, ma AI Studio bao *"Failed to list projects: permission denied"* (da thu 3 lan) |

Dung dung **dieu kien dung** da dat tu dau: *"Neu B dung lai o thu can quyen ma
toi khong co, hay bao cao va dung, dung di vong."* Day dung la ca do —
va **khong di vong**.

**Duong con lai: Anthropic.** Phan rieng cua Google trong script chi la ~6 dong
quanh `genai.Client`.

---

## Ket luan cuoi ve xac thuc (2026-09-05)

Key `AQ.` (Google Cloud API key) **DUOC** endpoint Developer API chap nhan.
Khong can gcloud, khong can ADC, khong can Vertex, khong can dang nhap trinh
duyet. Du doan truoc do cua toi ("AQ. chac chan bi tu choi") **SAI**.

Sau khi co key, thu chan duong khong phai xac thuc ma la **TEN MODEL**:
`gemini-2.5-flash` da bi khoa voi project moi. Doi sang `gemini-3.6-flash` la
chay. Da doi default trong script.

## Ba lan cung MOT kieu loi do luong, trong cung mot buoi

| # | "phep do" | no noi gi | su that |
|---|---|---|---|
| 1 | tien to 4 ky tu + do dai | key `AIzaXXXX...X` hop le | placeholder. Chi **so ky tu khac nhau** (5/39) moi phan biet duoc |
| 2 | `models.list` + `GET /models/gemini-2.5-flash` -> **200**, co `generateContent` | model dung duoc | goi that -> **404 no longer available to new users** |
| 3 | `401` tu Vertex | "API key khong dung duoc" | chi dung cho **Vertex**. Khong noi gi ve Developer API - va Developer API chap nhan key do |

| 4 | SDK nem exception khi thu key cu -> ket luan "key da bi thu hoi" | key cu da chet | exception that su la `Cannot send a request, as the client has been closed` - **loi noi bo SDK, khong phai tu choi xac thuc**. Phai goi HTTP THO + **doi chung** (cung request, key moi 200 / key cu 401) moi ket luan duoc |

> Ca bon deu la **phep do co hinh dang cua phep do**. Ca bon deu chi bi lat bang
> mot **positive test** - goi that mot lan. Dung hinh dang cua ket luan ma
> `VISUAL-REPEAT`, `RATCHET`, va guard placeholder deu day ve: *"khong bao gio
> bao loi" va "khong the bao loi" nhin tu ngoai la giong nhau*.

### Dinh chinh: check tien to KHONG phai do thua

Truoc do toi da noi check tien to 4 ky tu la "trang tri", vi no khong phan biet
duoc placeholder. **Sai** - hay chinh xac hon: dung ve mot ca, sai ve ca khac.

Ngay sau do, key duoc luu thanh `<AQ.Ab...>` (nguoi dung dan ca dau ngoac nhon
tu mau lenh `setx GEMINI_API_KEY "<new key>"` cua toi - loi cua toi khi viet
huong dan). Gia tri do co 36 ky tu khac nhau nen **check so ky tu khac nhau cho
qua**; chinh **check tien to** (`'<AQ.'` khong phai `AIza`/`AQ.`) da chan no.

> **Bai hoc khong phai "check tien to vo dung".** Moi check bat DUNG MOT thu,
> va viec can biet la *cai nao bat cai gi*:
> - **so ky tu khac nhau** -> bat PLACEHOLDER (`AIzaXXX...X`)
> - **tien to** -> bat HONG DO DAN/COPY (`<AQ...>`, khoang trang, dau ngoac kep)
> - **goi that** -> bat moi thu con lai (model da khai tu, quota, key bi xoa)
>
> Bo bat ky cai nao trong ba cung de lot mot lop loi rieng. Gop chung lai thanh
> "check key" roi tuong la da kiem xong moi la thu nguy hiem.

## Guard that bai: coi GHI HANG LOAT la mot hanh dong nguyen khoi

*(muc rieng - day la loi thiet ke cua toi, khong phai cua Google)*

Trinh tu day du:

| ban | quy tac | chuyen gi xay ra |
|---|---|---|
| goc | API loi -> ghi chuoi rong de len dap an | **xoa** dap an co san cua shot01-03 |
| sua lan 1 | co **bat ky** shot nao loi -> **khong ghi gi ca** | chan duoc lan 404 (3/3 loi). Nhung lan chay 20 shot **thanh cong 19**, shot11 dinh 429 -> **vut sach 19 ket qua tot**. Lan chay lai **dot het quota free-tier con lai** |
| sua lan 2 | ghi shot **thanh cong**, khong dong den shot **that bai** | 28 -> 28, khong mat gi, shot tot van duoc luu |

> **Ban sua gay thiet hai LON HON con bug no duoc them vao de chan.**
> Bug goc lam mat 3 dap an (khoi phuc duoc tu git). Ban guard lam mat 19 ket qua
> vua tinh xong **cong voi** han muc ca ngay - tuc la mat luon kha nang chay lai
> trong ngay.

**Loi goc re:** coi `ghi phieu` la **MOT** hanh dong, trong khi no la **20 hanh
dong doc lap**. Mot khi da gop lai thanh mot, chi con hai lua chon deu sai -
ghi tat (mat du lieu cu) hoac khong ghi gi (mat du lieu moi). Dung/sai chi xuat
hien tro lai khi tach nho ra dung muc ma that bai xay ra: **tung shot**.

Dang hinh chung voi `B5` (rule dung, pham vi qua rong) va voi chinh
`if style == "linear":` - mot dieu kien dat o **muc qua cao** so voi thu no dang
noi ve.

## Gioi han THUC TE cua free tier (do duoc 2026-09-05)

```
GenerateRequestsPerDayPerProjectPerModel-FreeTier   limit = 20 / NGAY / model
```

Phieu eval can dung **20 shot**. Nghia la **mot lan chay tron ven dot sach dung
het han muc ca ngay**, khong con du cho mot lan thu lai nao, va moi loi goi
probe (kiem key, doi chung) deu an vao cung cai han muc do.

Quan trong hon cho cau hoi goc *"model free co du tot cho khau tag khong"*:

| project | so shot | so NGAY o muc 20/ngay |
|---|---|---|
| howtomakemillions2024 | 280 | **14.0** |
| badgenius2017 | 231 | **11.6** |
| superbad2007 | 183 | 9.2 |
| **toan bo catalogue** | **1442** | **72.1** |

> Ke ca khi chat luong dat, **thong luong da loai free tier khoi viec tag that**.
> Tag mot phim la 10-14 ngay. Cau hoi chat luong van dang gia de tra loi (de
> biet co nen bat billing hay khong), nhung no khong con la cau hoi *"co dung
> free tier duoc khong"* - cau do da co dap an, va la **khong**.

## An toan phieu

Ban dau: ghi de dap an bang chuoi rong khi API loi -> **mat du lieu**.

Sua lan 1 (all-or-nothing): co shot nao loi thi **khong ghi gi ca**. Chan duoc
lan 404 that bai 3/3. Nhung ngay sau do no lai gay hai theo huong nguoc lai:
lan chay 20 shot **thanh cong 19**, shot11 dinh 429, va guard **vut het 19 ket
qua tot**. Lan chay lai dot sach quota free-tier con lai.

> **All-or-nothing sai o CA HAI dau.** Ban goc mat du lieu cu; ban guard mat ket
> qua moi + mat quota. Ca hai deu la cung mot loi thiet ke: coi "ghi" la mot
> hanh dong nguyen khoi, trong khi no la 20 hanh dong doc lap.

Sua lan 2 (dang dung): **ghi nhung shot THANH CONG, khong dong den shot that
bai**. Khong bao gio ghi chuoi rong de len dap an co san. `--force` de ghi de
that su. Da kiem: 28 -> 28, khong mat gi, va shot thanh cong van duoc ghi.

⚠️ **Key da bi dan vao lich su hoi thoai** - nen xoay (rotate) sau khi xong.

---

## Nguyen nhan that su cua loi "400 API key not valid"

`GEMINI_API_KEY` **chua mot placeholder, khong phai key**:

```
gia tri : AIza...[da xoa]
do dai  : 39   (dung do dai cua key AIza that)
ky tu khac nhau : 5      ('A','I','z','a','X')
so chu 'X'      : 35 / 39
pham vi         : ca Process lan User scope
```

Vi no dung do dai va dung tien to `AIza`, no **trong nhu that**, va Google tra
ve dung cau `API key not valid` - nghe nhu loi phia Google. Tu do chuoi chan
doan di nham sang project, billing, Vertex, ADC. **Khong cai nao trong so do
hong ca.**

> Bai hoc, cung dang hinh voi cac gate khac trong repo nay: *mot input khong hop
> le phai bi goi ten ngay tai nguon*. Neu de no truot xuong tang duoi, no se hien
> ra thanh mot thong bao loi cua HE THONG KHAC, va nguoi doc se di sua nham he
> thong. Da them guard o `gemini_vision_eval.py` (truoc moi loi goi mang).

## Nhung gi DA duoc chung minh la chay tot

Chay thu voi mot key **dung hinh dang nhung gia**:

```
1 shot | model gemini-2.5-flash | ~14 req/phut
  shot01: LOI - 400 INVALID_ARGUMENT ... 'API key not valid'
```

Nghia la: doc `VISION_EVAL.md`, cat `shots`, nap frame tu `vision_eval/`, dung
prompt, khoi tao `genai.Client`, gui request, nhan va in loi, dem thoi gian,
throttle - **toan bo duong ong deu chay**. Thieu duy nhat mot credential that.

## Tinh trang may (da kiem, khong phai suy doan)

| muc | ket qua |
|---|---|
| mang toi `generativelanguage.googleapis.com` | **OK** (403 = toi duoc, tu choi auth) |
| `gcloud` | **chua cai** |
| thu muc credential gcloud / ADC | **khong co** o bat ky dau |
| file JSON service-account | **khong co** o bat ky dau |
| key `AQ.Ab...` da tao | **khong con o dau tren may** (khong co trong env, .env, history, hay file nao) |
| quyen admin | **khong** (nhung khong can - xem duoi) |
| `google-genai` | **2.23.0, da cai** |

---

## Cac duong con lai

### A. Dan lai key `AQ.Ab...` da co  — *re nhat, thu truoc tien*

Khong cai gi, khong trinh duyet, mot lenh:

```powershell
$env:GEMINI_API_KEY = "AQ.Ab...."           # gia tri that
python tools\gemini_vision_eval.py shutterisland2010_linear --limit 3
```

Neu muon luu lau dai: `setx GEMINI_API_KEY "AQ.Ab...."` roi mo shell moi.

**Luu y:** chua chac key kieu `AQ.` duoc `generativelanguage` chap nhan - no la
key Google Cloud kieu moi. Nhung thu mat 5 giay, va guard moi se khong chan no.
Neu tra ve `API_KEY_SERVICE_BLOCKED` thi chi can bat service (xem B4).

### B. gcloud CLI — **tao key bang dong lenh, bo qua AI Studio hoan toan**

Day la diem quan trong: **AI Studio khong phai duong duy nhat de lay key.**
`gcloud services api-keys create` tao key tu terminal. Cai dang bi chan
(AI Studio "Failed to list projects") **khong nam tren duong nay**.

```powershell
# B1. tai va giai nen - KHONG can admin, KHONG can installer
$z="$env:TEMP\gcloud.zip"
Invoke-WebRequest "https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-windows-x86_64-bundled-python.zip" -OutFile $z -UseBasicParsing
Expand-Archive $z "$env:LOCALAPPDATA\gcloud-sdk" -Force      # 98 MB

# B2. dang nhap  <-- BUOC DUY NHAT CAN TRINH DUYET
& "$env:LOCALAPPDATA\gcloud-sdk\google-cloud-sdk\bin\gcloud.cmd" auth login --no-launch-browser

# B3. chon project
& ...\gcloud.cmd config set project recap-vid-508719

# B4. bat API  (Developer API - KHONG can billing, co free tier)
& ...\gcloud.cmd services enable generativelanguage.googleapis.com

# B5. tao key tu CLI
& ...\gcloud.cmd services api-keys create --display-name="recap-vision-eval" `
      --api-target=service=generativelanguage.googleapis.com
```

`keyString` in ra o buoc B5 chinh la thu can dat vao `GEMINI_API_KEY`.

### C. Vertex AI + ADC

```powershell
& ...\gcloud.cmd services enable aiplatform.googleapis.com
& ...\gcloud.cmd auth application-default login --no-launch-browser
$env:GOOGLE_GENAI_USE_VERTEXAI="true"; $env:GOOGLE_CLOUD_PROJECT="recap-vid-508719"
$env:GOOGLE_CLOUD_LOCATION="us-central1"
```

Va sua `genai.Client(api_key=key)` thanh `genai.Client()` (ADC tu dong).

**Vertex CAN billing bat** (trial £221 phu duoc). Developer API o duong B thi
khong can - nen **B don gian hon C**, va C khong cho them gi cho viec nay.

### D. Doi sang Anthropic

Phan rieng cua Google trong script chi la ~6 dong quanh `genai.Client`. Doi
sang `anthropic` (vision, base64 image) la thay duy nhat ham goi. Neu duong
A va B deu tac, day la duong chac chan nhat.

---

## Su that khong the di vong

**Moi credential Google deu can it nhat MOT lan dang nhap qua trinh duyet**,
tru khi da co san file JSON service-account - va tren may nay **khong co**.

- `gcloud auth login --no-launch-browser` van phai dan URL vao trinh duyet.
- Tao service account cung phai qua console hoac qua gcloud (ma gcloud lai can
  dang nhap truoc) - vong luan quan.

Tuc la: **khong co duong nao 100% command-line de co credential Google dau tien.**
Diem khac biet dang ke la lan dang nhap do **khong phai AI Studio** - no la man
hinh OAuth thong thuong cua Google, va gan nhu chac chan khong bi chan nhu
AI Studio da bi.
