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

import datetime as _dt
import json
import os
from dataclasses import dataclass, field
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
    # {tag: {words_per_sec, words_per_sec_conservative, samples, ...}} measured
    # per delivery tag. Empty when the voice has never been calibrated, in
    # which case every tag falls back to the aggregate rate - the old
    # behaviour, and the behaviour that produced 19 overruns on Warren.
    by_tag: dict = field(default_factory=dict)
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

    def rate_for(self, tag: str | None = None,
                 conservative: bool = False) -> float:
        """Words/sec for a delivery tag, falling back to the aggregate.

        `conservative` returns the BUDGET rate (slower), which is what a
        capacity question must use: over-estimating a line's length costs some
        footage, under-estimating it costs a failed render.
        """
        key = "words_per_sec_conservative" if conservative else "words_per_sec"
        t = str(tag or "").strip()
        row = (self.by_tag or {}).get(t)
        if row:
            v = row.get(key) or row.get("words_per_sec")
            if v:
                return float(v)
        agg = (self.words_per_sec_conservative if conservative
               else self.words_per_sec)
        return float(agg or (float(config.TTS_WORDS_PER_MINUTE) / 60.0))

    def estimate_narration_seconds(self, text: str,
                                   tag: str | None = None) -> float:
        """Best-estimate spoken length of `text` (seconds), incl. the inter-line
        pause overhead. Uses the tag's measured rate when there is one."""
        words = len(str(text).split())
        if tag is not None:
            return words / max(0.1, self.rate_for(tag)) + self.pause_overhead_sec
        # 2026-09-09: day tung la `or 3.5` - mot hang so DAT RA, khong do tu dau.
        # Mot truong thieu trong voice_profiles.json lang le sinh ra mot NHIP
        # THU HAI (3.5 w/s = 210 WPM) ben canh config.TTS_WORDS_PER_MINUTE=170,
        # va hai con so runtime cung ton tai: script.txt bao 24.7 phut con
        # DRAFT-TARGET bao 20.6. Toi da lap ngan sach tu con so nho hon.
        # Thieu du lieu thi lui ve CO SO DUY NHAT, khong tu nghi ra nhip moi.
        wps = self.words_per_sec or (float(config.TTS_WORDS_PER_MINUTE) / 60.0)
        return words / wps + self.pause_overhead_sec

    def max_words_for_capacity(self, capacity_sec: float,
                               tag: str | None = None) -> int:
        """How many words can be spoken within `capacity_sec` WITHOUT overrunning.

        Uses the CONSERVATIVE rate for the TAG, so the ceiling is safe for the
        delivery this line will actually get. With a flat rate this returned
        the same ceiling for a `sad` line and a `tense` one, and Warren speaks
        those 110 WPM apart - the `sad` ceilings were the ones that overran.
        """
        # THE SAME MARGIN THE FITTER USES. tools/fit_narration.py refuses to
        # size a line to land exactly on its capacity, because re-synthesized
        # audio comes back a percent or two either side of the prediction - so
        # a line written exactly at the ceiling needs fitting the moment it is
        # spoken. The writer's budget has to leave the same room, or the writer
        # is being told a number the render will not honour.
        cap = max(0.0, float(capacity_sec))
        margin = max(float(getattr(config, "CAPACITY_MARGIN_MIN_SEC", 0.25)),
                     float(getattr(config, "CAPACITY_MARGIN_FRACTION", 0.03))
                     * cap)
        usable = max(0.0, cap - self.pause_overhead_sec - margin)
        if tag is not None:
            return int(usable * max(0.1, self.rate_for(tag, conservative=True)))
        wps = (self.words_per_sec_conservative or self.words_per_sec
               or (float(config.TTS_WORDS_PER_MINUTE) / 60.0))
        return int(usable * wps)


def profile_key(voice_id: str, rate: str) -> str:
    return f"{voice_id}_{rate}"


