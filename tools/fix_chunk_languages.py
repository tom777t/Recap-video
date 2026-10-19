# -*- coding: utf-8 -*-
"""
fix_chunk_languages.py - sua cac chunk bi NHAN DANG NGON NGU SAI roi dich tu
mot ngon ngu khong he co trong phim.

Van de
------
Phat hien ngon ngu theo chunk chua lanh han van de. Tren tokyodrift2006 no tra
ve zh:2, hi:1, sv:1, pt:1, ko:1, ru:1, ml:1 - phim nay khong co ngon ngu nao
trong so do. Moi chunk nhu vay deu NGAN HON 2 GIAY, va ket qua dich ra deu la
tieng Anh nghe rat xuoi:

    0.9s  zh  "See you next time!"
    0.5s  zh  "Come on."
    1.1s  ml  "end of the"

Do moi la cho nguy: dau ra KHONG trong nhu rac, nen doc transcript khong bao
gio bat duoc. Chi co metadata (ngon ngu + do tin cay + do dai chunk) moi noi
duoc.

Luat sua (chung cho moi phim, khong phai ban va rieng cho phim nay):

  1. Tinh HAI ngon ngu chinh cua phim, can theo TONG THOI LUONG chunk chu
     khong phai so chunk - mot ngon ngu that se chiem nhieu giay, mot lan doan
     nham chi chiem mot giay le.
  2. Chunk nao co ngon ngu NGOAI top-2 -> giai ma lai bang ngon ngu chinh.
  3. Chunk nao co do tin cay duoi nguong -> cung giai ma lai bang ngon ngu
     chinh.

Luat 3 co mot cai gia phai noi ro: mot chunk tieng Nhat THAT nhung do tin cay
thap se bi ep ve tieng Anh, va doan do se thanh rac. Nen moi thay doi deu duoc
in ra kem van ban truoc/sau de nguoi doc tu phan xu, va chunk thuoc nhom nay
duoc danh dau rieng.

Dung:
    python tools/fix_chunk_languages.py <project> [--min-prob 0.35] [--dry-run]
"""
from __future__ import annotations
import argparse, io, json, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

