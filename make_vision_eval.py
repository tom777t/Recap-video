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

import argparse
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


def _sample_shots(pdir, n, seed):
    shots = [s for s in json.load(io.open(pdir / "shots.json", encoding="utf-8-sig"))["shots"]
             if s.get("clip_start") and s.get("clip_end")]
    random.seed(seed)
    pick = random.sample(shots, min(n, len(shots)))
    pick.sort(key=lambda s: pt(s["clip_start"]))
    return pick


def _frames_for(src, out_dir, tag, a, b, nf):
    frames = []
    span = max(0.0, b - a)
    for j in range(nf):
        t = a + 0.4 + (span - 0.8) * (j / max(1, nf - 1)) if span > 1.0 else a
        f = out_dir / f"{tag}_{j:02d}.jpg"
        if grab(src, t, f):
            frames.append(f.name)
    return frames


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--shots", type=int, default=20)
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--examples-from", default=None,
                    help="another project to draw SOLVED examples from. The "
                         "disagreements measured so far are about CONVENTION, not "
                         "perception - which moment of a composite window counts as "
                         "primary - and a convention is learned from examples, not "
                         "from a vocabulary list. Must be a different film, or the "
                         "examples leak the answers.")
    ap.add_argument("--examples", type=int, default=8)
    args = ap.parse_args()

    proj = args.project
    pdir = config.project_dir(proj)
    src = pdir / "source.mp4"
    if not src.exists():
        print(f"khong thay {src}")
        return

    out_dir = pdir / "vision_eval"
    out_dir.mkdir(exist_ok=True)
    # Clear first. A previous run with a different --shots count leaves frames
    # behind under names this run never overwrites, and they then sit in the
    # sheet next to the current ones - a still from an unrelated part of the
    # film, presented as if it belonged to the window being judged. That is a
    # measuring tool corrupting its own measurement.
    stale = list(out_dir.glob("*.jpg"))
    for f in stale:
        f.unlink()
    if stale:
        print(f"  (xoa {len(stale)} frame cu)")
    md = [f"# VISION EVAL - {proj}", ""]

    if args.examples_from:
        epdir = config.project_dir(args.examples_from)
        esrc = epdir / "source.mp4"
        if not esrc.exists():
            print(f"bo qua vi du: khong thay {esrc}")
        else:
            for i, sh in enumerate(_sample_shots(epdir, args.examples, SEED + 1), 1):
                a, b = pt(sh["clip_start"]), pt(sh["clip_end"])
                tag = f"ex{i:02d}"
                frames = _frames_for(esrc, out_dir, tag, a, b, min(3, args.frames))
                if i == 1:
                    md += ["## Vi du DA GIAI (phim khac - hoc QUY UOC tag, "
                           "khong phai dap an cua bai)", ""]
                md += [f"### {tag}  ({round(b-a,1)}s)", ""]
                md += [f"![{f}](vision_eval/{f})" for f in frames]
                md += ["",
                       f"- depicts: {', '.join(sh.get('depicts') or [])}",
                       f"- chars: {', '.join(sh.get('chars') or []) or '(khong ro)'}",
                       f"- action: {sh.get('action','')}", ""]
                print(f"  {tag}: {len(frames)} frame (vi du)")
            md += ["---", ""]

    pick = _sample_shots(pdir, args.shots, SEED)
    truth, rows = {}, []
    for i, sh in enumerate(pick, 1):
        a, b = pt(sh["clip_start"]), pt(sh["clip_end"])
        tag = f"shot{i:02d}"
        frames = _frames_for(src, out_dir, tag, a, b, args.frames)
        truth[tag] = {"id": sh.get("id"), "clip_start": sh["clip_start"],
                      "clip_end": sh["clip_end"], "depicts": sh.get("depicts", []),
                      "chars": sh.get("chars", []), "action": sh.get("action", "")}
        rows.append((tag, sh["clip_start"], sh["clip_end"], round(b - a, 1), frames))
        print(f"  {tag}: {len(frames)} frame")

    json.dump(truth, io.open(pdir / "_vision_truth.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    md += ["## Bai can lam", "",
           "Nhin anh va dien 3 cot cho TUNG shot duoi day. Khong co dap an o day.", "",
           "### `depicts` (chi dung tu trong day, 1-2 tu moi shot)", "",
           "`" + "`, `".join(DEPICTS_VOCAB) + "`", "",
           "Xem `docs/TAGGING_GUIDE.md`, va **bat chuoc quy uoc trong cac vi du o tren** - "
           "nhat la khi mot cua so co nhieu khoanh khac thi chon cai nao lam chinh.", "",
           "### `chars`", "",
           "Ten nhan vat NHIN THAY RO trong BAT KY frame nao. Khong chac -> `(khong ro)`.", "",
           "### `action`", "", "Mot cau ta cai dang xay ra tren man hinh.", "", "---", ""]

    for tag, cs, ce, dur, frames in rows:
        md += [f"### {tag}  ({cs} -> {ce}, {dur}s)", ""]
        md += [f"![{f}](vision_eval/{f})" for f in frames]
        md += ["", "- depicts: ", "- chars: ", "- action: ", ""]

    (pdir / "VISION_EVAL.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\nDa tao:\n  {pdir / 'VISION_EVAL.md'}\n  {out_dir}\n"
          f"  {pdir / '_vision_truth.json'}  <- dap an, DUNG dua cho model")


if __name__ == "__main__":
    main()
