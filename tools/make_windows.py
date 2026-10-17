# -*- coding: utf-8 -*-
"""
make_windows.py - gom cac cu cat lien tiep trong `_cuts.json` thanh MOMENT
(cua so catalogue), ghi ra `projects/<p>/windows.json`. KHONG dung LLM.

Vi sao ton tai
--------------
Vong tag may da chay duoc 231/231 tren badgenius2017, nhung catalogue may
KHONG co clip_start/clip_end - nen khong mot dong draft nao bind vao no duoc.
Lan A/B truoc muon windows tu catalogue NGUOI qua `_manifest.json`, nen no
khong doc lap. File nay cat phu thuoc do.

Van de that su la GOM, khong phai PHAT HIEN
-------------------------------------------
`_cuts.json` da co du moi cu cat may quay. Nhung mot cua so catalogue la MOT
KHOANH KHAC gom nhieu cu cat:

    badgenius2017          shot may quay trung vi 3.00s -> cua so nguoi 10.0s
    howtomakemillions2024  shot may quay trung vi 8.04s -> cua so nguoi 22.2s

DAU VAO DUOC PHEP - CHI HAI FILE
--------------------------------
    _cuts.json, transcript.json

CAM: shots.json (la dap an), beats_proposal.md (trong luong that duoc viet SAU
catalogue), draft.json, timeline.json. `gate_selftest.py` grep ma nguon file
nay de chan viec vo tinh them vao sau nay.

Tin hieu: KHONG phai khoang lang
--------------------------------
De bai goi y "khoang lang la tin hieu hop ly cho noi mot moment ket thuc".
Do xong trước khi xay:

    film                     cu cat roi vao khoang lang | cua so nguoi
    badgenius2017                        402            |     231
    howtomakemillions2024                 34            |     280   <-- 12%

howtomakemillions co 94% thoi luong la tieng noi. Luat dua tren khoang lang se
dau MOT phim va truot phim kia ngay tu thiet ke. Nen tin hieu dung la RANH GIOI
SEGMENT cua transcript (ket cau loi noi), ke ca khi gap = 0:

    cu cat nam trong 1.0s cua mot ranh gioi segment:
        badgenius2017          511/1812 (28%) -> 3.5 shot/moment
        howtomakemillions2024  207/614  (34%) -> 3.0 shot/moment

Cung MOT hang so cho hai kieu dung phim nguoc nhau, va so shot/moment TU NO roi
ve ~3 - dung bang trung vi cua nguoi - ma khong he dat muc tieu thoi luong.

CONG BO (docs/WINDOW_GROUPING_CRITERION.md): toi da xem thong ke cua so nguoi
TRUOC khi thiet ke, va toi chon TOL=1.0s SAU khi thay no cho ~3 shot/moment.
Do la fitting o muc nhe. Cai dung vung khong phai con so 1.0 ma la viec CUNG
mot con so chay duoc tren ca hai kieu dung phim - do mới la phan khong tam
thuong, va do chinh la dieu dieu khoan STYLE-TUNING kiem tra.

Granularity (bai hoc 2026-09-05)
--------------------------------
Mot cu cat hong chi duoc lam hong NHUNG cua so ke no. Cu cat hong duoc cach ly
theo CHI SO trong mang (vi gia tri khong doc duoc thi khong biet no o dau, nhung
biet no nam giua cut[i-1] va cut[i+1]), cua so chong len vung do bi danh dau
`degraded` - KHONG im lang, KHONG abort ca lo.

Dung:
    python tools/make_windows.py <project>
    python tools/make_windows.py <project> --dry-run
"""
from __future__ import annotations
import argparse, io, json, math, os, statistics, sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# --- hang so duy nhat, co nghia vat ly, KHONG theo phim -----------------------
# Do lech cho phep giua mot cu cat hinh anh va ranh gioi loi noi ma no phuc vu.
# Dung tho thuong cat dung tren hoac sat canh cau noi.
TOL = 1.0

ALLOWED_INPUTS = ("_cuts.json", "transcript.json")
FORBIDDEN_INPUTS = ("shots.json", "beats_proposal.md", "draft.json",
                    "timeline.json", "script.txt", "names.json")


def hms(s: float) -> str:
    s = max(0.0, float(s))
    return f"{int(s)//3600:02d}:{(int(s)%3600)//60:02d}:{s%60:06.3f}"


