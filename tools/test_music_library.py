# -*- coding: utf-8 -*-
"""test_music_library.py - the channel's music comes from one licensed,
classified library (owner, 18 Nov 2026).

  CATALOGUE-SANE   every mood the mix uses has enough tracks; every track
                   names a file, a title and an ISRC; the licence and the
                   author are stated once for all
  FETCH-URLS       fetch asks incompetech for exactly the catalogue's files,
                   skips one already there, and one failure does not stop
                   the rest
  PICK-FILLS       pick writes two cues per mood and a reveal under the
                   names pipeline/music.py looks for, and a CREDITS_cues.md naming
                   every title with the CC BY line; the channel's own bed is
                   left exactly as it was
  NO-REPEAT        the next project gets different tracks (least recently
                   used first) while the library has them
  OLD-KEPT         an existing music/cues/ is moved aside, not overwritten
  MISSING-SAID     a track absent from the library stops pick and names
                   `fetch`
  DESCRIBED        every track says what it sounds like (desc_vi, sound),
                   which scenes it fits (>= 4 scene words) and its energy
  FITS-THE-FILM    a film whose draft is about car chases and the police
                   gets the chase cue among its action cues; the cue
                   descriptions are written next to the files (cues.json)
  PLACED-BY-SCENE  at render, a tense run about waiting for a call gets the
                   waiting cue and a run about sneaking in gets the sneaking
                   one - not whichever the rotation reached; without
                   cues.json the old rotation still runs

Run:  python tools/test_music_library.py      (exit 0 = all pass)
"""
from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import music_library as ML  # noqa: E402
from pipeline import music as M  # noqa: E402


def _lib(tmp: Path, cat: dict) -> Path:
    lib = tmp / "lib"
    lib.mkdir()
    for t in cat["tracks"]:
        (lib / t["file"]).write_bytes(b"x" * 20_000)
    return lib


