"""Find the speaking_rate that makes the voice MEASURE at config.TARGET_WPM.

WHY THIS TOOL EXISTS
--------------------
The delivery mapping was flattened to one mode and one rate so the narrator
would stop sounding like three people. That fixed consistency and silently cost
a third of the pace: every tag gained a steering cue, and a cue costs roughly
20% of pace whatever it says. Measured before: `normal` at speaking_rate 1.02
with NO cue read 188.3 WPM. After: the same rate WITH a cue read 150.2 WPM.

The wrong response is to re-budget the writer down to the slower voice, which
is what happened - 185 WPM became 141 and every word budget shrank by a third.
The right response is to raise the base rate until the voice MEASURES at the
target, keeping the uniform mapping.

That requires synthesis, because steering is a request to a model and the
relationship between speaking_rate and delivered WPM is not linear - it cannot
be computed. So this tool synthesizes REAL draft lines at candidate rates and
measures what comes back.

    python tools/calibrate_rate.py --project NAME                 # measure current
    python tools/calibrate_rate.py --project NAME --rates 1.25,1.35,1.45
    python tools/calibrate_rate.py --project NAME --solve         # converge on TARGET_WPM

Costs money (Inworld bills per character). A 16-line sample is about 2,500
characters per candidate rate, so roughly $0.06 each at the On-Demand rate.
Audio goes to a scratch directory and never touches the project's narration
cache, so a test rate cannot contaminate a render.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import statistics as st
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402
from rich.console import Console  # noqa: E402

console = Console()

# Lines per tag in the sample. Enough to average out one odd reading without
# paying for the whole draft.
PER_TAG = 2
MIN_WORDS = 8


def _sample(project: str, per_tag: int = PER_TAG) -> list[dict]:
    """A spread of real draft lines: `per_tag` of each delivery tag."""
    pdir = Path(config.project_dir(project))
    d = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    by_tag: dict = {}
    for ln in d.get("lines") or []:
        if (ln.get("narration_silence_seconds") is not None
                or ln.get("film_speaks_seconds") is not None):
            continue
        txt = str(ln.get("narration") or "").strip()
        if len(txt.split()) < MIN_WORDS:
            continue
        tag = str(ln.get("delivery") or "normal")
        by_tag.setdefault(tag, []).append({"id": ln["id"], "tag": tag,
                                           "text": txt})
    out = []
    for tag in sorted(by_tag):
        # take the MEDIAN-length lines, not the extremes: a 4-word line and a
        # 60-word line both measure badly for different reasons
        rows = sorted(by_tag[tag], key=lambda r: len(r["text"].split()))
        mid = len(rows) // 2
        lo = max(0, mid - per_tag // 2)
        out.extend(rows[lo:lo + per_tag])
    return out


def measure_rate(project: str, speaking_rate: float,
                 sample: list | None = None) -> dict:
    """Synthesize the sample at `speaking_rate` and measure WPM per tag.

    Returns {wpm, wpm_by_tag, spread, rows}. `spread` is max/min of the per-tag
    means - the voice-consistency number.
    """
    from pipeline.tts_providers import all_providers, synthesize_cached
    from pipeline.tts import DEFAULT_PROVIDER
    from pipeline.preflight import _audio_dur

    prov = all_providers()[DEFAULT_PROVIDER]
    ok, why = prov.available()
    if not ok:
        raise RuntimeError(f"cannot synthesize: {why}")
    rows = sample if sample is not None else _sample(project)
    if not rows:
        raise RuntimeError("no usable sample lines in the draft")

    # Override the one rate every tag shares, for this measurement only.
    saved = {t: dict(prov.delivery[t]) for t in prov.delivery}
    for t in prov.delivery:
        prov.delivery[t]["speaking_rate"] = round(float(speaking_rate), 4)

    scratch = Path(tempfile.mkdtemp(prefix=f"rate_{speaking_rate:.3f}_"))
    ffp = config.ffprobe()
    try:
        got = []
        for i, r in enumerate(rows, 1):
            out = scratch / f"s{i:02d}.mp3"
            try:
                _cached, dur = synthesize_cached(
                    prov, r["text"], r["tag"], out, scratch)
            except Exception as e:
                console.print(f"[yellow]  line {r['id']} ({r['tag']}) failed: "
                              f"{e}[/]")
                continue
            if dur <= 0:
                dur = _audio_dur(ffp, out)
            if dur <= 0.2:
                continue
            w = len(r["text"].split())
            got.append({"id": r["id"], "tag": r["tag"], "words": w,
                        "sec": dur, "wpm": 60.0 * w / dur})
        if not got:
            raise RuntimeError("every sample line failed to synthesize")
        by_tag: dict = {}
        for g in got:
            by_tag.setdefault(g["tag"], []).append(g["wpm"])
        wpm_by_tag = {t: st.mean(v) for t, v in sorted(by_tag.items())}
        agg = 60.0 * sum(g["words"] for g in got) / sum(g["sec"] for g in got)
        spread = (max(wpm_by_tag.values()) / min(wpm_by_tag.values())
                  if len(wpm_by_tag) > 1 else 1.0)
        return {"speaking_rate": float(speaking_rate), "wpm": agg,
                "wpm_by_tag": wpm_by_tag, "spread": spread, "rows": got,
                "n": len(got)}
    finally:
        for t, v in saved.items():
            prov.delivery[t] = v
        shutil.rmtree(scratch, ignore_errors=True)


def _report(res: dict) -> None:
    target = float(getattr(config, "TARGET_WPM", 185.0))
    band = float(getattr(config, "VOICE_RATE_BAND", 0.10))
    console.print(
        f"[cyan]speaking_rate {res['speaking_rate']:.3f}[/] -> "
        f"[bold]{res['wpm']:.1f} WPM[/] on {res['n']} line(s)  "
        f"(target {target:.0f}, "
        f"{100.0 * (res['wpm'] / target - 1.0):+.1f}%)")
    mean = res["wpm"]
    for t, v in sorted(res["wpm_by_tag"].items(), key=lambda kv: kv[1]):
        dev = v / mean - 1.0
        flag = "" if abs(dev) <= band else "   <-- outside the band"
        console.print(f"[dim]    {t:<8} {v:6.1f} WPM  {dev:+6.1%}{flag}[/]")
    console.print(f"[dim]    tag spread {res['spread']:.2f}x "
                  f"(ceiling {config.VOICE_WPM_RATIO_MAX:.2f}x)[/]")


def measure_tag(project: str, tag: str, rate: float, rows: list) -> float:
    """Measured WPM for ONE tag at ONE rate, on that tag's own sample lines."""
    from pipeline.tts_providers import all_providers, synthesize_cached
    from pipeline.tts import DEFAULT_PROVIDER
    from pipeline.preflight import _audio_dur
    prov = all_providers()[DEFAULT_PROVIDER]
    saved = dict(prov.delivery[tag])
    prov.delivery[tag] = dict(saved, speaking_rate=round(float(rate), 4))
    scratch = Path(tempfile.mkdtemp(prefix=f"tag_{tag}_"))
    ffp = config.ffprobe()
    try:
        tw = ts = 0.0
        for i, r in enumerate(rows):
            out = scratch / f"{i}.mp3"
            try:
                _c, dur = synthesize_cached(prov, r["text"], tag, out, scratch)
            except Exception as e:
                console.print(f"[yellow]    {tag} line {r['id']}: {e}[/]")
                continue
            if dur <= 0:
                dur = _audio_dur(ffp, out)
            if dur <= 0.2:
                continue
            tw += len(r["text"].split())
            ts += dur
        return (60.0 * tw / ts) if ts else 0.0
    finally:
        prov.delivery[tag] = saved
        shutil.rmtree(scratch, ignore_errors=True)