def mapping_signature() -> str:
    """A hash of the production voice's tag -> controls mapping.

    A measured voice profile is only valid for the mapping it was measured
    under. Changing a steering cue or a speaking_rate changes the rate the
    voice actually reads at, so a profile carried across that change reports
    numbers the voice no longer produces - and the capacity budget silently
    plans against a narrator that no longer exists. This is how a stale profile
    is DETECTED instead of trusted: calibrate() records it, production_profile()
    refuses a profile whose signature no longer matches.
    """
    import hashlib
    try:
        from pipeline.tts import DEFAULT_PROVIDER
        from pipeline.tts_providers import all_providers
        p = all_providers().get(DEFAULT_PROVIDER)
        if p is None:
            return ""
        payload = json.dumps(
            {t: p.controls_for(t) for t in sorted(p.delivery)},
            sort_keys=True, ensure_ascii=False)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    except Exception:
        return ""


def production_voice_key() -> str:
    """The profile key for the voice the pipeline will actually render with.

    Derived from the TTS module's own provider selection rather than written
    down twice, so re-pointing the production voice re-points the budget with
    it instead of leaving a stale profile in use under a new voice.
    """
    try:
        from pipeline.tts import DEFAULT_PROVIDER
        from pipeline.tts_providers import all_providers
        p = all_providers().get(DEFAULT_PROVIDER)
        if p is not None:
            return f"{p.name}-{p.voice_label}_default"
    except Exception:
        pass
    return "(unknown)_default"


def production_profile() -> VoiceProfile:
    """Calibrated profile for the production voice, else the config fallback.

    This is the one the capacity budget and DRAFT-TARGET should use: the
    question "will this line fit" is about the voice that will speak it.
    """
    key = production_voice_key()
    meta = _load_all().get(key)
    if meta is not None:
        want = mapping_signature()
        got = str(meta.get("mapping_signature") or "")
        # An UNSIGNED profile is of unknown provenance, so it is treated as
        # stale too. That is the safe direction: the fallback is the single
        # config baseline, whereas trusting it means budgeting against rates
        # that may be from any past mapping. The first profile measured here
        # was exactly that case - it recorded sad at 151 WPM, which the new
        # mapping no longer produces.
        if want and got != want:
            # Measured under a different delivery mapping - the rates in it are
            # not this voice's rates any more. Fall back to the single config
            # baseline rather than budgeting against a narrator that no longer
            # exists, and say so: a silent stale profile is worse than none.
            from rich.console import Console
            Console().print(
                "[yellow]Voice profile is STALE:[/] it was measured under a "
                "different delivery mapping, so its per-tag rates no longer "
                "describe this voice. Using the config baseline until you "
                "re-run `python -m pipeline.calibration --project <p> "
                f"--voice-key {key}` on freshly synthesized narration.")
            return default_profile()
    if meta is not None:
        vid = meta.get("voice_id") or key.rsplit("_", 1)[0]
        rate = meta.get("rate_adjustment") or ""
        p = load_profile(vid, rate)
        if p is not None:
            return p
        return VoiceProfile(
            voice_id=vid, rate_adjustment=rate,
            words_per_sec=float(meta.get("words_per_sec", 0.0)),
            words_per_sec_conservative=float(
                meta.get("words_per_sec_conservative",
                         meta.get("words_per_sec", 0.0))),
            syllables_per_sec=float(meta.get("syllables_per_sec", 0.0)),
            pause_overhead_sec=float(meta.get("pause_overhead_sec", 0.18)),
            by_tag=dict(meta.get("by_tag") or {}),
            source="measured")
    return default_profile()


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
        by_tag=dict(meta.get("by_tag") or {}),
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


