"""Cross-video variation gates and the per-film titles - both directions.

THE CONTRACT (docs/DESIGN_human_variation.md v2, approved):
  - history empty -> NOT RUN, never a pass
  - brand lines (greeting/CTA) exempt; content measured by words the
    viewer hears
  - warn-only; TITLE-FORMULA is the LAST layer after package.py was
    fixed to write titles per film - the bank is gone for good
  - ship = one deliberate command: history entry + claims-ledger line

Cases:
  EMPTY-HISTORY       no history -> NOT RUN, never a silent pass.
  TITLE-MD5           a byte-identical titles.txt fires; a per-film one
                      does not.
  TITLE-STREAK        three titles in a row opening on he/she/they
                      fire; a broken pattern does not.
  CROSSPOST           an identical final.mp4 md5 fires; a different one
                      does not; no final.mp4 -> NOT RUN.
  STRUCTURE-NUMBER    role-share cosine prints as a number (report),
                      never as a gate finding.
  SNAPSHOT-BRAND      the greeting/CTA words are not in the snapshot;
                      the cold open's words are.
  TITLES-PER-FILM     two projects with different drafts get different
                      titles.txt line by line; no draft -> no bank
                      fallback, ever.
  SHIP-RECORD         ship writes history + one claims line; recording
                      again overwrites, never duplicates.

Run:  python tools/test_variation.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config                                    # noqa: E402
from pipeline import variation as V              # noqa: E402

P = "_var_test"
PDIR = Path(config.project_dir(P))


def _proj(name: str, draft: dict, titles: str | None = None,
          final_bytes: bytes | None = None) -> Path:
    d = Path(config.project_dir(name))
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    (d / "draft.json").write_text(json.dumps(draft, ensure_ascii=False),
                                  encoding="utf-8")
    if titles is not None:
        (d / "titles.txt").write_text(titles, encoding="utf-8")
    if final_bytes is not None:
        (d / "final.mp4").write_bytes(final_bytes)
    return d


def _draft(title, opens, outro, mode="A"):
    lines = [{"id": i + 1, "note": "OPEN", "narration": t,
              "delivery": "normal", "payload": "stake",
              "clip_start": "00:00:10.000", "clip_end": "00:00:14.000"}
             for i, t in enumerate(opens)]
    lines.append({"id": len(lines) + 1, "delivery": "intro",
                  "film_intro": True,
                  "narration": "This is Serabudabu, and today I am "
                               "walking you through the film."})
    lines.append({"id": len(lines) + 1, "delivery": "outro",
                  "narration": outro})
    return {"title": title, "open_mode": mode, "lines": lines}


_OPEN_A = ["Arizona, and a quarter mile of fresh asphalt decides a life.",
           "The wreck costs him the car and the last deal.",
           "Will one more crash put him away for good?"]
_OPEN_B = ["Sheet metal folds around a driver at an impossible speed.",
           "The crash costs him the car and the last deal.",
           "Will the city that runs on sideways cars put him away?"]
_OUTRO = ("The only car that was ever really his is the one he gave "
          "back. Subscribe and tell me what to recap next.")


def test_empty_history():
    _proj(P, _draft("A Teenager Bets His Life on One Downhill Race",
                    _OPEN_A, _OUTRO))
    f = V.compare({}, V.snapshot(P))
    missing = V.compare(None, V.snapshot(P))
    ok = (len(f) == 1 and "first video" in f[0]
          and len(missing) == 1 and "MISSING" in missing[0])
    return ok, f"{f[0]} | {missing[0][:60]}"


def test_title_md5():
    _proj(P, _draft("A Teenager Bets His Life on One Downhill Race",
                    _OPEN_A, _OUTRO),
          titles="1. same bank line\n2. same bank line two\n")
    cur = V.snapshot(P)
    hist = {"prev": dict(cur, project="prev", shipped_at="2026-11-01T00:00")}
    fires = V.compare(hist, cur)
    cur2 = dict(cur, titles_txt_md5="different" + (cur["titles_txt_md5"]
                                                   or ""))
    quiet = [f for f in V.compare(hist, cur2) if "identical" in f]
    ok = any("[TITLE-FORMULA]" in f and "byte-identical" in f
             for f in fires) and not quiet
    return ok, f"{[f for f in fires if 'TITLE' in f][:1]} / quiet={quiet}"


def test_title_streak():
    cur = V.snapshot(_proj(P, _draft("He Bets His Life on One Downhill",
                                     _OPEN_A, _OUTRO)))
    hist = {"a": dict(V.snapshot(_proj(P, _draft("She Bets It All",
                                                 _OPEN_B, _OUTRO))),
                      project="a", shipped_at="2026-11-01"),
            "b": dict(V.snapshot(_proj(P, _draft("They Race the Yakuza",
                                                 _OPEN_A, _OUTRO))),
                      project="b", shipped_at="2026-11-02")}
    fires = [f for f in V.compare(hist, cur) if "three titles" in f]
    cur2 = V.snapshot(_proj(P, _draft("One Downhill Race Decides a Life",
                                      _OPEN_A, _OUTRO)))
    quiet = [f for f in V.compare(hist, cur2) if "three titles" in f]
    return (bool(fires) and not quiet), f"streak {bool(fires)} / quiet ok"


def test_crosspost():
    blob = b"mp4-bytes-same-render"
    _proj(P, _draft("A Teenager Bets His Life on One Downhill Race",
                    _OPEN_A, _OUTRO), final_bytes=blob)
    cur = V.snapshot(P)
    hist = {"prev": dict(cur, project="prev", shipped_at="2026-11-01")}
    fires = [f for f in V.compare(hist, cur) if "CROSSPOST" in f]
    _proj(P, _draft("A Teenager Bets His Life on One Downhill Race",
                    _OPEN_A, _OUTRO), final_bytes=b"mp4-bytes-OTHER")
    quiet = [f for f in V.compare(hist, V.snapshot(P))
             if "CROSSPOST" in f and "NOT RUN" not in f]
    _proj(P, _draft("A Teenager Bets His Life on One Downhill Race",
                    _OPEN_A, _OUTRO), final_bytes=None)
    notrun = [f for f in V.compare(hist, V.snapshot(P))
              if "CROSSPOST" in f and "NOT RUN" in f]
    return (bool(fires) and not quiet and bool(notrun)), \
        f"fires/quiet/notrun = {bool(fires)}/{bool(quiet)}/{bool(notrun)}"


def test_structure_number():
    cur = V.snapshot(P)
    cur["role_share"] = {"action": 0.3, "reaction": 0.2, "bridge": 0.28,
                         "quote": 0.09, "intro": 0.01, "outro": 0.01}
    hist = {"prev": dict(cur, project="prev", shipped_at="2026-11-01",
                         role_share={"action": 0.31, "reaction": 0.19,
                                     "bridge": 0.29, "quote": 0.09,
                                     "intro": 0.01, "outro": 0.01})}
    f = [x for x in V.compare(hist, cur) if "STRUCTURE-ECHO" in x]
    ok = bool(f) and "cosine" in f[0] and "measurement" in f[0]
    return ok, f[0] if f else "no cosine printed"


def test_snapshot_brand():
    _proj(P, _draft("A Teenager Bets His Life on One Downhill Race",
                    _OPEN_A, _OUTRO))
    s = V.snapshot(P)
    co = " ".join(s["cold_open"])
    ft = " ".join(s["final_thesis"])
    ok = ("serabudabu" not in co and "subscribe" not in ft
          and "recap next" not in ft
          and "arizona" in co and "quarter" in co
          and "gave back" in ft)
    return ok, f"cold_open={co!r} final_thesis={ft!r}"


def test_titles_per_film():
    from pipeline import package as PK
    _proj(P, _draft("A Teenager Bets His Life on One Downhill Race",
                    _OPEN_A, _OUTRO))
    PK.write_titles(P)
    t1 = (PDIR / "titles.txt").read_text(encoding="utf-8-sig")
    _proj(P, _draft("The Kitchen That Trained a Spy She Cannot Kill",
                    ["Tokyo, and a kitchen knife decides two futures.",
                     "The menu costs her the mentor she loved.",
                     "Will the spy survive her own graduation dinner?"],
                    _OUTRO))
    PK.write_titles(P)
    t2 = (PDIR / "titles.txt").read_text(encoding="utf-8-sig")
    # numbered lines only - the header is shared by design
    n1 = [x for x in t1.splitlines() if x[:1].isdigit()]
    n2 = [x for x in t2.splitlines() if x[:1].isdigit()]
    shared = set(n1) & set(n2)
    ok = bool(n1) and bool(n2) and not shared \
        and "Sharks" not in t1 + t2
    # no draft -> no bank fallback
    d = Path(config.project_dir("_var_test_empty"))
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    PK.write_titles("_var_test_empty")
    nofb = not (d / "titles.txt").exists()
    return ok and nofb, \
        f"per-film distinct={not shared}, no-bank-fallback={nofb}"


def test_ship_record():
    hist_path, claims_path = V.HISTORY, V.CLAIMS
    V.HISTORY = Path(config.project_dir("_var_test_store")) / "history.json"
    V.CLAIMS = Path(str(V.HISTORY).replace("history.json", "claims.jsonl"))
    try:
        _proj(P, _draft("A Teenager Bets His Life on One Downhill Race",
                        _OPEN_A, _OUTRO))
        V.record(P, lane="dtv-thriller", claim_status="none")
        V.record(P, lane="dtv-thriller", claim_status="monetize",
                 claimant="UMPG", when="2026-11-10T12:00:00")
        h = json.loads(V.HISTORY.read_text(encoding="utf-8"))
        rows = [json.loads(x) for x in
                V.CLAIMS.read_text(encoding="utf-8").splitlines() if x]
        ok = (list(h) == [P]                     # overwrite, no duplicate
              and len(rows) == 2                 # ledger appends
              and rows[-1]["claimant"] == "UMPG"
              and h[P]["lane"] == "dtv-thriller")
        return ok, f"history keys={list(h)}, ledger rows={len(rows)}"
    finally:
        V.HISTORY, V.CLAIMS = hist_path, claims_path


TESTS = {
    "EMPTY-HISTORY": test_empty_history,
    "TITLE-MD5": test_title_md5,
    "TITLE-STREAK": test_title_streak,
    "CROSSPOST": test_crosspost,
    "STRUCTURE-NUMBER": test_structure_number,
    "SNAPSHOT-BRAND": test_snapshot_brand,
    "TITLES-PER-FILM": test_titles_per_film,
    "SHIP-RECORD": test_ship_record,
}


def main() -> int:
    fails = 0
    for name, fn in TESTS.items():
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, f"{type(e).__name__}: {e}"
        print(("PASS  " if ok else "FAIL  ") + f"{name:<18} {msg}")
        fails += 0 if ok else 1
    for d in (PDIR.parent / "_var_test_empty", PDIR.parent / "_var_test",
              PDIR.parent / "_var_test_store"):
        shutil.rmtree(d, ignore_errors=True)
    print("-" * 60)
    print("test_variation: all pass" if not fails
          else f"test_variation: {fails} FAILURE(S)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
