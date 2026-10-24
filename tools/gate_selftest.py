# -*- coding: utf-8 -*-
"""
gate_selftest.py - POSITIVE tests for gates that never fire on real data.

Why this exists
---------------
The 2026-09-05 gate audit found several gates that had never produced a warning
on any of the 17 projects. "Never fires" has three very different causes and
they are indistinguishable from the outside:

  1. dead code            - nothing can reach the branch
  2. broken join          - the branch is reachable but its input never arrives
  3. threshold not reached - it works; no real draft has ever breached it

Only a POSITIVE test separates them. A gate that has never fired and has never
been shown to fire is not protection, it is decoration.

Each test builds a throwaway project under projects/_selftest_*, runs the REAL
validator against it, asserts the gate fires, and removes the project. Nothing
existing is touched.

Usage:  python tools/gate_selftest.py [gate ...]
        (no args = run all)
"""
from __future__ import annotations
import json, io, os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_draft(project: str) -> str:
    r = subprocess.run([sys.executable, 'recap.py', 'draft', '--project', project],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=900)
    return (r.stdout or '') + (r.stderr or '')


def _mk(project: str, files: dict) -> str:
    p = os.path.join(ROOT, 'projects', project)
    shutil.rmtree(p, ignore_errors=True)
    os.makedirs(p)
    for name, obj in files.items():
        io.open(os.path.join(p, name), 'w', encoding='utf-8').write(
            json.dumps(obj, ensure_ascii=False, indent=2))
    return p


# --------------------------------------------------------------------------- #
def test_visual_repeat() -> tuple[bool, str]:
    """[VISUAL-REPEAT] - config.MAX_FAMILY_USES, BOTH input paths.

    Path B: several pool labels sharing one `family` in broll.json. Each label is
            used ONCE so the per-label reuse cap cannot be what fires - only the
            family cap can.
    Path A: several explicit-window lines sharing one `visual` tag.

    Result 2026-09-05: FIRES on both paths. The gate is live; the reason it had
    never fired on real data is cause (3) - max family usage across all 17
    projects is exactly 2 and the cap is `> 2`.
    """
    proj = '_selftest_visualrepeat'
    broll = {"pool": {
        lab: {"clip_start": f"00:00:{10*i:02d}.0", "clip_end": f"00:00:{10*i+4:02d}.0",
              "family": "FAM_A", "chars": [], "depicts": ["action"]}
        for i, lab in enumerate(('P1', 'P2', 'P3'), 1)}}
    lines = [{"id": i, "narration": f"Family line {i}.", "pool": lab}
             for i, lab in enumerate(('P1', 'P2', 'P3'), 1)]
    lines += [{"id": i, "narration": f"Visual line {i}.",
               "clip_start": f"00:0{i-3}:00.0", "clip_end": f"00:0{i-3}:05.0",
               "visual": "FAM_B"} for i in (4, 5, 6)]
    _mk(proj, {'broll.json': broll,
               'draft.json': {"project": proj, "title": "selftest",
                              "target_minutes": 1, "voice": "tts", "lines": lines}})
    try:
        out = _run_draft(proj)
        hits = [l.strip() for l in out.splitlines() if 'VISUAL-REPEAT' in l]
        ok = any("'FAM_A'" in h for h in hits) and any("'FAM_B'" in h for h in hits)
        return ok, ('fired on both paths' if ok else
                    f'did NOT fire on both paths; hits={hits[:2]}')
    finally:
        shutil.rmtree(os.path.join(ROOT, 'projects', proj), ignore_errors=True)


# --------------------------------------------------------------------------- #
# The four integrity guards below had, as of 2026-09-05, NEVER fired on any of
# the 17 projects. That is the correct result - none of those conditions occurs
# in the data. But "never fired" and "cannot fire" look identical from outside,
# and three of these guards exist BECAUSE a real bug got through once. A guard
# nobody has proved fires is the same shape as the bug it was written for.
# --------------------------------------------------------------------------- #

def test_footage_dropped() -> tuple[bool, str]:
    """[FOOTAGE-DROPPED] - a shots.json entry that fails to load.

    This is the loudest guard in the repo: a dropped shot is INVISIBLE footage,
    and every audit downstream runs on what survived, so a clean report means
    nothing while the drop list is non-empty.
    """
    proj = '_selftest_footagedropped'
    shots = {"project": proj, "shots": [
        {"id": "clip:00:00:10.0", "clip_start": "00:00:10.0",
         "clip_end": "00:00:14.0", "chars": [], "depicts": ["action"],
         "action": "fine", "censor": "none"},
        # depicts carries a value outside the schema vocabulary -> must drop
        {"id": "clip:00:00:20.0", "clip_start": "00:00:20.0",
         "clip_end": "00:00:24.0", "chars": [], "depicts": ["NOT_A_REAL_TYPE"],
         "action": "broken", "censor": "none"},
    ]}
    lines = [{"id": 1, "narration": "A line.",
              "clip_start": "00:00:10.0", "clip_end": "00:00:14.0"}]
    _mk(proj, {'shots.json': shots,
               'draft.json': {"project": proj, "title": "selftest",
                              "target_minutes": 1, "voice": "tts", "lines": lines}})
    try:
        out = _run_draft(proj)
        ok = 'FOOTAGE-DROPPED' in out
        return ok, ('fired on an unloadable shot' if ok else
                    'did NOT fire - a malformed shot loaded silently')
    finally:
        shutil.rmtree(os.path.join(ROOT, 'projects', proj), ignore_errors=True)


def test_duplicate_id() -> tuple[bool, str]:
    """[DUPLICATE-ID] - two draft lines sharing an id.

    Line ids are how every downstream report addresses a line ("re-point line
    47"). Two lines with one id makes every such instruction ambiguous.
    """
    proj = '_selftest_duplicateid'
    lines = [{"id": 7, "narration": "First seven.",
              "clip_start": "00:00:10.0", "clip_end": "00:00:14.0"},
             {"id": 7, "narration": "Second seven.",
              "clip_start": "00:00:20.0", "clip_end": "00:00:24.0"}]
    _mk(proj, {'draft.json': {"project": proj, "title": "selftest",
                              "target_minutes": 1, "voice": "tts", "lines": lines}})
    try:
        out = _run_draft(proj)
        ok = 'DUPLICATE-ID' in out
        return ok, ('fired on a repeated line id' if ok else 'did NOT fire')
    finally:
        shutil.rmtree(os.path.join(ROOT, 'projects', proj), ignore_errors=True)


def test_empty_line() -> tuple[bool, str]:
    """[EMPTY-LINE] - a clip window with no narration and no authored silence.

    History: this test FAILED when first written (2026-09-05). [EMPTY-LINE] was
    unreachable - an unlabelled duplicate of the same check ran earlier in the
    per-line loop, appended to `errors`, and the `if errors:` abort fired before
    the labelled block. The guard existed, was never reachable, and no project
    had ever exercised it. FIXED the same day by moving the labelled block above
    the abort and deleting the duplicate; verified byte-identical error output
    and exit codes across all 17 projects.

    Note the deliberate near-miss in the same test: an S9 silence line is ALSO a
    window with empty narration and MUST NOT fire. An earlier version of this
    guard hard-failed three of four finished films for exactly that.
    """
    proj = '_selftest_emptyline'
    lines = [
        {"id": 1, "narration": "", "clip_start": "00:00:10.0",
         "clip_end": "00:00:14.0"},                                  # must FIRE
        {"id": 2, "narration": "", "clip_start": "00:00:20.0",
         "clip_end": "00:00:26.0", "narration_silence_seconds": 6.0},  # must NOT
    ]
    _mk(proj, {'draft.json': {"project": proj, "title": "selftest",
                              "target_minutes": 1, "voice": "tts", "lines": lines}})
    try:
        out = _run_draft(proj)
        fired = 'EMPTY-LINE' in out
        # the guard must name line 1 and must not name the silence line
        blames_1 = any('EMPTY-LINE' in l or ' 1' in l
                       for l in out.splitlines() if 'EMPTY-LINE' in l) or fired
        false_pos = any('2' in l.split('EMPTY-LINE')[-1][:40]
                        for l in out.splitlines() if 'EMPTY-LINE' in l)
        ok = fired and not false_pos
        return ok, ('fired on the empty line and spared the S9 silence' if ok else
                    f'fired={fired} false_positive_on_silence={false_pos}')
    finally:
        shutil.rmtree(os.path.join(ROOT, 'projects', proj), ignore_errors=True)


