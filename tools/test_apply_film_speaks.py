"""tools/apply_film_speaks.py - selection -> draft.json, on the Tokyo Drift fixture.

Fixture: a COPY of projects/tokyodrift2006 (its film_speaks_selection.json and
current draft.json), never the project itself.

Cases
-----
  STALE-IDS-REFUSED     the real selection names line ids from an earlier draft;
                        the texts are NOT pasted onto whatever line sits there
                        now, the run exits 1 and says why, the units are not
                        duplicated.
  HOST-ENDS-AT-QUOTE    with the units removed and the host windows running
                        over the quotes: units are inserted after their host,
                        each host window ends exactly where its quote begins,
                        before/after texts are applied, and recap.py draft
                        reports no [FOOTAGE-REUSE] and no error the untouched
                        draft did not already have.
  HOST-EXTENDS-BACK     a host left too short for its narration by the trim is
                        extended BACKWARDS, never into the previous line.
  BY-POSITION           --by-position applies stale-id texts to the actual
                        neighbours and says it did.

Run:  python tools/test_apply_film_speaks.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config  # noqa: E402
import apply_film_speaks as afs  # noqa: E402
from pipeline.draft import parse_ts  # noqa: E402

SRC = "tokyodrift2006"
PROJ = "_fs_apply_fixture"


def _setup() -> Path:
    src = Path(config.project_dir(SRC))
    dst = Path(config.project_dir(PROJ))
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
        "narration", "*.mp4", "*.wav", "_*"))
    d = _load(dst / "draft.json")
    d["title"] = str(d.get("title")) + " (apply fixture)"   # not [TITLE-MATCH]
    _save(dst / "draft.json", d)
    return dst


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8-sig"))


def _save(p: Path, obj) -> None:
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2),
                 encoding="utf-8")


def _by_id(d):
    return {ln["id"]: ln for ln in d["lines"]}


def _problems(pdir: Path) -> tuple[int, set, str]:
    r = subprocess.run([sys.executable, "recap.py", "draft", "--project",
                        PROJ], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = r.stdout + r.stderr
    tags = set(re.findall(r"^\s*- \[([A-Z0-9-]+)\]", out, re.M))
    tags |= set(re.findall(r"Audit failed hard: \d+ ([A-Z-]+)", out))
    return r.returncode, tags, out


def _strip_units(d: dict, sel: dict) -> dict:
    """The draft as it was BEFORE any unit: drop units at the picks' spans
    and let each host window run over its quote again."""
    starts = [float(p["start"]) for p in sel["selected"]]
    keep = []
    for ln in d["lines"]:
        if ln.get("film_speaks_seconds") is not None and ln.get("clip_start") \
                and any(abs(parse_ts(ln["clip_start"]) - s) < 0.05
                        for s in starts):
            continue
        keep.append(ln)
    d["lines"] = keep
    return d


def test_stale_ids_refused():
    pdir = _setup()
    try:
        before = _load(pdir / "draft.json")
        rc = afs.main(["--project", PROJ])
        after = _load(pdir / "draft.json")
        if rc != 1:
            return False, f"stale selection exited {rc}, want 1"
        b, a = _by_id(before), _by_id(after)
        changed = [i for i in b if i in a and b[i].get("narration")
                   != a[i].get("narration")]
        if changed:
            return False, f"stale texts were pasted onto lines {changed}"
        n_units = [len([x for x in d["lines"]
                        if x.get("film_speaks_seconds") is not None])
                   for d in (before, after)]
        if n_units[0] != n_units[1]:
            return False, f"units duplicated: {n_units[0]} -> {n_units[1]}"
        return True, (f"stale line ids refused (exit 1), no text pasted, "
                      f"{n_units[1]} units kept, none duplicated")
    finally:
        shutil.rmtree(pdir, ignore_errors=True)


def test_host_ends_at_quote():
    pdir = _setup()
    try:
        rc0, base, _ = _problems(pdir)
        sel = _load(pdir / "film_speaks_selection.json")
        d = _load(pdir / "draft.json")
        ids = [ln["id"] for ln in d["lines"]]
        # the neighbours as the CURRENT draft has them, for each pick
        nbrs = []
        for p in sel["selected"]:
            ui = next(i for i, ln in enumerate(d["lines"])
                      if ln.get("film_speaks_seconds") is not None
                      and abs(parse_ts(ln["clip_start"]) - p["start"]) < 0.05)
            nbrs.append((ids[ui - 1], ids[ui + 1]))
            p["before"]["line_id"], p["after"]["line_id"] = nbrs[-1]
        _save(pdir / "film_speaks_selection.json", sel)
        d = _strip_units(d, sel)
        by = _by_id(d)
        for (host, _after), p in zip(nbrs, sel["selected"]):
            by[host]["clip_end"] = afs._ts(p["end"])        # runs over quote
        _save(pdir / "draft.json", d)
        rc = afs.main(["--project", PROJ])
        if rc != 0:
            return False, f"apply exited {rc} on a consistent selection"
        d2 = _load(pdir / "draft.json")
        by2 = _by_id(d2)
        order = [ln["id"] for ln in d2["lines"]]
        for (host, aft), p in zip(nbrs, sel["selected"]):
            if abs(parse_ts(by2[host]["clip_end"]) - p["start"]) > 1e-3:
                return False, (f"host {host} ends at "
                               f"{by2[host]['clip_end']}, quote starts "
                               f"{p['start']}")
            unit = d2["lines"][order.index(host) + 1]
            if unit.get("film_speaks_seconds") != round(p["seconds"], 2):
                return False, f"no unit right after host {host}"
            if by2[host]["narration"] != p["before"]["new_narration"].strip() \
                    or by2[aft]["narration"] != \
                    p["after"]["new_narration"].strip():
                return False, f"before/after texts not applied around {host}"
        rc2, tags, out = _problems(pdir)
        if "FOOTAGE-REUSE" in tags or "[FOOTAGE-REUSE]" in out:
            return False, "[FOOTAGE-REUSE] after applying"
        new = tags - base
        # Replacing narration after the review was signed MUST re-open the
        # review (film.md: an edit no resolved finding names fails the gate),
        # and the new sentences are judged afresh. Those are the system
        # working, and are reported. Anything about footage, capacity or the
        # units themselves is the applier's fault and fails here.
        review = {"COLD-READ", "REVIEWER", "SAME-POINT", "TIC-REPETITION"}
        structural = new - review
        if structural:
            return False, (f"applying introduced draft error(s): "
                           f"{sorted(structural)}")
        return True, (f"units after hosts {[h for h, _ in nbrs]}, hosts end "
                      f"at their quotes, texts applied; recap.py draft: no "
                      f"FOOTAGE-REUSE, no new structural error (pre-existing: "
                      f"{sorted(base) or 'none'}; re-opened by the text "
                      f"edit, as designed: {sorted(new) or 'none'})")
    finally:
        shutil.rmtree(pdir, ignore_errors=True)


def test_host_extends_back():
    lines = [
        {"id": 1, "clip_start": "00:01:00.000", "clip_end": "00:01:10.000",
         "narration": "one two three", "delivery": "normal"},
        {"id": 2, "clip_start": "00:01:28.000", "clip_end": "00:01:40.000",
         "narration": " ".join(["word"] * 30), "delivery": "normal"},
        {"id": 3, "clip_start": "00:01:40.000", "clip_end": "00:01:50.000",
         "narration": "after that", "delivery": "normal"},
    ]
    sel = {"selected": [{"start": 90.0, "end": 95.0, "seconds": 5.0,
                         "quote": "q", "criterion": "thesis"}]}
    d = {"lines": [dict(x) for x in lines]}
    acts, finds = afs.apply(d, sel)
    h = _by_id(d)[2]
    a, b = parse_ts(h["clip_start"]), parse_ts(h["clip_end"])
    nxt = _by_id(d)[3]
    if abs(b - 90.0) > 1e-3:
        return False, f"host ends at {b}, quote starts 90.0"
    if not (70.0 - 1e-3 <= a < 88.0):
        return False, f"host start {a}: not extended back, or into line 1"
    if not afs._fits(h, a, b):
        return False, f"host still does not fit {a}-{b}: {finds}"
    if parse_ts(nxt["clip_start"]) < 95.0 - 1e-3:
        return False, "the line after still overlaps the quote"
    return True, (f"host trimmed to end at 90.0 and extended back to {a:.2f} "
                  f"(previous line ends 70.0); line after moved to 95.0")


def test_by_position():
    pdir = _setup()
    try:
        sel = _load(pdir / "film_speaks_selection.json")
        rc = afs.main(["--project", PROJ, "--by-position"])
        d = _load(pdir / "draft.json")
        texts = {ln.get("narration") for ln in d["lines"]}
        missing = [p[s]["new_narration"] for p in sel["selected"]
                   for s in ("before", "after")
                   if p[s]["new_narration"].strip() not in texts]
        if rc != 0 or missing:
            return False, f"rc {rc}, texts not applied: {len(missing)}"
        return True, "stale-id texts applied to the actual neighbours"
    finally:
        shutil.rmtree(pdir, ignore_errors=True)


def test_cut_between():
    """Lost in the Stars pick 2: a 14.9 s quote over lines 167-171 (they
    paraphrase it), the selection naming 165 before and 172 after. The lines
    between are cut, the unit carries their slots, both texts are applied
    and no window goes negative. A pair that does not frame the quote cuts
    nothing."""
    T = lambda s_: afs._ts(s_)              # noqa: E731
    def L(i, a, b, t, **kw):
        return dict({"id": i, "slot": f"S{i}", "narration": t,
                     "clip_start": T(a), "clip_end": T(b)}, **kw)
    lines = [L(165, 5049.667, 5066.333, "He Fei breaks, eyes wet."),
             L(166, 5066.333, 5071.333, "", narration_silence_seconds=5.0),
             L(167, 5083.0, 5086.4, "A rental form."),
             L(168, 5086.4, 5089.8, "She asks if Muzi went missing?"),
             L(169, 5089.8, 5093.2, "He rented one."),
             L(170, 5093.2, 5096.6, "He planned beach fireworks."),
             L(171, 5096.6, 5100.0, "", narration_silence_seconds=3.4),
             L(172, 5100.083, 5119.818, "In flashback, he books the spot.")]
    sel = {"selected": [{"start": 5085.32, "end": 5100.2, "quote": "q",
                         "before": {"line_id": 165, "new_narration":
                                    "He Fei breaks; she slides a paper over."},
                         "after": {"line_id": 172, "new_narration":
                                   "Two sets of gear. One was his."}}]}
    d = {"lines": [dict(x) for x in lines]}
    acts, finds = afs.apply(d, sel)
    ids = [x["id"] for x in d["lines"]]
    unit = [x for x in d["lines"] if x.get("film_speaks_seconds")]
    bad = []
    if ids[:1] != [165] or ids[2:] != [172] or len(ids) != 3:
        bad.append(f"order {ids}")
    if not unit or unit[0].get("film_speaks_covers") != [
            "S166", "S167", "S168", "S169", "S170", "S171"]:
        bad.append(f"covers {unit[0].get('film_speaks_covers') if unit else None}")
    by = {x["id"]: x for x in d["lines"]}
    if not by[165]["narration"].startswith("He Fei breaks; she") or \
            not by[172]["narration"].startswith("Two sets"):
        bad.append("neighbour texts not applied")
    for x in d["lines"]:
        w = afs._win(x)
        if w and w[1] < w[0]:
            bad.append(f"line {x['id']} negative window")
    if finds:
        bad.append(f"findings {finds}")
    # a pair that does not frame the quote: nothing cut
    d2 = {"lines": [dict(x) for x in lines]}
    sel2 = {"selected": [dict(sel["selected"][0],
                              before={"line_id": 168, "new_narration": "x"},
                              after={"line_id": 172, "new_narration": "y"})]}
    afs.apply(d2, sel2)
    if len([x for x in d2["lines"] if not x.get("film_speaks_seconds")]) < 6:
        bad.append("a pair that does not frame the quote cut lines")
    from pipeline import draft as D
    return (not bad), ("lines 166-171 cut and conserved on the unit; texts "
                       "applied; no negative window; a non-framing pair "
                       "cuts nothing" if not bad else "; ".join(bad))


TESTS = {
    "STALE-IDS-REFUSED":  test_stale_ids_refused,
    "HOST-ENDS-AT-QUOTE": test_host_ends_at_quote,
    "HOST-EXTENDS-BACK":  test_host_extends_back,
    "BY-POSITION":        test_by_position,
    "CUT-BETWEEN":        test_cut_between,
}

if __name__ == "__main__":
    want = sys.argv[1:] or list(TESTS)
    bad = 0
    for name in want:
        fn = TESTS.get(name)
        if fn is None:
            print(f"?? no such test: {name}")
            continue
        try:
            ok, msg = fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            ok, msg = False, f"{type(e).__name__}: {e}"
        print(f'{"PASS" if ok else "FAIL"}  {name:<20} {msg}')
        bad += (not ok)
    print("-" * 60)
    print("test_apply_film_speaks: all pass" if not bad else
          f"test_apply_film_speaks: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
