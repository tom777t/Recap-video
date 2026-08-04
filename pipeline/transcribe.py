"""Transcribe source.mp4 with faster-whisper -> transcript.json (timestamps)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# --- Ensure HTTPS to Hugging Face (model download) trusts the right CA roots.
# Some Windows machines don't expose the full CA chain to Python's default
# SSL store; certifi's bundle does. Set this BEFORE huggingface_hub imports.
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    os.environ.setdefault("CURL_CA_BUNDLE", certifi.where())
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
except Exception:
    pass

# On managed networks (school/company) an SSL-inspecting proxy/antivirus can
# replace Hugging Face's certificate with one your machine doesn't trust, which
# breaks the one-time model download. Two escape hatches, in order of safety:
#   1. truststore  -> use the Windows certificate store (knows the proxy's CA).
#   2. RECAP_INSECURE_SSL=1  -> skip verification for the model download only.
# Neither affects video download or any file you keep; this is just the weights.
try:
    import truststore  # type: ignore
    truststore.inject_into_ssl()
    _TRUSTSTORE = True
except Exception:
    _TRUSTSTORE = False


def _disable_ssl_verify():
    """Last-resort: turn off TLS verification for the HF model download only."""
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    os.environ["HF_HUB_DISABLE_SSL_VERIFICATION"] = "1"
    os.environ["CURL_CA_BUNDLE"] = ""
    os.environ["REQUESTS_CA_BUNDLE"] = ""
    # httpx (used by huggingface_hub) reads its own context; patch its default.
    try:
        import httpx  # noqa
        _orig_init = httpx.Client.__init__

        def _insecure_init(self, *a, **kw):
            kw.setdefault("verify", False)
            return _orig_init(self, *a, **kw)

        httpx.Client.__init__ = _insecure_init  # type: ignore
    except Exception:
        pass


from rich.console import Console

import config

console = Console()

# Rough CPU transcription speed multipliers (x realtime) per model, very loose.
_CPU_SPEED_HINT = {
    "tiny": "~10-15x realtime",
    "base": "~6-10x realtime",
    "small": "~3-5x realtime",
    "medium": "~1-2x realtime",
    "large-v3": "~0.5-1x realtime (slow!)",
}


def _extract_audio(source: Path) -> Path:
    """Pull a 16k mono wav for whisper (faster + smaller than feeding mp4)."""
    wav = source.parent / "audio16k.wav"
    if wav.exists():
        return wav
    ff = config.ffmpeg()
    cmd = [
        ff, "-y", "-i", str(source),
        "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le", str(wav),
    ]
    console.print("Extracting 16kHz mono audio for transcription...")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        console.print("[red]ffmpeg audio extraction failed:[/]")
        console.print(proc.stderr[-1500:])
        sys.exit(1)
    return wav


def _probe_duration(source: Path) -> float:
    fp = config.ffprobe()
    out = subprocess.run(
        [fp, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(source)],
        capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def transcribe(project: str, model_size: str = config.DEFAULT_WHISPER_MODEL,
               keep_temp: bool = False, insecure_ssl: bool = False,
               translate: bool = False) -> Path:
    pdir = config.ensure_project(project)
    source = pdir / "source.mp4"
    if not source.exists():
        console.print(f"[red]No source.mp4 in project '{project}'. Run ingest first.[/]")
        sys.exit(1)

    out_json = pdir / "transcript.json"
    if out_json.exists():
        console.print(f"[yellow]transcript.json exists[/], reusing. Delete it to re-transcribe.")
        return out_json

    dur = _probe_duration(source)
    mins = dur / 60.0
    hint = _CPU_SPEED_HINT.get(model_size, "?")
    task = "translate" if translate else "transcribe"
    console.print(
        f"\n[bold]Transcription plan[/]\n"
        f"  video length : {mins:6.1f} min\n"
        f"  whisper model: {model_size}\n"
        f"  task         : {task}{'  (foreign speech -> English)' if translate else ''}\n"
        f"  CPU speed    : {hint}\n"
    )
    if mins > 45 and model_size in ("medium", "large-v3"):
        console.print(
            "[yellow]Heads up:[/] long video + big model on CPU can take a very long "
            "time. Consider --model small or base for a faster first pass.\n"
        )

    wav = _extract_audio(source)

    # Import here so the rest of the CLI works even before deps are installed.
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        console.print("[red]faster-whisper not installed.[/] Run: pip install -r requirements.txt")
        sys.exit(1)

    # SSL handling for the one-time model download on managed/proxied networks.
    if insecure_ssl or os.environ.get("RECAP_INSECURE_SSL") == "1":
        console.print("[yellow]Insecure SSL enabled for model download[/] "
                      "(proxy/antivirus on this network intercepts HTTPS).")
        _disable_ssl_verify()
    elif _TRUSTSTORE:
        console.print("[dim]Using Windows certificate store (truststore) for model "
                      "download.[/]")

    console.print(f"Loading model '{model_size}' (first run downloads weights)...")
    fw_model = model_size if model_size != "large" else "large-v3"
    try:
        wmodel = WhisperModel(fw_model, device="cpu", compute_type="int8")
    except Exception as e:
        msg = str(e).lower()
        if ("ssl" in msg or "certificate" in msg) and not insecure_ssl:
            console.print(
                "\n[red]Model download failed due to an SSL/certificate problem.[/]\n"
                "  Your network (school/company) likely inspects HTTPS traffic.\n"
                "  Re-run with the insecure flag to bypass verification for the\n"
                "  model download only (video/output are unaffected):\n"
                "    [bold]python recap.py ingest <url> --project NAME --insecure-ssl[/]\n"
                "  or set the env var once:  [bold]$env:RECAP_INSECURE_SSL='1'[/]\n"
            )
            sys.exit(1)
        raise

    # ---- Resumable checkpointing -------------------------------------------
    # A long film (2h+) on CPU can take hours; an interruption must NOT throw
    # away all progress. We append every finished segment to a .partial.jsonl
    # IMMEDIATELY. On re-run we load that, then resume transcription from just
    # after the last checkpointed timestamp (re-seek the model via an offset).
    partial = out_json.with_suffix(".partial.jsonl")
    seg_list = []
    resume_from = 0.0
    if partial.exists():
        try:
            for line in partial.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                seg_list.append(json.loads(line))
            if seg_list:
                resume_from = max(0.0, float(seg_list[-1]["end"]) - 0.5)
                console.print(f"[yellow]Resuming[/] from {resume_from:.1f}s "
                              f"({len(seg_list)} segments already done).")
        except Exception:
            seg_list = []
            resume_from = 0.0

    console.print(f"[cyan]{task.capitalize()}ing...[/] (progress shown by segment)")
    tkwargs = dict(task=task, vad_filter=True,
                   vad_parameters=dict(min_silence_duration_ms=500), beam_size=5)
    # faster-whisper supports a (start, end) clip window; resume = [resume_from, dur].
    if resume_from > 0:
        tkwargs["clip_timestamps"] = [resume_from, round(dur, 3)]
    segments, info = wmodel.transcribe(str(wav), **tkwargs)
    lang = info.language

    pf = partial.open("a", encoding="utf-8")
    try:
        for seg in segments:
            rec = {"start": round(seg.start, 3), "end": round(seg.end, 3),
                   "text": seg.text.strip()}
            seg_list.append(rec)
            pf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            pf.flush()
            safe = seg.text.strip()[:80].encode("ascii", errors="replace").decode("ascii")
            console.print(f"  [{seg.start:7.1f}s] {safe}")
    finally:
        pf.close()

    data = {
        "language": lang,
        "duration": round(dur, 2),
        "model": model_size,
        "segments": seg_list,
    }
    out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"\n[green]Transcript saved:[/] {out_json}  ({len(seg_list)} segments)")
    # success -> drop the checkpoint
    try:
        partial.unlink()
    except OSError:
        pass

    # Clean up the temporary 16kHz wav (only used for transcription). It can be
    # large for long films (~110MB/hour). source.mp4 is never touched here.
    if not keep_temp and wav.exists():
        try:
            freed = wav.stat().st_size / (1024 * 1024)
            wav.unlink()
            console.print(f"[dim]Removed temp {wav.name} (freed {freed:.0f} MB). "
                          f"Use --keep-temp to keep it.[/]")
        except OSError as e:
            console.print(f"[yellow]Could not remove {wav.name}: {e}[/]")

    return out_json
