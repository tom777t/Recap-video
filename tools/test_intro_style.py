# -*- coding: utf-8 -*-
"""test_intro_style.py - the intro montage's edit style and shot selection.

  HINT-ONLY            the music is measured (drums high, ballad low) but
                       never decides: a ballad with nothing set gets the
                       legacy default
  PRECEDENCE           draft.json intro_style > intro_style.txt > legacy
  INVALID-NAME         a name that is not a preset - in draft.json or the
                       file, or an empty file - raises, listing all 8; the
                       render re-raises it instead of downgrading to a notice
  NEVER-OVERWRITE      write_suggestion writes once with its reason, never
                       over an existing file (the owner's choice wins), and
                       refuses an invalid suggestion
  EACH-PRESET-RENDERS  every preset builds the intro on the smoke fixture; the
                       emotional one has fewer cuts and longer average shots
                       than energetic (dissolve / dip presets render
                       through the xfade chain)
  EPIC-BUILDS          epic's cut rate rises across the intro (shots shorten)
  ENERGETIC-LEGACY     energetic never calls the new planner or selector
                       (its bytes are today's - proven offline, see the
                       commit message)
  PROFILES-RANK        on a fixture catalogue, each profile ranks its target
                       shot first
  NEVER-FORBIDDEN      no profile ever selects footage at/after the first
                       reveal, censor-flagged footage, story-bound footage, or
                       (mystery) a shot naming the reveal-critical character
  IN-CACHE-KEY         changing the style changes the intro cache key

Run:  python tools/test_intro_style.py
"""
from __future__ import annotations

import io
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
import intro_music_fixtures as MF  # noqa: E402
from pipeline import intro as I  # noqa: E402
from pipeline import intro_style as S  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="introstyle_"))
DRUMS, BALLAD = TMP / "drums.mp3", TMP / "ballad.mp3"


def _music():
    if not DRUMS.exists():
        MF.drums(DRUMS)
        MF.ballad(BALLAD)


def _proj(name: str, draft: dict | None = None, angle: str | None = None):
    pdir = config.project_dir(name)
    shutil.rmtree(pdir, ignore_errors=True)
    pdir.mkdir(parents=True)
    (pdir / "draft.json").write_text(json.dumps(draft or {"lines": []}))
    if angle:
        (pdir / "angle.md").write_text(angle)
    return pdir


def test_hint_only():
    """The music is MEASURED (hint) but never decides: a ballad with no
    intro_style set gets the legacy default, not 'emotional' - the classifier
    read a real ballad as energetic, so the choice is a person's."""
    _music()
    _proj("_istyle_cal")
    try:
        fd, fb = S.music_features(DRUMS), S.music_features(BALLAD)
        hd, hb = S.arousal(fd)[0], S.arousal(fb)[0]
        pick, why = S.choose("_istyle_cal", BALLAD)
    finally:
        shutil.rmtree(config.project_dir("_istyle_cal"), ignore_errors=True)
    ok = (hd == "high" and hb == "low" and pick == "energetic"
          and any("not used to decide" in w for w in why))
    return ok, (f"hint: drums {hd}, ballad {hb}; ballad with nothing set -> "
                f"{pick} (legacy default)")


def test_precedence():
    try:
        pdir = _proj("_istyle_prec", {"lines": [], "intro_style": "horror"})
        (pdir / S.STYLE_FILE).write_text("romance\n# owner\n")
        both, _ = S.choose("_istyle_prec")
        (pdir / "draft.json").write_text(json.dumps({"lines": []}))
        filed, w = S.choose("_istyle_prec")
        (pdir / S.STYLE_FILE).unlink()
        none, wn = S.choose("_istyle_prec")
    finally:
        shutil.rmtree(config.project_dir("_istyle_prec"), ignore_errors=True)
    ok = both == "horror" and filed == "romance" and none == "energetic"
    return ok, (f"draft+file -> {both}; file only -> {filed}; neither -> "
                f"{none} ({wn[0]})")


