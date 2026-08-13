"""Soi hinh quanh mot moc, va cho biet cu cat gan nhat de snap vao.

    python _peek.py <project> <HH:MM:SS> [span_giay]

Dung khi can dat lai cua so cho mot shot: xem hinh o do co dung canh khong,
roi lay bien cua so tu cu cat that (_cuts.json) thay vi go tay mot con so tron.

In ra file anh vao vision_peek/ va danh sach cu cat trong khoang.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402


def pt(t):
    return sum(float(x) * m for x, m in zip(str(t).split(":"), (3600, 60, 1)))


def hms(s):
    return f"{int(s)//3600:02d}:{int(s)%3600//60:02d}:{s%60:06.3f}"


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    proj, at = sys.argv[1], sys.argv[2]
    span = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0
    pdir = config.project_dir(proj)
    src = pdir / "source.mp4"
    if not src.exists():
        print(f"khong thay {src}")
        return

    t0 = pt(at)
    a, b = max(0.0, t0 - span / 2), t0 + span / 2
    out = pdir / "vision_peek"
    out.mkdir(exist_ok=True)
    for f in out.glob("*.jpg"):
        f.unlink()

    n = 8
    print(f"trich {n} frame trong {hms(a)} -> {hms(b)}")
    for i in range(n):
        t = a + (b - a) * i / max(1, n - 1)
        name = f"{int(t)//60:03d}m{int(t)%60:02d}s.jpg"
        cmd = [config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
               "-ss", hms(t), "-i", str(src), "-frames:v", "1",
               "-vf", "scale=768:-2", str(out / name)]
        if subprocess.run(cmd, capture_output=True).returncode == 0:
            print(f"  {out.name}\\{name}")

    cp = pdir / "_cuts.json"
    if cp.exists():
        cuts = [float(c) for c in json.load(io.open(cp, encoding="utf-8"))["cuts"]]
        near = [c for c in cuts if a <= c <= b]
        print(f"\ncu cat that trong khoang ({len(near)}):")
        for c in near:
            print(f"  {hms(c)}")
        print("\n-> lay clip_start / clip_end tu danh sach nay, dung go so tron")
    else:
        print("\nkhong co _cuts.json - chay `recap.py cuts` neu muon snap vao cu cat")


if __name__ == "__main__":
    main()
