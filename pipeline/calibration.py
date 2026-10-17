"""
calibration.py — Mức 3 voice-profile management + capacity math.

A voice profile captures how FAST a particular TTS voice (at a given rate)
actually speaks, measured EMPIRICALLY from real output rather than guessed.
The two numbers that matter for capacity-aware authoring:

  words_per_sec               aggregate narrated rate (total words / total secs)
  words_per_sec_conservative  a safe ceiling (mean - 0.5*std) so a line that is
                              sized to "fit" never overruns the real audio.

Public API:
  load_profile(voice_id, rate) -> VoiceProfile
  VoiceProfile.estimate_narration_seconds(text) -> float
  VoiceProfile.max_words_for_capacity(capacity_sec) -> int
  calibrate(project, voice_key) -> dict   (re-measure from a project's TTS)

Backward compatible: if no profile matches, callers fall back to
config.TTS_WORDS_PER_MINUTE (the existing conservative WPM heuristic).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import config

_PROFILES_PATH = Path(__file__).resolve().parent.parent / "config" / "voice_profiles.json"


@dataclass
class VoiceProfile:
    voice_id: str
    rate_adjustment: str
    words_per_sec: float
    words_per_sec_conservative: float
    syllables_per_sec: float = 0.0
    pause_overhead_sec: float = 0.18
    # "measured"  = do that tu dau ra TTS cua CHINH giong se duoc render
    # "config-fallback" = suy ra tu config.TTS_WORDS_PER_MINUTE vi giong do
    #                     chua duoc do bao gio
    # Bat buoc phai phan biet duoc, vi co so runtime la cai do duoc khi co, va
    # chi lui ve hang so khi khong co. Nguoi doc phai biet ho dang xem cai nao.
    source: str = "measured"

    @property
    def is_measured(self) -> bool:
        return self.source == "measured"

    @property
    def words_per_minute(self) -> float:
        return self.words_per_sec * 60.0

    def estimate_narration_seconds(self, text: str) -> float:
        """Best-estimate spoken length of `text` (seconds), incl. the inter-line
        pause overhead. Uses the AGGREGATE rate (closest to reality)."""
        words = len(str(text).split())
        # 2026-09-09: day tung la `or 3.5` - mot hang so DAT RA, khong do tu dau.
        # Mot truong thieu trong voice_profiles.json lang le sinh ra mot NHIP
        # THU HAI (3.5 w/s = 210 WPM) ben canh config.TTS_WORDS_PER_MINUTE=170,
        # va hai con so runtime cung ton tai: script.txt bao 24.7 phut con
        # DRAFT-TARGET bao 20.6. Toi da lap ngan sach tu con so nho hon.
        # Thieu du lieu thi lui ve CO SO DUY NHAT, khong tu nghi ra nhip moi.
        wps = self.words_per_sec or (float(config.TTS_WORDS_PER_MINUTE) / 60.0)
        return words / wps + self.pause_overhead_sec

    def max_words_for_capacity(self, capacity_sec: float) -> int:
        """How many words can be spoken within `capacity_sec` WITHOUT overrunning.
        Uses the CONSERVATIVE rate so the ceiling is safe (a line at this many
        words is guaranteed to fit the real, faster-on-average audio)."""
        usable = max(0.0, float(capacity_sec) - self.pause_overhead_sec)
        wps = (self.words_per_sec_conservative or self.words_per_sec
               or (float(config.TTS_WORDS_PER_MINUTE) / 60.0))
        return int(usable * wps)


def profile_key(voice_id: str, rate: str) -> str:
    return f"{voice_id}_{rate}"


def _load_all() -> dict:
    if not _PROFILES_PATH.exists():
        return {}
    try:
        data = json.loads(_PROFILES_PATH.read_text(encoding="utf-8-sig"))
        return data.get("profiles", {})
    except Exception:
        return {}


def load_profile(voice_id: str, rate: str = "+22%") -> Optional[VoiceProfile]:
    """Return the calibrated profile for (voice_id, rate), or None if absent."""
    profiles = _load_all()
    key = profile_key(voice_id, rate)
    meta = profiles.get(key)
    if meta is None:
        # tolerate a stored key that already embeds voice+rate differently
        for k, v in profiles.items():
            if v.get("voice_id") == voice_id and v.get("rate_adjustment") == rate:
                meta = v
                break
    if meta is None:
        return None
    return VoiceProfile(
        voice_id=meta.get("voice_id", voice_id),
        rate_adjustment=meta.get("rate_adjustment", rate),
        words_per_sec=float(meta.get("words_per_sec",
                                     float(config.TTS_WORDS_PER_MINUTE) / 60.0)),
        words_per_sec_conservative=float(
            meta.get("words_per_sec_conservative",
                     meta.get("words_per_sec",
                              float(config.TTS_WORDS_PER_MINUTE) / 60.0))),
        syllables_per_sec=float(meta.get("syllables_per_sec", 0.0)),
        pause_overhead_sec=float(meta.get("pause_overhead_sec", 0.18)),
        source="measured",
    )


def default_profile() -> VoiceProfile:
    """Fallback profile derived from config.TTS_WORDS_PER_MINUTE (the existing
    conservative heuristic) so callers always get a usable object."""
    wps = max(0.1, float(config.TTS_WORDS_PER_MINUTE) / 60.0)
    return VoiceProfile(
        voice_id="(default)", rate_adjustment="",
        words_per_sec=wps, words_per_sec_conservative=wps,
        pause_overhead_sec=float(getattr(config, "GAP_BETWEEN_LINES", 0.18)),
        source="config-fallback",
    )


def get_profile(voice_id: Optional[str] = None, rate: str = "+22%") -> VoiceProfile:
    """Convenience: calibrated profile if found, else the config-derived default."""
    if voice_id:
        p = load_profile(voice_id, rate)
        if p is not None:
            return p
    return default_profile()


# --------------------------------------------------------------------------- #
# Calibration: re-measure a voice profile from a project's existing TTS audio.
# --------------------------------------------------------------------------- #
def _count_syllables(word: str) -> int:
    w = word.lower().strip(".,!?;:'\"-()")
    if not w:
        return 0
    vowels = "aeiouy"
    count, prev = 0, False
    for ch in w:
        isv = ch in vowels
        if isv and not prev:
            count += 1
        prev = isv
    if w.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def calibrate(project: str, voice_key: str, ffprobe: Optional[str] = None) -> dict:
    """Measure words/sec + syllables/sec from a project's narration/*.mp3 against
    its draft.json, and write/update config/voice_profiles.json[profiles][voice_key].
    Returns the computed stats dict."""
    import statistics
    import subprocess

    pdir = config.project_dir(project)
    draft = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    narr_dir = pdir / "narration"
    ffprobe = ffprobe or _find_ffprobe()

    def dur(p: Path) -> float:
        r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
                           capture_output=True, text=True)
        try:
            return float(r.stdout.strip())
        except Exception:
            return 0.0

    wps, sps = [], []
    tot_w = tot_s = tot_syl = 0
    for l in draft["lines"]:
        if l.get("narration_silence_seconds"):
            continue
        text = (l.get("narration") or "").strip()
        if not text:
            continue
        af = narr_dir / f"line_{l['id']:03d}.mp3"
        if not af.exists():
            continue
        secs = dur(af)
        if secs < 0.3:
            continue
        words = len(text.split())
        syl = sum(_count_syllables(w) for w in text.split())
        wps.append(words / secs)
        sps.append(syl / secs)
        tot_w += words
        tot_s += secs
        tot_syl += syl

    if not wps:
        raise RuntimeError(f"no usable TTS samples in {project}")

    stats = {
        "samples": len(wps),
        "words_per_sec": round(tot_w / tot_s, 3),
        "words_per_sec_mean": round(statistics.mean(wps), 3),
        "words_per_sec_std": round(statistics.pstdev(wps), 3),
        "words_per_sec_conservative": round(statistics.mean(wps) - 0.5 * statistics.pstdev(wps), 3),
        "syllables_per_sec": round(tot_syl / tot_s, 3),
        "total_words": tot_w,
        "total_speaking_sec": round(tot_s, 1),
    }
    return stats


def _find_ffprobe() -> str:
    cand = getattr(config, "FFPROBE_PATH", None)
    if cand and os.path.exists(cand):
        return cand
    return "ffprobe"


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Mức 3 voice-profile calibration")
    ap.add_argument("--project", required=True)
    ap.add_argument("--voice-key", required=True,
                    help="e.g. en-US-AndrewMultilingualNeural_+22%")
    args = ap.parse_args()
    s = calibrate(args.project, args.voice_key)
    print(json.dumps(s, indent=2))
