# -*- coding: utf-8 -*-
"""
extract_shot_frames.py - trich frame CHO TUNG SHOT, chay song song, granularity
theo tung shot.

Vi sao ton tai
--------------
Vong tag da doc lap theo shot (moi subagent mot context, mot file ra). Neu khau
trich frame van chay tuan tu / theo lo thi no tro thanh chinh cai nut co chai ma
vong tag vua go bo, va mot lan ffmpeg loi se keo sap ca lo.

Hai dieu bat buoc (2026-09-05):

1. **Granularity theo tung shot.** Mot shot trich loi chi mat SHOT DO. Trang
   thai tung shot ghi vao `_manifest.json`; chay lai chi lam nhung shot con
   thieu. Khong bao gio abort ca lo vi mot loi.

2. **BUOC LAY MAU KHONG PHAI HANG SO.** Doc trung vi shot tu `_cuts.json` roi
   suy ra buoc - dung cong thuc `run.ps1:163` da dung o khau overview:
       step = max(1.0, round(median * 2/3, 1))
   Bad Genius trung vi 3.0s -> luoi 5s mu voi 37% so shot va lam mat han tinh
   tiet B58. Gia Tai Cua Ngoai giu canh toi 27s - cung mot hang so sai ca hai
   dau, theo hai huong nguoc nhau.

Dung:
    python tools/extract_shot_frames.py <project> [--limit N] [--workers 8]
    python tools/extract_shot_frames.py <project> --dry-run
"""
from __future__ import annotations
import argparse, io, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

FALLBACK_STEP = 5.0
MIN_FRAMES, MAX_FRAMES = 2, 8


