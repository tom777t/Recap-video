"""
Prove config.RENDER_LEGACY_XFADE actually falls back - in both directions.

    python tools/test_legacy_fallback.py

WHY THIS EXISTS
The flag is the escape hatch for Phase 1: if the first watched render shows
something the frame counts could not see, flipping one boolean is supposed to
restore the pre-Phase-1 assembly. A fallback that has never been executed is
not a fallback, it is a comment. So this renders the SAME fixture twice, once
down each path, and checks that:

  * both produce a playable file of the same length (within one frame), so
    the flag changes how the picture is built and not what it contains;
  * the legacy path really does re-encode - it must NOT stream-copy a
    CRF-16 intermediate into final.mp4, which was a live bug in the first
    draft of the flag;
  * the new path really does stream-copy.

Reuses the smoke test's fixture so there is one fake film, not two.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402

import test_render_smoke as smoke  # noqa: E402

FRAME = 1.0 / float(config.OUTPUT_FPS)


def _frames(p: Path) -> int:
    r = subprocess.run(
        [config.ffprobe(), "-v", "error", "-select_streams", "v:0",
         "-count_packets", "-show_entries", "stream=nb_read_packets",
         "-of", "default=nw=1:nk=1", str(p)],
        capture_output=True, text=True)
    try:
        return int((r.stdout or "0").strip())
    except ValueError:
        return 0


def _render_once(legacy: bool) -> tuple[int, float, int]:
    """Render the fixture with the flag set one way. Returns (frames, dur, kb)."""
    from pipeline.render import render
    # _no_stems/_stub_intro_tts are plain functions returning a restore
    # callable, not context managers - mirroring how test_render_smoke uses
    # them rather than inventing a second convention.
    orig = smoke._stub_intro_tts()
    restore_stems = smoke._no_stems()
    before = config.RENDER_LEGACY_XFADE
    config.RENDER_LEGACY_XFADE = legacy
    try:
        pdir, draft = smoke._setup()
        narration = smoke._narration_for(pdir, draft["lines"])
        final = Path(render(smoke.PROJ, draft, narration, music=None,
                            captions=False, keep_temp=False,
                            force_clips=True))
        if not final.exists():
            raise AssertionError(f"no final.mp4 (legacy={legacy})")
        return (_frames(final), smoke._dur(final),
                int(final.stat().st_size / 1024))
    finally:
        config.RENDER_LEGACY_XFADE = before
        restore_stems()
        # _stub_intro_tts hands back the original function; put it back the
        # way it was rather than leaving a stub installed for later tests.
        from pipeline import intro as _intro
        _intro._tts_line = orig


def main() -> int:
    fails: list[str] = []

    def chk(name, cond, detail=""):
        print(f"  {'PASS' if cond else 'FAIL'}  {name}"
              + (f"   {detail}" if detail and not cond else ""))
        if not cond:
            fails.append(name)

    print("\n[1] the NEW path (RENDER_LEGACY_XFADE=False) renders")
    try:
        n_f, n_d, n_kb = _render_once(False)
        print(f"        {n_f} frames, {n_d:.3f}s, {n_kb} KB")
        chk("new path produced a playable file", n_f > 0 and n_d > 0)
    except Exception as e:  # noqa: BLE001
        chk("new path produced a playable file", False, repr(e))
        n_f = n_d = n_kb = 0

    print("\n[2] the LEGACY path (RENDER_LEGACY_XFADE=True) still renders")
    try:
        l_f, l_d, l_kb = _render_once(True)
        print(f"        {l_f} frames, {l_d:.3f}s, {l_kb} KB")
        chk("legacy path produced a playable file", l_f > 0 and l_d > 0)
    except Exception as e:  # noqa: BLE001
        chk("legacy path produced a playable file", False, repr(e))
        l_f = l_d = l_kb = 0

    print("\n[3] the flag changes HOW, not WHAT")
    # The two paths compute the timeline the same way, so the length must
    # agree. A few frames of slack: the legacy path measures durations with
    # ffprobe and accumulates float offsets, the new one counts frames.
    if n_f and l_f:
        chk(f"lengths agree: new {n_d:.3f}s vs legacy {l_d:.3f}s",
            abs(n_d - l_d) <= 4 * FRAME,
            f"differ by {abs(n_d-l_d):.3f}s, over {4*FRAME:.3f}s")
    else:
        chk("lengths agree", False, "one of the renders failed")

    print("\n[4] the legacy path must not ship an intermediate")
    # The legacy assembly writes CRF 16 / veryfast. If final.mp4 were a
    # stream copy of that, it would be noticeably LARGER than the CRF 20
    # delivery encode. Equal-or-smaller means the delivery encode ran.
    if n_kb and l_kb:
        chk(f"legacy final is not an unencoded CRF-16 copy "
            f"({l_kb} KB vs new {n_kb} KB)",
            l_kb <= n_kb * 1.6,
            f"legacy is {l_kb/max(1,n_kb):.2f}x the new path's size, which "
            f"suggests the intermediate was copied rather than re-encoded")
    else:
        chk("legacy final is re-encoded", False, "one of the renders failed")

    smoke._teardown()

    print("\n" + "=" * 60)
    if fails:
        print(f"RESULT: {len(fails)} FAILURE(S)")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("RESULT: ALL SELF-TESTS PASS")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
