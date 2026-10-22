# -*- coding: utf-8 -*-
"""measure_voice.py - do giong ke cua cac kenh recap tu file phu de.

    python tools/measure_voice.py references/voice/*.vtt
    python tools/measure_voice.py --selftest

TAI SAO CO FILE NAY, va gioi han cua no:

Phu de TU DONG cua YouTube thuong KHONG co dau cau va KHONG viet hoa. Neu cu
the ma tinh "do dai cau trung binh / SD", thi thuc chat dang do do dai CUE
(moi cue ~1-3 giay YouTube tu cat), roi goi no la "cau". Day dung la loai
"do luong hinh thuc" ma repo nay da bi dot nhieu lan: mot con so co ve chinh
xac, do mot thu khac voi thu minh tuyen bo.

Nen cong cu nay:
  - TU PHAT HIEN phu de co dau cau hay khong (mat do '.', '?', '!' tren tu);
  - neu KHONG co dau cau -> KHONG in thong ke cau, va noi ro vi sao;
  - khi co dau cau -> in thong ke cau VA ghi ro nguon la phu de tay hay tu dong.

Phu de tu dong con mot bay thu hai: chung CUON (rolling). Cung mot cum tu xuat
hien lai o cue sau nhu phan dau cua cue tiep theo, nen dem tu tho se phong len
~2x. Ham _dedupe_rolling() xu ly viec do va self-test kiem chinh no.
"""
from __future__ import annotations
import argparse, glob, io, os, re, sys, json
import statistics as st

# ----------------------------------------------------------------- parsing --
_TS = re.compile(r"(\d+):(\d{2}):(\d{2})[.,](\d{3})")


def _t(s: str) -> float:
    m = _TS.search(s)
    if not m:
        return -1.0
    h, mi, se, ms = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + se + ms / 1000.0


def parse_vtt(path: str) -> list:
    """Return [(start, end, text)] from a .vtt / .srt file."""
    raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    raw = raw.replace("\r\n", "\n")
    cues = []
    for block in re.split(r"\n\n+", raw):
        if "-->" not in block:
            continue
        lines = [l for l in block.split("\n") if l.strip()]
        tl = next((l for l in lines if "-->" in l), None)
        if not tl:
            continue
        a, _, b = tl.partition("-->")
        s, e = _t(a), _t(b)
        if s < 0 or e < 0:
            continue
        body = " ".join(l for l in lines if "-->" not in l
                        and not re.fullmatch(r"\d+", l.strip())
                        and not l.startswith(("WEBVTT", "Kind:", "Language:")))
        # strip inline karaoke timing tags and basic markup
        body = re.sub(r"<[^>]+>", "", body)
        body = re.sub(r"\s+", " ", body).strip()
        if body:
            cues.append((s, e, body))
    return cues


def _dedupe_rolling(cues: list) -> str:
    """Join cues, removing the ROLLING overlap auto-captions produce.

    Auto-captions repeat the tail of a cue at the head of the next one. Naive
    joining roughly doubles the word count, which would then be divided by the
    real duration and reported as a WPM about twice the truth.
    Strategy: for each new cue, find the longest suffix of what we have so far
    that is also a prefix of the new cue, and drop it.
    """
    out: list = []
    for _s, _e, text in cues:
        w = text.split()
        if not out:
            out.extend(w)
            continue
        maxk = min(len(w), 24, len(out))
        k = 0
        for n in range(maxk, 0, -1):
            if [x.lower() for x in out[-n:]] == [x.lower() for x in w[:n]]:
                k = n
                break
        out.extend(w[k:])
    return " ".join(out)


# ------------------------------------------------------------- punctuation --
def punctuation_density(text: str) -> float:
    w = max(1, len(text.split()))
    return len(re.findall(r"[.!?]", text)) / w


HAS_PUNCT = 0.015      # >= this many sentence marks per word = usable
# Mot van ban tieng Anh/Viet binh thuong co ~1 dau cau moi 12-20 tu
# (0.05-0.08). Nguong 0.015 la rat long: duoi no thi gan nhu chac chan la phu
# de tu dong khong dau cau.


def sentences(text: str) -> list:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