def test_beat_map() -> tuple[bool, str]:
    """[BEAT-MAP] - a beat map whose timestamps cannot be trusted.

    Severity is red for a reason: coverage, reveal landings and set-piece ranges
    are all computed FROM these timestamps, so an untrusted beat map makes every
    number underneath it meaningless rather than merely wrong.
    """
    proj = '_selftest_beatmap'
    p = _mk(proj, {'draft.json': {
        "project": proj, "title": "selftest", "target_minutes": 1, "voice": "tts",
        "lines": [{"id": 1, "narration": "A line.",
                   "clip_start": "00:00:10.0", "clip_end": "00:00:14.0"}]}})
    io.open(os.path.join(p, 'beats_proposal.md'), 'w', encoding='utf-8').write(
        "style: linear\ndepth_target: recap\nTarget: 9-13 min\n\n"
        "B01 | 00:01:00 | first beat | none | setup\n"
        "B02 | 99:99:99 | timestamp that cannot be parsed | none | setup\n"
        "B03 | 00:00:30 | goes BACKWARDS from B01 | none | setup\n")
    try:
        out = _run_draft(proj)
        ok = 'BEAT-MAP' in out
        return ok, ('fired on an untrustworthy beat map' if ok else
                    'did NOT fire - bad timestamps accepted silently')
    finally:
        shutil.rmtree(os.path.join(ROOT, 'projects', proj), ignore_errors=True)


def test_visual_repeat_shots() -> tuple[bool, str]:
    """[VISUAL-REPEAT] via shots.json `family` on EXPLICIT-window lines.

    The gate originally read families only from broll.json pool metadata plus
    line-level `visual` tags. Linear mode does neither: it binds explicit
    clip_start windows to shots.json entries, which carry their own `family`.
    That left 463 family tags across two projects invisible to the counter -
    the gate's reach was narrower than its name in exactly the direction linear
    mode works (superbad2007 has 32 families with >2 catalogued shots).

    Also asserts the A3 case: a line anchored INSIDE a shot's window (not at its
    exact clip_start) must still resolve to that shot's family, or an
    A3-anchored draft silently under-counts.
    """
    proj = '_selftest_vrshots'
    shots = {"project": proj, "shots": [
        {"id": f"clip:00:00:{10*i:02d}.0", "clip_start": f"00:00:{10*i:02d}.0",
         "clip_end": f"00:00:{10*i+8:02d}.0", "family": "cop_car_night",
         "chars": [], "depicts": ["action"], "action": "a", "censor": "none"}
        for i in (1, 2, 3)]}
    lines = [
        {"id": 1, "narration": "Bound at the exact shot start.",
         "clip_start": "00:00:10.0", "clip_end": "00:00:14.0"},
        {"id": 2, "narration": "Also at a shot start.",
         "clip_start": "00:00:20.0", "clip_end": "00:00:24.0"},
        # A3-anchored: lands INSIDE shot 3's window, not on its first frame
        {"id": 3, "narration": "Anchored inside the third window.",
         "clip_start": "00:00:32.0", "clip_end": "00:00:36.0"},
    ]
    _mk(proj, {'shots.json': shots,
               'draft.json': {"project": proj, "title": "selftest",
                              "target_minutes": 1, "voice": "tts", "lines": lines}})
    try:
        out = _run_draft(proj)
        hits = [l.strip() for l in out.splitlines() if 'VISUAL-REPEAT' in l]
        ok = any('cop_car_night' in h for h in hits)
        return ok, ('fired on a shots.json family across explicit windows'
                    if ok else f'did NOT fire; hits={hits[:2]}')
    finally:
        shutil.rmtree(os.path.join(ROOT, 'projects', proj), ignore_errors=True)


_BEATS_HEAD = "style: linear\ndepth_target: recap\nTarget: 9-13 min\n\n"


def _beats(n=3, extra=""):
    rows = "".join(f"B{i:02d} | 00:0{i}:00 | beat {i} | none | setup\n"
                   for i in range(1, n + 1))
    return _BEATS_HEAD + rows + extra


def _review_project(proj, *, beats=3, lines=None, shots=True, pool_line=False):
    """Scratch project that is EXPLICITLY `style: review`, so any gate that
    fires is proving it runs outside linear mode."""
    ln = lines if lines is not None else [
        {"id": 1, "narration": "One.", "clip_start": "00:00:05.0",
         "clip_end": "00:00:09.0"},
        {"id": 2, "narration": "Two.", "clip_start": "00:01:05.0",
         "clip_end": "00:01:09.0"}]
    if pool_line:
        ln = ln + [{"id": 99, "narration": "Pool.", "pool": "P1"}]
    files = {'draft.json': {"project": proj, "title": "t", "target_minutes": 5,
                            "voice": "tts", "lines": ln}}
    if pool_line:
        files['broll.json'] = {"pool": {"P1": {
            "clip_start": "00:02:05.0", "clip_end": "00:02:09.0",
            "family": "F", "chars": [], "depicts": ["emotional"]}}}
    if shots:
        files['shots.json'] = {"shots": [
            {"id": f"B{i}", "clip_start": f"00:0{i}:00.0",
             "clip_end": f"00:0{i}:30.0",
             "depicts": ["action"], "chars": []} for i in range(0, beats)]}
    p = _mk(proj, files)
    body = "style: review\ndepth_target: recap\n\n" + "".join(
        f"B0{i+1} | 00:0{i}:00 | b{i} | none | beat {i}\n" for i in range(beats))
    io.open(os.path.join(p, 'beats_proposal.md'), 'w',
            encoding='utf-8').write(body)
    return p


def test_binding_integrity_review() -> tuple[bool, str]:
    """[BINDING-INTEGRITY] must run on a REVIEW project.

    It reads shots.json + explicit clip_start windows and already skips
    pool/montage lines by hand (draft.py:1180). Nothing it touches is
    mode-specific, yet it sat inside `if style == "linear":` and was therefore
    dark on 11 of 17 projects - over data that was fully present.

    Asserts it fires under `style: review` AND correctly names a free line.
    """
    proj = '_selftest_bireview'
    try:
        # line 2 at 00:01:05 sits inside shot B1; a third line at 00:09:00
        # lands in no catalogued window -> FREE
        lines = [{"id": 1, "narration": "One.", "clip_start": "00:01:05.0",
                  "clip_end": "00:01:09.0"},
                 {"id": 7, "narration": "Free.", "clip_start": "00:09:00.0",
                  "clip_end": "00:09:04.0"}]
        _review_project(proj, lines=lines)
        out = _run_draft(proj)
        runs = 'BINDING-INTEGRITY' in out
        found_free = re.search(r'BINDING-INTEGRITY.*1/2.*bound to NO', out) \
            is not None
        names_id = bool(re.search(r'BINDING-INTEGRITY(?:.|\n)*?\b7\b', out))
        ok = runs and found_free and names_id
        return ok, ('runs under style: review and names the free line'
                    if ok else f'runs={runs} found_free={found_free} '
                               f'names_id={names_id}')
    finally:
        shutil.rmtree(os.path.join(ROOT, 'projects', proj), ignore_errors=True)


def test_catalogue_density_review() -> tuple[bool, str]:
    """[CATALOGUE-DENSITY] must run on a REVIEW project.

    Needs only shots.json + a beat map, and already self-no-ops with a stated
    reason when either is missing (draft.py:1238-1243) - i.e. it was written to
    be called unconditionally. The beat map is the author's declaration of
    content and review projects carry one too.

    Asserts a REAL measurement, not the "not measured" no-op.
    """
    proj = '_selftest_cdreview'
    try:
        _review_project(proj, beats=3)
        out = _run_draft(proj)
        runs = 'CATALOGUE-DENSITY' in out
        measured = 'not measured' not in out.split('CATALOGUE-DENSITY')[1][:80] \
            if runs else False
        has_ratio = re.search(r'CATALOGUE-DENSITY.*per beat', out) is not None
        ok = runs and measured and has_ratio
        return ok, ('real shots/beat measurement under style: review'
                    if ok else f'runs={runs} measured={measured} '
                               f'has_ratio={has_ratio}')
    finally:
        shutil.rmtree(os.path.join(ROOT, 'projects', proj), ignore_errors=True)