def calibrate(project: str, voice_key: str, ffprobe: Optional[str] = None,
              only_ids: Optional[set] = None) -> dict:
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
    by_tag: dict = {}
    tot_w = tot_s = tot_syl = 0
    for l in draft["lines"]:
        if l.get("narration_silence_seconds") or l.get("film_speaks_seconds"):
            continue
        # `only_ids` restricts the sample to lines whose audio on disk is known
        # to be a CLEAN reading - no rate bump applied when it was synthesized.
        # The draft's current rate_bump is not enough to know that: a bump can
        # be reset after the audio was made, which leaves a bumped waveform
        # attached to a line that now claims no bump. The caller recovers the
        # truth from the TTS cache manifest.
        if only_ids is not None and l.get("id") not in only_ids:
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
        # A line carrying a per-line rate_bump is NOT a sample of the voice's
        # natural rate for its tag - including it would bake the fix into the
        # baseline and quietly raise the budget for every future draft.
        if not l.get("rate_bump"):
            by_tag.setdefault(str(l.get("delivery") or "normal"),
                              []).append((words, secs))
        tot_w += words
        tot_s += secs
        tot_syl += syl

    if not wps:
        raise RuntimeError(f"no usable TTS samples in {project}")

    # ---- PER-TAG rates -----------------------------------------------------
    # The single aggregate rate is what let the first Warren render produce 19
    # capacity overruns. Measured on those 109 lines Warren runs 151 WPM on
    # `sad` and 261 WPM on `tense` - a 1.7x spread - so one number was wrong in
    # both directions at once: it over-estimated capacity on the slow tags
    # (every large overrun was `sad` or `reveal`) and wasted footage on the
    # fast ones. A delivery tag changes the performance; of course it changes
    # the rate. Budget per tag.
    tag_stats: dict = {}
    for tag, rows in sorted(by_tag.items()):
        each = [w / s for w, s in rows]
        tw = sum(w for w, _ in rows)
        ts = sum(s for _, s in rows)
        slow = min(each)
        mean = statistics.mean(each)
        std = statistics.pstdev(each) if len(each) > 1 else 0.0
        tag_stats[tag] = {
            "samples": len(rows),
            "words_per_sec": round(tw / ts, 3),
            "words_per_sec_mean": round(mean, 3),
            "words_per_sec_std": round(std, 3),
            # The budget rate. Two samples cannot support a distribution, so
            # with few samples fall back to the SLOWEST line seen rather than
            # a mean-minus-sigma computed from almost nothing.
            "words_per_sec_conservative": round(
                (mean - 1.0 * std) if len(each) >= 5 else slow, 3),
            "words_per_sec_slowest": round(slow, 3),
        }

    stats = {
        "samples": len(wps),
        "words_per_sec": round(tot_w / tot_s, 3),
        "words_per_sec_mean": round(statistics.mean(wps), 3),
        "words_per_sec_std": round(statistics.pstdev(wps), 3),
        "words_per_sec_conservative": round(statistics.mean(wps) - 0.5 * statistics.pstdev(wps), 3),
        "syllables_per_sec": round(tot_syl / tot_s, 3),
        "total_words": tot_w,
        "total_speaking_sec": round(tot_s, 1),
        "by_tag": tag_stats,
    }

    # 2026-09-10: ham nay TUNG chi tra ve stats roi thoi, du docstring cua no
    # viet la "write/update config/voice_profiles.json". Nghia la lenh ma
    # DRAFT-TARGET bao nguoi dung chay de hieu chuan lai KHONG he cap nhat gi -
    # con so 3.5 w/s nam trong file la do go tay tu bao gio khong ai biet, va
    # no lech 6% so voi phep do that. Mot cong cu quang cao mot tac dung no
    # khong lam la te hon khong co cong cu.
    _PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        blob = json.loads(_PROFILES_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        blob = {}
    blob.setdefault("profiles", {})
    voice_id = voice_key.rsplit("_", 1)[0]
    rate = voice_key.rsplit("_", 1)[1] if "_" in voice_key else ""
    prev = blob["profiles"].get(voice_key, {})
    blob["profiles"][voice_key] = {
        "voice_id": prev.get("voice_id", voice_id),
        "rate_adjustment": prev.get("rate_adjustment", rate),
        "words_per_sec": stats["words_per_sec"],
        "words_per_sec_conservative": stats["words_per_sec_conservative"],
        "syllables_per_sec": stats["syllables_per_sec"],
        "by_tag": stats["by_tag"],
        # What mapping these numbers were measured under. See
        # mapping_signature(): the profile is void if the mapping changes.
        "mapping_signature": mapping_signature(),
        "pause_overhead_sec": prev.get("pause_overhead_sec", 0.18),
        "measured_from": project,
        "measured_samples": stats["samples"],
        "measured_total_words": stats["total_words"],
        "measured_total_speaking_sec": stats["total_speaking_sec"],
        "measured_utc": _dt.datetime.now(_dt.timezone.utc)
                           .strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _PROFILES_PATH.write_text(
        json.dumps(blob, ensure_ascii=False, indent=2), encoding="utf-8")
    stats["written_to"] = str(_PROFILES_PATH)
    stats["previous_words_per_sec"] = prev.get("words_per_sec")
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