PAD = 0.2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--partial", default="transcript_vad.partial.jsonl")
    ap.add_argument("--out", default="transcript_vad.json")
    ap.add_argument("--model", default="medium")
    ap.add_argument("--min-prob", type=float, default=0.35)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    pdir = config.project_dir(a.project)
    pp = pdir / a.partial
    if not pp.exists():
        print(f"khong co {pp}")
        return 1
    recs = [json.loads(l) for l in io.open(pp, encoding="utf-8") if l.strip()]
    if not recs:
        print("partial rong")
        return 1

    # --- top-2 ngon ngu, can theo THOI LUONG -------------------------------
    secs = defaultdict(float)
    for r in recs:
        secs[r["lang"]] += float(r["b"]) - float(r["a"])
    order = sorted(secs, key=lambda k: -secs[k])
    top2 = order[:2]
    dom = order[0]
    total = sum(secs.values())
    print(f"{len(recs)} chunk | ngon ngu theo THOI LUONG:")
    for k in order:
        print(f"   {k:<4} {secs[k]:7.1f}s  {100*secs[k]/total:5.1f}%  "
              f"({sum(1 for r in recs if r['lang']==k)} chunk)"
              + ("   <- top-2" if k in top2 else ""))
    print(f"ngon ngu chinh: {dom}")

    out_of_top2 = [r for r in recs if r["lang"] not in top2]
    low_prob = [r for r in recs
                if r["lang"] in top2 and r["lang"] != dom
                and float(r["prob"]) < a.min_prob]
    todo = {r["i"]: r for r in out_of_top2}
    for r in low_prob:
        todo.setdefault(r["i"], r)

    print(f"\nse giai ma lai {len(todo)} chunk:")
    print(f"   {len(out_of_top2)} vi ngon ngu nam ngoai top-2")
    print(f"   {len(low_prob)} vi do tin cay < {a.min_prob} (ngon ngu phu)")
    if not todo:
        print("khong co gi de sua.")
        return 0

    dur_all = [float(r['b'])-float(r['a']) for r in todo.values()]
    print(f"   do dai cac chunk nay: min {min(dur_all):.1f}s  "
          f"max {max(dur_all):.1f}s  (nhan dang ngon ngu duoi ~2s rat khong "
          f"dang tin - do la co che gay loi)")

    if a.dry_run:
        for r in sorted(todo.values(), key=lambda x: x["i"]):
            txt = " / ".join(s["text"] for s in r["segs"])[:64]
            why = "ngoai top-2" if r["lang"] not in top2 else "tin cay thap"
            print(f"   chunk {r['i']:<4} {r['a']:7.1f}s +{float(r['b'])-float(r['a']):.1f}s "
                  f"{r['lang']} p={r['prob']:.2f} [{why}]  {txt}")
        print("\n--dry-run: khong sua gi.")
        return 0

    src = next((pdir / f"source{e}" for e in (".mp4", ".mkv", ".mov", ".m4v")
                if (pdir / f"source{e}").exists()), None)
    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio
    print("\ndecode audio + load model...")
    audio = decode_audio(str(src), sampling_rate=16000)
    m = WhisperModel(a.model, device="cpu", compute_type="int8")

    changed = []
    for i in sorted(todo):
        r = todo[i]
        ca, cb = float(r["a"]), float(r["b"])
        lo = max(0, int((ca - PAD) * 16000))
        hi = min(len(audio), int((cb + PAD) * 16000))
        clip = audio[lo:hi]
        task = "transcribe" if dom == "en" else "translate"
        segs, _ = m.transcribe(clip, task=task, language=dom,
                               condition_on_previous_text=False,
                               vad_filter=False, beam_size=5)
        new = []
        for s in segs:
            t = (s.text or "").strip()
            if t:
                new.append({"start": round(ca + max(0.0, s.start - PAD), 2),
                            "end": round(ca + max(0.0, s.end - PAD), 2),
                            "text": t})
        old_txt = " / ".join(s["text"] for s in r["segs"])
        new_txt = " / ".join(s["text"] for s in new)
        why = "ngoai top-2" if r["lang"] not in top2 else "tin cay thap"
        changed.append((i, r["lang"], r["prob"], why, old_txt, new_txt,
                        cb - ca))
        r["segs"] = new
        r["lang_fixed_from"] = r["lang"]
        r["lang"] = dom
        r["fix_reason"] = why

    io.open(pp, "w", encoding="utf-8").write(
        "".join(json.dumps(r, ensure_ascii=False) + "\n"
                for r in sorted(recs, key=lambda x: x["i"])))

    segs, langs = [], defaultdict(int)
    for r in sorted(recs, key=lambda x: x["i"]):
        langs[r["lang"]] += 1
        segs += r["segs"]
    segs.sort(key=lambda s: s["start"])
    tp = pdir / "transcript.json"
    dur = 0.0
    try:
        dur = float(json.load(io.open(tp, encoding="utf-8-sig"))["duration"])
    except Exception:
        dur = max(s["end"] for s in segs) if segs else 0.0
    io.open(pdir / a.out, "w", encoding="utf-8").write(json.dumps(
        {"language": "en (per-chunk detect+translate, misdetections corrected)",
         "duration": round(dur, 2),
         "model": f"{a.model} vad+perchunk+langfix",
         "chunk_languages": dict(langs),
         "segments": segs}, ensure_ascii=False, indent=2))

    print(f"\n{len(changed)} chunk da sua:\n")
    for i, old_l, p, why, o, n, g in changed:
        print(f"  chunk {i:<4} {g:4.1f}s  {old_l} p={p:.2f} -> {dom}  [{why}]")
        print(f"     truoc: {o[:72]}")
        print(f"     sau  : {n[:72] or '(khong co loi nao)'}")
    print(f"\nngon ngu sau khi sua: {dict(langs)}")
    print(f"da ghi {pdir / a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
