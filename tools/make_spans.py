# -*- coding: utf-8 -*-
"""
make_spans.py - chia phim thanh SPAN ~90s snap vao cu cat that, trich MOT frame
cho moi shot trong span (ke ca phan overlap), ghi `spans.json` + frame.

Vi sao ton tai
--------------
v1 da chung minh: 97.4%/88.9% cua so nguoi la VOI TOI duoc tu `_cuts.json`,
nhung khong gi trong `_cuts.json` + `transcript.json` doan duoc cach gom nao.
Quyet dinh gom la BIEN TAP. Nen no chuyen vao LLM, va file nay chi lo khau co
hoc: chia span, snap vao cu cat, trich frame.

Bien span - noi loi se don lai
------------------------------
Mot khoanh khac nam vat qua mep span la loi du doan truoc duoc: hai span deu
thay mot nua, ca hai deu dong moment tai mep, sinh ra mot ranh gioi gia o MOI
seam. 30 seam tren badgenius co the tu minh lam lech F1.

Cach xu ly (ghim trong docs/WINDOW_GROUPING_V2_CRITERION.md):
  - span i SO HUU [own_start, own_end), hai moc snap vao cu cat that
  - subagent duoc xem den ext_end = own_end + 20s (cung snap vao cu cat), va
    phai lat kin CA vung mo rong - 20s do la NGU CANH de no thay moment con
    tiep hay khong
  - khi lap rap, moment thuoc ve span nao chua DIEM GIUA cua no -> moment vat
    qua seam duoc giu NGUYEN VEN, dung MOT lan
  - mau thuan con lai duoc go deterministic va DEM LAI (assemble_moments.py)

Granularity: mot span trich loi chi mat SPAN DO. Trang thai ghi vao
`_spans_manifest.json`; chay lai chi lam span con thieu.

Dung:
    python tools/make_spans.py <project> --from 3600 --to 6300
    python tools/make_spans.py <project> --from 3600 --to 6300 --dry-run
"""
from __future__ import annotations
import argparse, bisect, io, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

SPAN = 90.0
OVERLAP = 20.0
LONG_SHOT = 12.0      # shot dai hon thi lay them mot frame giua
# 2026-09-08: tran nay tung la 34 va cat DUOI danh sach - 12/30 span cua
# badgenius mat frame tu shot 34 tro di, 77 shot mu hoan toan. Dung chо nao
# cung te, nhung DUOI span la cho te nhat: do chinh la phan duoi ma logic seam
# dua vao de biet moment co chay tiep qua mep hay khong.
# Tran chi duoc phep bo bot frame PHU ('b'), KHONG BAO GIO bo mot shot.
MAX_FRAMES = 64


def hms(s: float) -> str:
    s = max(0.0, float(s))
    return f"{int(s)//3600:02d}:{(int(s)%3600)//60:02d}:{s%60:06.3f}"


def snap(cuts, t):
    i = bisect.bisect_left(cuts, t)
    c = [cuts[j] for j in (i - 1, i) if 0 <= j < len(cuts)]
    return min(c, key=lambda x: abs(x - t)) if c else t


def build_spans(cuts, a, b, span=SPAN, overlap=OVERLAP):
    marks, t = [], a
    while t < b - 1e-9:
        marks.append(snap(cuts, t))
        t += span
    marks.append(snap(cuts, b))
    marks = sorted(set(marks))
    out = []
    for k, (s0, s1) in enumerate(zip(marks, marks[1:]), 1):
        ext = snap(cuts, min(s1 + overlap, cuts[-1]))
        if ext < s1:
            ext = s1
        inner = [x for x in cuts if s0 <= x <= ext]
        shots = [{"i": j, "start": x, "end": y, "dur": round(y - x, 3)}
                 for j, (x, y) in enumerate(zip(inner, inner[1:]))]
        out.append({"id": f"sp{k:02d}", "own_start": s0, "own_end": s1,
                    "ext_end": ext, "cuts": inner, "shots": shots})
    return out


