"""timeline.json co lech dan theo thoi gian khong?

    python tools/diag_offset.py <project> [so_mau] [window_giay]

LOCALITY (them 2026-08-26). Truoc day ham match quet TOAN BO transcript va giu
match SOM NHAT trong cac match cung diem, nen mot cua so vat qua doan im lang
dai co the thang va bao line lech bang dung mot hold.

Do duoc tren howtomakemillions2024: line 39 bao -22.3s (ngay sau mot hold 22.0s)
va line 80 bao -20.2s (ngay sau mot hold 20.0s), trong khi do truc tiep tren
audio thi hai line lech -0.8s va -0.2s. Khong phai loi render - loi cua tool nay.

Gio chi match trong +/-WINDOW giay quanh vi tri ky vong, va uu tien match GAN
nhat khi ty le bang nhau. Neu khong tim duoc gi trong cua so thi van quet toan
bo (de drift that su van lo ra) nhung danh dau FAR va KHONG tinh vao ket luan.

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


WINDOW = 15.0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    proj = sys.argv[1]
    n_sample = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    # Locality half-width. Generous enough that real cumulative drift still
    # lands inside it (and so still gets measured), tight enough to exclude a
    # neighbouring line across a long silence hold - the longest S9 hold is 30s.
    global WINDOW
    WINDOW = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0
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

    print(f"\nLOCALITY: matching within +/-{WINDOW:.0f}s of the expected position; "
          f"a match found only outside it is marked FAR.")
    print(f"\n{'id':<7}{'timeline':<10}{'audio':<10}{'lech':<9}dau cau")
    print("-" * 78)
    rows = []
    far = []
    for t in picks:
        want = norm(by_id[str(t["id"])])
        head = want.split()[:6]
        if len(head) < 3:
            continue
        target = " ".join(head)
        want_t = t["out_start"]

        def scan(lo, hi):
            """Best (ratio, closeness) match with word start time in [lo, hi]."""
            best = None
            for i in range(len(words) - len(head)):
                ti = words[i]["t"]
                if ti < lo or ti > hi:
                    continue
                cand = " ".join(words[i + k]["w"] for k in range(len(head)))
                r = SequenceMatcher(None, target, cand).ratio()
                # Tie-break on CLOSENESS to the expected position, not on
                # whichever came first. The old code took the earliest of equal
                # matches, so a window spanning a long silence could win and
                # land the line one hold early.
                key = (r, -abs(ti - want_t))
                if best is None or key > (best[0], best[1]):
                    best = (r, -abs(ti - want_t), ti)
            return best

        b = scan(want_t - WINDOW, want_t + WINDOW)
        marker = ""
        if b is None or b[0] < 0.55:
            # Nothing credible nearby. Fall back to a GLOBAL scan so genuine
            # large drift is still reported rather than hidden - but flag it,
            # because "matched 40s away" is a different claim from "is 40s off".
            b = scan(float("-inf"), float("inf"))
            marker = " FAR"
            if b is not None and b[0] >= 0.55:
                far.append(t["id"])
        if b is None or b[0] < 0.55:
            print(f"{t['id']:<7}{ms(want_t):<10}{'?':<10}{'?':<9}{' '.join(head)}")
            continue
        best_t = b[2]
        d = best_t - want_t
        # Only in-window matches feed the drift verdict; a FAR match is a
        # suspicion to look at by hand, not a measurement to average.
        if not marker:
            rows.append((want_t, d))
        print(f"{t['id']:<7}{ms(want_t):<10}{ms(best_t):<10}{d:+<9.1f}"
              f"{' '.join(head)}{marker}")
    if far:
        print(f"\n{len(far)} line(s) matched only OUTSIDE the +/-{WINDOW:.0f}s "
              f"window: {far}")
        print("  Check these by hand. Either the render really is that far off, "
              "or the\n  matcher latched onto similar wording elsewhere - both "
              "look the same here.")

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
