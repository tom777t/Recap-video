# -*- coding: utf-8 -*-
"""test_voice_measure.py - the voice stage measures a void voice profile.

Lost in the Stars stopped at VOICE with 214 freshly synthesized lines on
disk: "[VOICE-RATE-DRIFT] the production voice has NO valid measurement ...
python -m pipeline.calibration --project <p> ..." - a step by hand, on the
audio the stage had just made. calibration.ensure_measured does it there.

  MEASURED      void profile + enough fresh lines -> profile written, valid,
                its pace is the narration's (rate_drift then judges it)
  VALID-KEPT    a valid profile is not re-measured
  TOO-FEW       fewer than VOICE_AUTO_MEASURE_MIN lines -> not measured
  BUMP-EXCLUDED rate-bumped lines and film-speaks units are not samples

    python tools/test_voice_measure.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
from pipeline import calibration as C  # noqa: E402

PROJ = "_selftest_voice_measure"


def _tone(path: Path, secs: float) -> None:
    subprocess.run([config.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency=220:duration={secs}", "-ac", "1",
                    str(path)], check=True)


def main() -> int:
    pdir = Path(config.project_dir(PROJ))
    shutil.rmtree(pdir, ignore_errors=True)
    (pdir / "narration").mkdir(parents=True)
    tmp = Path(tempfile.mkdtemp(prefix="vprof_"))
    saved = (C._PROFILES_PATH, C.production_voice_key)
    key = "testvoice_default"
    C._PROFILES_PATH = tmp / "voice_profiles.json"
    C.production_voice_key = lambda: key
    res = []
    try:
        lines = []
        for i in range(1, 41):
            # 12 words in 4 s = 3 words/s = 180 WPM
            lines.append({"id": i, "delivery": "normal",
                          "narration": " ".join(["word"] * 12)})
            _tone(pdir / "narration" / f"line_{i:03d}.mp3", 4.0)
        # a bumped line and a unit read far faster - must not be samples
        lines.append({"id": 41, "delivery": "normal", "rate_bump": 1.3,
                      "narration": " ".join(["word"] * 40)})
        _tone(pdir / "narration" / "line_041.mp3", 4.0)
        lines.append({"id": 42, "film_speaks_seconds": 5.0, "narration": ""})
        draft = {"lines": lines}
        (pdir / "draft.json").write_text(json.dumps(draft))
        C._PROFILES_PATH.write_text(json.dumps({"profiles": {key: {
            "words_per_sec": 2.0, "mapping_signature": "old"}}}))
        C._STALE_SAID.clear()
        st = C.ensure_measured(PROJ, draft, pdir)
        prof = C.production_profile()
        wpm = prof.words_per_sec * 60
        res.append(("MEASURED", bool(st) and not st.get("skipped")
                    and prof.is_measured and 170 <= wpm <= 190,
                    f"profile {'valid' if prof.is_measured else 'void'}, "
                    f"{wpm:.0f} WPM (narration: 180)"))
        res.append(("BUMP-EXCLUDED", bool(st) and st.get("samples") == 40,
                    f"{(st or {}).get('samples')} samples of 40 clean lines"))
        res.append(("VALID-KEPT", C.ensure_measured(PROJ, draft, pdir) is None,
                    "a valid profile is left alone"))
        C._PROFILES_PATH.write_text(json.dumps({"profiles": {key: {
            "words_per_sec": 2.0, "mapping_signature": "old"}}}))
        few = {"lines": lines[:10]}
        st2 = C.ensure_measured(PROJ, few, pdir)
        res.append(("TOO-FEW", bool(st2) and "fewer than" in st2.get(
            "skipped", "") and not C.production_profile().is_measured,
                    (st2 or {}).get("skipped", "measured")))
    finally:
        C._PROFILES_PATH, C.production_voice_key = saved
        C._STALE_SAID.clear()
        shutil.rmtree(pdir, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)
    bad = 0
    for name, ok, msg in res:
        print(f'{"PASS" if ok else "FAIL"}  {name:<14} {msg}')
        bad += not ok
    print("-" * 60)
    print("test_voice_measure: all pass" if not bad else
          f"test_voice_measure: {bad} FAILURE(S)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