def grab(src, t, out, width):
    cmd = [config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
           "-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1",
           "-vf", f"scale={width}:-2", str(out)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        return False, "ffmpeg timeout"
    if r.returncode != 0:
        return False, (r.stderr.decode("utf-8", "replace").strip()
                       .splitlines() or ["ffmpeg loi"])[-1][:120]
    if not out.exists() or out.stat().st_size == 0:
        return False, "file rong"
    return True, ""


def do_span(src, out_dir, sp, width, force):
    """Mot span. KHONG BAO GIO nem exception - that bai la du lieu."""
    tag = sp["id"]
    existing = sorted(out_dir.glob(f"{tag}_*.jpg"))
    picks = []
    for sh in sp["shots"]:
        d = sh["dur"]
        picks.append((sh["i"], sh["start"] + min(0.5, max(0.05, d * 0.3)), "a"))
        if d >= LONG_SHOT:
            picks.append((sh["i"], sh["start"] + d / 2, "b"))
    if len(picks) > MAX_FRAMES:                     # bo frame PHU truoc
        picks = [p for p in picks if p[2] == "a"]
    if len(picks) > MAX_FRAMES:
        # Van qua tran: KHONG cat duoi danh sach. Moi shot van phai co frame -
        # thieu mot shot la mu mot doan phim, va neu no roi vao duoi span thi
        # seam hong theo. Giu het va bao cao de tran duoc nang.
        print(f"  {tag}: {len(picks)} shot > tran {MAX_FRAMES} - GIU HET, "
              f"khong cat; hay nang MAX_FRAMES.")

    # 2026-09-08: nhanh 'skip' truoc day tra ve [ten_file] con nhanh 'ok' tra ve
    # [{file, shot_i, t}]. Chay lai lan hai la DANH MAT anh xa shot cua moi span
    # bi bo qua - mot kieu du lieu khac nhau tuy duong di, dung cai bay cu.
    # Gio bo qua van dung CHINH picks de dung lai anh xa.
    if existing and not force and len(existing) == len(picks):
        return {"span": tag, "status": "skip",
                "frames": [{"file": f"{tag}_{n:02d}.jpg", "shot_i": si,
                            "t": round(t, 3)}
                           for n, (si, t, _k) in enumerate(picks)]}
    for p in existing:
        try:
            p.unlink()
        except OSError:
            pass
    frames, errs = [], []
    for n, (si, t, kind) in enumerate(picks):
        f = out_dir / f"{tag}_{n:02d}.jpg"
        ok, err = grab(src, t, f, width)
        if ok:
            frames.append({"file": f.name, "shot_i": si, "t": round(t, 3)})
        else:
            errs.append(f"[{n}] {err}")
    if not frames:
        return {"span": tag, "status": "fail", "frames": [],
                "reason": "; ".join(errs)[:300] or "khong trich duoc frame nao"}
    return {"span": tag, "status": "ok", "frames": frames,
            "want": len(picks), "got": len(frames),
            "reason": "; ".join(errs)[:200] if errs else ""}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--from", dest="a", type=float, required=True)
    ap.add_argument("--to", dest="b", type=float, required=True)
    ap.add_argument("--span", type=float, default=SPAN)
    ap.add_argument("--overlap", type=float, default=OVERLAP)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="frames/spans")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--prefix", default="sp",
                    help="tien to id span. Cho phep chay nhieu doan cua cung mot "
                         "phim ma khong dung id - spans.json duoc GOP, khong ghi de.")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    pdir = config.project_dir(a.project)
    cuts = sorted(json.load(io.open(pdir / "_cuts.json", encoding="utf-8"))["cuts"])
    cuts = [float(x) for x in cuts]
    spans = build_spans(cuts, a.a, a.b, a.span, a.overlap)
    for k, s in enumerate(spans, 1):
        s["id"] = f"{a.prefix}{k:02d}"
    nsh = sum(len(s["shots"]) for s in spans)
    print(f"{len(spans)} span | vung {a.a:.0f}-{a.b:.0f}s | {nsh} shot (ke ca overlap) "
          f"| {nsh/len(spans):.1f} shot/span")
    for s in spans[:3]:
        print(f"  {s['id']} own {hms(s['own_start'])}->{hms(s['own_end'])} "
              f"ext ->{hms(s['ext_end'])} ({len(s['shots'])} shot)")

    meta = {"project": a.project, "span_sec": a.span, "overlap_sec": a.overlap,
            "region": [a.a, a.b], "frame_width": a.width,
            "note": ("Moment thuoc span nao chua DIEM GIUA cua no. Vung overlap "
                     "CHI la ngu canh, khong duoc cham diem hai lan."),
            "spans": [{k: v for k, v in s.items() if k != "cuts"} for s in spans]}
    if a.dry_run:
        print("\n--dry-run: khong goi ffmpeg, khong ghi file.")
        return 0

    src = next((pdir / f"source{e}" for e in (".mp4", ".mkv", ".mov", ".m4v")
                if (pdir / f"source{e}").exists()), None)
    if src is None:
        print(f"khong co source video trong {pdir}")
        return 1
    out_dir = pdir / a.out
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(do_span, src, out_dir, s, a.width, a.force): s["id"]
                for s in spans}
        for fu in as_completed(futs):
            tag = futs[fu]
            try:
                results[tag] = fu.result()
            except Exception as e:
                results[tag] = {"span": tag, "status": "fail", "frames": [],
                                "reason": f"exception: {type(e).__name__}: {e}"}
    ok = [t for t, r in results.items() if r["status"] == "ok"]
    sk = [t for t, r in results.items() if r["status"] == "skip"]
    fa = [t for t, r in results.items() if r["status"] == "fail"]
    for s in meta["spans"]:
        r = results.get(s["id"], {})
        s["frames"] = r.get("frames", [])
        s["frame_status"] = r.get("status", "missing")
    # GOP, khong ghi de: mot phim co the duoc chia lam nhieu doan (prefix khac
    # nhau) va cac span da tag truoc do phai song sot. Ghi de o day tung lam
    # mat anh xa shot cua 18 span (2026-09-08).
    sp_path = pdir / "spans.json"
    if sp_path.exists():
        old = json.load(io.open(sp_path, encoding="utf-8"))
        byid = {s["id"]: s for s in old.get("spans", [])}
        for s in meta["spans"]:
            byid[s["id"]] = s
        meta["spans"] = sorted(byid.values(), key=lambda s: s["own_start"])
        oldreg = old.get("region_segments") or [old.get("region")]
        meta["region_segments"] = sorted(
            {tuple(r) for r in oldreg if r} | {tuple(meta["region"])})
        meta["region"] = [min(r[0] for r in meta["region_segments"]),
                          max(r[1] for r in meta["region_segments"])]
    else:
        meta["region_segments"] = [list(meta["region"])]
    meta["region_segments"] = [list(r) for r in meta["region_segments"]]
    io.open(sp_path, "w", encoding="utf-8").write(
        json.dumps(meta, ensure_ascii=False, indent=2))
    io.open(out_dir / "_spans_manifest.json", "w", encoding="utf-8").write(
        json.dumps({"project": a.project,
                    "spans": [results[t] for t in sorted(results)]},
                   ensure_ascii=False, indent=2))
    print(f"\nok {len(ok)} | bo qua {len(sk)} | LOI {len(fa)}")
    if fa:
        print(f"{len(fa)} span KHONG co frame nao:")
        for t in sorted(fa)[:10]:
            print(f"  {t}: {results[t]['reason'][:110]}")
    print(f"spans.json: {pdir/'spans.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
