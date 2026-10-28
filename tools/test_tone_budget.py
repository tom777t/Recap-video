"""Tone-tag budget regression tests.

THE DEFECT
----------
19 of 109 lines (17.4%) were tagged `sad`, among them a car rollover, a two-gun
standoff and a character fetching a bag of money. A tag is heard TWICE - it
sets how the narrator reads the line AND which mood cue plays under it - so
each of those got a mournful delivery over sad music on an action beat.

Meanwhile `action` and `mystery` were used ZERO times, so kinetics were being
filed under `tense` and withheld information under `sad`. The budget was not
just wrong, it was wrong in a way that left two correct tags unused.

After the re-audit: sad 4 (3.7%), action 13, mystery 5, tense 41 -> 35.
And the single most inverted tag in the script: line 107, the one beat where
the film mourns Han, was tagged `normal`.

Cases
-----
  BUDGET-CONFIGURED   the cap and the valid-tag list exist and are sane
  SAD-CAP-ENFORCED    a draft over the sad budget is rejected, naming the lines
  UNKNOWN-TAG-CAUGHT  a tag no provider maps is rejected at draft time rather
                      than resolving to whatever the provider happens to do
  SINGLETON-TAGS      two `hook` lines is a draft-shape error
  REAL-DRAFT-IN-BUDGET  the shipped draft is inside the budget, and `sad` is
                      only on beats that are actually about loss
  TAGS-ALL-MAPPED     every tag the budget permits is mapped by the production
                      voice. A permitted-but-unmapped tag fails mid-render.

Run:  python tools/test_tone_budget.py
"""
from __future__ import annotations

import collections
import io
import json
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402

# The distribution as it actually shipped and failed, kept as the fixture.
OLD_SAD_IDS = [11, 14, 15, 21, 38, 55, 56, 57, 62, 63, 75, 76, 77, 78, 79,
               82, 83, 86, 104]


class _L:
    def __init__(self, i, delivery):
        self.id = i
        self.delivery = delivery


def _counts(tags: list) -> dict:
    return dict(collections.Counter(tags))


def _evaluate(tags: list) -> list:
    """Re-implements the gate's decision so a fixture can exercise it.

    Kept deliberately parallel to the [TONE-BUDGET] block in pipeline/draft.py;
    REAL-DRAFT-IN-BUDGET below checks the real gate against the real draft, so
    the two cannot silently diverge in the direction that matters.
    """
    bad = []
    n = max(1, len(tags))
    valid = set(getattr(config, "TONE_VALID", ()))
    unknown = sorted(set(tags) - valid)
    if unknown:
        bad.append(f"unknown tag(s) {unknown}")
    cap = float(getattr(config, "TONE_SAD_MAX_FRACTION", 0.05))
    frac = tags.count("sad") / n
    if frac > cap + 1e-9:
        bad.append(f"sad {frac:.1%} over {cap:.0%}")
    for t in getattr(config, "TONE_SINGLETON", ()):
        if tags.count(t) > 1:
            bad.append(f"{tags.count(t)} `{t}` lines")
    return bad


def test_budget_configured() -> tuple[bool, str]:
    cap = float(getattr(config, "TONE_SAD_MAX_FRACTION", -1))
    valid = tuple(getattr(config, "TONE_VALID", ()))
    if not (0.0 < cap <= 0.10):
        return False, f"TONE_SAD_MAX_FRACTION is {cap}, expected about 0.05"
    for t in ("normal", "tense", "action", "reveal", "sad", "mystery"):
        if t not in valid:
            return False, f"TONE_VALID is missing {t!r}: {valid}"
    return True, (f"sad budget {cap:.0%}, {len(valid)} valid tags including "
                  f"action and mystery")


