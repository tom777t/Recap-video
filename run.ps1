<#
.SYNOPSIS
    Chay pipeline recap tu nguon phim toi final.mp4, dung lai o moi checkpoint nguoi.

.DESCRIPTION
    Script nay KHONG thay LLM. No dieu phoi phan MAY lam va dung lai o ba khau
    can nghia: catalogue, beat map, draft. Moi lan dung no in ra dung viec can
    lam va lenh de chay tiep.

    Vi sao co script nay: ba phim vua roi moi phim phai go ~15 lenh tay, va vai
    phep kiem quan trong (do trung vi shot truoc khi trich frame, kiem do phan
    giai nguon, sao luu truoc khi render) thi phai nho moi lam.

.EXAMPLE
    .\run.ps1 -Source "D:\Downloads\phim.mp4" -Project badgenius2017 -Translate
    .\run.ps1 -Project badgenius2017 -From draft
    .\run.ps1 -Project badgenius2017 -From filmspeaks
#>

[CmdletBinding()]
param(
    [string]$Source,
    [Parameter(Mandatory = $true)][string]$Project,
    [ValidateSet('ingest', 'frames', 'names', 'spans', 'tags', 'catalogue',
                 'beats', 'angle', 'draft', 'filmspeaks', 'voice', 'render', 'verify')]
    [string]$From = 'ingest',
    [switch]$Translate,
    [string]$Model = 'medium',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$Pdir = "projects\$Project"
$script:Stopped = $false

# --------------------------------------------------------------------------- #
function Say  ($m) { Write-Host "`n=== $m" -ForegroundColor Cyan }
function Ok   ($m) { Write-Host "  $m" -ForegroundColor Green }
function Warn ($m) { Write-Host "  $m" -ForegroundColor Yellow }
function Bad  ($m) { Write-Host "  $m" -ForegroundColor Red }

function Halt ($title, $what, $next) {
    Write-Host "`n$('-' * 68)" -ForegroundColor Magenta
    Write-Host "  DUNG: $title" -ForegroundColor Magenta
    Write-Host "$('-' * 68)" -ForegroundColor Magenta
    $what | ForEach-Object { Write-Host "  $_" }
    Write-Host "`n  Chay tiep:" -ForegroundColor Magenta
    Write-Host "    $next`n"
    $script:Stopped = $true
}

# Chay mot lenh recap.py. Tra ve exit code.
# exit 2 la canh bao mem (binh thuong), exit 1 la chan cung.
function Recap {
    param([string[]]$CmdArgs, [switch]$AllowSoftFail)
    Write-Host "  > python recap.py $($CmdArgs -join ' ')" -ForegroundColor DarkGray
    & python recap.py @CmdArgs | Out-Host
    $code = $LASTEXITCODE
    if ($code -eq 0) { return 0 }
    if ($code -eq 2 -and $AllowSoftFail) {
        Warn "exit 2 - co canh bao mem, doc o tren"
        return 2
    }
    Bad "exit $code"
    return $code
}

function Need-File ($path, $hint) {
    if (-not (Test-Path $path)) {
        Bad "thieu $path"
        if ($hint) { Write-Host "    $hint" }
        return $false
    }
    return $true
}

# --------------------------------------------------------------------------- #
# Cac buoc, theo thu tu. $From quyet dinh bat dau tu dau.
# 2026-09-11: 'names' da duoc chuyen len TRUOC 'spans'/'tags'.
# Truoc day no nam trong khau 'catalogue', tuc la SAU khi 70 span da duoc tag.
# He qua tren tokyodrift2006: tagger khong co danh sach dien vien, nen `chars`
# chua toan mo ta ("the American student"), va 31/33 speech claim cua draft
# thanh KHONG kiem duoc (SPEAKER_UNNAMED) - chua duoc bang gi ngoai viec tag
# lai ca phim. Danh sach ten la DAU VAO cua khau tag, khong phai phu luc.
$order = @('ingest', 'frames', 'names', 'spans', 'tags', 'catalogue', 'beats',
           'angle', 'draft', 'filmspeaks', 'voice', 'render', 'verify')
$start = [array]::IndexOf($order, $From)
function Should ($step) { return ([array]::IndexOf($order, $step) -ge $start) }

Write-Host "`nRECAP PIPELINE  -  project: $Project  -  bat dau tu: $From" -ForegroundColor White

# --------------------------------------------------------------------------- #
# 1. INGEST
# --------------------------------------------------------------------------- #
if (Should 'ingest') {
    Say "1. INGEST"

    if ((Test-Path "$Pdir\transcript.json") -and -not $Force) {
        Ok "transcript.json da co - bo qua (dung -Force de lam lai)"
    }
    else {
        if (-not $Source) {
            Bad "can -Source cho buoc ingest"
            exit 1
        }
        if (-not (Test-Path $Source)) { Bad "khong thay $Source"; exit 1 }

        # Kiem do phan giai TRUOC khi ton 40-70 phut transcribe.
        # Hai phim truoc deu 720p va chi phat hien ra sau khi da lam xong.
        $probe = python -c "import config;print(config.ffprobe())"
        $dims = & $probe -v error -select_streams v:0 `
            -show_entries stream=width,height -of csv=p=0 "$Source"
        $w, $h = $dims -split ','
        Write-Host "  nguon: ${w}x${h}"
        if ([int]$w -lt 1900) {
            Warn "KHONG phai 1080p. Render ra 1080p se bi phong to va nhin mem."
            Warn "Chap nhan duoc neu day la phim DE DO. Neu dinh ship, kiem ban khac."
            if (-not $Force) {
                $ans = Read-Host "  Tiep tuc? (y/N)"
                if ($ans -ne 'y') { exit 0 }
            }
        }

        $a = @('ingest', $Source, '--project', $Project, '--model', $Model)
        if ($Translate) { $a += '--translate' }
        if ((Recap $a) -ne 0) { exit 1 }
    }

    # Doc transcript ngay - mo hinh phim khac nhau cho transcript khac nhau,
    # va no quyet dinh cac buoc sau lam the nao.
    $py = @'
import json, io, sys
s = json.load(io.open(sys.argv[1], encoding="utf-8-sig"))["segments"]
dur = float(s[-1]["end"]) / 60 if s else 0
print(f"  {len(s)} segment | thoai toi {dur:.1f} phut | mat do {len(s)/max(dur,1):.1f}/phut")
print("  --- 8 dong mau ---")
for x in s[len(s)//3 : len(s)//3 + 8]:
    print(f'    {float(x["start"]):7.1f}  {x["text"].strip()[:66]}')
'@
    $py | Out-File -FilePath "$env:TEMP\_tr.py" -Encoding utf8
    python "$env:TEMP\_tr.py" "$Pdir\transcript.json"
    Warn "Doc 8 dong tren. Neu la chu vo nghia hoac lap cau -> transcript chi"
    Warn "dung de DINH VI, khong dung de hieu noi dung (rule I4)."

    # ---- [TRANSCRIPT-QUALITY] --------------------------------------------
    # Mot transcript hong KHONG trong nhu hong. Ban cu cua tokyodrift2006 bao
    # phu 89% thoi luong va chi 34% la dung duoc; phan con lai la mot cau bi
    # dong len hang phut audio. Doc 8 dong mau o tren khong bao gio bat duoc
    # dieu do - 8 dong do co the hoan toan sach. Nen co mot phep do rieng, va
    # no chay NGAY SAU whisper chu khong phai sau khi da tag xong 70 span.
    & python tools\check_transcript.py $Project --vad | Out-Host
    if ($LASTEXITCODE -eq 2) {
        Warn "Transcript co van de (xem tren). KHONG chan pipeline, nhung:"
        Warn "  - loi thoai se thua va co cho bi gan sai thoi diem"
        Warn "  - beat map va draft se yeu o dung nhung canh do"
        Warn "Lam lai bang VAD + phat hien ngon ngu theo chunk:"
        Warn "  python tools\retranscribe.py $Project --model medium"
        Warn "  (chay duoc thanh nhieu lat: them --minutes N)"
    }
}

# --------------------------------------------------------------------------- #
# 2. CUTS + FRAMES
# --------------------------------------------------------------------------- #
if (Should 'frames') {
    Say "2. CUT DETECTION + FRAMES"

    if ((Test-Path "$Pdir\_cuts.json") -and -not $Force) {
        Ok "_cuts.json da co"
    }
    else {
        if ((Recap @('cuts', '--project', $Project)) -ne 0) { exit 1 }
    }

    # Do trung vi shot TRUOC khi trich frame.
    # Bad Genius: trung vi 3.0s, luoi mac dinh 5s -> mu voi 37% so shot, va
    # lam mat han mot tinh tiet (B58). Mot pass catalogue phai lam lai.
    $py = @'
import json, io, sys
c = sorted(json.load(io.open(sys.argv[1], encoding="utf-8"))["cuts"])
d = sorted(b - a for a, b in zip(c, c[1:]) if b > a)
if not d:
    print("STEP=5.0"); raise SystemExit
med = d[len(d)//2]
step = max(1.0, round(med * 2 / 3, 1))
# SUA 2026-09-05: ban cu in ty le "shot ngan hon 5s" nhung goi no la "mu voi
# X% so shot" - gop hai dai luong khac nhau va bao qua GAP DOI. Mot shot dai 4s
# tren luoi 5s chi truot 20% so lan, khong phai 100%.
#   Bad Genius: ngan hon 5s = 74.2%, ky vong bi bo sot = 37.0%.
# 37% moi la con so ghi trong docs/STRESS_badgenius.md.
G = 5.0
shorter = sum(1 for x in d if x < G) / len(d)
missed = sum((G - x) / G for x in d if x < G) / len(d)
print(f"  {len(c)} cu cat | trung vi shot {med:.1f}s")
print(f"  ngan hon luoi 5s: {shorter*100:.0f}% so shot")
print(f"  KY VONG khong bao gio duoc lay mau o luoi 5s: {missed*100:.0f}%")
print(f"  -> nen dung --every {step}")
print(f"STEP={step}")
'@
    $py | Out-File -FilePath "$env:TEMP\_step.py" -Encoding utf8
    $out = python "$env:TEMP\_step.py" "$Pdir\_cuts.json"
    $out | Where-Object { $_ -notmatch '^STEP=' } | ForEach-Object { Write-Host $_ }
    $step = ($out | Where-Object { $_ -match '^STEP=' }) -replace 'STEP=', ''

    $needFrames = -not (Test-Path "$Pdir\frames\overview") -or $Force
    if ($needFrames) {
        if ((Recap @('frames', '--project', $Project, '--every', $step)) -ne 0) { exit 1 }
    }
    else {
        Ok "frames\overview da co - bo qua"
        Warn "Neu frames trich o buoc LON HON $step thi nen lam lai voi -Force."
    }
}

# --------------------------------------------------------------------------- #
# 3. NAMES  (phai xong TRUOC khi tag - tagger can danh sach dien vien)
# --------------------------------------------------------------------------- #
if (Should 'names') {
    Say "3. NAMES (truoc khi tag)"

    if ((Test-Path "$Pdir\names.json") -and -not $Force) {
        $n = python -c "import json,io,sys;print(len(json.load(io.open(sys.argv[1],encoding='utf-8-sig')).get('names') or []))" "$Pdir\names.json"
        Ok "names.json da co ($n nhan vat)"
    }
    else {
        Halt "NAMES - can danh sach dien vien tu WIKIPEDIA" @(
            "Chay:"
            "  python recap.py names --project $Project --wiki ""<Ten phim (film)>"" --dry-run"
            "roi bo --dry-run khi ket qua dung."
            ""
            "WIKIPEDIA quyet dinh AI TON TAI. Transcript chi dung de doi chieu"
            "CHINH TA va cach romanise - KHONG BAO GIO dung de quyet dinh ai co"
            "mat trong phim."
            ""
            "Tokyo Drift 2026-09-11: names.json tung duoc dung tu transcript, va"
            "Neela - vai nu chinh - bi loai vi Whisper khong he phat am ra ten"
            "co. Tim mo rong toan bo transcript: khong token nao giong 'Neela'"
            "toi 0.67. Earl, Reiko, Clay, Cindy, Dominic, Toretto cung vang mat."
            "Mot transcript la bang chung ve CHINH TA, khong phai mot danh sach."
            ""
            "Neu phim that su khong co trang Wikipedia, hay noi ro dieu do trong"
            "names.json va ghi nguon da dung thay the."
        ) ".\run.ps1 -Project $Project -From names"
        exit 0
    }
}

# --------------------------------------------------------------------------- #
# 4. SPANS  (co hoc - chia phim thanh span ~90s + trich frame)
# --------------------------------------------------------------------------- #
# Ba buoc tiep theo (spans / tags / beats) la vong LLM. Chung KHONG tu chay
# duoc tu PowerShell: khong co API key nao dung duoc (Gemini chan ca hai tang,
# ANTHROPIC_API_KEY chua dat), nen tagger la subagent do mot agent dieu phoi.
# (Pha 3: neu ANTHROPIC_API_KEY DA dat, buoc tags gui Message Batch thay vi
# subagent - xem khau 5. Beats van la subagent.)
# Nen moi buoc lam het phan CO HOC roi DUNG lai voi danh sach viec chinh xac.
# Noi thang: "mot lenh, phim vao, video ra" chua dat duoc o day, va cho ket
# la ba diem nay - khong phai mot chi tiet con thieu.
if (Should 'spans') {
    Say "4. SPANS (co hoc)"

    $spansOk = $false
    if (Test-Path "$Pdir\spans.json") {
        # "Co file" khong phai la "xong". Hop le = moi span co frame cho MOI
        # shot cua no. Tran MAX_FRAMES tung cat mat duoi 12/30 span va khong
        # gi phat hien ra, vi file van ton tai.
        $spansOk = (python tools\check_stage.py $Project spans) -eq 'OK'
    }
    if ($spansOk -and -not $Force) { Ok "spans.json hop le - bo qua" }
    else {
        if (-not (Test-Path "$Pdir\_cuts.json")) { Bad "thieu _cuts.json"; exit 1 }
        $dur = python tools\check_stage.py $Project duration
        & python tools\make_spans.py $Project --from 0 --to $dur | Out-Host
        if ($LASTEXITCODE -ne 0) { Bad "make_spans that bai"; exit 1 }
        if ((python tools\check_stage.py $Project spans) -ne 'OK') {
            Bad "spans.json sinh ra nhung KHONG hop le - xem canh bao tren"
            exit 1
        }
    }
}

# --------------------------------------------------------------------------- #
# 4. TAGS  (vong LLM: API theo lo neu co key, khong thi mot subagent moi span)
# --------------------------------------------------------------------------- #
if (Should 'tags') {
    Say "5. TAG SPANS (vong LLM)"

    $todo = python tools\check_stage.py $Project tags-todo
    # Pha 3: co ANTHROPIC_API_KEY thi tag bang Message Batches (tools\tag_batch.py),
    # tra bang tin dung API, khong tieu vao gioi han tuan cua goi ma cac buoc
    # VIET can. Batch chay bat dong bo (vai phut toi vai gio), nen o day chi
    # GUI roi DUNG; lan chay sau thu ve. Span nao API van hong sau mot lan thu
    # lai bang model lon hon thi roi xuong duong subagent ben duoi - y nguyen.
    if ($todo -and $todo -ne 'NONE' -and -not $Force -and $env:ANTHROPIC_API_KEY) {
        $st = python tools\tag_batch.py status --project $Project
        if ($st -eq 'PENDING') {
            Write-Host "  > python tools\tag_batch.py collect --project $Project" -ForegroundColor DarkGray
            & python tools\tag_batch.py collect --project $Project | Out-Host
            $code = $LASTEXITCODE
            if ($code -eq 3) {
                Halt "TAG SPANS - batch API chua xong" @(
                    "Batch da gui, dang chay phia Anthropic (vai phut toi vai gio)."
                    "Thu ve bang tay, doi toi khi xong:"
                    "  python tools\tag_batch.py collect --project $Project --wait"
                    "roi chay lai lenh duoi. Hoac chay lai thang lenh duoi luc nao cung duoc."
                ) ".\run.ps1 -Project $Project -From tags"
                exit 0
            }
            if ($code -eq 1) {
                Bad "tag_batch collect that bai - doc loi o tren"
                exit 1
            }
            $st = python tools\tag_batch.py status --project $Project
        }
        if ($st -eq 'NEW') {
            Write-Host "  > python tools\tag_batch.py submit --project $Project" -ForegroundColor DarkGray
            & python tools\tag_batch.py submit --project $Project | Out-Host
            if ($LASTEXITCODE -eq 0) {
                Halt "TAG SPANS - da gui batch API" @(
                    "Model: config.TAG_MODEL. Id batch ghi trong $Pdir\tag_batch.json."
                    "Batch chay bat dong bo. Thu ve (doi toi khi xong):"
                    "  python tools\tag_batch.py collect --project $Project --wait"
                    ""
                    "Span nao van hong sau khi thu ve se duoc liet ke va chuyen"
                    "sang duong subagent o lan chay tiep theo."
                ) ".\run.ps1 -Project $Project -From tags"
                exit 0
            }
            Warn "tag_batch submit that bai - dung duong subagent"
        }
        $todo = python tools\check_stage.py $Project tags-todo
    }
    if ($todo -and $todo -ne 'NONE' -and -not $Force) {
        $n = ($todo -split ' ').Count
        Halt "TAG SPANS - $n span chua duoc tag" @(
            "Moi span mot subagent, context rieng. Prompt: tools\span_prompt.md"
            ""
            "Span con thieu:"
            "  $todo"
            ""
            "Moi subagent:"
            "  1. doc tools\span_prompt.md"
            "  2. chay: python tools\span_payload.py $Project <span>"
            "  3. doc MOI frame duoc liet ke"
            "  4. ghi $Pdir\spans.json.d\<span>.json"
            ""
            "KHONG duoc doc shots.json hay beats_proposal.md - do la dap an."
        ) ".\run.ps1 -Project $Project -From tags"
        exit 0
    }
    Ok "moi span da co tag"
}

# --------------------------------------------------------------------------- #
# 5. NAMES + CATALOGUE MAY  (co hoc: lap rap moment thanh shots_machine.json)
# --------------------------------------------------------------------------- #
if (Should 'catalogue') {
    Say "6. CATALOGUE MAY"

    if (-not (Test-Path "$Pdir\names.json")) {
        Warn "chua co names.json"
        Write-Host "    python recap.py names --project $Project --wiki ""<Ten phim (film)>"" --dry-run"
    }
    else { Ok "names.json co" }

    if ((Test-Path "$Pdir\shots_machine.json") -and -not $Force) {
        Ok "shots_machine.json da co"
    }
    else {
        & python tools\assemble_moments.py $Project | Out-Host
        if ($LASTEXITCODE -ne 0) { Bad "assemble_moments that bai"; exit 1 }
    }
    if (-not (Test-Path "$Pdir\shots.json")) {
        Copy-Item "$Pdir\shots_machine.json" "$Pdir\shots.json"
        Ok "shots.json <- shots_machine.json (catalogue may la catalogue)"
    }
}

# --------------------------------------------------------------------------- #
# 6. BEAT MAP + CHOT DU LIEU  (vong LLM + checkpoint nguoi)
# --------------------------------------------------------------------------- #
if (Should 'beats') {
    Say "7. BEAT MAP + CHOT DU LIEU"

    if (-not (Test-Path "$Pdir\beats_proposal.md") -and $env:ANTHROPIC_API_KEY) {
        # Co key: 8 chunk (mot batch) + vong reveals qua API thay vi dung lai.
        Say "   beat map qua API (tools\write_api.py beats)"
        & python tools\write_api.py beats --project $Project | Out-Host
        $wc = $LASTEXITCODE
        if ($wc -eq 3) {
            Halt "BEAT MAP - batch API chua xong" @(
                "Batch da gui; chay lai sau vai phut de lay ket qua."
            ) ".\run.ps1 -Project $Project -From beats"
            exit 0
        }
        if ($wc -ne 0) { Bad "write_api beats exit $wc - xem o tren"; exit 1 }
    }
    if (-not (Test-Path "$Pdir\beats_proposal.md")) {
        $bt = python tools\check_stage.py $Project beats-todo
        if ($bt -and $bt -ne 'NONE') {
            Halt "BEAT MAP - $bt chunk chua de xuat beat (vong LLM)" @(
                "Mot subagent moi chunk. Prompt: tools\beats_prompt.md"
                ""
                "Moi subagent:"
                "  1. doc tools\beats_prompt.md"
                "  2. chay: python tools\beat_payload.py $Project <k> 8"
                "  3. ghi $Pdir\beats.json.d\chunk<k>.json"
                ""
                "Sau khi du 8 chunk, mot subagent nua gop reveal-map +"
                "set-pieces toan phim vao $Pdir\reveals.json, roi:"
                "  python tools\assemble_beats.py $Project --out beats_proposal.md"
                ""
                "CANH BAO: thieu beats_proposal.md thi project roi ve"
                "style: review va TAT TOAN BO gate linear trong im lang."
            ) ".\run.ps1 -Project $Project -From beats"
            exit 0
        }
        if (Test-Path "$Pdir\reveals.json") {
            & python tools\assemble_beats.py $Project --out beats_proposal.md | Out-Host
            if ($LASTEXITCODE -ne 0) { Bad "assemble_beats that bai"; exit 1 }
        }
        else {
            Halt "BEAT MAP - du chunk nhung thieu reveals.json" @(
                "8 chunk da xong. Con thieu buoc gop toan phim:"
                "  reveal-map (2-4 muc, chi nhung gi phim CO Y giau roi tra)"
                "  set-pieces (gop cac doan bi cat doi o ranh chunk)"
                "Ghi vao $Pdir\reveals.json roi chay lai."
            ) ".\run.ps1 -Project $Project -From beats"
            exit 0
        }
    }

    # Kiem beat map doc duoc khong - va style co phai linear khong.
    $py = @'
import sys
sys.path.insert(0, ".")
from pipeline import draft as D, catalogue as C
proj = sys.argv[1]
info = C.parse_beats(proj)
print(f"  style: {info.get('style')} | beats: {len(info.get('beats') or [])}")
bt = D.beat_times(proj)
for p in bt.get("problems", []):
    print(f"  [BEAT-MAP] {p}")
o = bt.get("ordered") or []
if o:
    print(f"  beat dau {o[0][0]} @{o[0][1]/60:.1f}m | beat cuoi {o[-1][0]} @{o[-1][1]/60:.1f}m")
print(f"  reveal-map: {len(D.parse_reveal_map(proj))} muc")
'@
    $py | Out-File -FilePath "$env:TEMP\_beats.py" -Encoding utf8
    python "$env:TEMP\_beats.py" $Project

    $istyle = python -c "import sys; sys.path.insert(0, '.'); from pipeline import intro_style as S`ntry:`n    p, w = S.choose(sys.argv[1]); print(p + ' - ' + w[0])`nexcept Exception as e:`n    print('LOI: ' + str(e))" $Project
    Halt "CHOT DU LIEU - viec cua BAN, truoc khi sinh draft" @(
        "Doc ba thu tren va xac nhan:"
        ""
        "  1. style co phai 'linear' khong. Neu 'review' thi gate linear tat het."
        "  2. beat cuoi co gan cuoi phim khong. Lech nhieu = sai quy uoc timestamp."
        "  3. reveal-map:"
        "       - moi reveal: khan gia co biet TRUOC khi bam play khong?"
        "         Co -> KHONG bao ve, ghi vao DELIBERATELY NOT PROTECTED (rule H1)"
        "       - moi reveal: HINH mang hay THOAI mang?"
        "         Thoai -> gate khong kiem duoc, phai mat nguoi doc beat do"
        ""
        "  4. intro montage style hien tai: $istyle"
        "       Doi: sua dong dau cua $Pdir\intro_style.txt (mot trong:"
        "       energetic emotional suspense mystery horror comedy epic romance)."
        "       Stage angle chi GOI Y khi file chua co; khong bao gio ghi de."
        ""
        "Chot xong thi khoa lai: model viet draft doc duoc, khong sua duoc."
    ) ".\run.ps1 -Project $Project -From angle"
    exit 0
}

# --------------------------------------------------------------------------- #
# 7a. FILM FACTS + ANGLE  (vong LLM - truoc day lam TAY, nen phim sau bi quen)
# --------------------------------------------------------------------------- #
# Tokyo Drift co angle.md, film_facts.json, coverage_policy.json - deu do agent
# lam tay ngoai quy trinh. Thieu angle.md thi cac gate nhip ke / persona /
# hook-payoff KHONG CHAY; thieu film_facts.json thi phan gioi thieu phim khong
# co gi de kiem. Gio la mot stage, va no chan truoc khi viet draft.
if (Should 'angle') {
    Say "7a. FILM FACTS + ANGLE"
    if ($env:ANTHROPIC_API_KEY) {
        # Co key: film facts (Wikipedia, mot revision) va angle qua API.
        if (-not (Test-Path "$Pdir\film_facts.json")) {
            & python tools\write_api.py facts --project $Project | Out-Host
            if ($LASTEXITCODE -ne 0) { Bad "write_api facts exit $LASTEXITCODE - xem o tren (--wiki ""<Ten phim (film)>"")"; exit 1 }
        }
        if (-not (Test-Path "$Pdir\angle.md") -or
            -not (Test-Path "$Pdir\coverage_policy.json")) {
            & python tools\write_api.py angle --project $Project | Out-Host
            if ($LASTEXITCODE -ne 0) { Bad "write_api angle exit $LASTEXITCODE - xem o tren"; exit 1 }
        }
    }
    if (-not (Test-Path "$Pdir\film_facts.json")) {
        Halt "FILM FACTS - thieu film_facts.json (vong LLM)" @(
            "Mot subagent. Prompt: tools\film_facts_prompt.md"
            "Nguon DUY NHAT: bai Wikipedia tieng Anh cua phim (ghi oldid)."
            "Doc reveals.json truoc: dien vien ma su xuat hien la reveal"
            "(cameo) phai nam trong 'withheld', khong nam trong cast."
            "Ghi: $Pdir\film_facts.json"
        ) ".\run.ps1 -Project $Project -From angle"
        exit 0
    }
    if (-not (Test-Path "$Pdir\angle.md") -or
        -not (Test-Path "$Pdir\coverage_policy.json")) {
        Halt "ANGLE - thieu angle.md / coverage_policy.json (vong LLM)" @(
            "Mot subagent MOI. Prompt: tools\angle_prompt.md"
            "Doc: beats_proposal.md, reveals.json, names.json, film_facts.json,"
            "     prompts\recap_style.md, docs\NARRATOR_VOICE.md"
            "Ghi: $Pdir\angle.md  (ANGLE, ATTITUDE, RUNNING BITS, ANCHORS,"
            "     HOOK PROMISES, NARRATOR PERSONA, WHAT THE ANGLE SELECTS)"
            "     $Pdir\coverage_policy.json  ({""mandatory"": [""B01"", ...]})"
            ""
            "Moi anchor va moi hook promise phai co evidence: ""..."" trich"
            "NGUYEN VAN tu 'what' cua beat - gate kiem tung cau."
        ) ".\run.ps1 -Project $Project -From angle"
        exit 0
    }
    $chk = python -c @"
import sys
sys.path.insert(0, '.')
from pathlib import Path
from pipeline import angle_spec
try:
    angle_spec.load(Path(r'$Pdir'))
    print('OK')
except Exception as e:
    print('BAD: ' + str(e).replace(chr(10), ' '))
"@
    if ($chk -ne 'OK') {
        Bad "angle.md khong dung dinh dang: $chk"
        Warn "Sua theo tools\angle_prompt.md roi chay lai: .\run.ps1 -Project $Project -From angle"
        exit 1
    }
    Ok "film_facts.json + angle.md + coverage_policy.json: du va doc duoc"
}

# --------------------------------------------------------------------------- #
# 7. DRAFT  (vong LLM toi da 3 + checkpoint nguoi #1)
# --------------------------------------------------------------------------- #
if (Should 'draft') {
    Say "8. DRAFT (vong toi da 3)"

    # Vong draft: toi da 3 vong. Dem vong nam trong state.json nen mot lan
    # crash khong lam mat so vong va khong khoi dong lai tu 0.
    $round = [int](python tools\check_stage.py $Project draft-round)
    $acts  = python tools\check_stage.py $Project acts-todo

    if ($acts -and $acts -ne 'NONE' -and $env:ANTHROPIC_API_KEY) {
        # Co key: cac act trong mot batch + toi da 2 vong feedback gate qua
        # API. exit 2 = con finding (da liet ke) - di tiep, gate ben duoi
        # va checkpoint nguoi se thay chung.
        Say "   draft qua API (tools\write_api.py draft)"
        & python tools\write_api.py draft --project $Project | Out-Host
        $wc = $LASTEXITCODE
        if ($wc -eq 3) {
            Halt "DRAFT - batch API chua xong" @(
                "Batch da gui; chay lai sau vai phut de lay ket qua."
            ) ".\run.ps1 -Project $Project -From draft"
            exit 0
        }
        if ($wc -eq 1) { Bad "write_api draft exit 1 - xem o tren"; exit 1 }
        if ($wc -eq 4) {
            # dan y (plan.json) bi tu choi 2 lan - CHUA co act nao duoc viet,
            # nen KHONG phai vong subagent; loi cu the in ngay o tren
            Halt "DRAFT - dan y (plan) chua qua gate, chua viet act nao" @(
                "Ly do: xem cac dong 'plan: attempt ...' o tren."
                "Ban bi tu choi cuoi: $Pdir\plan_rejected.json"
                "Gui man hinh nay cho nguoi bao tri pipeline - dung tu sua tay."
            ) ".\run.ps1 -Project $Project -From draft"
            exit 0
        }
        $acts = python tools\check_stage.py $Project acts-todo
    }

    if ($acts -and $acts -ne 'NONE') {
        Halt "DRAFT - $acts act chua viet (vong LLM, vong $($round+1)/3)" @(
            "Mot subagent moi act. Prompt: tools\draft_prompt.md"
            ""
            "Moi subagent:"
            "  1. doc tools\draft_prompt.md"
            "  2. chay: python tools\act_payload.py $Project <n>"
            "     (payload da gom ca transcript cho tung moment)"
            "  3. ghi $Pdir\draft.json.d\act<n>.json"
            ""
            "Roi: python tools\assemble_draft.py $Project"
        ) ".\run.ps1 -Project $Project -From draft"
        exit 0
    }

    if (-not (Test-Path "$Pdir\draft.json")) {
        & python tools\assemble_draft.py $Project | Out-Host
        if ($LASTEXITCODE -ne 0) { Bad "assemble_draft that bai"; exit 1 }
    }

    # HAI BAN DOC DOC LAP, truoc checkpoint nguoi. [COLD-READ] va [REVIEWER]
    # chan draft cho den khi co ca hai, nen day khong phai viec lam sau. Agent
    # viet draft KHONG duoc lam viec nay: mot nguoi doc lai bai minh viet
    # khong thay gi.
    # Co ANTHROPIC_API_KEY: ba ban doc chay qua API (tools\review_api.py, moi
    # ban doc la mot request MOI, chi thay dung phan cua no) thay vi dung lai.
    # Khong co key: dung lai nhu cu.
    $needReview = (-not (Test-Path "$Pdir\cold_read.md") -or
                   -not (Test-Path "$Pdir\review.md") -or
                   -not (Test-Path "$Pdir\ending_read.md"))
    if ($needReview -and $env:ANTHROPIC_API_KEY) {
        Say "   review qua API (cold read, reviewer, ending read)"
        & python tools\review_api.py all --project $Project | Out-Host
        if ($LASTEXITCODE -ne 0) {
            Bad "review_api exit $LASTEXITCODE - xem o tren; xoa key de quay ve subagent"
            exit 1
        }
        $needReview = $false
    }
    if ($needReview) {
        Halt "REVIEW - hai subagent MOI, chua tung thay draft nay" @(
            "1. COLD READ (agent chua he thay phim, beats, angle hay payload):"
            "   python tools\cold_read_payload.py $Project > _coldread.txt"
            "   No chi doc file do - khong co delivery tag, khong co payload"
            "   label, khong co hook question. Liet ke:"
            "     - thu duoc nhac nhu da biet ma script chua gioi thieu"
            "     - dai tu mo ho (hai nguoi deu co the la 'he')"
            "     - cho nao doc mot lan khong hieu"
            "     - claim ve viec nhan vat 'luon' / 'ca phim' lam gi"
            "   Ghi: $Pdir\cold_read.md"
            ""
            "2. REVIEWER (agent moi, checklist co dinh): phat hien cua cold"
            "   read, motif budget, cau lap, claim khong co cho kiem, dat ten"
            "   o reveal, va cac dinh diem co bi noi chen len khong."
            "   Ghi: $Pdir\review.md"
            ""
            "3. ENDING READ (agent moi nua, chua thay phim): CHI doc 5 cau"
            "   cuoi trong _coldread.txt, mot lan, nhu nguoi xem nghe doan ket."
            "   Ai noi cau nao, callback tro ve dau, co ket that khong."
            "   Ghi: $Pdir\ending_read.md  ([ENDING-READ] chan neu thieu)"
            ""
            "Ca hai file: khoi review-signatures (tool in ra san de dan) va"
            "khoi review-findings 'STATUS | kind | line ids | text'. Moi"
            "FINDING phai thanh RESOLVED hoac ANSWERED."
        ) ".\run.ps1 -Project $Project -From draft"
        exit 0
    }

    $code = Recap @('draft', '--project', $Project) -AllowSoftFail
    if ($code -eq 1 -and $env:ANTHROPIC_API_KEY) {
        # Co key: vong RESOLVE qua API (toi da 2 vong) thay cho vong subagent.
        & python tools\write_api.py resolve --project $Project | Out-Host
        $code = Recap @('draft', '--project', $Project) -AllowSoftFail
        if ($code -eq 1) {
            Halt "DRAFT - gate con loi sau vong API" @(
                "Cac loi con lai in o tren (write_api resolve + recap.py draft)."
                "Sua tay trong $Pdir\draft.json, hoac chay lai vong API:"
                "  python tools\write_api.py resolve --project $Project"
            ) ".\run.ps1 -Project $Project -From draft"
            exit 0
        }
    }
    if ($code -eq 1) {
        if ($round -ge 3) {
            Bad "draft van bi CHAN CUNG sau 3 vong - DUNG, can nguoi vao"
            Write-Host "    Khong tu sua them. Ba vong la tran, va mot vong thu tu"
            Write-Host "    thuong la model tu bien minh chu khong phai sua that."
            exit 1
        }
        python tools\check_stage.py $Project draft-round-inc | Out-Null
        Halt "DRAFT vong $($round+1)/3 - gate tra ve loi, feed nguoc cho LLM" @(
            "Doc cac phat hien o tren va giao lai cho subagent theo tung act."
            "Chi sua nhung gi gate chi ra. Khong viet lai toan bo."
            ""
            "Het 3 vong ma van do thi DUNG va goi nguoi - dung vong thu tu."
        ) ".\run.ps1 -Project $Project -From draft"
        exit 0
    }

    Halt "DUYET DRAFT - checkpoint nguoi #1, khong bo duoc" @(
        "Mo $Pdir\script.txt va doc het."
        ""
        "Bon thu can soi:"
        "  1. Ro ri am chi. REVEAL-TIMING chi quet TERM, khong bat duoc am chi."
        "     Shutter Island: mot cau chu de am chi tron cu lat ma gate thay sach."
        "  2. Chu thich khung hinh (I1). Cau khong chu ngu, khong dong tu,"
        "     kieu 'Bon gio sang. Con hem, duong ray, mot con meo.'"
        "  3. Quyet dinh bien tap - cho nay chi ban lam duoc:"
        "     tach line de moi cu lat co clip rieng, bo ve dien giai o cau ket."
        "  4. Cho LLM tu bien minh. Mot lan ha tier sai den kem ba doan lap luan"
        "     trong y het su can than."
        ""
        "Khong can biet sua the nao. Chi tro ra CHO NAO SAI la du."
    # -From filmspeaks, KHONG phai -From render. Stage filmspeaks nam NGAY SAU
    # checkpoint nay (muc 8b ben duoi), nen resume bang 'render' se BO QUA no
    # hoan toan: draft ra khong co unit film_speaks nao, va day dung la cach
    # mot phim 17 phut da ship voi SO KHONG unit.
    ) ".\run.ps1 -Project $Project -From filmspeaks"
    exit 0
}

# --------------------------------------------------------------------------- #
# 8b. FILM_SPEAKS - chon 2-3 cho de PHIM tu noi (vong LLM)
# --------------------------------------------------------------------------- #
# Moi phim phai co 2-3 unit film_speaks. Day la CHO DUY NHAT con nghe duoc
# thoai goc: moi noi khac dung no-vocals stem. Mot phim 17 phut da ship voi
# SO KHONG unit, vi khong co gi hoi den no. Gio la mot stage, va
# [FILM-SPEAKS-COUNT] FAIL khi co ung vien ma draft khong co unit nao.
if (Should 'filmspeaks') {
    Say "8b. FILM_SPEAKS - de phim tu noi 2-3 lan"

    $fsNeed = python -c @"
import json, io, sys
sys.path.insert(0, '.')
try:
    d = json.load(io.open(r'$Pdir\draft.json', encoding='utf-8'))
except Exception:
    print('NODRAFT'); raise SystemExit
n = len([l for l in d.get('lines') or []
         if l.get('film_speaks_seconds') is not None])
print('OK' if n >= 2 else f'NEED:{n}')
"@
    # Selection da co (vong LLM da chay): AP DUNG vao draft.json roi kiem lai
    # bang chinh gate cua draft. tools\apply_film_speaks.py cat cua so line chu
    # cho KET THUC o cho quote bat dau (neu khong se trip [FOOTAGE-REUSE]) va
    # thay cau truoc/sau. exit 1 = co finding can nguoi xem (vd line id trong
    # selection khong con la hang xom cua unit) - DUNG, khong doan.
    if ($fsNeed -like 'NEED:*' -and (Test-Path "$Pdir\film_speaks_selection.json")) {
        Say "   ap dung film_speaks_selection.json vao draft.json"
        & python tools\apply_film_speaks.py --project $Project | Out-Host
        $fsApply = $LASTEXITCODE
        if ($fsApply -ne 0) {
            Halt "FILM_SPEAKS - ap dung selection co finding (exit $fsApply)" @(
                "Doc cac dong FINDING o tren."
                "Line id trong selection khong khop draft hien tai: chay lai"
                "vong chon (prompts\film_speaks_select.md), hoac neu cau thay"
                "van dung cho hang xom hien tai:"
                "  python tools\apply_film_speaks.py --project $Project --by-position"
            ) ".\run.ps1 -Project $Project -From filmspeaks"
            exit 0
        }
        $code = Recap -CmdArgs @('draft', '--project', $Project) -AllowSoftFail
        if ($code -eq 1) {
            Halt "FILM_SPEAKS - draft khong qua gate sau khi ap dung" @(
                "Sua cac loi [..] o tren trong $Pdir\draft.json"
                "(ban truoc: draft.pre_film_speaks.json)."
            ) ".\run.ps1 -Project $Project -From filmspeaks"
            exit 0
        }
        $fsNeed = 'OK'
        Ok "film_speaks: selection da ap dung, draft qua gate"
    }
    if ($fsNeed -like 'NEED:*') {
        if (-not (Test-Path "$Pdir\film_speaks_candidates.json")) {
            Say "   sinh ung vien (co do sach thoai bang Demucs - cham)"
            & python tools\film_speaks_candidates.py --project $Project | Out-Host
        }
        $nCand = python -c @"
import json, io
try:
    print(len(json.load(io.open(r'$Pdir\film_speaks_candidates.json',
                                encoding='utf-8')).get('candidates') or []))
except Exception:
    print(0)
"@
        $fsDone = $false
        if ([int]$nCand -gt 0 -and $env:ANTHROPIC_API_KEY) {
            # Co key: chon qua API roi tools\apply_film_speaks.py, roi kiem gate.
            & python tools\write_api.py filmspeaks --project $Project | Out-Host
            if ($LASTEXITCODE -ne 0) {
                Halt "FILM_SPEAKS - write_api filmspeaks exit $LASTEXITCODE" @(
                    "Doc cac dong FINDING o tren (selection da ghi:"
                    "$Pdir\film_speaks_selection.json)."
                ) ".\run.ps1 -Project $Project -From filmspeaks"
                exit 0
            }
            $code = Recap -CmdArgs @('draft', '--project', $Project) -AllowSoftFail
            if ($code -eq 1) {
                Halt "FILM_SPEAKS - draft khong qua gate sau khi ap dung" @(
                    "Sua cac loi [..] o tren trong $Pdir\draft.json"
                    "(ban truoc: draft.pre_film_speaks.json)."
                ) ".\run.ps1 -Project $Project -From filmspeaks"
                exit 0
            }
            Ok "film_speaks: chon + ap dung qua API, draft qua gate"
            $fsDone = $true
            $nCand = 0
        }
        if ([int]$nCand -gt 0) {
            Halt "FILM_SPEAKS - $nCand ung vien, can chon 2-3 (vong LLM)" @(
                "Mot subagent MOI (fresh context). Prompt:"
                "  prompts\film_speaks_select.md"
                ""
                "Input:  $Pdir\film_speaks_candidates.json"
                "Doc them: draft.json, angle.md, beats_proposal.md, reveals.json"
                "Ghi:    $Pdir\film_speaks_selection.json"
                ""
                "Subagent phai: cham diem theo a-c, ghi criterion +"
                "mot cau ly do moi pick, VA viet lai cau TRUOC (dan vao"
                "ma khong noi truoc noi dung) + cau SAU (phan ung)."
                ""
                "Sau do ap dung vao draft.json: cua so cua line chu phai"
                "KET THUC o cho quote bat dau, neu khong se trip"
                "[FOOTAGE-REUSE]."
            ) ".\run.ps1 -Project $Project -From filmspeaks"
            exit 0
        }
        if (-not $fsDone) { Warn "khong co ung vien nao du dieu kien - so khong la hop le cho phim nay" }
    }
    else { Ok "film_speaks: du unit" }
}

# --------------------------------------------------------------------------- #
# 8c. VOICE - doc giong + kiem do dai TRUOC khi dung clip
# --------------------------------------------------------------------------- #
# Truoc day loi "cau doc dai hon hinh" chi lo ra o RENDER, sau khi da tach
# tieng va probe phim (Tokyo Drift cau 79, lo 0.2s). Doc giong va pre-flight
# khong can gi tu buoc dung clip, nen chay o day: --fit tu noi cua so / tang
# toc nhe roi doc lai dung nhung cau do. Render phia sau chi con lap rap.
if (Should 'voice') {
    Say "8c. VOICE - doc giong (Inworld) + kiem do dai tren audio THAT"
    if ((Recap @('voice', '--project', $Project, '--fit')) -ne 0) {
        Bad "voice that bai"
        Warn "Neu con cau phai cat chu: sua draft.json theo narration_fit_todo.json,"
        Warn "roi chay lai:  .\run.ps1 -Project $Project -From voice"
        exit 1
    }
}

# --------------------------------------------------------------------------- #
# 9. RENDER
# --------------------------------------------------------------------------- #
if (Should 'render') {
    Say "9. RENDER"

    $hasBed = (Test-Path "$Pdir\music.mp3") -or
              ((Get-ChildItem "$Pdir\music" -Filter 'bed.*' -ErrorAction SilentlyContinue) -ne $null)
    if (-not (Test-Path "$Pdir\intro_music.*")) {
        Warn "khong thay intro_music.* - doan intro se khong co nhac edit rieng"
    }
    if (-not $hasBed) {
        Warn "khong thay music\bed.* hay music.mp3 - render se khong co nhac nen"
        Warn "Nhac nen phai la INSTRUMENTAL. Nhac co loi hat canh tranh voi"
        Warn "voiceover: hai giong cung luc, nguoi xem met ma khong biet vi sao."
    }

    # Sao luu ban cu TRUOC khi de len.
    if (Test-Path "$Pdir\final.mp4") {
        $stamp = Get-Date -Format 'yyyyMMdd-HHmm'
        foreach ($f in 'final.mp4', 'draft.json', 'timeline.json', 'script.txt') {
            if (Test-Path "$Pdir\$f") {
                $ext = [IO.Path]::GetExtension($f)
                $bn = [IO.Path]::GetFileNameWithoutExtension($f)
                Copy-Item "$Pdir\$f" "$Pdir\${bn}_$stamp$ext" -Force
            }
        }
        Ok "da sao luu ban cu voi hau to _$stamp"
    }

    if ((Recap @('render', '--project', $Project, '--voice', 'tts')) -ne 0) {
        Bad "render that bai"
        exit 1
    }
}

# --------------------------------------------------------------------------- #
# 9. VERIFY + checkpoint xem video
# --------------------------------------------------------------------------- #
if (Should 'verify') {
    Say "10. VERIFY"

    $null = Recap @('verify', '--project', $Project) -AllowSoftFail

    if (Test-Path 'tools\diag_offset.py') {
        Write-Host "  > python tools\diag_offset.py $Project" -ForegroundColor DarkGray
        python tools\diag_offset.py $Project 2>&1 | Select-Object -Last 6
    }

    Halt "XEM VIDEO - checkpoint nguoi #2, khong bo duoc" @(
        "$Pdir\final.mp4"
        ""
        "Sau phim lien tiep, mat nguoi tim ra thu moi gate bo qua."
        ""
        "  1. Drift: hinh co khop loi khong. Ghi lai ID LINE, dung ghi 'khoang"
        "     phut 7' - timeline.json tra ra duoc trong vai giay."
        "  2. Line mang claim.type 'speech': gate dat duoc nguoi len man hinh"
        "     dang noi, KHONG biet ho noi gi. Chi tai ban xac nhan duoc."
        "  3. Cu lat co dong lai khong."
        "  4. Nhip: hinh co dung cho giong khong? Phim cat nhanh co the can"
        "     NARRATION_LEAD_IN thap hon 0.5s."
        "  5. Cau rieng cho the loai:"
        "       hai      -> co buon cuoi khong"
        "       cam xuc  -> co xuc dong khong"
        "       quy trinh-> co hieu duoc cach no van hanh khong"
        ""
        "Con lai: censor review - checkpoint nguoi #3."
    ) "(xong)"
}

if (-not $script:Stopped) {
    Write-Host "`n$('=' * 68)" -ForegroundColor Green
    Ok "Chay het cac buoc may lam duoc."
    Write-Host "$('=' * 68)`n" -ForegroundColor Green
}