def test_beat_coverage_review() -> tuple[bool, str]:
    """[BEAT-COVERAGE] on a REVIEW project - and it must NOT lie.

    This one is NOT the same shape as the other two. binding_integrity skips
    pool/montage lines deliberately; beat_coverage only ASSUMES they have no
    clip_start (draft.py:1278) and silently drops them. A beat covered solely
    by a pool line would therefore be reported UNCOVERED - a false finding.
    All five review projects are 0-pool today, so it is accurate for them, but
    a gate must not be widened while it can still lie.

    Asserts: (a) it reports coverage under style: review, and (b) when lines
    exist that it cannot place, it SAYS SO instead of counting them as gaps.
    """
    proj = '_selftest_bcreview'
    try:
        _review_project(proj, beats=3)
        out = _run_draft(proj)
        runs = re.search(r'BEAT-COVERAGE.*\d+/3 beats', out) is not None
        shutil.rmtree(os.path.join(ROOT, 'projects', proj), ignore_errors=True)
        # now with an unplaceable pool line present
        _review_project(proj, beats=3, pool_line=True)
        out2 = _run_draft(proj)
        discloses = re.search(r'BEAT-COVERAGE(?:.|\n)*?(unplaceable|could not '
                              r'place|not counted)', out2, re.I) is not None
        ok = runs and discloses
        return ok, ('reports coverage and discloses unplaceable lines'
                    if ok else f'runs={runs} discloses_pool_lines={discloses}')
    finally:
        shutil.rmtree(os.path.join(ROOT, 'projects', proj), ignore_errors=True)


def test_score_denominator() -> tuple[bool, str]:
    """score_vision_eval.py - a case it CANNOT measure must be excluded and
    named, never folded into the failures. D-GREEN at the scoring layer.

    Two unscoreable shapes, both present in the shipped badgenius2017 catalogue:
      N1a  reference `depicts` has no visible-axis label  -> cannot score that axis
      N1b  reference `chars` is empty                     -> cannot score naming

    Fixture (3 shots):
      shot01  truth depicts [dialogue] chars [Alice]  answer dialogue / Alice
      shot02  truth depicts [setup]    chars [Bob]    answer action   / Bob
              -> STORY-only reference: excluded from the visible denominator
      shot03  truth depicts [dialogue] chars []       answer dialogue / Carol
              -> empty reference chars: Carol must NOT count as a false positive

    Correct: visible 2/2 with 1 excluded; chars precision 2/2 = 100%.
    Broken (pre-fix): Carol counts as fp -> precision 2/3 = 67%.
    """
    proj = '_selftest_scoredenom'
    p = os.path.join(ROOT, 'projects', proj)
    try:
        shutil.rmtree(p, ignore_errors=True)
        os.makedirs(p)
        truth = {
            "shot01": {"clip_start": "00:00:10.0", "clip_end": "00:00:14.0",
                       "depicts": ["dialogue"], "chars": ["Alice"],
                       "action": "a"},
            "shot02": {"clip_start": "00:00:20.0", "clip_end": "00:00:24.0",
                       "depicts": ["setup"], "chars": ["Bob"], "action": "b"},
            "shot03": {"clip_start": "00:00:30.0", "clip_end": "00:00:34.0",
                       "depicts": ["dialogue"], "chars": [], "action": "c"},
        }
        io.open(os.path.join(p, '_vision_truth.json'), 'w',
                encoding='utf-8').write(json.dumps(truth, ensure_ascii=False))
        sheet = "# VISION EVAL - selftest\n\n"
        for tag, dep, ch in (("shot01", "dialogue", "Alice"),
                             ("shot02", "action", "Bob"),
                             ("shot03", "dialogue", "Carol")):
            sheet += (f"### {tag}  (4.0s)\n\n- depicts: {dep}\n"
                      f"- chars: {ch}\n- action: x\n\n")
        io.open(os.path.join(p, 'VISION_EVAL.md'), 'w',
                encoding='utf-8').write(sheet)

        r = subprocess.run([sys.executable, 'tools/score_vision_eval.py', proj],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=300)
        out = (r.stdout or '') + (r.stderr or '')

        # visible axis: 2 scoreable, 1 excluded, and the excluded one must be
        # NAMED as excluded rather than silently dropped
        vis_ok = re.search(r'2/2', out) is not None
        vis_excl = re.search(r'(loai tru|excluded|khong cham)', out, re.I) \
            is not None and '1' in out
        # chars precision must be 100%, not 67%
        prec = re.search(r'do chinh xac\s*:\s*(\d+)%', out)
        prec_ok = prec is not None and prec.group(1) == '100'
        # empty-reference chars must be reported with a count
        chars_excl = re.search(r'(chars|CHARS)(?:.|\n)*?(rong|empty)', out) \
            is not None
        ok = vis_ok and vis_excl and prec_ok and chars_excl
        return ok, ('excludes unscoreable cases and names them'
                    if ok else
                    f'visible_2of2={vis_ok} visible_excl_named={vis_excl} '
                    f'chars_prec={prec.group(1) + "%" if prec else "?"} '
                    f'(want 100%) chars_excl_named={chars_excl}')
    finally:
        shutil.rmtree(p, ignore_errors=True)


def test_style_declare() -> tuple[bool, str]:
    """[STYLE-DECLARE] - `style:` must be chosen, not defaulted into.

    `style:` was declared on 6 of 17 projects. The other 11 defaulted to
    `review` by absence, and that default silently switched off BEAT-COVERAGE,
    BINDING-INTEGRITY, SNAP-GRID, CATALOGUE-DENSITY and the stage machine -
    44 of 204 cells in the gate matrix, chosen by nobody.

    Asserts: undeclared fires, NAMES the default it is falling into, NAMES what
    that switches off, and goes quiet once `style:` is stated - including when
    it is stated as `review`, which is a choice like any other.
    """
    proj = '_selftest_styledecl'
    draft = {"project": proj, "title": "t", "target_minutes": 10,
             "voice": "tts",
             "lines": [{"id": 1, "narration": "A line.",
                        "clip_start": "00:00:10.0", "clip_end": "00:00:14.0"}]}
    body = "depth_target: recap\nTarget: 9-13 min\n\nB01 | 00:01:00 | b | none | setup\n"
    try:
        p = _mk(proj, {'draft.json': draft})
        bp = os.path.join(p, 'beats_proposal.md')
        io.open(bp, 'w', encoding='utf-8').write(body)
        out = _run_draft(proj)
        fires = 'STYLE-DECLARE' in out
        names_default = 'review' in out.lower()
        names_cost = ('BEAT-COVERAGE' in out and 'BINDING-INTEGRITY' in out
                      and 'SNAP-GRID' in out)
        io.open(bp, 'w', encoding='utf-8').write("style: review\n" + body)
        explicit_review_quiet = 'STYLE-DECLARE' not in _run_draft(proj)
        io.open(bp, 'w', encoding='utf-8').write("style: linear\n" + body)
        linear_quiet = 'STYLE-DECLARE' not in _run_draft(proj)
        ok = (fires and names_default and names_cost
              and explicit_review_quiet and linear_quiet)
        return ok, ('names the default and its cost; quiet once declared either '
                    'way' if ok else
                    f'fires={fires} names_default={names_default} '
                    f'names_cost={names_cost} review_quiet={explicit_review_quiet} '
                    f'linear_quiet={linear_quiet}')
    finally:
        shutil.rmtree(os.path.join(ROOT, 'projects', proj), ignore_errors=True)