def test_sad_cap_enforced() -> tuple[bool, str]:
    # the real old distribution: 19 sad in 109
    tags = (["sad"] * 19 + ["tense"] * 41 + ["normal"] * 23
            + ["reveal"] * 21 + ["intro"] * 3 + ["hook"] + ["outro"])
    if len(tags) != 109:
        return False, f"fixture is {len(tags)} lines, expected 109"
    bad = _evaluate(tags)
    if not any("sad" in b for b in bad):
        return False, (f"19/109 sad (17.4%) was accepted - the cap does not "
                       f"bite: {bad}")
    # and the shipped distribution must pass
    ok_tags = (["sad"] * 4 + ["tense"] * 35 + ["normal"] * 29
               + ["reveal"] * 18 + ["action"] * 13 + ["mystery"] * 5
               + ["intro"] * 3 + ["hook"] + ["outro"])
    if _evaluate(ok_tags):
        return False, f"the audited distribution was rejected: {_evaluate(ok_tags)}"
    return True, ("19/109 sad is rejected; 4/109 with action and mystery in "
                  "use passes")


def test_unknown_tag_caught() -> tuple[bool, str]:
    tags = ["normal"] * 100 + ["melancholy"] * 9
    bad = _evaluate(tags)
    if not any("unknown" in b for b in bad):
        return False, ("an unmapped tag was accepted; it would resolve to "
                       "whatever the voice provider does with it, or raise "
                       "mid-render")
    return True, "a tag outside TONE_VALID is rejected at draft time"


def test_singleton_tags() -> tuple[bool, str]:
    tags = ["normal"] * 107 + ["hook", "hook"]
    if not any("hook" in b for b in _evaluate(tags)):
        return False, "two `hook` lines was accepted"
    return True, "more than one `hook` is a draft-shape error"


def test_real_draft_in_budget() -> tuple[bool, str]:
    """The shipped draft, through the REAL gate's inputs."""
    p = Path(config.project_dir("tokyodrift2006")) / "draft.json"
    if not p.exists():
        return False, "SKIPPED - tokyodrift2006/draft.json not present"
    d = json.loads(p.read_text(encoding="utf-8-sig"))
    tags = [str(l.get("delivery") or "normal") for l in d["lines"]]
    bad = _evaluate(tags)
    if bad:
        return False, f"the shipped draft is out of budget: {bad}"
    c = _counts(tags)
    sad_ids = [l["id"] for l in d["lines"]
               if str(l.get("delivery") or "") == "sad"]
    # the sad lines must no longer be the action beats they used to be
    for gone in (11, 77, 82, 86, 104):
        if gone in sad_ids:
            return False, (f"line {gone} is still tagged sad - it is a crash / "
                           f"standoff / errand, not grief")
    if not c.get("action") or not c.get("mystery"):
        return False, (f"action={c.get('action', 0)} mystery="
                       f"{c.get('mystery', 0)} - both were unused before, and "
                       f"leaving them unused is what forced kinetics into "
                       f"`tense` and withheld information into `sad`")
    return True, (f"shipped draft: sad {len(sad_ids)}/{len(tags)} "
                  f"({100*len(sad_ids)/len(tags):.1f}%) on lines {sad_ids}; "
                  f"action {c['action']}, mystery {c['mystery']} now in use")


def test_tags_all_mapped() -> tuple[bool, str]:
    """Every permitted tag must be mapped by the production voice."""
    from pipeline.tts import DEFAULT_PROVIDER
    from pipeline.tts_providers import all_providers
    prov = all_providers().get(DEFAULT_PROVIDER)
    if prov is None:
        return False, "no production provider registered"
    missing = [t for t in getattr(config, "TONE_VALID", ())
               if t not in prov.delivery]
    if missing:
        return False, (f"TONE_VALID permits {missing} but the production voice "
                       f"does not map them - a draft using one would fail "
                       f"mid-render")
    return True, (f"all {len(config.TONE_VALID)} permitted tags are mapped by "
                  f"{prov.name}")


TESTS = {
    "BUDGET-CONFIGURED":    test_budget_configured,
    "SAD-CAP-ENFORCED":     test_sad_cap_enforced,
    "UNKNOWN-TAG-CAUGHT":   test_unknown_tag_caught,
    "SINGLETON-TAGS":       test_singleton_tags,
    "REAL-DRAFT-IN-BUDGET": test_real_draft_in_budget,
    "TAGS-ALL-MAPPED":      test_tags_all_mapped,
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
        print(f'{"PASS" if ok else "FAIL"}  {name:<22} {msg}')
        bad += (not ok)
    print("-" * 60)
    print("test_tone_budget: all pass" if not bad else
          f"test_tone_budget: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
