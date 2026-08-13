"""Thu nghiem: cat shot tu dong co du tot de thay cho catalogue lam tay khong?

    python diag_scenedetect.py <project>

Khong ghi gi vao pipeline. Chi doc source.mp4 + shots.json + beats_proposal.md
roi in ra bao cao so sanh.

Tra loi ba cau:
  1. RECALL  - may co tim ra cac moc ban da chon bang tay khong?
  2. THEM    - may tim them bao nhieu, va co lap duoc beat dang trong khong?
  3. RAC     - bao nhieu doan qua ngan de dung lam shot?

Cai dat truoc khi chay:
    pip install "scenedetect[opencv]" --quiet
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

TOL = 2.0        # giay - coi la "khop" neu lech duoi nguong nay
MIN_LEN = 2.0    # giay - ngan hon thi khong dung duoc lam shot


def pt(t) -> float:
    return sum(float(x) * m for x, m in zip(str(t).split(":"), (3600, 60, 1)))


def ms(s) -> str:
    return f"{int(s)//60:02d}:{int(s)%60:02d}"


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    proj = sys.argv[1]
    pdir = config.project_dir(proj)
    src = pdir / "source.mp4"
    if not src.exists():
        print(f"khong thay {src} - da xoa bang cleanup roi?")
        return

    try:
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector
    except ImportError:
        print('chua cai. chay:  pip install "scenedetect[opencv]" --quiet')
        return

    print(f"dang quet {src.name} ... (phim 2h mat vai phut)")
    video = open_video(str(src))
    sm = SceneManager()
    sm.add_detector(ContentDetector(threshold=27.0, min_scene_len=15))
    sm.detect_scenes(video, show_progress=True)
    scenes = sm.get_scene_list()
    auto = [(s.get_seconds(), e.get_seconds()) for s, e in scenes]
    print()

    # ---- catalogue lam tay ------------------------------------------------
    hand = []
    sp = pdir / "shots.json"
    if sp.exists():
        for s in json.load(io.open(sp, encoding="utf-8-sig")).get("shots", []):
            if s.get("clip_start"):
                hand.append(pt(s["clip_start"]))
    hand.sort()

    usable = [(a, b) for a, b in auto if (b - a) >= MIN_LEN]
    junk = len(auto) - len(usable)

    print("=" * 66)
    print(f"may cat duoc : {len(auto)} doan  ({len(usable)} dung duoc, "
          f"{junk} ngan hon {MIN_LEN}s -> rac)")
    print(f"ban lam tay  : {len(hand)} shot")

    # ---- 1. RECALL --------------------------------------------------------
    starts = [a for a, _b in usable]
    hit = [h for h in hand if any(abs(h - a) <= TOL for a in starts)]
    miss = [h for h in hand if h not in hit]
    pct = 100.0 * len(hit) / len(hand) if hand else 0.0
    print("-" * 66)
    print(f"1. RECALL: may tim trung {len(hit)}/{len(hand)} moc cua ban "
          f"({pct:.0f}%, sai so {TOL}s)")
    if miss:
        print("   may BO SOT: " + ", ".join(ms(m) for m in miss[:15])
              + (" ..." if len(miss) > 15 else ""))
        print("   -> mo mấy mốc này xem: canh cham, mo dan, hay quay dai khong cat?")

    # ---- 2. beat dang trong co duoc lap khong -----------------------------
    try:
        from pipeline import draft as D
        bt = D.beat_times(proj)
        bounds = bt.get("ordered") or []
    except Exception as e:
        bounds = []
        print(f"   (khong doc duoc beat map: {e})")

    if bounds:
        dur = D._film_duration(proj) or (bounds[-1][1] + 600.0)
        print("-" * 66)
        print("2. BEAT DANG TRONG - may co lap duoc khong?")
        fixed = still = 0
        for i, (bid, a) in enumerate(bounds):
            b = bounds[i + 1][1] if i + 1 < len(bounds) else dur
            n_hand = sum(1 for h in hand if a <= h < b)
            if n_hand:
                continue
            n_auto = sum(1 for s, _e in usable if a <= s < b)
            flag = "LAP DUOC" if n_auto else "van trong"
            if n_auto:
                fixed += 1
            else:
                still += 1
            print(f"   {bid} ({ms(a)}-{ms(b)}): tay 0 shot -> may {n_auto} "
                  f"doan  [{flag}]")
        print(f"   => lap duoc {fixed} beat, con trong {still}")

    # ---- 3. do dai doan ---------------------------------------------------
    if usable:
        lens = sorted(b - a for a, b in usable)
        mid = lens[len(lens) // 2]
        print("-" * 66)
        print(f"3. DO DAI doan may cat: ngan nhat {lens[0]:.1f}s | "
              f"giua {mid:.1f}s | dai nhat {lens[-1]:.1f}s")
        print(f"   so doan >= 5s: {sum(1 for x in lens if x >= 5)}  "
              f"(du dai de gan mot cau narration)")

    print("=" * 66)
    print("Doc ket qua:")
    print("  RECALL cao (>80%) + lap duoc beat trong  -> huong nay dung, lam tiep")
    print("  RECALL thap                              -> may cat khac cach ban chon")
    print("  Lap duoc it beat trong                   -> khong giai quyet dung van de")


if __name__ == "__main__":
    main()
