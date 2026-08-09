"""Dung bo de MU de cham vision model tag shot.

    python make_vision_eval.py <project> [so_shot]     # mac dinh 20

Y tuong: ban da co 293 shot tag tay qua 4 phim. Do la ground truth co san -
du de CHAM mot vision model thay vi doan xem no co dung khong.

Script lam 3 viec:
  1. Chon ngau nhien N shot tu shots.json (seed co dinh -> lap lai duoc)
  2. Trich 3 frame moi shot (dau / giua / cuoi) bang ffmpeg
  3. Ghi VISION_EVAL.md - phieu tra loi MU: co anh, co bang tu vung,
     KHONG co dap an. Va _vision_truth.json de cham diem sau

Vi sao mu: neu model nhin thay tag tay truoc, no se dong y voi tag do.
Do la filter, khong phai kiem tra (RULES B4). Bo de phai mu thi ket qua
moi co nghia.

Sau khi chay:
  - Dua thu muc vision_eval/ + VISION_EVAL.md cho OpenCode (hoac model nao khac)
  - No dien cot depicts / chars / action cho tung shot
  - Roi chay score_vision_eval.py de cham
"""
from __future__ import annotations

import io
import json
import random
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

SEED = 20260809
DEPICTS_VOCAB = ["action", "aftermath", "dialogue", "discovery", "emotion",
                 "establishing", "montage", "reaction", "reveal", "setup",
                 "transition"]


def pt(t) -> float:
    return sum(float(x) * m for x, m in zip(str(t).split(":"), (3600, 60, 1)))


def hms(s: float) -> str:
    return f"{int(s)//3600:02d}:{(int(s)%3600)//60:02d}:{s%60:06.3f}"


def grab(src: Path, t: float, out: Path) -> bool:
    cmd = [config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
           "-ss", hms(t), "-i", str(src), "-frames:v", "1",
           "-vf", "scale=768:-2", str(out)]
    return subprocess.run(cmd, capture_output=True).returncode == 0


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    proj = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    pdir = config.project_dir(proj)
    src = pdir / "source.mp4"
    if not src.exists():
        print(f"khong thay {src}")
        return

    shots = [s for s in json.load(io.open(pdir / "shots.json", encoding="utf-8-sig"))["shots"]
             if s.get("clip_start") and s.get("clip_end")]
    random.seed(SEED)
    pick = random.sample(shots, min(n, len(shots)))
    pick.sort(key=lambda s: pt(s["clip_start"]))

    out_dir = pdir / "vision_eval"
    out_dir.mkdir(exist_ok=True)
    truth, rows = {}, []

    for i, s in enumerate(pick, 1):
        a, b = pt(s["clip_start"]), pt(s["clip_end"])
        tag = f"shot{i:02d}"
        frames = []
        for label, t in (("a", a + 0.5), ("b", (a + b) / 2), ("c", max(a, b - 0.5))):
            f = out_dir / f"{tag}_{label}.jpg"
            if grab(src, t, f):
                frames.append(f.name)
        truth[tag] = {"id": s.get("id"), "clip_start": s["clip_start"],
                      "clip_end": s["clip_end"], "depicts": s.get("depicts", []),
                      "chars": s.get("chars", []), "action": s.get("action", "")}
        rows.append((tag, s["clip_start"], s["clip_end"], round(b - a, 1), frames))
        print(f"  {tag}: {len(frames)} frame")

    json.dump(truth, io.open(pdir / "_vision_truth.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    md = [f"# VISION EVAL - {proj}", "",
          "Nhin anh va dien 3 cot cho TUNG shot. Khong co dap an o day - "
          "dung doan theo transcript, chi tra loi tu cai NHIN THAY.", "",
          "## Tu vung `depicts` (chi duoc dung tu trong day, 1-2 tu moi shot)", "",
          "`" + "`, `".join(DEPICTS_VOCAB) + "`", "",
          "Xem `docs/TAGGING_GUIDE.md` de biet khi nao dung tu nao.", "",
          "## Cot `chars`", "",
          "Ten nhan vat NHIN THAY RO trong khung hinh. Khong chac thi ghi "
          "`(khong ro)` - dung doan. (RULES A5: admit uncertainty + flag.)", "",
          "## Cot `action`", "",
          "Mot cau ta cai dang xay ra tren man hinh.", "", "---", ""]

    for tag, cs, ce, dur, frames in rows:
        md += [f"### {tag}  ({cs} -> {ce}, {dur}s)", ""]
        md += [f"![{f}](vision_eval/{f})" for f in frames]
        md += ["", "- depicts: ", "- chars: ", "- action: ", ""]

    (pdir / "VISION_EVAL.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\nDa tao:")
    print(f"  {pdir / 'VISION_EVAL.md'}      <- phieu tra loi (mu)")
    print(f"  {out_dir}          <- {len(rows)*3} frame")
    print(f"  {pdir / '_vision_truth.json'}  <- dap an, DUNG dua cho model")


if __name__ == "__main__":
    main()