def test_invalid_name():
    errs = []
    try:
        for setup in ("draft", "file", "empty-file"):
            pdir = _proj("_istyle_bad", {"lines": [], "intro_style": "jazzy"}
                         if setup == "draft" else {"lines": []})
            if setup == "file":
                (pdir / S.STYLE_FILE).write_text("Jazzy\n")
            if setup == "empty-file":
                (pdir / S.STYLE_FILE).write_text("# nothing here\n")
            try:
                S.choose("_istyle_bad")
                errs.append(f"{setup}: no error")
            except S.IntroStyleError as e:
                if not all(p in str(e) for p in S.PRESETS):
                    errs.append(f"{setup}: message does not list all 8: {e}")
    finally:
        shutil.rmtree(config.project_dir("_istyle_bad"), ignore_errors=True)
    src = (ROOT / "pipeline" / "render.py").read_text(encoding="utf-8")
    if "_StyleErr" not in src or "(_Spoil, _StyleErr)" not in src:
        errs.append("render.py swallows IntroStyleError as a notice")
    return (not errs), ("invalid name in draft / file / empty file raises, "
                        "listing all 8; the render re-raises it"
                        if not errs else "; ".join(errs))


def test_never_overwrite():
    try:
        pdir = _proj("_istyle_ow")
        w1 = S.write_suggestion(pdir, "suspense", "a slow-burn thriller")
        first = (pdir / S.STYLE_FILE).read_text()
        (pdir / S.STYLE_FILE).write_text("comedy\n# the owner changed it\n")
        w2 = S.write_suggestion(pdir, "epic", "should not land")
        after = (pdir / S.STYLE_FILE).read_text()
        pick, _w = S.choose("_istyle_ow")
        try:
            S.write_suggestion(_proj("_istyle_ow2"), "jazzy", "x")
            bad = "an invalid suggestion was written"
        except S.IntroStyleError:
            bad = ""
    finally:
        shutil.rmtree(config.project_dir("_istyle_ow"), ignore_errors=True)
        shutil.rmtree(config.project_dir("_istyle_ow2"), ignore_errors=True)
    ok = (w1 and first.startswith("suspense\n") and "slow-burn" in first
          and not w2 and after.startswith("comedy") and pick == "comedy"
          and not bad)
    return ok, ("suggestion written once with its reason; the owner's edit "
                "is never overwritten and wins; invalid suggestion refused"
                if ok else f"{w1} {w2} {after!r} {pick} {bad}")


def _render(preset: str):
    """Build the intro on the smoke fixture with `preset`; (cuts, total, log)."""
    import test_render_smoke as T
    from rich.console import Console
    proj0, T.PROJ = T.PROJ, "_istyle_render"
    orig = T._stub_intro_tts()
    old_console = I.console
    I.console = Console(record=True, width=400)
    try:
        pdir, draft = T._setup()
        draft["intro_style"] = preset
        (pdir / "draft.json").write_text(json.dumps(draft))
        shutil.copy(DRUMS, pdir / "intro_music.mp3")
        out = I.build_intro(T.PROJ)
        log = I.console.export_text()
        m = re.search(r"(\d+) beat cuts over ([\d.]+)s", log)
        return (out is not None and Path(out).exists(),
                int(m.group(1)) if m else 0, float(m.group(2)) if m else 0.0,
                log)
    finally:
        I.console = old_console
        I._tts_line = orig
        T._teardown()
        T.PROJ = proj0


def test_each_preset_renders():
    _music()
    res = {p: _render(p) for p in S.PRESETS}
    bad = [p for p, r in res.items() if not r[0]]
    if bad:
        return False, f"did not render: {bad}"
    e, m = res["energetic"], res["emotional"]
    avg = lambda r: r[2] / max(1, r[1])            # noqa: E731
    if not (m[1] < e[1] and avg(m) > avg(e)):
        return False, (f"emotional {m[1]} cuts avg {avg(m):.2f}s vs energetic "
                       f"{e[1]} cuts avg {avg(e):.2f}s")
    return True, ("all 8 render; " + ", ".join(f"{p} {r[1]}" for p, r in
                                               res.items()) + " cuts; "
                  f"emotional avg {avg(m):.2f}s > energetic {avg(e):.2f}s")


