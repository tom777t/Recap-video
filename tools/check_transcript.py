# -*- coding: utf-8 -*-
"""
check_transcript.py - [TRANSCRIPT-QUALITY]. Chay NGAY SAU whisper.

Vi sao gate nay ton tai
-----------------------
Transcript cu cua tokyodrift2006 bao phu 89% thoi luong va trong hoan toan on.
Su that: 34 segment dai hon 30s, trong do MOT segment dai 569.6s mang dung mot
cau. Tru chung ra thi phan phu that con 34%. Con so 89% khong phai mot phep do
- chinh cai hong sinh ra no, vi mot cau bi keo dai hang phut dem vao "do phu"
dung bang hang phut do.

Ba hinh dang cua hong, ba phep kiem rieng:

  1. SEGMENT KHONG LO - mot cau dong len hang phut audio. Moc thoi gian cua no
     sai, va bat ky khau nao gan loi thoai theo giao thoa thoi gian se dan cau
     do xuong hang chuc khoanh khac nhu the no duoc noi o tung cho.
  2. VONG LAP - cung mot cau lap lien tiep 3 lan tro len. Day la Whisper tu
     noi lai chinh no khi gap doan khong nghe ro (condition_on_previous_text).
  3. MU KHI CO TIENG NOI - mot doan dai khong co chu nao, NHUNG VAD noi o do
     co nguoi dang noi. Khac han voi mot doan dai im lang that, va chi phan
     biet duoc khi hoi den audio chu khong phai hoi den transcript.

Gate CANH BAO, khong chan. Nguoi quyet dinh co lam lai hay khong.

Dung:
    python tools/check_transcript.py <project> [--file transcript.json] [--vad]
"""
from __future__ import annotations
import argparse, io, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

MAX_SEG = 30.0          # giay
LONG_SHARE_WARN = 0.10  # >10% runtime nam trong segment qua dai -> canh bao
REPEAT_WARN = 3         # cung mot cau lap lien tiep N lan
BLIND_WARN = 60.0       # doan mu dai hon the nay moi dang hoi VAD


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--file", default="transcript.json")
    ap.add_argument("--vad", action="store_true",
                    help="chay VAD de phan biet 'im lang that' voi 'co tieng "
                         "noi ma khong co chu'. Cham hon nhung la phep kiem "
                         "duy nhat tra loi duoc cau hoi do.")
    a = ap.parse_args()
    pdir = config.project_dir(a.project)
    tp = pdir / a.file
    if not tp.exists():
        print(f"[TRANSCRIPT-QUALITY] khong co {tp}")
        return 1

    d = json.load(io.open(tp, encoding="utf-8-sig"))
    S = [s for s in (d.get("segments") or [])
         if isinstance(s.get("start"), (int, float))]
    if not S:
        print("[TRANSCRIPT-QUALITY] transcript KHONG co segment nao.")
        return 1
    dur = float(d.get("duration") or S[-1]["end"])

    # --- 1. segment khong lo ------------------------------------------------
    longs = [s for s in S if float(s["end"]) - float(s["start"]) > MAX_SEG]
    long_time = sum(float(s["end"]) - float(s["start"]) for s in longs)
    long_share = long_time / dur if dur else 0

    # --- 2. vong lap --------------------------------------------------------
    loops, run, prev = [], 1, None
    for s in S:
        t = str(s.get("text", "")).strip().lower()
        if t and t == prev:
            run += 1
        else:
            if prev and run >= REPEAT_WARN:
                loops.append((prev, run))
            prev, run = t, 1
    if prev and run >= REPEAT_WARN:
        loops.append((prev, run))

    # --- 3. mu ----------------------------------------------------------------
    good = sorted((float(s["start"]), float(s["end"])) for s in S
                  if float(s["end"]) - float(s["start"]) <= MAX_SEG)
    merged = []
    for x, y in good:
        if merged and x <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], y)
        else:
            merged.append([x, y])
    usable = sum(y - x for x, y in merged)
    blind, prev_end = [], 0.0
    for x, y in merged:
        if x - prev_end > BLIND_WARN:
            blind.append((prev_end, x - prev_end))
        prev_end = y
    if dur - prev_end > BLIND_WARN:
        blind.append((prev_end, dur - prev_end))

    print(f"[TRANSCRIPT-QUALITY] {a.file}: {len(S)} segment, "
          f"{100*sum(float(s['end'])-float(s['start']) for s in S)/dur:.0f}% "
          f"raw coverage, {100*usable/dur:.0f}% usable coverage")

    bad = False
    if long_share > LONG_SHARE_WARN:
        bad = True
        print(f"  ! {len(longs)} segment(s) longer than {MAX_SEG:.0f}s cover "
              f"{100*long_share:.0f}% of runtime (limit {100*LONG_SHARE_WARN:.0f}%).")
        print(f"    A segment that long is one line stamped over minutes of "
              f"audio; its timestamps are not usable.")
        for s in sorted(longs, key=lambda x: x["start"]-x["end"])[:4]:
            print(f"      {float(s['start']):7.0f}s +{float(s['end'])-float(s['start']):5.0f}s  "
                  f"{str(s.get('text',''))[:52]}")
    else:
        print(f"  ok  long segments cover {100*long_share:.0f}% of runtime")

    if loops:
        bad = True
        print(f"  ! {len(loops)} repetition loop(s) - the same line repeated "
              f"{REPEAT_WARN}+ times in a row:")
        for t, n in sorted(loops, key=lambda x: -x[1])[:5]:
            print(f"      {n}x  {t[:56]}")
    else:
        print(f"  ok  no line repeats {REPEAT_WARN}+ times in a row")

    if blind:
        tot = sum(g for _t, g in blind)
        if a.vad:
            try:
                from faster_whisper.audio import decode_audio
                from faster_whisper.vad import VadOptions, get_speech_timestamps
                src = next((pdir / f"source{e}" for e in
                            (".mp4", ".mkv", ".mov", ".m4v")
                            if (pdir / f"source{e}").exists()), None)
                audio = decode_audio(str(src), sampling_rate=16000)
                ts = get_speech_timestamps(audio, VadOptions())
                sp = [(t["start"]/16000.0, t["end"]/16000.0) for t in ts]
                worst = []
                for t, g in blind:
                    voiced = sum(max(0.0, min(b, t+g)-max(x, t))
                                 for x, b in sp if b > t and x < t+g)
                    if voiced > 10:
                        worst.append((t, g, voiced))
                if worst:
                    bad = True
                    print(f"  ! {len(worst)} blind stretch(es) where VAD says "
                          f"people ARE speaking:")
                    for t, g, v in sorted(worst, key=lambda x: -x[2])[:5]:
                        print(f"      {t:7.0f}s +{g:5.0f}s  "
                              f"{v:.0f}s of speech with no transcript")
                else:
                    print(f"  ok  {len(blind)} blind stretch(es), none with "
                          f"meaningful speech (VAD-checked)")
            except Exception as e:
                print(f"  ?  VAD check unavailable ({type(e).__name__}) - "
                      f"{len(blind)} blind stretch(es) NOT verified against "
                      f"audio. This is unchecked, not clean.")
        else:
            print(f"  ?  {len(blind)} blind stretch(es) totalling {tot/60:.0f} "
                  f"min. Re-run with --vad to learn whether anyone is speaking "
                  f"in them. Until then this is unchecked, not clean.")

    print(f"[TRANSCRIPT-QUALITY] {'PROBLEMS - read above' if bad else 'clean'}")
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