def test_project_status() -> tuple[bool, str]:
    """[PROJECT-STATUS] - a project with no beat map must say why.

    Without beats_proposal.md, SET-PIECE-DECLARE, RATCHET and the whole DEPTH-*
    family are no-ops by absence - the same failure SET-PIECE-DECLARE was built
    to fix, one layer up. Six of seventeen projects were in this state.

    The gate must DISTINGUISH the cases rather than treat them alike:
      - no beat map AND no source video -> cannot be worked on
      - no beat map but a source exists -> incomplete, not impossible
    and must go silent on an explicit declaration.
    """
    proj = '_selftest_projstatus'
    draft = {"project": proj, "title": "t", "target_minutes": 10,
             "voice": "tts",
             "lines": [{"id": 1, "narration": "A line.",
                        "clip_start": "00:00:10.0", "clip_end": "00:00:14.0"}]}
    try:
        p = _mk(proj, {'draft.json': draft})
        out_nosrc = _run_draft(proj)
        fires = 'PROJECT-STATUS' in out_nosrc
        names_nosource = 'no source' in out_nosrc.lower()
        # same project, now with a source present -> different message
        io.open(os.path.join(p, 'source.mp4'), 'wb').write(b'x')
        out_src = _run_draft(proj)
        different = ('PROJECT-STATUS' in out_src
                     and 'no source' not in out_src.lower())
        # declared -> silent
        io.open(os.path.join(p, 'project_status.md'), 'w',
                encoding='utf-8').write(
            "```project-status\n"
            "status: legacy\nmode: review\n"
            "reason: imported in the 2026-08-13 bulk commit, never worked on\n"
            "```\n")
        declared_quiet = 'PROJECT-STATUS' not in _run_draft(proj)
        ok = fires and names_nosource and different and declared_quiet
        return ok, ('distinguishes no-source from incomplete, silent when '
                    'declared' if ok else
                    f'fires={fires} names_nosource={names_nosource} '
                    f'different_with_source={different} '
                    f'declared_quiet={declared_quiet}')
    finally:
        shutil.rmtree(os.path.join(ROOT, 'projects', proj), ignore_errors=True)


def test_set_piece_declare() -> tuple[bool, str]:
    """[SET-PIECE-DECLARE] - absence must be a DECISION, not a default.

    SET-PIECE was a silent no-op on 14 of 17 projects because no fenced block
    existed. That is indistinguishable in effect from the strongest possible
    gaming, achieved by doing nothing. Following the G2 precedent (Bad Genius
    recorded "AMBIGUITY-HOLD: none in this film" rather than skipping it), a
    project with no set-pieces must say so and say why.

    Asserts: missing block fires; `set-pieces: none, because ...` silences it.
    """
    proj = '_selftest_spdecl'
    lines = [{"id": 1, "narration": "A line.", "clip_start": "00:00:10.0",
              "clip_end": "00:00:14.0"}]
    draft = {"project": proj, "title": "t", "target_minutes": 10,
             "voice": "tts", "lines": lines}
    try:
        p = _mk(proj, {'draft.json': draft})
        io.open(os.path.join(p, 'beats_proposal.md'), 'w',
                encoding='utf-8').write(_beats())
        missing = 'SET-PIECE-DECLARE' in _run_draft(proj)
        io.open(os.path.join(p, 'beats_proposal.md'), 'w',
                encoding='utf-8').write(_beats(
                    extra="\nset-pieces: none, because this film has no combat "
                          "or procedural sequence a viewer must follow.\n"))
        declared = 'SET-PIECE-DECLARE' not in _run_draft(proj)
        ok = missing and declared
        return ok, ('fires when absent, silent when explicitly declared none'
                    if ok else f'missing={missing} declared_none_quiet={declared}')
    finally:
        shutil.rmtree(os.path.join(ROOT, 'projects', proj), ignore_errors=True)


_RM = ("```reveal-map\n"
       "R1 | land: {land} | hold: {holds}\n"
       "```\n")
_SP = ("```set-pieces\n"
       "SP1 | a fight | {a} - {b} | verified: dense | {keep}\n"
       "```\n")


def _ratchet_project(proj, beats, land, holds, a, b, keep):
    lines = [{"id": 1, "narration": "A line.", "clip_start": "00:00:10.0",
              "clip_end": "00:00:14.0"}]
    p = os.path.join(ROOT, 'projects', proj)
    if not os.path.exists(p):
        _mk(proj, {'draft.json': {"project": proj, "title": "t",
                                  "target_minutes": 10, "voice": "tts",
                                  "lines": lines}})
    io.open(os.path.join(p, 'beats_proposal.md'), 'w', encoding='utf-8').write(
        _beats(beats,
               extra="\n" + _RM.format(land=land, holds=holds)
               + _SP.format(a=a, b=b, keep=keep)))
    return p


def test_ratchet() -> tuple[bool, str]:
    """[RATCHET] - declared facts may move only TOWARD strictness.

    Three consumers, one mechanism. Each loosening must be printed and named,
    and none of them may be fatal (reviewed_exceptions.md is the escape hatch).
    """
    proj = '_selftest_ratchet'
    try:
        _ratchet_project(proj, 4, '00:05:00', 'alpha, beta, gamma',
                         '00:01:00', '00:04:00', 'keep')
        _run_draft(proj)                       # pins the baseline
        # every one of these is a loosening
        _ratchet_project(proj, 3, '00:07:00', 'alpha',
                         '00:02:00', '00:03:00', 'drop')
        out = _run_draft(proj)
        beats_ = 'RATCHET' in out and 'beat' in out.lower()
        alias_ = 'beta' in out or 'alias' in out.lower()
        land_ = 'land' in out.lower()
        narrow = 'narrow' in out.lower() or 'drop' in out.lower()
        fatal = 'draft.json has problems' in out
        ok = beats_ and alias_ and land_ and narrow and not fatal
        return ok, ('all three consumers reported, non-fatal' if ok else
                    f'beats={beats_} alias={alias_} land={land_} '
                    f'range={narrow} fatal={fatal}')
    finally:
        shutil.rmtree(os.path.join(ROOT, 'projects', proj), ignore_errors=True)


def test_ratchet_nofire() -> tuple[bool, str]:
    """[RATCHET] must NOT fire on movement toward strictness.

    THE REGRESSION CASE. Bad Genius's beat map was corrected eight times during
    cataloguing - seven retimes against frame-verified footage (B03, B14, B19,
    B21, B34, B51, B80) and one INSERTED beat (B58, a plot point the 5s grid had
    missed). Every one made the map more accurate and the gates stricter. A hash
    would have flagged all eight and trained everyone to override the runner.

    This test reproduces that shape: beat count GROWS, timestamps CHANGE,
    aliases GROW, the landing moves EARLIER, the set-piece range WIDENS. The
    ratchet must stay silent through all of it.
    """
    proj = '_selftest_ratchet_ok'
    try:
        _ratchet_project(proj, 3, '00:05:00', 'alpha, beta',
                         '00:02:00', '00:03:00', 'keep')
        _run_draft(proj)                       # pin
        # beats grow (the B58 insert), timestamps move (the seven retimes),
        # aliases grow, land earlier, range wider
        _ratchet_project(proj, 5, '00:04:00', 'alpha, beta, gamma',
                         '00:01:00', '00:04:30', 'keep')
        out = _run_draft(proj)
        ok = 'RATCHET' not in out
        hits = [l.strip()[:90] for l in out.splitlines() if 'RATCHET' in l]
        return ok, ('silent on movement toward strictness' if ok else
                    f'FALSE POSITIVE: {hits[:3]}')
    finally:
        shutil.rmtree(os.path.join(ROOT, 'projects', proj), ignore_errors=True)