def pt(ts: str) -> float:
    p = [float(x) for x in str(ts).split(":")]
    while len(p) < 3:
        p.insert(0, 0.0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def hms(s: float) -> str:
    return f"{int(s)//3600:02d}:{(int(s)%3600)//60:02d}:{s%60:06.3f}"


def derive_step(pdir: Path):
    """Same derivation as run.ps1:158-168. Returns (step, note)."""
    cp = pdir / "_cuts.json"
    if not cp.exists():
        return FALLBACK_STEP, ("khong co _cuts.json - dung buoc mac dinh "
                               f"{FALLBACK_STEP}s (CHUA do trung vi)")
    try:
        c = sorted(json.load(io.open(cp, encoding="utf-8"))["cuts"])
    except Exception as e:
        return FALLBACK_STEP, f"_cuts.json khong doc duoc ({e}) - buoc mac dinh"
    d = sorted(b - a for a, b in zip(c, c[1:]) if b > a)
    if not d:
        return FALLBACK_STEP, "_cuts.json khong co khoang hop le - buoc mac dinh"
    med = d[len(d) // 2]
    step = max(1.0, round(med * 2 / 3, 1))
    # HAI dai luong KHAC NHAU - run.ps1:164 gop chung lam mot va bao qua gap doi.
    #   shorter : ty le shot NGAN HON luoi. KHONG phai ty le bi bo sot.
    #   missed  : ky vong ty le shot KHONG chua diem luoi nao. Mot shot dai L<G
    #             dat ngau nhien so voi luoi thi truot voi xac suat (G-L)/G.
    # Bad Genius: shorter=74.2% nhung missed=37.0%. Con so 37% moi la con so da
    # ghi trong docs/STRESS_badgenius.md va moi la con so dung.
    G = 5.0
    shorter = sum(1 for x in d if x < G) / len(d)
    missed = sum((G - x) / G for x in d if x < G) / len(d)
    return step, (f"{len(c)} cu cat | trung vi shot {med:.1f}s | "
                  f"ngan hon luoi 5s: {shorter*100:.0f}% | "
                  f"KY VONG khong bao gio lay mau o luoi 5s: {missed*100:.0f}% "
                  f"-> buoc {step}s")


def n_frames(dur: float, step: float) -> int:
    return max(MIN_FRAMES, min(MAX_FRAMES, int(dur / max(0.1, step)) + 1))


def grab(src: Path, t: float, out: Path) -> tuple[bool, str]:
    cmd = [config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
           "-ss", hms(t), "-i", str(src), "-frames:v", "1",
           "-vf", "scale=768:-2", str(out)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        return False, "ffmpeg timeout 120s"
    if r.returncode != 0:
        return False, (r.stderr.decode("utf-8", "replace").strip()
                       .splitlines() or ["ffmpeg loi khong ro"])[-1][:120]
    if not out.exists() or out.stat().st_size == 0:
        return False, "ffmpeg bao OK nhung file rong"
    return True, ""


def do_shot(src: Path, out_dir: Path, tag: str, a: float, b: float,
            step: float, force: bool) -> dict:
    """Mot shot. KHONG BAO GIO nem exception ra ngoai - that bai la du lieu."""
    dur = max(0.0, b - a)
    nf = n_frames(dur, step)
    existing = sorted(out_dir.glob(f"{tag}_*.jpg"))
    if existing and not force:
        return {"shot": tag, "status": "skip", "frames": [p.name for p in existing],
                "reason": "da co frame"}
    for p in existing:
        try:
            p.unlink()
        except OSError:
            pass
    frames, errs = [], []
    for j in range(nf):
        t = a + 0.4 + (dur - 0.8) * (j / max(1, nf - 1)) if dur > 1.0 else a
        f = out_dir / f"{tag}_{j:02d}.jpg"
        ok, err = grab(src, t, f)
        if ok:
            frames.append(f.name)
        else:
            errs.append(f"[{j}] {err}")
    if not frames:
        return {"shot": tag, "status": "fail", "frames": [],
                "reason": "; ".join(errs)[:300] or "khong trich duoc frame nao"}
    return {"shot": tag, "status": "ok", "frames": frames,
            "want": nf, "got": len(frames),
            "reason": ("; ".join(errs)[:200] if errs else "")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="frames/tagging")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="tinh buoc + so frame, KHONG goi ffmpeg")
    a = ap.parse_args()

    pdir = config.project_dir(a.project)
    sp = pdir / "shots.json"
    if not sp.exists():
        print(f"khong co {sp}")
        return 1
    src = None
    for ext in (".mp4", ".mkv", ".mov", ".m4v"):
        if (pdir / f"source{ext}").exists():
            src = pdir / f"source{ext}"
            break
    if src is None and not a.dry_run:
        print(f"khong co source video trong {pdir}")
        return 1

    raw = [s for s in json.load(io.open(sp, encoding="utf-8-sig"))["shots"]
           if s.get("clip_start") and s.get("clip_end")]

    # Phan tich moc thoi gian TRUOC khi sort, va khong bao gio de mot shot hong
    # lam chet ca lo.
    # 2026-09-05: ban dau sort truc tiep bang pt(); mot moc thoi gian sai dinh
    # dang lam ValueError o SORT - tuc la TRUOC khi bat ky xu ly theo-shot nao
    # chay, nen try/except trong do_shot() khong bao gio duoc dung toi va CA LO
    # chet. Dung cai loi ma tool nay sinh ra de chan: granularity phai bat dau
    # tu luc DOC du lieu, khong phai tu luc goi ffmpeg.
    parsed, badts = [], []
    for s in raw:
        try:
            t0, t1 = pt(s["clip_start"]), pt(s["clip_end"])
        except Exception as e:
            badts.append((s, f"moc thoi gian khong doc duoc: {e}"))
            continue
        if t1 <= t0:
            badts.append((s, f"cua so rong/am: {s['clip_start']} -> {s['clip_end']}"))
            continue
        parsed.append((t0, t1, s))
    parsed.sort(key=lambda x: x[0])
    if a.limit:
        parsed = parsed[:a.limit]
    shots = [s for _t0, _t1, s in parsed]
    if badts:
        print(f"{len(badts)} shot bi loai truoc khi trich (moc thoi gian hong) "
              f"- van duoc ghi vao manifest, khong lam chet lo.")

    step, note = derive_step(pdir)
    print(f"buoc lay mau: {note}")

    durs = [pt(s["clip_end"]) - pt(s["clip_start"]) for s in shots]
    plan = [n_frames(d, step) for d in durs]
    print(f"{len(shots)} shot | frame/shot: min {min(plan)} max {max(plan)} "
          f"tong {sum(plan)}")
    if a.dry_run:
        print("\n--dry-run: khong goi ffmpeg.")
        for s, d, n in list(zip(shots, durs, plan))[:8]:
            print(f"  {s.get('id','?'):<22} {d:5.1f}s -> {n} frame")
        if len(shots) > 8:
            print(f"  ... con {len(shots)-8} shot")
        return 0

    out_dir = pdir / a.out
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for k, (s, why) in enumerate(badts, 1):
        tag = f"badts{k:03d}"
        results[tag] = {"shot": tag, "status": "fail", "frames": [],
                        "reason": why, "clip_start": str(s.get("clip_start")),
                        "clip_end": str(s.get("clip_end")),
                        "shot_id": s.get("id", "")}
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {}
        for i, (t0, t1, s) in enumerate(parsed, 1):
            tag = f"shot{i:03d}"
            futs[ex.submit(do_shot, src, out_dir, tag, t0, t1,
                           step, a.force)] = (tag, s)
        for fu in as_completed(futs):
            tag, s = futs[fu]
            try:
                r = fu.result()
            except Exception as e:                      # phao cuoi
                r = {"shot": tag, "status": "fail", "frames": [],
                     "reason": f"exception: {type(e).__name__}: {e}"}
            r["clip_start"] = s["clip_start"]
            r["clip_end"] = s["clip_end"]
            r["shot_id"] = s.get("id", "")
            results[tag] = r

    ok = [t for t, r in results.items() if r["status"] == "ok"]
    sk = [t for t, r in results.items() if r["status"] == "skip"]
    fa = [t for t, r in results.items() if r["status"] == "fail"]
    short = [t for t, r in results.items()
             if r["status"] == "ok" and r.get("got", 0) < r.get("want", 0)]

    man = out_dir / "_manifest.json"
    io.open(man, "w", encoding="utf-8").write(json.dumps(
        {"project": a.project, "step": step, "note": note,
         "shots": [results[t] for t in sorted(results)]},
        ensure_ascii=False, indent=2))

    print(f"\nok {len(ok)} | bo qua {len(sk)} | LOI {len(fa)}")
    if short:
        print(f"thieu frame (van dung duoc): {', '.join(sorted(short)[:10])}")
    if fa:
        # D-GREEN: that bai phai duoc goi ten, khong bao gio im lang
        print(f"\n{len(fa)} shot KHONG co frame nao:")
        for t in sorted(fa)[:10]:
            print(f"  {t} ({results[t]['clip_start']}): {results[t]['reason'][:110]}")
        print("  -> chay lai chi nhung shot nay; khong can lam lai ca lo.")
    print(f"\nmanifest: {man}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
