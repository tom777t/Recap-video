# -*- coding: utf-8 -*-
"""
retranscribe.py - lam lai transcript bang VAD + PHAT HIEN NGON NGU THEO CHUNK.

Vi sao
------
Ban transcript cu cua tokyodrift2006 trong rat on: phu 89% thoi luong. Nhung
34 segment dai hon 30s, trong do mot segment dai 569.6s mang DUNG MOT cau. Tru
chung ra thi phan phu that chi con 34%. Con so 89% khong phai mot phep do -
no do chinh cai hong sinh ra.

Hai nguyen nhan, hai cach chua:

1. `condition_on_previous_text=True` (mac dinh) lam model lap lai chinh no khi
   gap doan khong nghe ro - sinh ra vong lap "Uwabaki. Uwabaki. Uwabaki." va
   nhung segment khong lo. Tat no di.

2. Ngon ngu duoc phat hien MOT LAN cho ca phim. Phim nay tron tieng Anh va
   tieng Nhat; Whisper chot "en" roi nuot hoac bia qua cac canh tieng Nhat
   (canh truong hoc, canh Kamata). Nen o day ngon ngu duoc phat hien TREN TUNG
   CHUNK, va chunk nao khong phai tieng Anh thi dich sang tieng Anh
   (task="translate"), giu nguyen moc thoi gian cua nguoi noi.

Day la cach chua CHUNG cho phim da ngon ngu, khong phai mot ban va rieng cho
Tokyo Drift.

Chay lai duoc: moi chunk xong duoc ghi ngay vao .partial.jsonl, chay lai se
tiep tu cho do chu khong lam lai tu dau.

Dung:
    python tools/retranscribe.py <project> [--model medium] [--out transcript_vad.json]
"""
from __future__ import annotations
import argparse, io, json, os, sys, time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

MAX_CHUNK = 25.0     # giay. Tran cung: khong segment nao duoc dai hon the nay.
MIN_CHUNK = 0.4
PAD = 0.2


def log(m):
    print(m, flush=True)