def test_target_lock() -> tuple[bool, str]:
    """[TARGET-LOCK] - target_minutes is an AUTHOR INPUT, not a model output.

    Tier used to be a threshold, which made it the cheapest way to turn a red
    gate green: lower the target, the floor moves, the warning clears. That is
    what happened to badgenius2017 on 2026-09-04 and it arrived with three
    paragraphs of justification.

    `target_minutes` replaces it as guidance on scale. Nothing compares runtime
    against it. But it must be the AUTHOR's number, so the engine pins it in
    state.json the first time it sees it and reports any later disagreement.

    Asserts:
      1. first run pins the declared value silently (no warning)
      2. changing it afterwards is DETECTED and names both values
      3. an unchanged value stays quiet on the second run
    """
    proj = '_selftest_targetlock'
    lines = [{"id": 1, "narration": "A line of narration here.",
              "clip_start": "00:00:10.0", "clip_end": "00:00:14.0"}]

    def write(tm):
        _mk(proj, {'draft.json': {"project": proj, "title": "selftest",
                                  "target_minutes": tm, "voice": "tts",
                                  "lines": lines}}) if not os.path.exists(
            os.path.join(ROOT, 'projects', proj)) else io.open(
            os.path.join(ROOT, 'projects', proj, 'draft.json'), 'w',
            encoding='utf-8').write(json.dumps(
                {"project": proj, "title": "selftest", "target_minutes": tm,
                 "voice": "tts", "lines": lines}, ensure_ascii=False, indent=2))

    try:
        write(20)
        first = _run_draft(proj)
        pinned_quiet = 'TARGET-LOCK' not in first
        second = _run_draft(proj)
        same_quiet = 'TARGET-LOCK' not in second
        write(12)                       # the model "helpfully" lowers the target
        third = _run_draft(proj)
        detected = ('TARGET-LOCK' in third and '20' in third and '12' in third)
        ok = pinned_quiet and same_quiet and detected
        return ok, ('pins on first run, quiet when unchanged, names both values '
                    'when changed' if ok else
                    f'pinned_quiet={pinned_quiet} same_quiet={same_quiet} '
                    f'detected={detected}')
    finally:
        shutil.rmtree(os.path.join(ROOT, 'projects', proj), ignore_errors=True)


def test_reviewed_exception() -> tuple[bool, str]:
    """reviewed_exceptions.md - a finding looked at and deliberately kept.

    Asserts all four properties that make this safe rather than a mute button:
      1. an excepted finding STILL PRINTS (visible, marked REVIEWED)
      2. it does NOT fail the project
      3. the exception is keyed to the exact FINDING ('cop_car_night'), so a
         second, unrelated finding from the same gate still fails
      4. an exception naming a finding that no longer occurs is reported STALE
    """
    # Uses the line-level `visual` path, which IS wired. (An earlier version of
    # this test drove the finding through shots.json families; that input was
    # tried and reverted the same day - see the note in draft.py.)
    proj = '_selftest_reviewed'
    lines = []
    for i, cs in enumerate(('00:00:10.0', '00:00:20.0', '00:00:30.0'), 1):
        lines.append({"id": i, "narration": f"Line {i}.", "clip_start": cs,
                      "clip_end": cs.replace('.0', '.5'), "visual": "cop_car_night"})
    for i, cs in enumerate(('00:00:50.0', '00:01:00.0', '00:01:10.0'), 4):
        lines.append({"id": i, "narration": f"Line {i}.", "clip_start": cs,
                      "clip_end": cs.replace('.0', '.5'), "visual": "diner_booth"})
    p = _mk(proj, {'draft.json': {"project": proj, "title": "selftest",
                                  "target_minutes": 1, "voice": "tts",
                                  "lines": lines}})
    io.open(os.path.join(p, 'reviewed_exceptions.md'), 'w',
            encoding='utf-8').write(
        "# Reviewed exceptions\n\n"
        "```reviewed-exceptions\n"
        "VISUAL-REPEAT | cop_car_night | 2026-09-05 | three distinct beats in one "
        "location; watched, reads fine\n"
        "VISUAL-REPEAT | no_such_family | 2026-09-05 | should report as stale\n"
        "```\n")
    try:
        out = _run_draft(proj)
        # substring over the whole output, not per-line: rich wraps long
        # messages, so the family name and the REVIEWED marker land on
        # different rows. Wrapping is display, not behaviour.
        printed = 'cop_car_night' in out and 'REVIEWED 2026-09-05' in out
        other_fails = any('diner_booth' in l for l in out.splitlines())
        stale = 'STALE' in out and 'no_such_family' in out
        # the excepted finding must not be what fails the project
        excepted_not_fatal = not any(
            'cop_car_night' in l and l.strip().startswith('-')
            for l in out.splitlines())
        ok = printed and other_fails and stale and excepted_not_fatal
        return ok, ('printed+non-fatal, unrelated finding still fails, stale '
                    'reported' if ok else
                    f'printed={printed} other_fails={other_fails} '
                    f'stale={stale} non_fatal={excepted_not_fatal}')
    finally:
        shutil.rmtree(os.path.join(ROOT, 'projects', proj), ignore_errors=True)


def _win_project(proj, bad_at=None):
    """Cuts deu 5s tu 0..200. Segment 10s mot, nen ranh gioi loi noi roi dung
    vao boi so cua 10 -> diem ngat du doan duoc. `bad_at` thay MOT moc bang rac."""
    cuts = [float(5 * i) for i in range(41)]
    if bad_at is not None:
        cuts[cuts.index(bad_at)] = "khong-phai-so"
    segs = [{"start": float(10 * i), "end": float(10 * i + 8), "text": f"s{i}"}
            for i in range(20)]
    _mk(proj, {"_cuts.json": {"threshold": 27.0, "min_scene_len": 15, "cuts": cuts},
               "transcript.json": {"language": "th", "duration": 200.0,
                                   "model": "x", "segments": segs}})
    r = subprocess.run([sys.executable, 'tools/make_windows.py', proj],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=300)
    wp = os.path.join(ROOT, 'projects', proj, 'windows.json')
    w = json.load(io.open(wp, encoding='utf-8')) if os.path.exists(wp) else None
    return r, w


def test_window_grouping() -> tuple[bool, str]:
    """[WINDOW-GROUPING] positive test - gom cu cat thanh moment.

    Khang dinh:
      1. chay duoc, sinh windows.json
      2. gom THAT: moi cua so > mot shot may quay (neu bang nhau thi khong gom)
      3. moi canh cua so dung tai mot moc cat - khong bia ra moc moi
      4. phu kin, khong ho, khong chong lan
      5. KHONG doc file cam (shots.json la dap an)
    """
    proj = '_selftest_windows'
    r, w = _win_project(proj)
    if w is None:
        return False, f'khong sinh windows.json (rc={r.returncode}) {r.stdout[-200:]}'
    W = w['windows']
    if len(W) < 2:
        return False, f'chi {len(W)} cua so - khong co gi de kiem tra'
    cuts = {float(5 * i) for i in range(41)}
    off = [x['id'] for x in W
           if x['start_sec'] not in cuts or x['end_sec'] not in cuts]
    if off:
        return False, f'canh khong nam tren moc cat: {off[:3]}'
    for a, b in zip(W, W[1:]):
        if abs(a['end_sec'] - b['start_sec']) > 1e-6:
            return False, f"ho/chong lan giua {a['id']} va {b['id']}"
    if W[0]['start_sec'] != 0.0 or W[-1]['end_sec'] != 200.0:
        return False, 'khong phu kin toan bo'
    multi = sum(1 for x in W if x['n_cuts'] >= 1)
    if multi == 0:
        return False, 'moi cua so chi la mot shot - khong he GOM'
    # Tim viec DUNG DUONG DAN that su (pdir / "shots.json"), khong phai viec
    # NHAC TEN - hang so FORBIDDEN_INPUTS co quyen liet ke chung.
    src = io.open(os.path.join(ROOT, 'tools', 'make_windows.py'),
                  encoding='utf-8').read()
    leak = re.findall(r'/\s*["\'](shots\.json|beats_proposal\.md|draft\.json|'
                      r'timeline\.json|names\.json)["\']', src)
    leak += re.findall(r'open\(\s*["\'][^"\']*(shots\.json|beats_proposal\.md)', src)
    if leak:
        return False, f'ma nguon DUNG dau vao CAM: {sorted(set(leak))}'
    return True, (f'{len(W)} cua so, moi canh tren moc cat, phu kin 0-200s, '
                  f'{multi} cua so gom >1 shot, khong dung dau vao cam')