# ------------------------------------------------------------------ voice ---
# Cac dau hieu do duoc. Moi nhom la mot PROXY, va duoc goi dung ten la proxy.
EN_ASIDE = [
    (r"\b(i|i'm|i've|i'd|me|my)\b", "first person"),
    (r"\byou\b|\byour\b|\byou're\b", "second person"),
    (r"\b(honestly|frankly|of course|apparently|somehow|obviously|clearly)\b",
     "stance adverb"),
    (r"\b(poor|classic|genius|brilliant|terrible|insane|wild|brutal)\b",
     "evaluative adjective"),
    (r"\b(yeah|yep|nope|well|look|okay|alright)\b", "conversational filler"),
    (r"\b(turns out|as you(?:'d| would) expect|naturally|no surprise)\b",
     "knowing aside"),
    (r"\?", "question to viewer"),
]
VI_ASIDE = [
    (r"\b(tôi|tớ|mình|anh em|các bạn|bạn)\b", "address / first person"),
    (r"\b(thật ra|thực ra|nói thật|công nhận|quả thật|rõ ràng)\b", "stance"),
    (r"\b(đấy|nhé|nha|á|ơ|ồ|chứ|cơ|luôn|hẳn)\b", "sentence-final particle"),
    (r"\b(kiểu|kiểu như|đúng kiểu)\b", "hedge/compare"),
    (r"\b(dã man|kinh khủng|bá đạo|đỉnh|xịn|gắt|vl|vcl)\b", "slang intensifier"),
    (r"\?", "question to viewer"),
]
EN_TRANSITION = [
    r"\bmeanwhile\b", r"\bback (?:at|in|to)\b", r"\bthe next (?:day|morning|night)\b",
    r"\bbut (?:first|before)\b", r"\bso\b", r"\banyway\b", r"\bnow\b",
    r"\bthat(?:'s| is) when\b", r"\bturns out\b", r"\bhere(?:'s| is) the thing\b",
]
VI_TRANSITION = [
    r"\btrong khi đó\b", r"\bquay (?:lại|về)\b", r"\bhôm sau\b", r"\bsáng hôm sau\b",
    r"\bnhưng (?:trước|mà)\b", r"\bthế là\b", r"\bvà rồi\b", r"\bbấy giờ\b",
    r"\bhóa ra\b", r"\bvấn đề là\b", r"\bcơ mà\b", r"\bnói chung\b",
]


def count_patterns(text: str, pats) -> dict:
    low = text.lower()
    out = {}
    for item in pats:
        pat, label = item if isinstance(item, tuple) else (item, item)
        n = len(re.findall(pat, low))
        if n:
            out[label] = out.get(label, 0) + n
    return out


def window_text(cues: list, a: float, b: float) -> str:
    return _dedupe_rolling([c for c in cues if c[1] > a and c[0] < b])


def report(path: str, lang: str) -> dict:
    cues = parse_vtt(path)
    if not cues:
        print(f"!! {os.path.basename(path)}: no cues parsed")
        return {}
    dur = max(c[1] for c in cues)
    full = _dedupe_rolling(cues)
    naive = " ".join(c[2] for c in cues)
    words = len(full.split())
    pd = punctuation_density(full)
    name = os.path.basename(path)
    print("=" * 74)
    print(name)
    print("  duration        %.1f min (%d cues)" % (dur / 60.0, len(cues)))
    print("  words           %d after de-rolling (%d naive, x%.2f inflation)"
          % (words, len(naive.split()),
             len(naive.split()) / max(1, words)))
    print("  WPM             %.1f  (words / full duration, silence included)"
          % (words / max(1e-9, dur / 60.0)))
    print("  punctuation     %.4f marks/word -> %s"
          % (pd, "USABLE" if pd >= HAS_PUNCT else "NOT USABLE"))
    out = {"file": name, "lang": lang, "dur_min": dur / 60.0,
           "words": words, "wpm": words / max(1e-9, dur / 60.0),
           "punct_density": pd}

    if pd >= HAS_PUNCT:
        sl = [len(s.split()) for s in sentences(full)]
        if len(sl) > 1:
            print("  sentence words  mean %.1f  SD %.1f  min %d  max %d  (n=%d)"
                  % (st.mean(sl), st.pstdev(sl), min(sl), max(sl), len(sl)))
            out.update(sent_mean=st.mean(sl), sent_sd=st.pstdev(sl),
                       sent_n=len(sl))
    else:
        print("  sentence stats  SKIPPED - these captions carry no sentence")
        print("                  punctuation, so any 'sentence length' figure")
        print("                  would really be YouTube's cue length wearing")
        print("                  a sentence's name. Cue length instead:")
        cl = [len(c[2].split()) for c in cues]
        print("                  cue words mean %.1f SD %.1f (NOT sentences)"
              % (st.mean(cl), st.pstdev(cl)))
        out.update(cue_mean=st.mean(cl), cue_sd=st.pstdev(cl))

    asides = EN_ASIDE if lang == "en" else VI_ASIDE
    trans = EN_TRANSITION if lang == "en" else VI_TRANSITION
    ac = count_patterns(full, asides)
    tc = count_patterns(full, trans)
    tot_a = sum(ac.values())
    print("  aside markers   %d total = 1 per %.0f words"
          % (tot_a, words / max(1, tot_a)))
    for k, v in sorted(ac.items(), key=lambda x: -x[1]):
        print("                    %-26s %d" % (k, v))
    print("  transitions     %d total" % sum(tc.values()))
    for k, v in sorted(tc.items(), key=lambda x: -x[1])[:6]:
        print("                    %-26s %d" % (k, v))
    out.update(asides=ac, aside_total=tot_a, transitions=tc)

    print("  --- FIRST 30s ---")
    print("   ", (window_text(cues, 0, 30)[:420] or "(empty)"))
    print("  --- LAST 30s ---")
    print("   ", (window_text(cues, dur - 30, dur + 1)[:420] or "(empty)"))
    out["first30"] = window_text(cues, 0, 30)
    out["last30"] = window_text(cues, dur - 30, dur + 1)
    return out