# ---------------------------------------------------------------- doc dau vao
def load_cuts(pdir: Path):
    """Doc _cuts.json. Parse TUNG phan tu - mot gia tri hong khong lam chet lo.

    Tra ve (cuts_hop_le, danh_sach_hong). Moi muc hong:
        {"index": i, "raw": <gia tri goc>, "reason": str,
         "after": float|None, "before": float|None}
    `after`/`before` la hai moc hop le ke no -> vung bi anh huong.
    """
    cp = pdir / "_cuts.json"
    if not cp.exists():
        raise FileNotFoundError(f"khong co {cp}")
    raw = json.load(io.open(cp, encoding="utf-8-sig"))
    arr = raw["cuts"] if isinstance(raw, dict) else raw
    if not isinstance(arr, list):
        raise ValueError("_cuts.json: truong 'cuts' khong phai mang")

    vals, bad = [], []
    for i, v in enumerate(arr):
        try:
            if isinstance(v, bool) or v is None:
                raise TypeError(f"kieu {type(v).__name__}")
            f = float(v)
            if math.isnan(f) or math.isinf(f):
                raise ValueError("NaN/Inf")
            if f < 0:
                raise ValueError(f"am ({f})")
        except Exception as e:
            bad.append({"index": i, "raw": repr(v)[:60],
                        "reason": f"moc khong doc duoc: {e}"})
            continue
        vals.append((i, f))

    # Khong don-dieu la LOI DU LIEU THAT (bai hoc gonegirl M1) - cach ly, khong
    # lang le sort de giau di.
    good, last = [], None
    for i, f in vals:
        if last is not None and f < last:
            bad.append({"index": i, "raw": repr(f),
                        "reason": f"khong don dieu: {f:.3f} < moc truoc {last:.3f}"})
            continue
        good.append((i, f))
        last = f

    # gan vung anh huong cho tung muc hong
    gi = [i for i, _ in good]
    gv = {i: f for i, f in good}
    for b in bad:
        prev = max((i for i in gi if i < b["index"]), default=None)
        nxt = min((i for i in gi if i > b["index"]), default=None)
        b["after"] = gv[prev] if prev is not None else None
        b["before"] = gv[nxt] if nxt is not None else None

    cuts = sorted({f for _i, f in good})
    if len(cuts) < 2:
        raise ValueError(f"_cuts.json chi con {len(cuts)} moc hop le - khong gom duoc")
    return cuts, bad


def load_boundaries(pdir: Path):
    """Ranh gioi segment cua transcript (ca start va end). Thieu transcript thi
    tra ve None - va goi ten viec do, khong im lang (D-GREEN)."""
    tp = pdir / "transcript.json"
    if not tp.exists():
        return None, "KHONG co transcript.json"
    try:
        segs = json.load(io.open(tp, encoding="utf-8-sig")).get("segments") or []
    except Exception as e:
        return None, f"transcript.json khong doc duoc ({e})"
    B = set()
    for s in segs:
        for k in ("start", "end"):
            try:
                v = float(s[k])
                if not (math.isnan(v) or math.isinf(v)):
                    B.add(v)
            except Exception:
                pass
    if not B:
        return None, "transcript.json khong co moc segment hop le"
    return sorted(B), f"{len(segs)} segment -> {len(B)} ranh gioi"


# ------------------------------------------------------------------- gom nhom
def nearest(sorted_vals, x: float) -> float:
    import bisect
    i = bisect.bisect_left(sorted_vals, x)
    c = [sorted_vals[j] for j in (i - 1, i) if 0 <= j < len(sorted_vals)]
    return min((abs(x - y) for y in c), default=float("inf"))


def group(cuts, bounds, tol=TOL):
    """Gom shot may quay thanh moment.

    Tham so suy ra TU PHIM, khong phai hang so dan san:
        d_min = max(2.0, trung vi shot)   mot moment >= mot shot dien hinh
        d_max = max(20.0, 8x trung vi)    CHAN an toan, khong phai muc tieu
    Ty le break do `maxdur` duoc bao cao: neu no lon thi day la luat thoi luong
    doi lot luat loi noi, va ket qua phai doc theo kieu khac.
    """
    durs = [b - a for a, b in zip(cuts, cuts[1:]) if b > a]
    med = statistics.median(durs) if durs else 3.0
    d_min = max(2.0, med)
    d_max = max(20.0, 8.0 * med)

    def breakable(t: float) -> bool:
        return bounds is not None and nearest(bounds, t) <= tol

    wins, start, n_cuts, reason = [], cuts[0], 0, "start"
    for t in cuts[1:-1]:
        n_cuts += 1
        dur = t - start
        if dur < d_min:
            continue
        sp = breakable(t)
        if sp or dur >= d_max:
            wins.append({"a": start, "b": t, "n_cuts": n_cuts,
                         "break_reason": "speech" if sp else "maxdur"})
            start, n_cuts, reason = t, 0, "speech" if sp else "maxdur"
    wins.append({"a": start, "b": cuts[-1], "n_cuts": n_cuts,
                 "break_reason": "end"})

    # cua so cuoi qua ngan -> nhap vao cai truoc (khong de lai manh vun)
    if len(wins) > 1 and (wins[-1]["b"] - wins[-1]["a"]) < d_min:
        tail = wins.pop()
        wins[-1]["b"] = tail["b"]
        wins[-1]["n_cuts"] += tail["n_cuts"] + 1
    return wins, {"median_shot": med, "d_min": d_min, "d_max": d_max, "tol": tol}