def _solve_per_tag(a, sample: list, target: float) -> int:
    """Per-tag rate that makes every tag DELIVER target WPM.

    Secant per tag, clamped to the engine's hard [0.5, VOICE_SPEAKING_RATE_MAX]
    range. A tag that cannot reach the target inside that range is REPORTED as
    such rather than quietly left short - that is the information that tells
    you the CUE is too expensive, which is how the pause-led cues were caught.
    """
    cap = float(getattr(config, "VOICE_SPEAKING_RATE_MAX", 1.5))
    base = float(config.VOICE_BASE_SPEAKING_RATE)
    by_tag: dict = {}
    for r in sample:
        by_tag.setdefault(r["tag"], []).append(r)

    solved: dict = {}
    stuck: list = []
    for tag in sorted(by_tag):
        rows = by_tag[tag]
        r1 = base
        w1 = measure_tag(a.project, tag, r1, rows)
        if not w1:
            console.print(f"[red]{tag}: could not measure[/]")
            continue
        best = (r1, w1)
        for _ in range(3):
            if abs(w1 / target - 1.0) <= 0.03:
                break
            guess = max(0.5, min(cap, r1 * target / w1))
            if abs(guess - r1) < 0.004:
                break
            w2 = measure_tag(a.project, tag, guess, rows)
            if not w2:
                break
            if abs(w2 / target - 1.0) < abs(best[1] / target - 1.0):
                best = (guess, w2)
            r1, w1 = guess, w2
        solved[tag] = round(best[0], 3)
        dev = best[1] / target - 1.0
        flag = ""
        if best[0] >= cap - 1e-6 and best[1] < target * 0.9:
            stuck.append(tag)
            flag = f"   <-- AT THE {cap:.2f} ENGINE CAP and still short"
        console.print(f"[cyan]{tag:<8}[/] rate {best[0]:.3f} -> "
                      f"{best[1]:6.1f} WPM  {dev:+6.1%}{flag}")

    console.print()
    console.print("VOICE_TAG_SPEAKING_RATE = " + json.dumps(solved, indent=4))
    if stuck:
        console.print(f"[red]{stuck} cannot reach {target:.0f} WPM inside the "
                      f"{cap:.2f} engine cap - their CUE is too expensive. "
                      f"Make it ask for less (a pause instruction costs ~27% "
                      f"of pace) rather than accepting the shortfall.[/]")
    if a.write:
        p = Path(ROOT) / "config.py"
        s = p.read_text(encoding="utf-8")
        import re
        new = "VOICE_TAG_SPEAKING_RATE: dict = " + json.dumps(solved, indent=4)
        s2 = re.sub(r"VOICE_TAG_SPEAKING_RATE: dict = \{[^}]*\}", new, s,
                    count=1, flags=re.S)
        if s2 == s:
            console.print("[red]Could not find VOICE_TAG_SPEAKING_RATE[/]")
            return 1
        p.write_text(s2, encoding="utf-8")
        console.print("[green]Wrote VOICE_TAG_SPEAKING_RATE to config.py[/]")
    return 0