# --------------------------------------------------------------- self-test --
def selftest() -> int:
    ok = True
    print("### de-rolling must undo auto-caption overlap")
    cues = [(0.0, 2.0, "a girl sits down at a long"),
            (1.5, 3.5, "a girl sits down at a long table in a dark"),
            (3.0, 5.0, "table in a dark room and her reflection runs")]
    got = _dedupe_rolling(cues)
    want = ("a girl sits down at a long table in a dark room and her "
            "reflection runs")
    print("  got : %s" % got)
    if got != want:
        print("  FAIL: expected %r" % want)
        ok = False
    else:
        print("  PASS: %d words, not %d"
              % (len(got.split()), sum(len(c[2].split()) for c in cues)))

    print()
    print("### punctuation detector, both directions")
    no_p = "he walks into the room and nobody looks up at him at all"
    yes_p = "He walks in. Nobody looks up. That is the whole scene, really."
    a, b = punctuation_density(no_p), punctuation_density(yes_p)
    print("  unpunctuated %.4f -> %s" % (a, "usable" if a >= HAS_PUNCT else "skip"))
    print("  punctuated   %.4f -> %s" % (b, "usable" if b >= HAS_PUNCT else "skip"))
    if not (a < HAS_PUNCT <= b):
        print("  FAIL: detector does not separate the two")
        ok = False
    else:
        print("  PASS")

    print()
    print("### WPM must use real duration, not cue sum")
    cues2 = [(0.0, 60.0, " ".join(["word"] * 120))]
    tmp = os.path.join(os.environ.get("TEMP", "."), "_mv_selftest.vtt")
    io.open(tmp, "w", encoding="utf-8").write(
        "WEBVTT\n\n00:00:00.000 --> 00:01:00.000\n"
        + " ".join(["word"] * 120) + "\n")
    c3 = parse_vtt(tmp)
    w = len(_dedupe_rolling(c3).split())
    d = max(x[1] for x in c3)
    wpm = w / (d / 60.0)
    print("  120 words over 60s -> %.0f WPM" % wpm)
    os.remove(tmp)
    if abs(wpm - 120) > 1:
        print("  FAIL")
        ok = False
    else:
        print("  PASS")
    print()
    print("RESULT:", "ALL SELF-TESTS PASS" if ok else "SELF-TEST FAILURE")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    paths: list = []
    for pat in a.files:
        paths += sorted(glob.glob(pat))
    if not paths:
        ap.error("no caption files matched")
    rows = []
    for p in paths:
        lang = "vi" if (".vi" in p or "saukura" in os.path.basename(p)) else "en"
        r = report(p, lang)
        if r:
            rows.append(r)
        print()
    if a.json:
        io.open(a.json, "w", encoding="utf-8").write(
            json.dumps(rows, ensure_ascii=False, indent=2))
        print("wrote", a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