def t_catalogue():
    cat = ML.load()
    n = Counter(t["mood"] for t in cat["tracks"])
    bad = [m for m in ML.MOODS if n[m] < 4]
    bad += [m for m in ("reveal",) if n[m] < 2]
    bad += [m for m in ("bed", "ending") if n[m]]      # owner: none
    bad += [t.get("title") for t in cat["tracks"]
            if not (t.get("file", "").endswith(".mp3") and t.get("title")
                    and t.get("isrc"))]
    if "Attribution 4.0" not in cat.get("license", "") or not cat.get(
            "author"):
        bad.append("licence/author")
    return not bad, (f"{len(cat['tracks'])} tracks: {dict(n)}" if not bad
                     else f"problems: {bad}")


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def t_fetch():
    tmp = Path(tempfile.mkdtemp(prefix="ml_"))
    try:
        cat = ML.load()
        cat["tracks"] = cat["tracks"][:3]
        lib = tmp / "lib"
        lib.mkdir()
        (lib / cat["tracks"][0]["file"]).write_bytes(b"x" * 20_000)
        asked = []

        def opener(req, timeout=0):
            asked.append(req.full_url)
            if len(asked) == 1:
                raise OSError("connection reset")
            return _Resp(b"y" * 50_000)
        got, had, bad = ML.fetch(cat, lib, opener=opener)
        want = ML.url_of(cat, cat["tracks"][1])
        base = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/"
        ok = (len(had) == 1 and len(bad) == 1 and len(got) == 1
              and asked[0] == want and " " not in want
              and all(u.startswith(base) for u in asked))
        return ok, (f"1 already there, 1 failed, 1 fetched from "
                    f"{asked[-1][:70]}" if ok else f"{got} {had} {bad} "
                    f"{asked}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_pick_fills():
    tmp = Path(tempfile.mkdtemp(prefix="ml_"))
    try:
        cat = ML.load()
        lib = _lib(tmp, cat)
        pdir = tmp / "film2026"
        (pdir / "music").mkdir(parents=True)
        (pdir / "music" / "bed.mp3").write_bytes(b"the channel's own bed")
        picked = ML.pick(cat, pdir, lib, per_mood=2, now=1.0)
        cues = M.cue_files(pdir)
        cr = (pdir / "music" / "CREDITS_cues.md").read_text(encoding="utf-8")
        bad = []
        if (pdir / "music" / "bed.mp3").read_bytes() != \
                b"the channel's own bed":
            bad.append("the channel's bed was touched")
        if M.ending_file(pdir) is not None:
            bad.append("an ending track was placed")
        for m in ML.MOODS:
            if len(cues.get(m, [])) != 2:
                bad.append(f"{m}: {len(cues.get(m, []))} cue(s)")
        if len(cues.get("reveal", [])) != 1:
            bad.append("no reveal")
        miss = [t["title"] for t in picked.values() if t["title"] not in cr]
        if miss or "Attribution 4.0" not in cr or "Kevin MacLeod" not in cr:
            bad.append(f"credits incomplete {miss[:3]}")
        return not bad, (f"{len(picked)} cues placed; music.py finds "
                         f"{sum(len(v) for v in cues.values())}; own bed "
                         f"untouched, no ending; "
                         f"CREDITS_cues.md names them all" if not bad
                         else "; ".join(bad))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_no_repeat():
    tmp = Path(tempfile.mkdtemp(prefix="ml_"))
    try:
        cat = ML.load()
        lib = _lib(tmp, cat)
        a, b = tmp / "a", tmp / "b"
        a.mkdir()
        b.mkdir()
        pa = ML.pick(cat, a, lib, per_mood=2, now=1.0)
        pb = ML.pick(cat, b, lib, per_mood=2, now=2.0)
        fa = {t["file"] for t in pa.values()}
        fb = {t["file"] for t in pb.values()}
        same = fa & fb
        return not same, ("the second film shares no track with the first"
                          if not same else f"repeated: {sorted(same)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_old_kept():
    tmp = Path(tempfile.mkdtemp(prefix="ml_"))
    try:
        cat = ML.load()
        lib = _lib(tmp, cat)
        pdir = tmp / "p"
        (pdir / "music" / "cues").mkdir(parents=True)
        (pdir / "music" / "cues" / "tense1.mp3").write_bytes(b"hand-made")
        ML.pick(cat, pdir, lib, now=1.0)
        olds = list(pdir.glob("music/cues_old_*/tense1.mp3"))
        ok = len(olds) == 1 and olds[0].read_bytes() == b"hand-made"
        return ok, ("the hand-made cues are kept as music/cues_old_*/" if ok
                    else "the old cues were overwritten")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_missing():
    tmp = Path(tempfile.mkdtemp(prefix="ml_"))
    try:
        cat = ML.load()
        lib = tmp / "empty"
        lib.mkdir()
        pdir = tmp / "p"
        pdir.mkdir()
        try:
            ML.pick(cat, pdir, lib)
        except FileNotFoundError as e:
            ok = "fetch" in str(e) and not (pdir / "music" / "cues").exists()
            return ok, ("stops before touching the project and names fetch"
                        if ok else str(e))
        return False, "picked from an empty library"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_described():
    cat = ML.load()
    bad = [t["title"] for t in cat["tracks"]
           if not (t.get("desc_vi") and t.get("sound")
                   and len(t.get("scenes") or []) >= 4
                   and t.get("energy") in (1, 2, 3))]
    return not bad, ("every track has a description, >= 4 scene words and "
                     "an energy" if not bad else f"undescribed: {bad[:5]}")


def t_fits_the_film():
    import json
    tmp = Path(tempfile.mkdtemp(prefix="ml_"))
    try:
        cat = ML.load()
        lib = _lib(tmp, cat)
        pdir = tmp / "fast"
        pdir.mkdir()
        (pdir / "draft.json").write_text(json.dumps({"lines": [
            {"narration": "The chase starts on the road; the police close in "
                          "and the getaway car takes the race downhill."}]}),
            encoding="utf-8")
        picked = ML.pick(cat, pdir, lib, per_mood=3, now=1.0)
        acts = [t["title"] for k, t in picked.items() if k.startswith("action")]
        meta = json.loads((pdir / "music" / "cues" / "cues.json").read_text(
            encoding="utf-8"))
        ok = ("Mistake the Getaway" in acts and len(meta) == len(picked)
              and all(m.get("scenes") for m in meta.values()))
        return ok, (f"action cues {acts}; cues.json describes all "
                    f"{len(meta)}" if ok else f"{acts}; {len(meta)} described")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_placed_by_scene():
    import json
    tmp = Path(tempfile.mkdtemp(prefix="ml_"))
    try:
        cdir = tmp / "music" / "cues"
        cdir.mkdir(parents=True)
        for n in ("tense1.mp3", "tense2.mp3"):
            (cdir / n).write_bytes(b"x")
        cat = {t["title"]: t for t in ML.load()["tracks"]}
        (cdir / "cues.json").write_text(json.dumps({
            "tense1.mp3": cat["Satiate - only percussion"],
            "tense2.mp3": cat["Crypto"]}), encoding="utf-8")
        lines, tl = [], []
        texts = ["They wait for the phone call.", "Still waiting, nervous.",
                 "The deadline passes while they wait.",
                 "Quiet line.", "Quiet line.", "Quiet line.",
                 "Quiet line.", "Quiet line.",
                 "They sneak in through the back.", "She tracks the guard.",
                 "They move in and search the office."]
        for i, t in enumerate(texts, 1):
            tense = i <= 3 or i >= 9
            lines.append({"id": i, "narration": t,
                          "delivery": "tense" if tense else "normal"})
            tl.append({"id": i, "start": (i - 1) * 10.0,
                       "end": (i - 1) * 10.0 + 9.0})
        cues = M.cue_files(tmp)
        plan = M.plan_cues({"lines": lines}, tl, cues, [], [])
        got = [p["file"].name for p in plan]
        (cdir / "cues.json").unlink()
        plain = [p["file"].name for p in M.plan_cues({"lines": lines}, tl,
                                                     M.cue_files(tmp), [], [])]
        ok = got == ["tense2.mp3", "tense1.mp3"] and plain == [
            "tense1.mp3", "tense2.mp3"]
        return ok, (f"waiting run -> Crypto, sneaking run -> Satiate "
                    f"Percussion; without cues.json the rotation gives "
                    f"{plain}" if ok else f"{got} / plain {plain}: "
                    f"{[p['why'] for p in plan]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


TESTS = [("CATALOGUE-SANE", t_catalogue), ("FETCH-URLS", t_fetch),
         ("PICK-FILLS", t_pick_fills), ("NO-REPEAT", t_no_repeat),
         ("OLD-KEPT", t_old_kept), ("MISSING-SAID", t_missing),
         ("DESCRIBED", t_described), ("FITS-THE-FILM", t_fits_the_film),
         ("PLACED-BY-SCENE", t_placed_by_scene)]

if __name__ == "__main__":
    fails = 0
    for name, fn in TESTS:
        try:
            ok, msg = fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            ok, msg = False, f"{type(e).__name__}: {e}"
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:15s} {msg}")
    print("-" * 60)
    print("test_music_library: all pass" if not fails
          else f"test_music_library: {fails} FAILURE(S)")
    sys.exit(1 if fails else 0)