def test_epic_builds():
    _music()
    on = I.detect_onsets(DRUMS, 35)
    slots = S.plan_slots(on, 20.0, 12.0, S.PRESETS["epic"])
    lens = [b - a for a, b in slots]
    h = len(lens) // 2
    first, second = sum(lens[:h]) / h, sum(lens[h:]) / (len(lens) - h)
    legacy = S.legacy_slots([t for t, _ in on], 20.0)
    ok = first > second * 1.3 and len(slots) < len(legacy)
    return ok, (f"epic: mean shot {first:.2f}s in the first half -> "
                f"{second:.2f}s in the second ({len(slots)} cuts)")


def test_energetic_legacy():
    _music()
    called = []
    real_p, real_s = S.plan_slots, I.select_moments
    S.plan_slots = lambda *a, **k: called.append("plan") or real_p(*a, **k)
    I.select_moments = lambda *a, **k: called.append("sel") or real_s(*a, **k)
    try:
        ok_r, cuts, _t, log = _render("energetic")
    finally:
        S.plan_slots, I.select_moments = real_p, real_s
    leg = S.legacy_slots(I.detect_beats(DRUMS, 35), 7.4)
    ok = ok_r and not called and "Intro style:[/]" not in log
    return ok, (f"energetic used legacy cuts + legacy footage "
                f"({cuts} cuts; legacy formula gives {len(leg)} on 7.4s)")


# fixture catalogue: one target shot per profile, plus distractors
CAT = [
    ("energetic", "A car chase: the racing cars drift and crash through fire",
     ["action"], ["Kai"], 9.0, 90),
    ("emotional", "Close-up of his face, tears; his mother hugs him in quiet",
     ["emotion"], ["Kai", "Mother"], 0.5, 70),
    ("suspense", "A lone figure in the dark corridor; the door handle turns",
     ["setup"], ["Kai"], 1.0, 20),
    ("horror", "The empty abandoned hallway at night; she screams in terror",
     ["reaction"], ["Mira"], 1.2, 15),
    ("comedy", "He gapes, a double-take, then slips and falls - absurd and "
               "awkward", ["reaction"], ["Kai"], 3.0, 110),
    ("epic", "A wide aerial shot of the city skyline, the crowd cheers as he "
             "stands in triumph", ["establishing"], ["Kai", "A", "B", "C"],
     4.0, 120),
    ("romance", "They look at each other, smile at each other and dance "
                "together in the warm sunset", ["emotion"], ["Kai", "Mira"],
     1.5, 100),
    ("mystery", "A letter and a key on the table by the window; a phone "
                "rings in the dark", ["setup"], [], 0.8, 40),
    (None, "People talk in an office", ["dialogue"], ["Kai"], 2.0, 100),
    (None, "He walks along a street", ["establishing"], ["Kai"], 2.5, 100),
]


def _cands():
    out = []
    for i, (_t, act, dep, chars, mot, luma) in enumerate(CAT):
        shot = {"action": act, "depicts": dep, "chars": chars}
        out.append({"a": 10.0 * i, "b": 10.0 * i + 4, "shot": shot,
                    "f": S.shot_features(shot, {"Kai", "Mira"}, motion=mot,
                                         luma=luma), "target": _t})
    return out


def test_profiles_rank():
    bad = []
    for prof in S.PROFILES:
        c = _cands()
        ranked = sorted(c, key=lambda x: -S.score(x["f"], prof)[0])
        if ranked[0]["target"] != prof:
            bad.append(f"{prof}: top is {ranked[0]['target']} "
                       f"({S.score(ranked[0]['f'], prof)[0]})")
    return (not bad), ("every profile ranks its target first" if not bad
                       else "; ".join(bad))


