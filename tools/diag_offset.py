"""timeline.json co lech dan theo thoi gian khong?

    python tools/diag_offset.py <project> [so_mau]

Khac `diag_timeline.py`: cai kia chi soi 20 line DAU, nen mot sai lech TICH LUY
se khong lo ra. Cai nay lay mau TRAI DEU khap phim.

Doc ket qua:
  - lech gan nhu nhau tu dau den cuoi  -> LECH HANG SO, mot thu co dinh o dau
    video chua duoc tinh vao. Sua mot cho.
  - lech tang dan theo line             -> TICH LUY, phep tinh clip_len/XFADE moi
    line sai mot chut. Sua khac han.

Khong ghi gi. Mot lan chay Whisper (~2-4 phut cho 17 phut audio).
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def ms(s):
    return f"{int(s)//60:02d}:{int(s)%60:02d}"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    proj = sys.argv[1]
    n_sample = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    pdir = config.project_dir(proj)

    tl = json.load(io.open(pdir / "timeline.json", encoding="utf-8-sig"))["lines"]
    lines = json.load(io.open(pdir / "draft.json", encoding="utf-8-sig"))["lines"]
    by_id = {str(l.get("id")): (l.get("narration") or "") for l in lines}

    wav = pdir / "_offset16k.wav"
    subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(pdir / "final.mp4"), "-vn", "-ac", "1", "-ar", "16000",
                    str(wav)], check=True)
    from faster_whisper import WhisperModel
    print("transcribing (word timestamps)...")
    segs, _ = WhisperModel("small", device="cpu", compute_type="int8").transcribe(
        str(wav), beam_size=1, vad_filter=False, word_timestamps=True)

    words = []
    for s in segs:
        for w in (getattr(s, "words", None) or []):
            words.append({"t": float(w.start), "w": norm(w.word)})
    try:
        wav.unlink()
    except Exception:
        pass
    if not words:
        print("khong lay duoc word timestamps - model nay khong ho tro?")
        return

    # sample evenly across the whole film, not just the head
    usable = [t for t in tl if by_id.get(str(t.get("id", ""))) ]
    step = max(1, len(usable) // n_sample)
    picks = usable[::step]

    print(f"\n{'id':<7}{'timeline':<10}{'audio':<10}{'lech':<9}dau cau")
    print("-" * 78)
    rows = []
    for t in picks:
        want = norm(by_id[str(t["id"])])
        head = want.split()[:6]
        if len(head) < 3:
            continue
        best_t, best_r = None, 0.0
        for i in range(len(words) - len(head)):
            cand = [words[i + k]["w"] for k in range(len(head))]
            r = SequenceMatcher(None, " ".join(head), " ".join(cand)).ratio()
            if r > best_r:
                best_r, best_t = r, words[i]["t"]
        if best_t is None or best_r < 0.55:
            print(f"{t['id']:<7}{ms(t['out_start']):<10}{'?':<10}{'?':<9}{' '.join(head)}")
            continue
        d = best_t - t["out_start"]
        rows.append((t["out_start"], d))
        print(f"{t['id']:<7}{ms(t['out_start']):<10}{ms(best_t):<10}{d:+<9.1f}{' '.join(head)}")

    if len(rows) < 4:
        print("\nkhong du mau de ket luan")
        return
    print("-" * 78)
    first = sum(d for _s, d in rows[:3]) / 3
    last = sum(d for _s, d in rows[-3:]) / 3
    print(f"lech trung binh 3 line DAU : {first:+.1f}s")
    print(f"lech trung binh 3 line CUOI: {last:+.1f}s")
    if abs(last - first) < 1.0:
        print("=> LECH HANG SO. Mot thu co dinh chua duoc tinh vao. Sua mot cho.")
    else:
        per = (last - first) / max(1, len(rows) - 1)
        print(f"=> TICH LUY: ~{per:+.2f}s moi line lay mau.")
        print("   Phep tinh clip_len - XFADE trong render.py lech so voi cach ffmpeg")
        print("   thuc su ghep. Sai so nhan len theo so line.")


if __name__ == "__main__":
    main()