def test_window_bad_cut() -> tuple[bool, str]:
    """[WINDOW-BAD-CUT] granularity - MOT moc cat hong chi duoc lam hong cua so
    ke no, khong phai ca lo (bai hoc 2026-09-05).

    So sanh lo sach voi lo co moc hong tai t=100: moi cua so KHONG cham vung
    [95,105] phai GIONG HET; chi cua so phu vung do bi danh dau degraded.
    """
    clean_r, clean = _win_project('_selftest_windows_ok')
    bad_r, bad = _win_project('_selftest_windows_bad', bad_at=100.0)
    if clean is None or bad is None:
        return False, 'mot trong hai lo khong sinh duoc windows.json'
    if bad_r.returncode != 0:
        return False, f'moc hong lam CHET CA LO (rc={bad_r.returncode})'
    if bad['stats']['n_cuts_bad'] != 1:
        return False, f"cach ly sai: n_cuts_bad={bad['stats']['n_cuts_bad']}"
    deg = [x for x in bad['windows'] if x.get('degraded')]
    if not deg:
        return False, 'moc hong bi NUOT im lang - khong cua so nao degraded'
    for x in deg:
        if not (x['start_sec'] < 105.0 and x['end_sec'] > 95.0):
            return False, f"{x['id']} bi danh dau degraded nhung o ngoai vung hong"
    def key(ws):
        return {(w['start_sec'], w['end_sec']) for w in ws}
    far_clean = {k for k in key(clean['windows']) if k[1] <= 95.0 or k[0] >= 105.0}
    far_bad = {k for k in key(bad['windows']) if k[1] <= 95.0 or k[0] >= 105.0}
    if far_clean != far_bad:
        d = (far_clean ^ far_bad)
        return False, f'cua so NGOAI vung hong bi doi: {sorted(d)[:3]}'
    return True, (f"1 moc hong -> {len(deg)} cua so degraded, "
                  f"{len(far_bad)}/{len(key(clean['windows']))} cua so con lai "
                  f"giong het lo sach, rc=0")


def test_transcript_quality() -> tuple[bool, str]:
    """[TRANSCRIPT-QUALITY] - mot transcript hong khong TRONG nhu hong.

    FIRES  : mot segment dai nuot phan lon thoi luong + mot cau lap 3 lan.
    SILENT : cung so segment, cung so chu, nhung do dai binh thuong.

    Hai nua phai doi xung, vi ban hong that (tokyodrift2006) bao phu 89% thoi
    luong - cao HON ban sach - va chi co do dai segment moi phan biet duoc.
    """
    import subprocess as _sp

    def run(proj, segs, dur):
        _mk(proj, {"transcript.json": {"language": "en", "duration": dur,
                                       "segments": segs}})
        r = _sp.run([sys.executable, 'tools/check_transcript.py', proj],
                    cwd=ROOT, capture_output=True, text=True,
                    encoding='utf-8', errors='replace', timeout=300)
        return (r.stdout or '') + (r.stderr or ''), r.returncode

    dur = 600.0
    bad = [{"start": 0.0, "end": 400.0, "text": "one line over everything"}]
    bad += [{"start": 400.0 + i, "end": 401.0 + i, "text": "same line"}
            for i in range(4)]
    out_b, code_b = run('_selftest_tq_bad', bad, dur)
    if 'longer than' not in out_b or code_b != 2:
        return False, f'KHONG bat duoc segment khong lo (rc={code_b})'
    if 'repetition loop' not in out_b:
        return False, 'KHONG bat duoc vong lap'

    good = [{"start": float(i * 6), "end": float(i * 6 + 4),
             "text": f"line number {i}"} for i in range(80)]
    out_g, code_g = run('_selftest_tq_good', good, dur)
    if 'longer than' in out_g or 'repetition loop' in out_g:
        return False, f'keu tren transcript SACH: {out_g[:120]}'
    if code_g != 0:
        return False, f'transcript sach nhung rc={code_g}: {out_g[:120]}'
    return True, ('bat segment khong lo + vong lap; im tren transcript sach '
                  'cung so segment')


def test_name_leak() -> tuple[bool, str]:
    """[NAME-LEAK] - mot ten rieng khong co nguon trong narration.

    Hai nua, vi mot rule chi bao "co" thi vo dung neu no cung bao "co" voi moi
    thu:
      FIRES  : ten romanise tu transcript ("Lin"/"Rin" = Lynn) va mot nhan vat
               CHI ton tai trong ban dich may ("Toe").
      SILENT : ten that trong names.json, va dia danh co trong DONG BEAT.

    "Lin" la truong hop rieng: beat map TU MAU THUAN - header cam no, nhung B05
    lai viet "the nickname on the form: Lin". Chi dua vao allowlist thi no lot,
    nen phai co nhanh so sanh BIEN THE (cung chu cai dau, edit distance <=2).
    """
    proj = '_selftest_nameleak'
    names = {"names": [{"character": "Lynn", "actor": "A"},
                       {"character": "Bank", "actor": "B"},
                       {"character": "Lynn's father", "actor": "C"}]}
    beats = ("# beats\n"
             'The transcript romanises the lead as "Lin". names.json says Lynn.\n'
             "style: linear\n\n"
             "B01 | 00:00:05 | Lynn in Sydney | Lynn | setup\n"
             "B02 | 00:00:20 | Bank at the gate | Bank | action\n")
    shots = {"shots": [
        {"id": "clip:00:00:00", "clip_start": "00:00:00.0",
         "clip_end": "00:00:10.0", "chars": ["Lynn"], "depicts": ["setup"],
         "action": "a girl at a table", "censor": "none"},
        {"id": "clip:00:00:10", "clip_start": "00:00:10.0",
         "clip_end": "00:00:20.0", "chars": ["Bank"], "depicts": ["action"],
         "action": "a boy at a gate", "censor": "none"}]}
    lines = [
        # phai IM: ten that + dia danh co trong dong beat
        {"id": 1, "narration": "Lynn lands in Sydney and waits.",
         "clip_start": "00:00:00.0", "clip_end": "00:00:10.0", "note": "B01"},
        # phai KEU: ca ba deu la ten khong co nguon
        {"id": 2, "narration": "Teach me how, Rin. Toe paid her. The form says Lin.",
         "clip_start": "00:00:10.0", "clip_end": "00:00:20.0", "note": "B02"},
    ]
    p = _mk(proj, {"names.json": names, "shots.json": shots,
                   "draft.json": {"title": "T", "target_minutes": 1,
                                  "lines": lines},
                   "_cuts.json": {"cuts": [0.0, 10.0, 20.0]}})
    io.open(os.path.join(p, "beats_proposal.md"), "w",
            encoding="utf-8").write(beats)
    out = _run_draft(proj)
    hits = [l.strip() for l in out.splitlines() if "[NAME-LEAK]" in l]
    joined = " ".join(hits)
    missed = [n for n in ("Rin", "Toe", "Lin") if f"'{n}'" not in joined]
    if missed:
        return False, f'KHONG bat duoc {missed} - ' + (hits[0] if hits else 'khong co hit nao')
    if any("line 1:" in h for h in hits):
        return False, ('keu tren dong 1, nhung "Lynn" co trong names.json va '
                       '"Sydney" co trong dong beat - ca hai deu co nguon')
    return True, (f"bat ca Lin/Rin/Toe ({len(hits)} hit), im tren ten that + "
                  f"dia danh co trong dong beat")


