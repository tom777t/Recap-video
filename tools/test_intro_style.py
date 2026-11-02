# -*- coding: utf-8 -*-
"""test_intro_style.py - the intro montage's edit style and shot selection.

  CALIBRATE            synthetic drums -> energetic, synthetic slow ballad
                       -> emotional (tools/intro_music_fixtures.py), from
                       the measured music features alone; a SILENT track is
                       not classified (legacy style) - nothing to measure is
                       not a calm track
  TOKYODRIFT-MUSIC     tokyodrift2006/intro_music.mp3 -> energetic (runs where
                       the file exists; prints NOT RUN otherwise)
  OVERRIDE-AND-TONE    draft.json intro_style wins; an angle.md comedy tone
                       picks comedy on a high-arousal track; a tone that does
                       not fit the arousal is ignored; tokyodrift2006's real
                       angle.md carries no genre tone (its music decides)
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


def test_calibrate():
    _music()
    _proj("_istyle_cal")
    try:
        a, wa = S.choose("_istyle_cal", DRUMS)
        b, wb = S.choose("_istyle_cal", BALLAD)
    finally:
        shutil.rmtree(config.project_dir("_istyle_cal"), ignore_errors=True)
    import subprocess
    silent = TMP / "silent.mp3"
    subprocess.run([config.ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=48000:cl=mono", "-t", "20", str(silent)],
                   check=True)
    _proj("_istyle_cal")
    try:
        c, wc = S.choose("_istyle_cal", silent)
    finally:
        shutil.rmtree(config.project_dir("_istyle_cal"), ignore_errors=True)
    ok = (a == "energetic" and b == "emotional" and c == "energetic"
          and "not a classification" in wc[-1])
    return ok, (f"drums -> {a}; ballad -> {b} ({wb[-1]}); silent track -> "
                f"{c} (legacy, not classified)")


def test_tokyodrift_music():
    m = config.project_dir("tokyodrift2006") / "intro_music.mp3"
    if not m.exists():
        print("NOT RUN  TOKYODRIFT-MUSIC     tokyodrift2006/intro_music.mp3 is "
              "not on this box; on the owner's laptop it must choose energetic")
        return None, ""
    p, why = S.choose("tokyodrift2006", m)
    return p == "energetic", f"tokyodrift2006 -> {p}: {'; '.join(why)}"


COMEDY_ANGLE = ("## ANGLE\nA comedy: the funny side of a disaster, every joke "
                "landing on the hero; slapstick and absurd.\n")


def test_override_and_tone():
    _music()
    try:
        _proj("_istyle_ov", {"lines": [], "intro_style": "horror"})
        ov, _w = S.choose("_istyle_ov", DRUMS)
        _proj("_istyle_ov", angle=COMEDY_ANGLE)
        tone, _w = S.choose("_istyle_ov", DRUMS)
        romance = "## ANGLE\nA love story; the lovers and their romance.\n"
        _proj("_istyle_ov", angle=romance)
        misfit, wm = S.choose("_istyle_ov", DRUMS)     # romance not in high
    finally:
        shutil.rmtree(config.project_dir("_istyle_ov"), ignore_errors=True)
    td, _c = S.angle_tone(config.project_dir("tokyodrift2006"))
    ok = (ov == "horror" and tone == "comedy" and misfit == "energetic"
          and td is None)
    return ok, (f"override -> {ov}; comedy angle -> {tone}; romance angle on "
                f"drums -> {misfit}; tokyodrift2006 angle tone {td}")


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
    "CALIBRATE":           test_calibrate,
    "TOKYODRIFT-MUSIC":    test_tokyodrift_music,
    "OVERRIDE-AND-TONE":   test_override_and_tone,
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
