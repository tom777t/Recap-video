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
    .\run.ps1 -Project badgenius2017 -From render
#>

[CmdletBinding()]
param(
    [string]$Source,
    [Parameter(Mandatory = $true)][string]$Project,
    [ValidateSet('ingest', 'frames', 'spans', 'tags', 'catalogue', 'beats',
                 'draft', 'render', 'verify')]
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
$order = @('ingest', 'frames', 'spans', 'tags', 'catalogue', 'beats',
           'draft', 'render', 'verify')
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
# 3. SPANS  (co hoc - chia phim thanh span ~90s + trich frame)
# --------------------------------------------------------------------------- #
# Ba buoc tiep theo (spans / tags / beats) la vong LLM. Chung KHONG tu chay
# duoc tu PowerShell: khong co API key nao dung duoc (Gemini chan ca hai tang,
# ANTHROPIC_API_KEY chua dat), nen tagger la subagent do mot agent dieu phoi.
# Nen moi buoc lam het phan CO HOC roi DUNG lai voi danh sach viec chinh xac.
# Noi thang: "mot lenh, phim vao, video ra" chua dat duoc o day, va cho ket
# la ba diem nay - khong phai mot chi tiet con thieu.
if (Should 'spans') {
    Say "3. SPANS (co hoc)"

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
# 4. TAGS  (vong LLM: mot subagent moi span)
# --------------------------------------------------------------------------- #
if (Should 'tags') {
    Say "4. TAG SPANS (vong LLM)"

    $todo = python tools\check_stage.py $Project tags-todo
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
    Say "5. NAMES + CATALOGUE MAY"

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
    Say "6. BEAT MAP + CHOT DU LIEU"

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
        "Chot xong thi khoa lai: model viet draft doc duoc, khong sua duoc."
    ) ".\run.ps1 -Project $Project -From draft"
    exit 0
}

# --------------------------------------------------------------------------- #
# 7. DRAFT  (vong LLM toi da 3 + checkpoint nguoi #1)
# --------------------------------------------------------------------------- #
if (Should 'draft') {
    Say "7. DRAFT (vong toi da 3)"

    # Vong draft: toi da 3 vong. Dem vong nam trong state.json nen mot lan
    # crash khong lam mat so vong va khong khoi dong lai tu 0.
    $round = [int](python tools\check_stage.py $Project draft-round)
    $acts  = python tools\check_stage.py $Project acts-todo

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

    $code = Recap @('draft', '--project', $Project) -AllowSoftFail
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
    ) ".\run.ps1 -Project $Project -From render"
    exit 0
}

# --------------------------------------------------------------------------- #
# 8. RENDER
# --------------------------------------------------------------------------- #
if (Should 'render') {
    Say "8. RENDER"

    if (-not (Test-Path "$Pdir\music.mp3")) {
        Warn "khong thay music.mp3 - render se khong co nhac nen"
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
    Say "9. VERIFY"

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