def write_profile(project: str, per_tag: int = 3) -> dict:
    """Synthesize a sample at the LIVE mapping and write the voice profile.

    Closes a chicken-and-egg: [VOICE-RATE-DRIFT] refuses to render without a
    valid measurement, a mapping change voids the measurement on purpose, and
    the full-draft measurement needs a render to exist first. So the profile is
    seeded here from a dedicated sample at the live mapping - same code path,
    same provider, same cache signature - and the next full render refines it
    from all 100-odd lines.
    """
    import datetime as _dt
    from pipeline import calibration as cal
    from pipeline.tts_providers import all_providers, synthesize_cached
    from pipeline.tts import DEFAULT_PROVIDER
    from pipeline.preflight import _audio_dur

    prov = all_providers()[DEFAULT_PROVIDER]
    rows = _sample(project, per_tag)
    scratch = Path(tempfile.mkdtemp(prefix="profile_"))
    ffp = config.ffprobe()
    try:
        per: dict = {}
        tw = ts = 0.0
        tsyl = 0
        for i, r in enumerate(rows):
            out = scratch / f"{i}.mp3"
            try:
                _c, dur = synthesize_cached(prov, r["text"], r["tag"], out,
                                            scratch)
            except Exception as e:
                console.print(f"[yellow]  {r['tag']} {r['id']}: {e}[/]")
                continue
            if dur <= 0:
                dur = _audio_dur(ffp, out)
            if dur <= 0.2:
                continue
            w = len(r["text"].split())
            per.setdefault(r["tag"], []).append((w, dur))
            tw += w
            ts += dur
            tsyl += sum(cal._count_syllables(x) for x in r["text"].split())
        if not ts:
            raise RuntimeError("nothing measurable was synthesized")

        by_tag = {}
        for tag, v in sorted(per.items()):
            each = [w / d for w, d in v]
            m = st.mean(each)
            sd = st.pstdev(each) if len(each) > 1 else 0.0
            by_tag[tag] = {
                "samples": len(v),
                "words_per_sec": round(sum(w for w, _ in v)
                                       / sum(d for _, d in v), 3),
                "words_per_sec_mean": round(m, 3),
                "words_per_sec_std": round(sd, 3),
                "words_per_sec_conservative": round(
                    (m - 1.0 * sd) if len(each) >= 5 else min(each), 3),
                "words_per_sec_slowest": round(min(each), 3),
            }
        agg = tw / ts
        allr = [w / d for v in per.values() for w, d in v]
        meta = {
            "voice_id": prov.voice_label or prov.voice,
            "rate_adjustment": "",
            "words_per_sec": round(agg, 3),
            "words_per_sec_conservative": round(
                st.mean(allr) - 0.5 * st.pstdev(allr), 3),
            "syllables_per_sec": round(tsyl / ts, 3),
            "by_tag": by_tag,
            "mapping_signature": cal.mapping_signature(),
            "pause_overhead_sec": 0.18,
            "measured_from": f"{project} (live-mapping sample)",
            "measured_samples": sum(len(v) for v in per.values()),
            "measured_total_words": int(tw),
            "measured_total_speaking_sec": round(ts, 1),
            "measured_utc": _dt.datetime.now(_dt.timezone.utc)
                               .strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        path = Path(ROOT) / "config" / "voice_profiles.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            blob = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            blob = {}
        blob.setdefault("profiles", {})
        blob["profiles"][cal.production_voice_key()] = meta
        path.write_text(json.dumps(blob, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        console.print(f"[green]Wrote the voice profile[/] - "
                      f"{meta['measured_samples']} sample(s), "
                      f"{agg * 60:.1f} WPM aggregate, "
                      f"{len(by_tag)} tag(s), signed with the current mapping")
        return meta
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--rates", default="",
                    help="comma-separated speaking_rate values to measure")
    ap.add_argument("--solve", action="store_true",
                    help="converge on config.TARGET_WPM and print the rate")
    ap.add_argument("--per-tag", type=int, default=PER_TAG)
    ap.add_argument("--write", action="store_true",
                    help="write the solved rate into config.py")
    ap.add_argument("--write-profile", action="store_true",
                    help="synthesize a sample at the LIVE mapping and write "
                         "config/voice_profiles.json, signed with the current "
                         "mapping. Seeds the profile that [VOICE-RATE-DRIFT] "
                         "requires after a mapping change.")
    ap.add_argument("--solve-per-tag", action="store_true",
                    help="solve a speaking_rate PER TAG so every tag DELIVERS "
                         "TARGET_WPM. The rates differ only to cancel each "
                         "cue's measured pace cost, so the delivered tempo is "
                         "uniform - the opposite of varying rates to create "
                         "different tempos.")
    a = ap.parse_args()

    target = float(getattr(config, "TARGET_WPM", 185.0))
    sample = _sample(a.project, a.per_tag)
    console.print(f"[cyan]Sample:[/] {len(sample)} line(s) across "
                  f"{len({r['tag'] for r in sample})} tag(s), "
                  f"{sum(len(r['text'].split()) for r in sample)} words")

    if a.rates:
        for rv in [float(x) for x in a.rates.split(",") if x.strip()]:
            _report(measure_rate(a.project, rv, sample))
        return 0

    if a.write_profile:
        write_profile(a.project, a.per_tag)
        return 0

    if a.solve_per_tag:
        return _solve_per_tag(a, sample, target)

    if not a.solve:
        _report(measure_rate(a.project, config.VOICE_BASE_SPEAKING_RATE,
                             sample))
        return 0

    # ---- solve ---------------------------------------------------------- #
    # Secant on (rate -> measured WPM). The relationship is monotone but not
    # linear, so it is measured rather than computed, and three or four probes
    # land inside a couple of percent.
    lo_r = float(config.VOICE_BASE_SPEAKING_RATE)
    first = measure_rate(a.project, lo_r, sample)
    _report(first)
    if abs(first["wpm"] / target - 1.0) <= 0.02:
        console.print("[green]Already on target.[/]")
        return 0
    # a first guess that assumes proportionality, then correct by measurement
    guess = max(0.5, min(1.8, lo_r * target / first["wpm"]))
    pts = [(lo_r, first["wpm"])]
    best = first
    for _ in range(4):
        res = measure_rate(a.project, round(guess, 3), sample)
        _report(res)
        pts.append((res["speaking_rate"], res["wpm"]))
        if abs(res["wpm"] / target - 1.0) < abs(best["wpm"] / target - 1.0):
            best = res
        if abs(res["wpm"] / target - 1.0) <= 0.02:
            break
        pts.sort()
        # secant through the two points nearest the target
        pts2 = sorted(pts, key=lambda p: abs(p[1] - target))[:2]
        (r1, w1), (r2, w2) = pts2
        if abs(w2 - w1) < 1e-6:
            break
        guess = r1 + (target - w1) * (r2 - r1) / (w2 - w1)
        guess = max(0.5, min(1.8, guess))

    console.print()
    console.print(f"[bold green]Best: speaking_rate "
                  f"{best['speaking_rate']:.3f} -> {best['wpm']:.1f} WPM[/] "
                  f"({100.0 * (best['wpm'] / target - 1.0):+.1f}% of target "
                  f"{target:.0f})")
    if a.write:
        p = Path(ROOT) / "config.py"
        s = p.read_text(encoding="utf-8")
        import re
        s2 = re.sub(r"VOICE_BASE_SPEAKING_RATE = [\d.]+",
                    f"VOICE_BASE_SPEAKING_RATE = {best['speaking_rate']:.3f}",
                    s, count=1)
        if s2 == s:
            console.print("[red]Could not find VOICE_BASE_SPEAKING_RATE[/]")
            return 1
        p.write_text(s2, encoding="utf-8")
        console.print(f"[green]Wrote VOICE_BASE_SPEAKING_RATE = "
                      f"{best['speaking_rate']:.3f} to config.py[/]")
        console.print("[yellow]Now re-synthesize and re-calibrate the profile: "
                      "the mapping changed, so every cached line is stale and "
                      "the measured profile is void.[/]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
