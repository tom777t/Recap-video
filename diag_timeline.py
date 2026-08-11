"""Where is the timeline offset coming from?

    python diag_timeline.py <project>

[RENDER-VERIFY] shows every line's window containing the PREVIOUS line's audio,
by a roughly constant amount. Either timeline.json starts each line too early,
or the render puts something before the first line that it does not account for.

This prints, side by side:
  - what timeline.json says each line's window is
  - where Whisper actually finds that line's first few words in the rendered audio
  - the difference

A constant difference means one fixed thing is unaccounted for at the front.
A difference that grows means the per-line arithmetic (clip_len / XFADE) is wrong.
Those are two different bugs with two different fixes, so measure before patching.
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def main():
    proj = sys.argv[1]
    pdir = config.project_dir(proj)
    tl = json.load(io.open(pdir / "timeline.json", encoding="utf-8-sig"))["lines"]
    lines = json.load(io.open(pdir / "draft.json", encoding="utf-8-sig"))["lines"]
    by_id = {str(l.get("id")): (l.get("narration") or "") for l in lines}

    wav = pdir / "_diag16k.wav"
    subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(pdir / "final.mp4"), "-vn", "-ac", "1", "-ar", "16000",
                    str(wav)], check=True)
    from faster_whisper import WhisperModel
    print("transcribing...")
    segs, _ = WhisperModel("small", device="cpu", compute_type="int8").transcribe(
        str(wav), beam_size=1, vad_filter=False)
    segs = [{"start": float(s.start), "end": float(s.end), "text": s.text} for s in segs]
    try:
        wav.unlink()
    except Exception:
        pass

    print(f"\n{'id':<7}{'timeline':<10}{'audio at':<10}{'diff':<9}first words of the line")
    print("-" * 90)
    diffs = []
    for t in tl[:20]:
        lid = str(t.get("id"))
        want = norm(by_id.get(lid, ""))
        if not want:
            continue
        head = " ".join(want.split()[:8])
        # where does this line's opening actually appear?
        best, best_r = None, 0.0
        for s in segs:
            cand = " ".join(norm(s["text"]).split()[:8])
            r = SequenceMatcher(None, head, cand).ratio()
            if r > best_r:
                best_r, best = r, s["start"]
        if best is None or best_r < 0.5:
            print(f"{lid:<7}{t['out_start']:<10.1f}{'?':<10}{'?':<9}{head}")
            continue
        d = best - t["out_start"]
        diffs.append(d)
        print(f"{lid:<7}{t['out_start']:<10.1f}{best:<10.1f}{d:+<9.1f}{head}")

    if diffs:
        print("-" * 90)
        print(f"lech dau : {diffs[0]:+.1f}s")
        print(f"lech cuoi: {diffs[-1]:+.1f}s")
        spread = max(diffs) - min(diffs)
        print(f"bien do  : {spread:.1f}s")
        if spread < 2.0:
            print("=> LECH HANG SO. Mot thu co dinh o dau video chua duoc tinh vao.")
        else:
            print("=> LECH TICH LUY. Phep tinh clip_len / XFADE moi line bi sai.")


if __name__ == "__main__":
    main()
