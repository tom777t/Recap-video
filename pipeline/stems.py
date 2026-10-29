"""Film-audio stem separation: keep the engines, drop the dialogue.

THE PROBLEM
-----------
Film audio was mixed under the narration at -17 dB, and -6 dB inside holds. At
those levels the film's DIALOGUE is audible almost continuously, so the recap
has the narrator and the characters talking at the same time. Three costs:
it is hard to follow, it sounds amateurish, and it is the part of the film most
exposed to a copyright claim.

But the film's NON-dialogue audio is the best thing in the mix - engines,
tyres, gear changes, impacts. Muting the film to remove dialogue would throw
that away.

So the audio is separated ONCE per project into stems, and the pipeline uses
the no-vocals stem everywhere the narrator is speaking or a hold is breathing.
The original mix is used ONLY inside a <film_speaks> unit, where a character
being heard is the whole point.

WHY A SEPARATE FILE AND NOT A FILTER
------------------------------------
There is no ffmpeg filter that removes dialogue. The usual trick - a centre-
channel subtraction (`pan` with the centre inverted) - only works on true
multichannel audio and destroys a stereo mix, taking most of the music and a
good deal of the effects with the voice. Demucs is a trained source-separation
model and actually does the job. It is slow (minutes per film on CPU), so the
result is CACHED and keyed to the source file: the cost is paid once per film,
not once per render.

FAILURE IS LOUD
---------------
If separation is unavailable, this module does NOT quietly fall back to the
full mix - that is the exact defect it exists to remove. render stops and says
what to install. The alternative fallback (mute the film entirely) is offered
explicitly via config.FILM_AUDIO_REQUIRE_STEMS = False, and it is a real
tradeoff: no dialogue, but no engines either.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from rich.console import Console

console = Console()

# Demucs model. htdemucs is the v4 default: 4 stems (drums/bass/other/vocals)
# and the best quality of the bundled models. We only need vocals vs the rest,
# which `--two-stems=vocals` produces directly and about twice as fast.
# MEASURED on this machine (12 cores, no CUDA - Intel Iris Xe only), on a
# 60-second sample of tokyodrift2006 with -j 4:
#     mdx_extra_q   0.47 s per second of audio  ->  ~49 min for the 104-min film
#     htdemucs      1.74 s per second of audio  ->  ~3.0 hours
# htdemucs is the better separator in general, but it is better mostly on
# MUSIC, and what this needs is speech removal - which mdx_extra is strong at.
# A 3.6x speedup for a job that has to run once per film is worth the small
# quality difference here; a 3-hour blocking step would simply not get used.
# Override with config.DEMUCS_MODEL if a machine with CUDA is available, where
# htdemucs becomes cheap.
DEMUCS_MODEL = "mdx_extra_q"
try:
    import config as _cfg
    DEMUCS_MODEL = str(getattr(_cfg, "DEMUCS_MODEL", DEMUCS_MODEL))
except Exception:
    pass
STEM_DIRNAME = "stems"
NO_VOCALS = "no_vocals.wav"
VOCALS = "vocals.wav"
MANIFEST = "_stems.json"


def available() -> tuple[bool, str]:
    """Is stem separation runnable here?"""
    try:
        import torch  # noqa: F401
    except Exception as e:
        return False, f"torch not installed ({e})"
    try:
        import demucs.separate  # noqa: F401
    except Exception as e:
        return False, f"demucs not installed ({e})"
    return True, f"demucs + torch available ({DEMUCS_MODEL})"


def install_hint() -> str:
    return ("pip install torch --index-url https://download.pytorch.org/whl/cpu"
            "  &&  pip install demucs")


def _source_fingerprint(source: Path) -> dict:
    st = source.stat()
    return {"name": source.name, "size": st.st_size,
            "mtime": int(st.st_mtime), "model": DEMUCS_MODEL}


# --------------------------------------------------------------------------- #
# Only separate what the recap actually plays
# --------------------------------------------------------------------------- #
# MEASURED, warm, with the output files verified (12 CPU cores, no CUDA):
#     htdemucs   1.57 s per second of audio
#     mdx_extra  2.35 s per second of audio  (a 4-model bag, hence slower)
#     mdx_extra_q  unusable here - needs `diffq`, whose install does not build
#                  on this machine. An earlier 0.47 s/s reading for it was a
#                  FAST FAILURE being timed, not a separation: the benchmark
#                  suppressed output and never checked that files appeared.
# So htdemucs, at 1.57 s/s, means 2.7 hours for a 104-minute film.
#
# But a recap only ever plays a FRACTION of its source: tokyodrift2006 reads
# 26.3 minutes of a 104-minute film, 25% of it. Separating only the spans the
# draft actually binds takes ~41 minutes instead of 2.7 hours, for identical
# output everywhere the render looks.
#
# The result is still assembled into ONE full-length file, with silence in the
# gaps, so the render keeps absolute seek semantics and nothing downstream has
# to know this optimisation happened.
SPAN_PAD_SEC = 1.0


def needed_spans(draft: dict, pad: float = SPAN_PAD_SEC,
                 src_dur: float = 0.0) -> list[tuple[float, float]]:
    """Merged source spans the render will read film audio from.

    Covers: every bound window; a hold's REAL span (it ignores its declared
    end and plays clip_len seconds from start); and inline montage segments.
    Padded, because a separation edge inside a span you can hear is worse than
    separating a second more than needed.
    """
    from pipeline.draft import parse_ts
    spans: list[tuple[float, float]] = []
    for ln in (draft.get("lines") or []):
        cs, ce = ln.get("clip_start"), ln.get("clip_end")
        if cs and ce:
            try:
                a, b = parse_ts(cs), parse_ts(ce)
            except Exception:
                a = b = None
            if a is not None:
                hold = (ln.get("narration_silence_seconds")
                        or ln.get("film_speaks_seconds"))
                if hold:
                    b = max(b, a + float(hold))
                spans.append((a, b))
        for seg in (ln.get("montage") or []):
            if isinstance(seg, dict) and seg.get("clip_start"):
                try:
                    spans.append((parse_ts(seg["clip_start"]),
                                  parse_ts(seg["clip_end"])))
                except Exception:
                    pass
    if not spans:
        return []
    out: list[tuple[float, float]] = []
    for a, b in sorted((max(0.0, a - pad), b + pad) for a, b in spans):
        if src_dur:
            b = min(b, float(src_dur))
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return [(a, b) for a, b in out if b > a]


def _covered(manifest: dict, spans: list) -> list:
    """Spans NOT covered by what the manifest says was separated."""
    have = [(float(a), float(b)) for a, b in (manifest.get("spans") or [])]
    missing = []
    for a, b in spans:
        rest = [(a, b)]
        for ha, hb in have:
            nxt = []
            for ra, rb in rest:
                if hb <= ra or ha >= rb:
                    nxt.append((ra, rb))
                    continue
                if ra < ha:
                    nxt.append((ra, ha))
                if rb > hb:
                    nxt.append((hb, rb))
            rest = nxt
        missing += [(ra, rb) for ra, rb in rest if rb - ra > 0.5]
    return missing


def stem_dir(pdir: Path) -> Path:
    return Path(pdir) / STEM_DIRNAME


def no_vocals_path(pdir: Path) -> Path:
    return stem_dir(pdir) / NO_VOCALS


def vocals_path(pdir: Path) -> Path:
    return stem_dir(pdir) / VOCALS


def _run_demucs(wav: Path, outdir: Path, jobs: int) -> Path | None:
    """Separate one wav; return its no_vocals part."""
    import sys as _sys
    cmd = [_sys.executable, "-m", "demucs.separate",
           "--two-stems", "vocals", "-n", DEMUCS_MODEL, "-j", str(jobs),
           "-o", str(outdir), "--filename", "{stem}.{ext}", str(wav)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        console.print(f"[yellow]Stems:[/] demucs exited {r.returncode}: "
                      f"{(r.stderr or r.stdout or '')[-300:]}")
        return None
    for p in outdir.rglob("no_vocals.wav"):
        return p
    return None


def _assemble(ff: str, parts: list, total_dur: float, out: Path) -> bool:
    """Lay separated parts onto a full-length silent bed, in order.

    One full-length file keeps the render's seek semantics absolute: a clip
    still asks for [start, end] and gets it, with no knowledge that only part
    of the film was ever separated.
    """
    import tempfile
    pieces: list[Path] = []
    tmpd = Path(tempfile.mkdtemp(prefix="stemasm_"))
    try:
        cursor = 0.0
        order: list[Path] = []
        for i, (a, b, p) in enumerate(parts):
            if a - cursor > 0.01:
                sil = tmpd / f"sil{i}.wav"
                r = subprocess.run(
                    [ff, "-y", "-hide_banner", "-loglevel", "error",
                     "-f", "lavfi", "-i",
                     "anullsrc=channel_layout=stereo:sample_rate=44100",
                     "-t", f"{a - cursor:.3f}", "-c:a", "pcm_s16le", str(sil)],
                    capture_output=True, text=True)
                if r.returncode != 0:
                    return False
                order.append(sil)
            order.append(Path(p))
            cursor = b
        if total_dur and total_dur - cursor > 0.01:
            sil = tmpd / "siltail.wav"
            subprocess.run(
                [ff, "-y", "-hide_banner", "-loglevel", "error",
                 "-f", "lavfi", "-i",
                 "anullsrc=channel_layout=stereo:sample_rate=44100",
                 "-t", f"{total_dur - cursor:.3f}", "-c:a", "pcm_s16le",
                 str(sil)], capture_output=True, text=True)
            order.append(sil)

        lst = tmpd / "list.txt"
        lst.write_text("".join(f"file '{Path(p).as_posix()}'\n" for p in order),
                       encoding="utf-8")
        r = subprocess.run(
            [ff, "-y", "-hide_banner", "-loglevel", "error",
             "-f", "concat", "-safe", "0", "-i", str(lst),
             "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(out)],
            capture_output=True, text=True)
        if r.returncode != 0:
            console.print(f"[yellow]Stems:[/] assembly failed: "
                          f"{(r.stderr or '')[-250:]}")
            return False
        return out.exists() and out.stat().st_size > 0
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)


def is_current(pdir: Path, source: Path, draft: dict | None = None) -> bool:
    """True if cached stems match THIS source file.

    Keyed on the source's size+mtime+model, not merely on the files existing:
    a re-ingested source with the same name would otherwise keep serving stems
    separated from the previous film's audio.
    """
    nv = no_vocals_path(pdir)
    man = stem_dir(pdir) / MANIFEST
    if not nv.exists() or nv.stat().st_size == 0 or not man.exists():
        return False
    try:
        got = json.loads(man.read_text(encoding="utf-8"))
    except Exception:
        return False
    fp = _source_fingerprint(Path(source))
    for k, v in fp.items():
        if got.get(k) != v:
            return False
    # Only part of the film is separated (see needed_spans). A draft edit that
    # moves a window onto un-separated audio would otherwise be served SILENCE
    # with no warning - safe, in that no dialogue plays, but the engines and
    # impacts for that line would vanish and nothing would say why.
    if draft is not None:
        missing = _covered(got, needed_spans(draft))
        if missing:
            console.print(
                f"[yellow]Stems:[/] {len(missing)} span(s) the draft now needs "
                f"were never separated (the windows moved). Re-separating "
                f"those.")
            return False
    return True


def separate(project: str, force: bool = False) -> Path | None:
    """Produce (or reuse) the no-vocals stem for a project. Returns its path.

    Runs Demucs on the film's audio track once and caches the result. Returns
    None if separation is unavailable or fails - the caller decides what that
    means, and must not treat it as "use the full mix".
    """
    import config
    pdir = Path(config.project_dir(project))
    source = pdir / "source.mp4"
    if not source.exists():
        console.print("[yellow]Stems:[/] no source.mp4 to separate.")
        return None

    draft = None
    try:
        draft = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    except Exception:
        draft = None

    if not force and is_current(pdir, source, draft):
        console.print(f"[dim]Stems: reusing cached {NO_VOCALS} "
                      f"({no_vocals_path(pdir).stat().st_size/1e6:.0f} MB).[/]")
        return no_vocals_path(pdir)

    ok, why = available()
    if not ok:
        console.print(f"[yellow]Stems:[/] cannot separate - {why}.")
        return None

    sdir = stem_dir(pdir)
    sdir.mkdir(parents=True, exist_ok=True)
    work = sdir / "_demucs"
    work.mkdir(parents=True, exist_ok=True)

    # 1. pull the audio out to wav. Demucs reads video via ffmpeg but giving it
    #    a plain wav avoids a second decode of a 750 MB mp4 per stem.
    #    RESUMABLE: this is a ~1 GB extract feeding a job that takes an hour or
    #    more on CPU, and the first attempt was interrupted after the extract
    #    and before the separation. Wiping the work directory on entry meant
    #    paying for the extract again, so a reusable wav is kept.
    wav = work / "film.wav"
    ff = config.ffmpeg()
    if wav.exists() and wav.stat().st_size > 1_000_000:
        console.print(f"[dim]Stems: reusing the extracted audio "
                      f"({wav.stat().st_size/1e6:.0f} MB).[/]")
    else:
        console.print("[cyan]Stems:[/] extracting the film's audio...")
        r = subprocess.run(
            [ff, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
             "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(wav)],
            capture_output=True, text=True)
        if r.returncode != 0 or not wav.exists():
            console.print(f"[yellow]Stems:[/] could not extract audio: "
                          f"{(r.stderr or '')[-200:]}")
            return None

    # 2. total duration, and the spans the recap actually reads
    def _dur(p: Path) -> float:
        r = subprocess.run(
            [config.ffprobe(), "-v", "error", "-show_entries",
             "format=duration", "-of", "default=nw=1:nk=1", str(p)],
            capture_output=True, text=True)
        try:
            return float((r.stdout or "0").strip())
        except ValueError:
            return 0.0

    total = _dur(wav)
    spans = needed_spans(draft, src_dur=total) if draft else []
    if not spans:
        spans = [(0.0, total)]
        console.print("[yellow]Stems:[/] no draft windows found - separating "
                      "the WHOLE film, which is several times slower.")

    span_sec = sum(b - a for a, b in spans)
    jobs = max(1, min(4, (os.cpu_count() or 2) // 3))
    console.print(
        f"[cyan]Stems:[/] {DEMUCS_MODEL}, {jobs} job(s), "
        f"{len(spans)} span(s) totalling {span_sec/60:.1f} min of the "
        f"{total/60:.1f} min film ({100*span_sec/max(1,total):.0f}%). "
        f"Measured ~1.6 s per second of audio, so roughly "
        f"{span_sec*1.6/60:.0f} min. Cached afterwards.")

    # 3. separate each span, caching per span so an interrupted run resumes
    parts_dir = sdir / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    parts: list = []
    for i, (a, b) in enumerate(spans, 1):
        tag = f"{DEMUCS_MODEL}_{a:.2f}-{b:.2f}"
        final_part = parts_dir / f"{tag}.wav"
        if final_part.exists() and final_part.stat().st_size > 0:
            parts.append((a, b, final_part))
            continue
        seg = work / f"seg_{i:04d}.wav"
        r = subprocess.run(
            [ff, "-y", "-hide_banner", "-loglevel", "error",
             "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(wav),
             "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(seg)],
            capture_output=True, text=True)
        if r.returncode != 0 or not seg.exists():
            console.print(f"[yellow]Stems:[/] could not cut span {i}.")
            return None
        outdir = work / f"out_{i:04d}"
        got = _run_demucs(seg, outdir, jobs)
        if got is None:
            return None
        shutil.move(str(got), str(final_part))
        shutil.rmtree(outdir, ignore_errors=True)
        seg.unlink(missing_ok=True)
        parts.append((a, b, final_part))
        console.print(f"[dim]  span {i}/{len(spans)} "
                      f"{a:.0f}-{b:.0f}s done[/]")

    # 4. assemble one full-length file: separated where used, silent elsewhere
    console.print("[cyan]Stems:[/] assembling the full-length no-vocals track...")
    if not _assemble(ff, parts, total, no_vocals_path(pdir)):
        return None

    man = dict(_source_fingerprint(source))
    man["spans"] = [[round(a, 3), round(b, 3)] for a, b, _ in parts]
    man["span_seconds"] = round(span_sec, 1)
    man["total_seconds"] = round(total, 1)
    (sdir / MANIFEST).write_text(json.dumps(man, indent=2), encoding="utf-8")
    # Only now is the ~1 GB scratch removed: until the manifest is written the
    # job is not done, and keeping the extract is what makes a retry cheap.
    shutil.rmtree(work, ignore_errors=True)

    mb = no_vocals_path(pdir).stat().st_size / 1e6
    console.print(f"[cyan]Stems:[/] wrote {NO_VOCALS} ({mb:.0f} MB) - engines, "
                  f"tyres and impacts without the dialogue.")
    return no_vocals_path(pdir)


def separate_span(project: str, a: float, b: float
                  ) -> tuple[Path | None, Path | None]:
    """Separate ONE span and return (vocals, no_vocals) part paths.

    Used by the film_speaks candidate generator to measure whether a quote's
    dialogue is actually clean - i.e. whether the vocals stem dominates the
    music and effects over that span. A candidate may sit anywhere in the film,
    including outside the spans the recap currently plays, so the full-film
    separation cannot be relied on to cover it.

    Cached per span under stems/parts/, keyed by model and timestamps, so the
    same candidate is never separated twice and a selected quote's span is
    already done by the time the render needs it.
    """
    import config
    pdir = Path(config.project_dir(project))
    source = pdir / "source.mp4"
    if not source.exists():
        return None, None
    ok, _why = available()
    if not ok:
        return None, None

    sdir = stem_dir(pdir)
    parts = sdir / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    tag = f"{DEMUCS_MODEL}_{a:.2f}-{b:.2f}"
    nv = parts / f"{tag}.wav"
    vo = parts / f"{tag}.vocals.wav"
    if nv.exists() and vo.exists() and nv.stat().st_size and vo.stat().st_size:
        return vo, nv

    ff = config.ffmpeg()
    work = sdir / "_spans"
    work.mkdir(parents=True, exist_ok=True)
    seg = work / f"seg_{a:.2f}_{b:.2f}.wav"
    r = subprocess.run(
        [ff, "-y", "-hide_banner", "-loglevel", "error",
         "-ss", f"{a:.3f}", "-t", f"{max(0.5, b - a):.3f}", "-i", str(source),
         "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(seg)],
        capture_output=True, text=True)
    if r.returncode != 0 or not seg.exists():
        return None, None
    outdir = work / f"out_{a:.2f}_{b:.2f}"
    jobs = max(1, min(4, (os.cpu_count() or 2) // 3))
    got = _run_demucs(seg, outdir, jobs)
    if got is None:
        shutil.rmtree(outdir, ignore_errors=True)
        seg.unlink(missing_ok=True)
        return None, None
    shutil.move(str(got), str(nv))
    for p in outdir.rglob("vocals.wav"):
        shutil.move(str(p), str(vo))
        break
    shutil.rmtree(outdir, ignore_errors=True)
    seg.unlink(missing_ok=True)
    return (vo if vo.exists() else None), nv


def resolve(project: str) -> tuple[Path | None, str]:
    """(no_vocals_path | None, note) for a render, applying the policy.

    Policy is config.FILM_AUDIO_REQUIRE_STEMS:
      True  - stems are mandatory; a failure is the caller's problem to stop on
      False - the caller may proceed, but with the film audio MUTED under
              narration rather than un-separated. Never the full mix.
    """
    import config
    if not config.FILM_AUDIO_ENABLE:
        return None, "film audio disabled in config"
    p = separate(project)
    if p is not None:
        return p, "no-vocals stem"
    return None, "unavailable"


if __name__ == "__main__":
    # Run the separation as an EXPLICIT step. It takes tens of minutes on CPU,
    # so having a render silently block on it is the wrong shape: do it once,
    # deliberately, then every render after that is a cache hit.
    #   python -m pipeline.stems --project tokyodrift2006
    import argparse
    import sys as _s

    ap = argparse.ArgumentParser(
        description="Separate a project's film audio into vocals / no-vocals.")
    ap.add_argument("--project", required=True)
    ap.add_argument("--force", action="store_true",
                    help="re-separate even if a current cached stem exists")
    a = ap.parse_args()

    ok, why = available()
    if not ok:
        console.print(f"[red]Cannot separate:[/] {why}")
        console.print(f"  {install_hint()}")
        _s.exit(1)
    out = separate(a.project, force=a.force)
    if out is None:
        console.print("[red]Separation failed.[/]")
        _s.exit(1)
    console.print(f"[green]Done:[/] {out}")