def test_never_forbidden():
    """Real usable_moments + select_moments on a fixture project."""
    pdir = _proj("_istyle_forbid", {"lines": [
        {"id": 1, "clip_start": "00:00:40.000", "clip_end": "00:00:45.000",
         "narration": "bound"}]})
    shots = []
    for i, (_t, act, dep, chars, _m, _l) in enumerate(CAT):
        shots.append({"clip_start": f"00:00:{i * 5:02d}.000",
                      "clip_end": f"00:00:{i * 5 + 4:02d}.000",
                      "action": act, "depicts": dep, "chars": chars,
                      "censor": "none"})
    # flagged: the strongest energetic shot, censor-flagged
    shots.append({"clip_start": "00:00:50.000", "clip_end": "00:00:54.000",
                  "action": "car chase drift crash fire explosion race",
                  "depicts": ["action"], "chars": ["Kai"],
                  "censor": "blur_heavy",
                  "censor_region": {"x": 0, "y": 0, "width": 10, "height": 10}})
    # bound: inside the draft line's window
    shots.append({"clip_start": "00:00:40.500", "clip_end": "00:00:44.500",
                  "action": "car chase drift crash fire", "depicts": ["action"],
                  "chars": ["Kai"], "censor": "none"})
    # after the reveal lands (60s)
    shots.append({"clip_start": "00:01:05.000", "clip_end": "00:01:09.000",
                  "action": "the wide crowd cheers, hugs, tears, car crash",
                  "depicts": ["reveal"], "chars": ["Kai", "Mira"],
                  "censor": "none"})
    # reveal-critical character, before the land: mystery must skip it
    shots.append({"clip_start": "00:00:56.000", "clip_end": "00:00:59.500",
                  "action": "Victor holds a letter and a key in the dark",
                  "depicts": ["setup"], "chars": ["Victor"],
                  "censor": "none"})
    (pdir / "shots.json").write_text(json.dumps({"shots": shots}))
    (pdir / "reveals.json").write_text(json.dumps({"reveals": [
        {"id": "R1", "land": "00:01:00", "land_ref": "00:01:00", "type": "A",
         "fact": "Victor is the father", "what": "Victor is the father",
         "hold": ["victor", "the father"], "holds": ["victor"]}]}))
    (pdir / "beats_proposal.md").write_text(
        "# Fixture\n\n```reveal-map\nR1 | land: 00:01:00 | hold: Victor, "
        "the father\n```\n")
    try:
        land = I.first_reveal_land("_istyle_forbid")
        bad = []
        for prof in S.PROFILES:
            got = I.select_moments("_istyle_forbid", land, 20, prof)
            if len(got) < 3:
                bad.append(f"{prof} picked only {len(got)} shot(s)")
            for a, b in got:
                if b > land or (50 <= a < 54) or (40 <= a < 45):
                    bad.append(f"{prof} picked {a}-{b}")
                if prof == "mystery" and 56 <= a < 59.5:
                    bad.append("mystery showed the reveal-critical character")
        return (not bad and land == 60.0), (
            f"0 forbidden picks across {len(S.PROFILES)} profiles (land "
            f"{land:.0f}s)" if not bad else "; ".join(bad[:5]))
    finally:
        shutil.rmtree(pdir, ignore_errors=True)


def test_in_cache_key():
    _music()
    pdir = _proj("_istyle_key", {"lines": []})
    try:
        shutil.copy(DRUMS, pdir / "intro_music.mp3")
        k1 = I._intro_cache_key("_istyle_key")
        (pdir / "draft.json").write_text(json.dumps(
            {"lines": [], "intro_style": "emotional"}))
        k2 = I._intro_cache_key("_istyle_key")
        return k1 != k2, "style change -> new intro cache key"
    finally:
        shutil.rmtree(pdir, ignore_errors=True)


TESTS = {
    "HINT-ONLY":           test_hint_only,
    "PRECEDENCE":          test_precedence,
    "INVALID-NAME":        test_invalid_name,
    "NEVER-OVERWRITE":     test_never_overwrite,
    "EACH-PRESET-RENDERS": test_each_preset_renders,
    "EPIC-BUILDS":         test_epic_builds,
    "ENERGETIC-LEGACY":    test_energetic_legacy,
    "PROFILES-RANK":       test_profiles_rank,
    "NEVER-FORBIDDEN":     test_never_forbidden,
    "IN-CACHE-KEY":        test_in_cache_key,
}

if __name__ == "__main__":
    bad = 0
    try:
        for name, fn in TESTS.items():
            try:
                ok, msg = fn()
            except Exception as e:
                import traceback
                traceback.print_exc()
                ok, msg = False, f"{type(e).__name__}: {e}"
            if ok is None:
                continue
            print(f'{"PASS" if ok else "FAIL"}  {name:<20} {msg}')
            bad += (not ok)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print("-" * 60)
    print("test_intro_style: all pass" if not bad else
          f"test_intro_style: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
