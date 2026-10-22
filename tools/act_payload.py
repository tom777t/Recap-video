# -*- coding: utf-8 -*-
"""In payload cho mot ACT: cac beat cua act do + cac moment MAY trong khung
thoi gian cua act (lay tu shots.json cua project, voi project may thi do chinh
la catalogue may).

Dung:
    python tools/act_payload.py <project> <act_number>
"""
from __future__ import annotations
import io, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def pt(ts) -> float:
    p = [float(x) for x in str(ts).split(":")]
    while len(p) < 3:
        p.insert(0, 0.0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def main() -> int:
    proj, actn = sys.argv[1], int(sys.argv[2])
    pdir = config.project_dir(proj)
    bp = io.open(pdir / "beats_proposal.md", encoding="utf-8").read().splitlines()

    heads = [(i, l) for i, l in enumerate(bp) if re.match(r"^ACT \d", l.strip())]
    all_beats = [l.rstrip() for l in bp if re.match(r"^\s*B\d+\s*\|", l)]

    if heads:
        if actn < 1 or actn > len(heads):
            print(f"act {actn} khong ton tai (co {len(heads)} act)")
            return 1
        i0 = heads[actn - 1][0]
        i1 = heads[actn][0] if actn < len(heads) else len(bp)
        head = heads[actn - 1][1].strip()
        m = re.search(r"\(([\d:]+)\s*-\s*([\d:]+)\)", head)
        a, b = (pt(m.group(1)), pt(m.group(2))) if m else (0.0, 1e9)
        beats = [l.rstrip() for l in bp[i0:i1]
                 if re.match(r"^\s*B\d+\s*\|", l)]
    else:
        # Beat map do MAY sinh ra khong co dong "ACT n" - do la mot quy uoc
        # cua beat map NGUOI. Chia deu theo SO BEAT, va cat thoi gian dung tai
        # moc cua beat dau tien thuoc nua sau, de hai act khong chong lan.
        n_acts = int(os.environ.get("RECAP_ACTS", "4"))
        if actn < 1 or actn > n_acts:
            print(f"act {actn} khong ton tai (chia deu thanh {n_acts} act)")
            return 1
        if not all_beats:
            print("beats_proposal.md khong co dong beat nao")
            return 1
        per = (len(all_beats) + n_acts - 1) // n_acts
        lo_i, hi_i = per * (actn - 1), min(per * actn, len(all_beats))
        beats = all_beats[lo_i:hi_i]
        if not beats:
            print(f"act {actn} rong")
            return 1
        ts = [pt(re.split(r"\s*\|\s*", l.strip())[1]) for l in all_beats]
        a = ts[lo_i]
        b = ts[hi_i] if hi_i < len(ts) else 1e9
        head = (f"ACT {actn} of {n_acts} (machine beat map has no ACT "
                f"headings - split evenly by beat count)")

    # Act dai qua mot luot subagent thi chia doi THEO BEAT, va cat thoi gian
    # dung tai moc cua beat dau tien cua nua sau - khong de hai nua chong lan.
    half = sys.argv[3] if len(sys.argv) > 3 else None
    if half in ("1", "2") and len(beats) > 2:
        mid = len(beats) // 2
        bts = [pt(re.split(r"\s*\|\s*", l.strip())[1]) for l in beats]
        split = bts[mid]
        if half == "1":
            beats, b = beats[:mid], split
        else:
            beats, a = beats[mid:], split
        head += f"  [HALF {half} of 2]"
    print(f"### {head}")
    print(f"### time range {a:.0f}s - {b:.0f}s | {len(beats)} beats\n")
    print("BEATS (id | ts | what happens | chars | kind):")
    for l in beats:
        print("  " + l.strip())

    # Chap nhan ca hai ten, nhu beat_payload.py: trong luong that catalogue may
    # ten la shots_machine.json va chi duoc doi ten o khau catalogue cua
    # run.ps1. Mot tool bat nguoi goi phai nho dang o buoc nao la mot tool de
    # vo, va no vua vo that.
    _cp = next((p for p in (pdir / "shots.json", pdir / "shots_machine.json")
                if p.exists()), None)
    if _cp is None:
        print(f"khong co shots.json hay shots_machine.json trong {pdir}")
        return 1
    shots = json.load(io.open(_cp, encoding="utf-8-sig"))["shots"]
    # 2026-10-20 START-OWNERSHIP. Truoc day dong nay la:
    #     S = [s for s in shots if a - 30 <= pt(s["clip_start"])
    #                              and pt(s["clip_end"]) <= b + 30]
    # Phan dem +-30s khien MOT moment nam vat ranh gioi act xuat hien trong
    # payload cua CA HAI act, va khong co gi noi voi nguoi viet rang no khong
    # thuoc ve ho. Ket qua that: act1b va act2a cung buoc dong vao ba moment
    # 00:25:32-00:25:53, va [WINDOW-OVERLAP] bat duoc ba cap dong noi de len
    # hinh cua nhau. Day dung la loi MOMENT-SEAM cu o mot do cao khac: quyen
    # so huu phai tinh theo DIEM BAT DAU, va dung mot lan duy nhat.
    # Moment van duoc CHO THAY lam ngu canh, nhung duoc danh dau khong-buoc.
    S = [s for s in shots if a <= pt(s["clip_start"]) < b]
    CTX = [s for s in shots
           if (a - 30 <= pt(s["clip_start"]) < a
               or b <= pt(s["clip_start"]) <= b + 30)]

    # --- SPEECH ------------------------------------------------------------
    # 2026-09-09: khau nay TRUOC DAY khong he ton tai. Nguoi viet chi nhan
    # `action` (mo ta HINH ANH) nen moi lien ket nhan qua nao song trong LOI
    # THOAI deu bien mat: ban draft dau khong co cho nao noi Bank to cao Lynn,
    # nen viec mat hoc bong khong co nguyen nhan, va hang loat dong chi con
    # "talks / argues / pitches" - mot dong tac mieng khong noi dieu gi.
    tp = pdir / "transcript.json"
    segs = []
    if tp.exists():
        try:
            segs = json.load(io.open(tp, encoding="utf-8-sig")).get("segments") or []
        except Exception:
            segs = []
    segs = [s for s in segs if isinstance(s.get("start"), (int, float))]
    # Xem ghi chu trong tools/beat_payload.py: mot segment dai hon 30s la mot
    # cau bi dong len hang phut audio, va gan no theo giao thoa thoi gian se
    # dan mot cau duy nhat xuong hang chuc moment nhu the no duoc noi o tung
    # cho. Loai ra, va noi ra.
    MAX_SEG = 30.0
    _long = [s for s in segs if float(s["end"]) - float(s["start"]) > MAX_SEG]
    segs = [s for s in segs if float(s["end"]) - float(s["start"]) <= MAX_SEG]

    def speech_for(x0, x1):
        return [s for s in segs if s["end"] > x0 and s["start"] < x1]

    print(f"\nAVAILABLE MACHINE MOMENTS in range: {len(S)}")
    print("Each moment: id | start -> end | dur | maxwords | chars | depicts | "
          "censor | action")
    print("SPEECH lines under a moment are the transcript for that window.")
    for s in S:
        x0, x1 = pt(s["clip_start"]), pt(s["clip_end"])
        print(f"  {s['id']} | {s['clip_start']} -> {s['clip_end']} | "
              f"{s['raw_duration_sec']:.1f}s | "
              f"{int(s['raw_duration_sec'] * 1.4 * 3.5)}w | "
              f"{','.join(s['chars']) or '-'} | {','.join(s['depicts'])} | "
              f"{s['censor']} | {s['action']}")
        for sp in speech_for(x0, x1):
            print(f"       SPEECH {sp['start']:.1f}-{sp['end']:.1f}: "
                  f"{str(sp.get('text','')).strip()}")

    if CTX:
        print(f"\nCONTEXT ONLY - {len(CTX)} neighbouring moment(s). "
              f"DO NOT BIND A LINE TO THESE.")
        print("They belong to the adjacent act and another writer owns them. "
              "They are shown so you know what happens either side of your "
              "range. Binding a line here puts two lines over the same "
              "footage, which [WINDOW-OVERLAP] rejects.")
        for s in CTX:
            print(f"  (ctx) {s['id']} | {s['clip_start']} -> {s['clip_end']} | "
                  f"{s['action'][:90]}")

    _drop = [s for s in _long if float(s["end"]) > a and float(s["start"]) < b]
    if _drop:
        print(f"\n!! {len(_drop)} transcript segment(s) overlapping this act were "
              f"SUPPRESSED (longer than {MAX_SEG:.0f}s). Whisper stamped one "
              f"line across minutes of audio there, so its timestamps are not "
              f"trustworthy. Those stretches have NO reliable speech - write "
              f"them from `action` and do not invent dialogue.")
        for s in _drop[:4]:
            print(f"   suppressed {float(s['start']):.0f}s "
                  f"+{float(s['end'])-float(s['start']):.0f}s: "
                  f"{str(s.get('text','')).strip()[:60]}")
    if not segs:
        print("\n!! NO transcript.json - this act has NO speech evidence at all. "
              "Causal links carried by dialogue cannot be written and must not "
              "be guessed.")
    else:
        print(f"\nHOW TO USE THE SPEECH LINES")
        print("- The audio is Thai and the transcript is machine translation. "
              "Per RULES I4 it tells you WHAT IS SAID and WHO IS SPEAKING; it is "
              "NOT a source for what happens on screen. Where transcript and "
              "frames disagree, the frames win.")
        print("- A causal link that only exists in dialogue (who informed on "
              "whom, who paid, what was threatened) can ONLY come from here. "
              "Write it.")
        print("- Any line whose evidence is SPEECH must carry:")
        print('      "claim": {"type": "speech", "subject": "<the speaker>"}')
        print("  and the speaker MUST be in that moment's `chars`, because the "
              "audit checks speaker presence and nothing else (RULES Part J).")
        print("- Never write 'X talks to Y' / 'argues' / 'pitches' when the "
              "transcript tells you WHAT was said. Say the content.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