def mark_degraded(wins, bad):
    """Cu cat hong lam hong DUNG nhung cua so chong len vung cua no."""
    for b in bad:
        lo = b["after"] if b["after"] is not None else -float("inf")
        hi = b["before"] if b["before"] is not None else float("inf")
        for w in wins:
            if w["a"] < hi and w["b"] > lo:
                w.setdefault("degraded", []).append(
                    f"cut[{b['index']}] {b['reason']}")
    return wins


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--out", default="windows.json")
    ap.add_argument("--tol", type=float, default=TOL)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    pdir = config.project_dir(a.project)
    cuts, bad = load_cuts(pdir)
    bounds, bnote = load_boundaries(pdir)
    if bounds is None:
        print(f"CANH BAO: {bnote} - khong co tin hieu loi noi. Moi diem ngat se "
              f"den tu CHAN THOI LUONG. Day la gom theo thoi luong, khong phai "
              f"gom theo khoanh khac; doc ket qua theo dung dieu do.")
    else:
        print(f"transcript: {bnote}")
    if bad:
        print(f"{len(bad)} moc cat HONG - cach ly, chi lam hong cua so ke no:")
        for b in bad[:6]:
            print(f"  cut[{b['index']}]={b['raw']}: {b['reason']}")

    wins, par = group(cuts, bounds, a.tol)
    wins = mark_degraded(wins, bad)

    durs = [w["b"] - w["a"] for w in wins]
    by_speech = sum(1 for w in wins if w["break_reason"] == "speech")
    by_max = sum(1 for w in wins if w["break_reason"] == "maxdur")
    deg = sum(1 for w in wins if w.get("degraded"))
    span = cuts[-1] - cuts[0]
    stats = {
        "n_windows": len(wins),
        "n_cuts_valid": len(cuts), "n_cuts_bad": len(bad),
        "median_window": round(statistics.median(durs), 2),
        "mean_window": round(sum(durs) / len(durs), 2),
        "min_window": round(min(durs), 2), "max_window": round(max(durs), 2),
        "mean_cuts_per_window": round(sum(w["n_cuts"] for w in wins) / len(wins), 2),
        "mean_shots_per_window": round((len(cuts) - 1) / len(wins), 2),
        "breaks_by_speech": by_speech, "breaks_by_maxdur": by_max,
        "pct_breaks_by_speech": round(100 * by_speech / max(1, by_speech + by_max), 1),
        "degraded_windows": deg,
        "coverage_pct": round(100 * sum(durs) / span, 1) if span else 0.0,
    }
    print(f"\n{stats['n_windows']} cua so | trung vi {stats['median_window']}s "
          f"(min {stats['min_window']} max {stats['max_window']}) | "
          f"{stats['mean_shots_per_window']} shot/cua so")
    print(f"diem ngat: loi noi {by_speech} ({stats['pct_breaks_by_speech']}%) | "
          f"chan thoi luong {by_max}")
    if stats["pct_breaks_by_speech"] < 50:
        print("  LUU Y: duoi 50% diem ngat den tu loi noi - day dang la luat "
              "THOI LUONG doi lot luat loi noi.")
    if deg:
        print(f"{deg} cua so bi danh dau degraded (co moc cat hong trong vung)")

    if a.dry_run:
        print("\n--dry-run: khong ghi file.")
        for w in wins[:8]:
            print(f"  {hms(w['a'])} -> {hms(w['b'])}  {w['b']-w['a']:5.1f}s "
                  f"{w['n_cuts']} cut  {w['break_reason']}")
        return 0

    out = {
        "project": a.project,
        "generated_by": "tools/make_windows.py",
        "inputs_used": list(ALLOWED_INPUTS),
        "note": ("Cua so MAY, gom tu _cuts.json + transcript.json. KHONG doc "
                 "shots.json/beats_proposal.md. Day la GOM, khong phai CHON - "
                 "phu toan phim; viec chon khoanh khac nao dang ke la piece 3."),
        "params": par, "stats": stats,
        "bad_cuts": bad,
        "windows": [{
            "id": f"w{i:04d}",
            "clip_start": hms(w["a"]), "clip_end": hms(w["b"]),
            "start_sec": round(w["a"], 3), "end_sec": round(w["b"], 3),
            "raw_duration_sec": round(w["b"] - w["a"], 3),
            "n_cuts": w["n_cuts"], "break_reason": w["break_reason"],
            **({"degraded": w["degraded"]} if w.get("degraded") else {}),
        } for i, w in enumerate(wins, 1)],
    }
    op = pdir / a.out
    io.open(op, "w", encoding="utf-8").write(
        json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nda ghi {op}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
