"""Calibrate the recap-runtime share from the renders that actually shipped.

THE DEFECT. RECAP_RUNTIME_PCT_LO/HI were 15.0/20.0 with the derivation "the
human reference (Bad Genius) sits near 15%" - one film, and the band was then
drawn +-5 points around it by hand. The gate was a bare console.print with no
severity, so a draft 30% over the band shipped as a warning nobody had to act
on, and a rewrite brief to "pay for dwell by cutting connective tissue" came
back 1,200 words longer with nothing to stop it.

BASIS, which is the whole difficulty. Two different numbers are both called
"the recap's runtime":

  DRAFT basis    words / WPM. What the draft gate can see before anything is
                 synthesized. Ignores holds, the intro, music tails and the
                 gaps between lines, so it UNDER-states the finished video.
  RENDER basis   the measured duration of final.mp4. What the viewer gets.

A band calibrated on one basis and enforced on the other is the mistake this
whole series keeps making, so this tool measures BOTH for every shipped render
and reports the conversion between them. The draft-stage gate is converted to
the draft basis by the measured factor; the render-stage gate uses the render
basis directly.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config                                            # noqa: E402

OUT = os.path.join(ROOT, "config", "runtime_control.json")


def _film_seconds(pdir: str) -> float | None:
    """Source film duration.

    transcript.json carries its own `duration`; prefer it over the last
    segment's end, which stops short whenever the film ends on silence.
    """
    p = os.path.join(pdir, "transcript.json")
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8-sig") as fh:
            t = json.load(fh)
    except Exception:
        return None
    if isinstance(t, dict) and t.get("duration"):
        return float(t["duration"])
    segs = (t.get("segments") if isinstance(t, dict) else t) or []
    try:
        return max(float(s.get("end") or 0) for s in segs) or None
    except Exception:
        return None


def _probe_seconds(path: str) -> float | None:
    """Measured duration, read off the VIDEO STREAM.

    pipeline.probe exists precisely because the container header lies; use it
    rather than reimplementing a header read here.
    """
    try:
        from pathlib import Path as _P
        from pipeline.probe import streams
        s = streams(_P(path))
        v = (s.get("video") or {}).get("duration")
        return float(v) if v else None
    except Exception:
        return None


def main() -> int:
    wpm = float(getattr(config, "TTS_WORDS_PER_MINUTE", 210) or 210)
    rows = []
    pbase = os.path.join(ROOT, "projects")
    for name in sorted(os.listdir(pbase)):
        if name.startswith("_"):
            continue
        pdir = os.path.join(pbase, name)
        final = os.path.join(pdir, "final.mp4")
        draft = os.path.join(pdir, "draft.json")
        if not os.path.exists(final) or not os.path.exists(draft):
            continue
        film = _film_seconds(pdir)
        fin = _probe_seconds(final)
        try:
            with open(draft, encoding="utf-8-sig") as fh:
                d = json.load(fh)
            words = sum(len(str(l.get("narration") or "").split())
                        for l in d.get("lines") or [])
        except Exception:
            d, words = {}, 0

        # Is draft.json the draft this final.mp4 was MADE from? If a project
        # has been redrafted since it rendered, pairing the two measures a
        # word count against an unrelated video - which is how the first run
        # of this tool reported a 0.772 factor for a project whose real
        # factor is 1.075, and 0.772 is outside every other render's range.
        # stale_audio already answers this from the TTS manifest's recorded
        # signatures, so ask it rather than eyeballing the outlier.
        paired = True
        why_unpaired = ""
        try:
            from pathlib import Path as _P
            from pipeline import preflight as _pf
            _nar = [l for l in d.get("lines") or []
                    if str(l.get("narration") or "").strip()]
            _st = _pf.stale_audio(d, _P(pdir))
            if _nar and len(_st) >= len(_nar) * 0.5:
                paired = False
                why_unpaired = (f"{len(_st)} of {len(_nar)} lines have audio "
                                f"that does not match their text - draft.json "
                                f"is not the draft this render was made from")
        except Exception:
            pass

        if not (film and fin and words):
            rows.append({"project": name, "film_sec": film, "final_sec": fin,
                         "words": words, "skipped": "missing a measurement"})
            continue
        est = words / wpm * 60.0
        rows.append({
            "project": name,
            "film_min": round(film / 60.0, 2),
            "final_min": round(fin / 60.0, 2),
            "words": words,
            "draft_est_min": round(est / 60.0, 2),
            "render_share": round(fin / film, 4),
            "draft_share": round(est / film, 4) if paired else None,
            "render_over_draft": round(fin / est, 3) if paired else None,
            "paired": paired,
            "why_unpaired": why_unpaired,
        })

    ok = [r for r in rows if r.get("render_share")]
    rs = sorted(r["render_share"] for r in ok)
    ds = sorted(r["draft_share"] for r in ok if r.get("draft_share"))
    conv = sorted(r["render_over_draft"] for r in ok
                  if r.get("render_over_draft"))
    # WHICH STATISTIC IS USABLE. The band has to be drawn on whichever of
    # these two actually holds still across the shipped renders; drawing it on
    # the looser one produces a bar so wide it rejects nothing. Spread =
    # max/min, the same test PACING_CALIBRATION used to throw out
    # lines_per_scene_mean.
    absmin = sorted(r["final_min"] for r in ok)

    def _spread(v: list) -> float | None:
        return round(v[-1] / v[0], 3) if v and v[0] else None

    def _outliers(v: list) -> tuple:
        """(kept, dropped) by the 1.5xIQR rule.

        The raw spreads are dominated by a single render half the length of
        every other, which makes BOTH statistics look equally loose (2.06x
        and 2.18x) and hides the fact that one of them is far tighter once
        that render is set aside. The exclusion is done by a stated rule
        rather than by eye, and the dropped values are recorded, because
        "excluding the outlier" with no rule and no record is just picking
        the numbers that suit the bar.
        """
        if len(v) < 4:
            return list(v), []
        q1 = v[int(0.25 * (len(v) - 1))]
        q3 = v[int(0.75 * (len(v) - 1))]
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        return ([x for x in v if lo <= x <= hi],
                [x for x in v if not lo <= x <= hi])
    out = {
        "wpm_basis": wpm,
        "basis_note": ("render_share = measured final.mp4 / film. "
                       "draft_share = (words/WPM) / film, which is what the "
                       "draft gate can see. render_over_draft is the measured "
                       "factor between them - the draft bar must be the "
                       "render bar divided by this, never the same number."),
        "renders": rows,
        "render_share": {"n": len(rs), "values": rs,
                         "min": rs[0] if rs else None,
                         "median": rs[len(rs) // 2] if rs else None,
                         "max": rs[-1] if rs else None},
        "draft_share": {"values": ds,
                        "min": ds[0] if ds else None,
                        "median": ds[len(ds) // 2] if ds else None,
                        "max": ds[-1] if ds else None},
        "render_over_draft": {"values": conv,
                              "median": conv[len(conv) // 2] if conv else None},
        "absolute_minutes": {"values": absmin,
                             "min": absmin[0] if absmin else None,
                             "median": (absmin[len(absmin) // 2]
                                        if absmin else None),
                             "max": absmin[-1] if absmin else None},
        "which_statistic": {
            "absolute_minutes_spread": _spread(absmin),
            "render_share_spread": _spread(rs),
            "film_min_spread": _spread(sorted(r["film_min"] for r in ok)),
            # The pair the bars are actually argued from. Reported next to
            # the raw pair, never instead of it.
            "iqr_rule": "1.5xIQR",
            "absolute_minutes_kept": _outliers(absmin)[0],
            "absolute_minutes_dropped": _outliers(absmin)[1],
            "absolute_minutes_spread_filtered": _spread(_outliers(absmin)[0]),
            "render_share_spread_filtered": _spread(_outliers(rs)[0]),
            "render_share_dropped": _outliers(rs)[1],
            "note": ("the band belongs on whichever spread is TIGHTER. If "
                     "absolute runtime holds still while the share moves, the "
                     "format's real constraint is the viewer's attention, not "
                     "the film's length, and a share-based bar wide enough to "
                     "contain every shipped render rejects nothing."),
        },
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

    print(f"{'project':26} {'film':>7} {'final':>7} {'words':>6} "
          f"{'est':>6} {'render%':>8} {'draft%':>7} {'fin/est':>7}")
    for r in rows:
        if r.get("skipped"):
            print(f"{r['project'][:26]:26} SKIPPED - {r['skipped']}")
            continue
        _d = (f"{100*r['draft_share']:6.1f}%" if r.get("draft_share")
              else "     -")
        _c = (f"{r['render_over_draft']:7.3f}" if r.get("render_over_draft")
              else "      -")
        print(f"{r['project'][:26]:26} {r['film_min']:7.1f} "
              f"{r['final_min']:7.1f} {r['words']:6d} {r['draft_est_min']:6.1f} "
              f"{100*r['render_share']:7.1f}% {_d} {_c}")
        if not r.get("paired"):
            print(f"{'':26} draft basis EXCLUDED: {r['why_unpaired']}")
    if rs:
        print(f"\nabsolute minutes: {absmin}")
        print(f"  spread  absolute {_spread(absmin)}x   share "
              f"{_spread(rs)}x   (film length varies "
              f"{_spread(sorted(r['film_min'] for r in ok))}x)")
        print(f"\nrender share:  min {100*rs[0]:.1f}%  median "
              f"{100*rs[len(rs)//2]:.1f}%  max {100*rs[-1]:.1f}%")
        print(f"draft  share:  min {100*ds[0]:.1f}%  median "
              f"{100*ds[len(ds)//2]:.1f}%  max {100*ds[-1]:.1f}%")
        print(f"final/estimate factor: {conv}  median "
              f"{conv[len(conv)//2]:.3f}")
    print(f"written: {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