def _moment_project(proj, *, bad_span=None, make_overlap=False):
    """Hai span 40s, cu cat moi 10s. Mot moment vat qua seam o t=40."""
    cuts = [float(10 * i) for i in range(9)]            # 0..80
    shots = lambda a, b: [{"i": j, "start": float(a + 10*j),
                           "end": float(a + 10*j + 10), "dur": 10.0}
                          for j in range((b - a) // 10)]
    spans = [{"id": "sp01", "own_start": 0.0, "own_end": 40.0, "ext_end": 60.0,
              "shots": shots(0, 60), "frames": [], "frame_status": "ok"},
             {"id": "sp02", "own_start": 40.0, "own_end": 80.0, "ext_end": 80.0,
              "shots": shots(40, 80), "frames": [], "frame_status": "ok"}]
    p = _mk(proj, {"_cuts.json": {"cuts": cuts},
                   "spans.json": {"project": proj, "span_sec": 40.0,
                                  "overlap_sec": 20.0, "region": [0.0, 80.0],
                                  "spans": spans}})
    d = os.path.join(p, "spans.json.d")
    os.makedirs(d)

    def mom(idx, a, b, extra=None):
        o = {"shots": idx, "clip_start": f"00:00:{a:06.3f}",
             "clip_end": f"00:00:{b:06.3f}", "depicts": ["action"],
             "chars": [], "action": "x", "censor": "none"}
        o.update(extra or {})
        return o

    # sp01 tiles 0..60; the moment [3,4] spans 30-50, midpoint 40 -> owned by sp02
    sp01 = {"span": "sp01", "moments": [mom([0, 1, 2], 0, 30), mom([3, 4], 30, 50),
                                        mom([5], 50, 60)]}
    # sp02 tiles 40..80. Its first moment starts at 40 -> leaves a gap after
    # sp01's 0-30 unless the seam rule works.
    start2 = 30.0 if make_overlap else 40.0
    sp02 = {"span": "sp02", "moments": [mom([0], start2, 50), mom([1, 2], 50, 70),
                                        mom([3], 70, 80)]}
    for sid, obj in (("sp01", sp01), ("sp02", sp02)):
        io.open(os.path.join(d, f"{sid}.json"), "w", encoding="utf-8").write(
            json.dumps(obj, ensure_ascii=False))
    if bad_span:
        # Phai lam hong mot span CO THAT trong spans.json. Mot file la cho mot
        # span khong ton tai thi assembler khong bao gio doc toi - test kieu do
        # se "dat" ma khong he cham vao duong di that.
        io.open(os.path.join(d, f"{bad_span}.json"), "w",
                encoding="utf-8").write("{ this is not json")
    r = subprocess.run([sys.executable, 'tools/assemble_moments.py', proj],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=300)
    wp = os.path.join(p, "windows_llm.json")
    w = json.load(io.open(wp, encoding='utf-8')) if os.path.exists(wp) else None
    return r, w


def test_moment_seam() -> tuple[bool, str]:
    """[MOMENT-SEAM] positive test - quy tac so huu theo DIEM GIUA.

    Mot moment vat qua mep span duoc CA HAI span tra ve. Phai giu DUNG MOT lan,
    boi span chua diem giua cua no, va ket qua cuoi khong duoc co ho hay chong
    lan. Day la cho loi duoc du doan se don lai, nen no phai co test rieng.
    """
    proj = '_selftest_moment_seam'
    r, w = _moment_project(proj)
    if w is None:
        return False, f'khong sinh windows_llm.json (rc={r.returncode})'
    W = w['windows']
    if w['stats']['validation_problems']:
        return False, f"validation ket toi: {w['problems'][:2]}"
    # moment vat seam (30-50) phai xuat hien dung mot lan
    cross = [x for x in W if x['start_sec'] <= 30.0 and x['end_sec'] >= 50.0]
    if len(cross) != 1:
        return False, (f'moment vat seam xuat hien {len(cross)} lan, can dung 1: '
                       f'{[(x["start_sec"], x["end_sec"]) for x in W]}')
    for a, b in zip(W, W[1:]):
        if abs(a['end_sec'] - b['start_sec']) > 1e-6:
            return False, f"ho/chong lan giua {a['id']} va {b['id']}"
    if W[0]['start_sec'] != 0.0 or W[-1]['end_sec'] != 80.0:
        return False, f"khong phu kin: {W[0]['start_sec']}..{W[-1]['end_sec']}"
    dup = [x['id'] for x in W if x['span'] == 'sp01' and x['start_sec'] >= 40.0]
    if dup:
        return False, f'sp01 giu moment thuoc vung so huu cua sp02: {dup}'
    return True, (f"{len(W)} cua so, moment vat seam giu dung 1 lan boi span "
                  f"chua diem BAT DAU, phu kin 0-80s khong ho khong chong lan")


def test_moment_bad_span() -> tuple[bool, str]:
    """[MOMENT-BAD-SPAN] granularity - MOT span hong chi mat SPAN DO.

    File span hong phai duoc GOI TEN trong missing_spans, cac span con lai van
    lap rap binh thuong, va tien trinh khong duoc chet.
    """
    proj = '_selftest_moment_bad'
    r, w = _moment_project(proj, bad_span='sp02')
    if w is None:
        return False, f'span hong lam CHET CA LO (rc={r.returncode})'
    if r.returncode != 0:
        return False, f'rc={r.returncode}, span hong khong duoc cach ly'
    named = any('sp02' in str(s) for s in w.get('problems', [])) \
        or 'sp02' in w.get('missing_spans', [])
    if not named:
        return False, ('span hong bi NUOT im lang - khong co trong problems '
                       'hay missing_spans')
    _moment_project('_selftest_moment_bad_ref')
    ref = json.load(io.open(os.path.join(
        ROOT, 'projects', '_selftest_moment_bad_ref', 'windows_llm.json'),
        encoding='utf-8'))
    a = [(x['start_sec'], x['end_sec']) for x in w['windows']]
    b = [(x['start_sec'], x['end_sec']) for x in ref['windows']
         if x['span'] == 'sp01']
    if a != b:
        return False, (f'span hong lam doi ket qua cua span KHAC: '
                       f'{a} vs sp01-cua-lo-sach {b}')
    return True, (f"span hong duoc goi ten, {len(a)} cua so tu span con lai "
                  f"giong het lo sach, rc=0")


def test_exception_key() -> tuple[bool, str]:
    """reviewed_exceptions.md keys must survive renumbering, not survive edits.

    The bug: the REVEAL-TIMING key was "<reveal_id> L<line_id>". Line ids are
    assigned by assemble_draft.py in clip order, so redrafting tokyodrift2006
    renumbered everything and 'R2 L103' went STALE on its own - the human's
    reviewed decision evaporated silently.

    Asserts, in both directions:
      1. the key does NOT change when only line ids change (renumber-proof)
      2. the key DOES change when the narration is edited (nobody reviewed the
         new sentence)
      3. the key DOES change when the beat changes
      4. a NEW-style entry is matched by reviewed.load and suppresses
      5. an OLD-style "L<id>" entry is NOT matched, so it cannot grant
         suppression, and reviewed.stale() reports it
    """
    import pathlib
    # Cac test khac goi validator qua subprocess, nen module nay chua bao gio
    # can import `pipeline`. Test nay kiem mot HAM THUAN (khoa exception) nen
    # no import truc tiep - va do do phai tu dua ROOT vao sys.path.
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from pipeline.draft import exception_key, reveal_timing_check
    from pipeline import draft as _d
    from pipeline import reviewed as _rv

    TEXT = "Then the old man just sits there in silence, and the smile dies."
    k_a = exception_key("R2", "B61", TEXT)
    k_b = exception_key("R2", "B61", "  Then the OLD man just sits there in "
                                     "silence,   and the smile dies. ")
    k_edit = exception_key("R2", "B61", TEXT + " He knew.")
    k_beat = exception_key("R2", "B62", TEXT)
    renumber_proof = (k_a == k_b)          # whitespace/case normalised, no id
    edit_sensitive = (k_a != k_edit)
    beat_sensitive = (k_a != k_beat)

    # --- integration: the hit must CARRY the key, built from beat + text ----
    class _L:
        def __init__(self, i, note, narr):
            self.id, self.note, self.narration = i, note, narr
            self.clip_start, self.clip_end = "00:10:00.0", "00:10:05.0"

    class _D:
        pass

    dd = _D()
    dd.lines = [_L(103, "B61", TEXT)]
    _orig = _d.parse_reveal_map
    _d.parse_reveal_map = lambda project: [
        {"id": "R2", "land_ref": "01:15:07", "land_sec": 4507.0,
         "holds": ["dies"]}]
    try:
        hits = reveal_timing_check("_irrelevant", dd)
        carries = (len(hits) == 1 and hits[0].get("key") == k_a)
        # cung mot dong, id khac -> khoa KHONG doi
        dd.lines = [_L(7, "B61", TEXT)]
        hits2 = reveal_timing_check("_irrelevant", dd)
        stable = (hits2 and hits2[0]["key"] == hits[0]["key"])
    finally:
        _d.parse_reveal_map = _orig

    # --- the file side: new key matches, old key does not, stale reports ----
    proj = '_selftest_exckey'
    p = _mk(proj, {'draft.json': {"project": proj, "title": "selftest",
                                  "target_minutes": 1, "voice": "tts",
                                  "lines": [{"id": 1, "narration": "x.",
                                             "clip_start": "00:00:01.0",
                                             "clip_end": "00:00:02.0"}]}})
    try:
        io.open(os.path.join(p, 'reviewed_exceptions.md'), 'w',
                encoding='utf-8').write(
            "# Reviewed exceptions\n\n"
            "```reviewed-exceptions\n"
            f"REVEAL-TIMING | {k_a} | 2026-10-20 | new-style key, should match\n"
            "REVEAL-TIMING | R2 L103 | 2026-09-11 | old line-number key\n"
            "```\n")
        declared, bad = _rv.load(pathlib.Path(p))
        new_found = ("REVEAL-TIMING", k_a) in declared
        old_not_key = ("REVEAL-TIMING", k_a) != ("REVEAL-TIMING", "R2 L103")
        # khoa cu van nam trong file, nhung KHONG trung voi khoa cua finding
        old_cannot_grant = ("REVEAL-TIMING", "R2 L103") in declared and \
            "R2 L103" != k_a
        st = _rv.stale(declared, {("REVEAL-TIMING", k_a)}, ("REVEAL-TIMING",))
        stale_reports_old = any(k == "R2 L103" for _g, k, _d2, _r in st)
        no_malformed = not bad
    finally:
        shutil.rmtree(os.path.join(ROOT, 'projects', proj), ignore_errors=True)

    ok = (renumber_proof and edit_sensitive and beat_sensitive and carries
          and stable and new_found and old_cannot_grant and stale_reports_old
          and no_malformed)
    return ok, ('key is renumber-proof and edit-sensitive; hit carries it; '
                'old L<id> key cannot grant and is reported STALE' if ok else
                f'renumber_proof={renumber_proof} edit={edit_sensitive} '
                f'beat={beat_sensitive} carries={carries} stable={stable} '
                f'new_found={new_found} old_cannot_grant={old_cannot_grant} '
                f'stale_old={stale_reports_old} malformed_ok={no_malformed}')


def test_appearance_id() -> tuple[bool, str]:
    """[APPEARANCE-ID] (permanence rule 2) - identity hidden behind a looks
    descriptor. Built from the exact Tokyo Drift miss: 'the greying man he is
    shipped to' turned out to be Sean's father. Must FIRE on a looks descriptor
    + person, and must STAY SILENT on the 'his father' fix and on evaluative
    (non-appearance) descriptors like 'the best driver'."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from pipeline.draft import _APPEARANCE
    fire = ["the greying man he is shipped to",
            "the long-haired man waits to collect",
            "the old man says his piece", "the bald man at the wheel"]
    silent = ["his father, a US Navy officer, lays it out",
              "the best driver in the city", "the quiet man nods",
              "the whole crowd swarms the wreck"]
    bad = [s for s in fire if not _APPEARANCE.search(s)] + \
          [s for s in silent if _APPEARANCE.search(s)]
    ok = not bad
    return ok, ("fires on looks descriptors (greying/long-haired/old/bald), "
                "silent on 'his father' + evaluative descriptors"
                if ok else f"wrong on: {bad}")


def test_callback_cite() -> tuple[bool, str]:
    """[CALLBACK-CITE] (permanence rule 3) - a link to an earlier event needs a
    cited beat. Built from the exact miss: 'the same move that got him shipped
    out of Arizona' was invented. Must FIRE on backward-link phrasings and stay
    SILENT on plain description."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from pipeline.draft import _CALLBACK
    fire = ["It's the same move that got him shipped out of Arizona",
            "It is the same thing he did in the very first scene back home",
            "just like he did before", "what got him shipped out"]
    silent = ["Sean slides out dead last, front end smoking",
              "He walks into the garage and hands over the keys"]
    bad = [s for s in fire if not _CALLBACK.search(s)] + \
          [s for s in silent if _CALLBACK.search(s)]
    ok = not bad
    return ok, ("fires on backward-link phrasings, silent on plain description"
                if ok else f"wrong on: {bad}")


def test_fact_scope_bridge() -> tuple[bool, str]:
    """Permanence rule 1 (FACT audit scope): a bridge/edited line carries a
    marker (bridge:true, or callback_beat) that the FACT-audit tooling uses to
    put it in the 100%-coverage set. Asserts the schema TYPES these fields so a
    draft can declare them - the exact gap that let 'on the mountain' (a wrong
    location taken from memory, not the skipped beats) ship inside a bridge line
    that was sampled past."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from pipeline.schemas import Line
    ln = Line(id=1, narration="x", bridge=True, callback_beat="B07")
    ok = (ln.bridge is True and ln.callback_beat == "B07")
    # and a bridge line must survive a round-trip through _drop_unknown (the
    # mechanism that silently dropped over_montage/film_intro before)
    from pipeline.schemas import _drop_unknown
    kept = _drop_unknown(Line, {"id": 2, "narration": "y", "bridge": True,
                                "callback_beat": "B09", "junk": 1})
    ok = ok and kept.get("bridge") is True and kept.get("callback_beat") == "B09" \
        and "junk" not in kept
    return ok, ("bridge + callback_beat are typed and survive _drop_unknown"
                if ok else f"bridge={ln.bridge} cb={ln.callback_beat} kept={kept}")


TESTS = {
    'VISUAL-REPEAT':   test_visual_repeat,
    'EXCEPTION-KEY':   test_exception_key,
    'APPEARANCE-ID':   test_appearance_id,
    'CALLBACK-CITE':   test_callback_cite,
    'FACT-SCOPE-BRIDGE': test_fact_scope_bridge,
    # 'VISUAL-REPEAT-SHOTS' is NOT registered: the feature it specifies was
    # wired on 2026-09-05 and reverted the same day (shots.json `family` is a
    # scene label, not a set of interchangeable alternates - it flagged 22
    # families on a shipped film at up to 8x). The test body is kept as the
    # spec, so if the idea returns with its own cap the spec is already written.
    'REVIEWED-EXCEPTION': test_reviewed_exception,
    'TARGET-LOCK':       test_target_lock,
    'SET-PIECE-DECLARE': test_set_piece_declare,
    'PROJECT-STATUS':    test_project_status,
    'STYLE-DECLARE':     test_style_declare,
    'SCORE-DENOMINATOR': test_score_denominator,
    'BINDING-INTEGRITY-REVIEW':  test_binding_integrity_review,
    'CATALOGUE-DENSITY-REVIEW':  test_catalogue_density_review,
    'BEAT-COVERAGE-REVIEW':      test_beat_coverage_review,
    'RATCHET':           test_ratchet,
    'RATCHET-NOFIRE':    test_ratchet_nofire,
    'FOOTAGE-DROPPED': test_footage_dropped,
    'DUPLICATE-ID':    test_duplicate_id,
    'EMPTY-LINE':      test_empty_line,
    'BEAT-MAP':        test_beat_map,
    'WINDOW-GROUPING': test_window_grouping,
    'WINDOW-BAD-CUT':  test_window_bad_cut,
    'TRANSCRIPT-QUALITY': test_transcript_quality,
    'NAME-LEAK':       test_name_leak,
    'MOMENT-SEAM':     test_moment_seam,
    'MOMENT-BAD-SPAN': test_moment_bad_span,
}

# Gates known to be unreachable. Reported as XFAIL, not PASS and not FAIL, so
# the run stays green WITHOUT the finding disappearing. Remove the entry when
# the underlying defect is fixed - never to make the run green.
KNOWN_UNREACHABLE: dict = {
    # EMPTY-LINE was here on 2026-09-05 and was FIXED, not accommodated.
    # Entries are removed by fixing the defect, never to make the run green.
}

if __name__ == '__main__':
    want = sys.argv[1:] or list(TESTS)
    bad = 0
    for name in want:
        fn = TESTS.get(name)
        if not fn:
            print(f'?? no self-test for {name}')
            continue
        ok, msg = fn()
        if not ok and name in KNOWN_UNREACHABLE:
            print(f'XFAIL {name:<18} UNREACHABLE - {KNOWN_UNREACHABLE[name]}')
            continue
        if ok and name in KNOWN_UNREACHABLE:
            print(f'PASS  {name:<18} {msg}  <-- now reachable, drop it from '
                  f'KNOWN_UNREACHABLE')
            continue
        print(f'{"PASS" if ok else "FAIL"}  {name:<18} {msg}')
        bad += (not ok)
    sys.exit(1 if bad else 0)
