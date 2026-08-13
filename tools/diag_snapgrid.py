"""Moc lam tay cach cu cat hinh that bao xa?

    python diag_snapgrid.py <project>

Lan dau se quet source.mp4 va LUU danh sach cu cat vao projects/<p>/_cuts.json.
Nhung lan sau doc thang tu cache, chay trong vai giay.

Cau hoi: 8 moc ma may "bo sot" o thi nghiem truoc - chung cach cu cat gan nhat
bao xa?
  - duoi ~3s  -> moc tay VON nam tren cu cat, chi lech nho. Luoi snap nan duoc.
  - 5-20s     -> moc tay la UOC CHUNG cua nguoi, khong phai bien hinh that.
                 Cua so bat dau giua canh -> vai giay dau con duoi canh truoc.
                 Day chinh la mot nguon drift.
  - >60s      -> may that su bo sot canh. Phai ha threshold roi quet lai.

Khong ghi gi vao pipeline (tru file cache _cuts.json).
"""
from __future__ import annotations

import io
import json
import sys
from bisect import bisect_left
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

THRESHOLD = 27.0
MIN_SCENE_LEN = 15


def pt(t) -> float:
    return sum(float(x) * m for x, m in zip(str(t).split(":"), (3600, 60, 1)))


def ms(s) -> str:
    return f"{int(s)//60:02d}:{int(s)%60:04.1f}"


def get_cuts(pdir: Path) -> list[float]:
    """Danh sach moc bat dau moi doan. Cache lai de khoi quet lai."""
    cache = pdir / "_cuts.json"
    if cache.exists():
        data = json.load(io.open(cache, encoding="utf-8"))
        print(f"doc cache: {len(data['cuts'])} cu cat "
              f"(threshold {data.get('threshold')})")
        return data["cuts"]

    src = pdir / "source.mp4"
    if not src.exists():
        print(f"khong thay {src}")
        return []
    try:
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector
    except ImportError:
        print('chua cai. chay:  pip install scenedetect --quiet')
        return []

    print(f"quet {src.name} lan dau (~14 phut), se cache lai...")
    video = open_video(str(src))
    sm = SceneManager()
    sm.add_detector(ContentDetector(threshold=THRESHOLD, min_scene_len=MIN_SCENE_LEN))
    sm.detect_scenes(video, show_progress=True)
    cuts = sorted({round(s.seconds, 3) for s, _e in sm.get_scene_list()}
                  | {round(e.seconds, 3) for _s, e in sm.get_scene_list()})
    json.dump({"threshold": THRESHOLD, "min_scene_len": MIN_SCENE_LEN, "cuts": cuts},
              io.open(cache, "w", encoding="utf-8"))
    print(f"\nda luu {len(cuts)} moc vao {cache.name}")
    return cuts


def nearest(cuts: list[float], t: float) -> tuple[float, float]:
    """(moc gan nhat, khoang cach)."""
    i = bisect_left(cuts, t)
    best, dist = None, float("inf")
    for j in (i - 1, i, i + 1):
        if 0 <= j < len(cuts):
            d = abs(cuts[j] - t)
            if d < dist:
                best, dist = cuts[j], d
    return best, dist


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    proj = sys.argv[1]
    pdir = config.project_dir(proj)
    cuts = get_cuts(pdir)
    if not cuts:
        return

    shots = json.load(io.open(pdir / "shots.json", encoding="utf-8-sig"))["shots"]
    marks = []
    for s in shots:
        if s.get("clip_start"):
            marks.append((s.get("id", "?"), "start", pt(s["clip_start"])))
        if s.get("clip_end"):
            marks.append((s.get("id", "?"), "end", pt(s["clip_end"])))

    buckets = {"<1s": 0, "1-3s": 0, "3-10s": 0, "10-30s": 0, ">30s": 0}
    rows = []
    for sid, kind, t in marks:
        _c, d = nearest(cuts, t)
        rows.append((d, sid, kind, t))
        if d < 1:
            buckets["<1s"] += 1
        elif d < 3:
            buckets["1-3s"] += 1
        elif d < 10:
            buckets["3-10s"] += 1
        elif d < 30:
            buckets["10-30s"] += 1
        else:
            buckets[">30s"] += 1

    print("=" * 68)
    print(f"{len(marks)} moc lam tay ({len(shots)} shot x start/end) "
          f"vs {len(cuts)} cu cat may tim duoc")
    print("-" * 68)
    print("KHOANG CACH toi cu cat gan nhat:")
    for k, v in buckets.items():
        pct = 100.0 * v / len(marks) if marks else 0
        bar = "#" * int(pct / 2)
        print(f"  {k:>7} : {v:3d}  ({pct:4.0f}%) {bar}")

    rows.sort(reverse=True)
    print("-" * 68)
    print("20 moc LECH NHAT (day la cho cua so bat dau giua canh):")
    for d, sid, kind, t in rows[:20]:
        print(f"  {ms(t)}  {kind:<5} lech {d:6.1f}s   {sid}")

    close = sum(v for k, v in buckets.items() if k in ("<1s", "1-3s"))
    print("=" * 68)
    print(f"Ket luan: {100.0*close/len(marks):.0f}% moc tay nam sat cu cat that.")
    print("  Cao (>70%)  -> moc tay von dung, luoi snap chi nan not phan con lai")
    print("  Thap        -> nhieu cua so bat dau giua canh = nguon drift co that")


if __name__ == "__main__":
    main()