def build_chunks(speech, max_chunk=MAX_CHUNK):
    """Gop cac vung co tieng noi thanh chunk <= max_chunk giay.

    Khong bao gio noi hai vung cach nhau qua xa thanh mot chunk: mot khoang
    lang dai o giua nghia la hai luot noi khac nhau, va gop chung lai chinh la
    cai sinh ra segment khong lo o ban cu.
    """
    out, cur = [], None
    for s in speech:
        a, b = s["start"], s["end"]
        if cur is None:
            cur = [a, b]
            continue
        if b - cur[0] <= max_chunk and a - cur[1] <= 1.0:
            cur[1] = b
        else:
            out.append(tuple(cur))
            cur = [a, b]
    if cur:
        out.append(tuple(cur))
    # cat nho bat ky chunk nao van qua dai (mot luot noi lien tuc rat dai)
    final = []
    for a, b in out:
        if b - a <= max_chunk:
            final.append((a, b))
        else:
            t = a
            while t < b:
                final.append((t, min(t + max_chunk, b)))
                t += max_chunk
    return [(a, b) for a, b in final if b - a >= MIN_CHUNK]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--model", default="medium")
    ap.add_argument("--out", default="transcript_vad.json")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--minutes", type=float, default=0,
                    help="dung sach se sau N phut. Checkpoint theo tung chunk "
                         "nen lan chay sau tiep tu dung cho do - mot job CPU "
                         "nhieu gio phai chay duoc thanh nhieu lat.")
    a = ap.parse_args()

    pdir = config.project_dir(a.project)
    src = next((pdir / f"source{e}" for e in (".mp4", ".mkv", ".mov", ".m4v")
                if (pdir / f"source{e}").exists()), None)
    if src is None:
        log(f"khong co source trong {pdir}")
        return 1

    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    log(f"decode audio: {src.name}")
    audio = decode_audio(str(src), sampling_rate=16000)
    total = len(audio) / 16000.0
    log(f"audio {total:.0f}s")

    log("VAD...")
    vo = VadOptions(min_silence_duration_ms=500, speech_pad_ms=200)
    ts = get_speech_timestamps(audio, vo)
    speech = [{"start": t["start"] / 16000.0, "end": t["end"] / 16000.0}
              for t in ts]
    sp_total = sum(s["end"] - s["start"] for s in speech)
    log(f"VAD: {len(speech)} vung co tieng noi, tong {sp_total:.0f}s "
        f"= {100*sp_total/total:.0f}% thoi luong")

    chunks = build_chunks(speech)
    if a.limit:
        chunks = chunks[:a.limit]
    log(f"{len(chunks)} chunk (tran {MAX_CHUNK:.0f}s moi chunk)")

    outp = pdir / a.out
    partial = outp.with_suffix(".partial.jsonl")
    done = {}
    if partial.exists():
        for line in io.open(partial, encoding="utf-8"):
            try:
                o = json.loads(line)
                done[o["i"]] = o
            except Exception:
                pass
        log(f"resume: {len(done)} chunk da xong truoc do")

    log(f"load model '{a.model}' (cpu/int8)...")
    m = WhisperModel(a.model, device="cpu", compute_type="int8")

    fh = io.open(partial, "a", encoding="utf-8")
    t0 = time.time()
    for i, (ca, cb) in enumerate(chunks):
        if i in done:
            continue
        lo = max(0, int((ca - PAD) * 16000))
        hi = min(len(audio), int((cb + PAD) * 16000))
        clip = audio[lo:hi]
        if len(clip) < 1600:
            continue
        try:
            lang, prob, _ = m.detect_language(clip)
        except Exception:
            lang, prob = "en", 0.0
        task = "transcribe" if lang == "en" else "translate"
        segs, _info = m.transcribe(
            clip, task=task, language=lang,
            condition_on_previous_text=False,   # <- khong tu lap lai
            vad_filter=False,                   # da VAD o tren roi
            beam_size=5,
        )
        texts = []
        for s in segs:
            t = (s.text or "").strip()
            if t:
                texts.append({"start": round(ca + max(0.0, s.start - PAD), 2),
                              "end": round(ca + max(0.0, s.end - PAD), 2),
                              "text": t})
        rec = {"i": i, "a": round(ca, 2), "b": round(cb, 2),
               "lang": lang, "prob": round(float(prob), 3),
               "task": task, "segs": texts}
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()
        done[i] = rec
        if (i + 1) % 25 == 0 or i == len(chunks) - 1:
            el = time.time() - t0
            log(f"  chunk {i+1}/{len(chunks)}  {100*(i+1)/len(chunks):.0f}%  "
                f"elapsed {el/60:.1f}m  done {len(done)}/{len(chunks)}")
        if a.minutes and (time.time() - t0) / 60.0 >= a.minutes:
            log(f"  -- time cap {a.minutes:.0f}m reached, stopping cleanly at "
                f"chunk {i+1}/{len(chunks)} ({len(done)} done). Re-run to resume.")
            break
    fh.close()
    if len(done) < len(chunks):
        log(f"INCOMPLETE: {len(done)}/{len(chunks)} chunks. "
            f"transcript_vad.json below is PARTIAL - re-run to finish.")

    segs = []
    langs = {}
    for i in sorted(done):
        r = done[i]
        langs[r["lang"]] = langs.get(r["lang"], 0) + 1
        segs += r["segs"]
    segs.sort(key=lambda s: s["start"])
    out = {"language": "en (per-chunk detect+translate)",
           "duration": round(total, 2),
           "model": f"{a.model} vad+perchunk",
           "chunk_languages": langs,
           "segments": segs}
    io.open(outp, "w", encoding="utf-8").write(
        json.dumps(out, ensure_ascii=False, indent=2))
    log(f"\n{len(segs)} segment | ngon ngu theo chunk: {langs}")
    log(f"da ghi {outp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
