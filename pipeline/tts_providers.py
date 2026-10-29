"""
TTS provider abstraction: one interface, many engines, real delivery controls.

WHY THIS EXISTS
Edge-TTS can only change rate, pitch and volume. Those are not acting. A
<reveal> and a <sad> line differ in Edge only by being slightly faster or
lower, which is why the narration reads flat no matter how the draft is
tagged. Every other provider here exposes some form of *direction* - inline
performance tags, a natural-language instruction field, or script inference -
and this module's job is to map our nine tone tags onto whatever each engine
actually has, rather than flattening everything back down to rate and pitch.

THE CENTRAL RULE: NO SILENT FALLBACK.
An unknown tag raises. A provider that cannot express a tag must say so, not
quietly read the line as normal. This repo already paid for that lesson once:
ten <reveal> lines in tokyodrift2006 were read at ordinary pace because the
preset did not exist and the fallback was silent. See pipeline/tts.py.

MODEL NAMES - VERIFIED, AND THREE WERE WRONG
Checked against each vendor's live docs on 2026-10-24. The names in the
request were not all real, so the corrections are recorded here rather than
in a chat message that will be lost:

  "Qwen-Audio-3.1-TTS"    -> no such id. Real: qwen-audio-3.1-tts-plus /
                             -flash. (Qwen-Audio is an umbrella family that
                             covers BOTH tts and asr, so the name was
                             imprecise, not misplaced.)
  "Fish Audio S2.1 Pro"   -> correct: s2.1-pro.
  "Drama 3 preview"       -> drama-3 is real but it is GA, not a preview.
                             What is time-limited is its PROMO PRICE.
  "Inworld Realtime TTS-2"-> correct: inworld-tts-2. Note the cheaper
                             inworld-tts-2-flash CANNOT steer at all.
  "ElevenLabs v4 Turbo"   -> correct: eleven_v4_turbo. I had assumed this one
                             did not exist; it does.
  "Hume Octave 2"         -> real, but selected by `version: 2`, not a model
                             string. Two caveats below, both serious.

HUME IS ON A DEATH CLOCK. Hume's own docs state the TTS and EVI APIs shut off
2026-11-13 and account data is deleted after that. That is about three weeks
from now. It is implemented here because it was asked for and because the
script-inference contrast is genuinely informative, but it must not be
chosen as the pipeline's voice.

KEYS COME FROM THE ENVIRONMENT ONLY.
No key is read from a file, written to a file, logged, or echoed. A provider
with no key reports itself unavailable and is skipped. The env var names are
each vendor's own documented convention - note Fish is FISH_API_KEY, not
FISH_AUDIO_API_KEY.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import config

# The nine tone tags the drafts actually use. Checked against
# tokyodrift2006/draft.json: hook 1, intro 1, normal 69, tense 62, reveal 24,
# action 22, sad 26, mystery 13, outro 1 = 219 lines, no others.
TAGS = ("normal", "tense", "sad", "reveal", "mystery", "hook", "intro",
        "outro", "action")


class UnknownTag(Exception):
    """A tag with no mapping for this provider. Never falls back to normal."""


class ProviderUnavailable(Exception):
    """No API key, or a missing dependency. Caller should skip, not die."""


class SynthesisFailed(Exception):
    """The provider was reachable but refused or broke."""


def audio_duration(path: Path) -> float:
    out = subprocess.run(
        [config.ffprobe(), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


# --------------------------------------------------------------------------- #
# Pricing + licence facts, each with the figure's basis recorded.
# --------------------------------------------------------------------------- #
@dataclass
class Commerce:
    """What a provider costs and whether we may monetize its output.

    `usd_per_million_chars` is None when the vendor does not publish a
    computable per-character rate. None means UNKNOWN and is reported as
    unknown - it is never silently treated as zero or guessed at, because a
    plausible-looking invented number is worse than an admitted gap.
    """
    usd_per_million_chars: float | None
    monetize_youtube: str            # "yes" / "yes, paid tier" / "unknown"
    min_tier_for_commercial: str
    notes: str = ""
    bills_direction_text: bool | None = None  # are inline cues billed too?

    def cost_for(self, chars: int) -> float | None:
        if self.usd_per_million_chars is None:
            return None
        return self.usd_per_million_chars * chars / 1_000_000.0


# --------------------------------------------------------------------------- #
# Base provider
# --------------------------------------------------------------------------- #
@dataclass
class Provider:
    name: str
    model: str
    voice: str
    env_var: str | None
    commerce: Commerce
    # Human-readable voice name for filenames. ElevenLabs voice ids are opaque
    # strings like bIHbv24MWmeRgasZH58o, which make an unlistenable filename.
    # Must carry a default, so it sits after the non-defaulted fields.
    voice_label: str = ""
    control_kind: str = ""     # how delivery is expressed, for the report
    docs: str = ""
    # tag -> provider-specific control bundle
    delivery: dict = field(default_factory=dict)

    # ---- availability ----------------------------------------------------- #
    def key(self) -> str | None:
        """Read the key from the environment. Never logged, never persisted."""
        if self.env_var is None:
            return None
        return os.environ.get(self.env_var) or None

    def available(self) -> tuple[bool, str]:
        if self.env_var is None:
            return True, "no key needed"
        if not self.key():
            return False, f"{self.env_var} not set"
        return True, "key present"

    # ---- delivery --------------------------------------------------------- #
    # Hard ceilings per control, so a per-line speed bump cannot push a voice
    # into gabbling. Keys are whatever a provider happens to call its rate.
    _SPEED_KEYS = {
        # key              (min,  max)
        "speaking_rate":   (0.60, 1.60),   # Inworld
        "speed":           (0.70, 1.20),   # ElevenLabs (API hard limit)
    }

    def controls_for(self, tag: str, speed_mult: float = 1.0) -> dict:
        """Resolve a tone tag to this provider's real controls.

        Raises on an unmapped tag. The whole point of the module is that a tag
        changes the performance; a tag that silently maps to nothing is a
        defect that looks like success.

        `speed_mult` is a PER-LINE multiplier on this provider's rate control,
        used by tools/fit_narration.py when one line's audio overruns its
        footage window by a few percent. It is deliberately a multiplier on the
        tag's own rate rather than a replacement: a `sad` line that has to fit
        should still be slower than a `tense` one. Clamped per control so the
        fix can never become the defect.
        """
        t = (tag or "normal").strip() or "normal"
        if t not in self.delivery:
            raise UnknownTag(
                f"{self.name}: no delivery mapping for tag '{t}'. "
                f"Mapped: {', '.join(sorted(self.delivery))}. Add a deliberate "
                f"mapping - do not let it read as a normal line.")
        c = dict(self.delivery[t])
        m = float(speed_mult or 1.0)
        if abs(m - 1.0) > 1e-9:
            c = self._scale_speed(c, m)
        return c

    def _scale_speed(self, c: dict, m: float) -> dict:
        """Apply a rate multiplier to whichever control this provider uses.

        Raises if the provider has no recognised rate control: silently
        returning an unscaled copy would make a requested rate bump look
        applied (the cache key would change, the audio would not), which is the
        failure mode this module exists to avoid.
        """
        for key, (lo, hi) in self._SPEED_KEYS.items():
            if key in c:
                c[key] = round(min(hi, max(lo, float(c[key]) * m)), 4)
                return c
        if "rate" in c:      # Edge: a percent string like "+22%"
            base = str(c["rate"]).strip().rstrip("%")
            try:
                pct = float(base)
            except ValueError:
                pct = 0.0
            new = (1.0 + pct / 100.0) * m - 1.0
            # Edge takes the whole range but past ~+60% it is unintelligible.
            new = min(0.60, max(-0.40, new))
            c["rate"] = f"{new * 100:+.0f}%"
            return c
        raise UnknownTag(
            f"{self.name}: asked for a {m:.3f}x rate bump but this provider "
            f"exposes no rate control among {sorted(c)}. Refusing to pretend "
            f"it was applied.")

    # ---- cache ------------------------------------------------------------ #
    def cache_signature(self, text: str, tag: str,
                        speed_mult: float = 1.0) -> str:
        """Cache key: text + voice + tag, PLUS model and the RESOLVED controls.

        The brief said text + voice + tag. That key is not sufficient and the
        gap is the interesting part: when I retune the tag->control mapping -
        which is the entire activity this module exists to support - the text,
        the voice and the tag are all unchanged, so a text+voice+tag cache
        would serve the OLD audio and the retune would appear to do nothing.
        Hashing the resolved controls and the model id closes that.
        """
        return hashlib.sha1(
            self.signature_payload(text, tag, speed_mult)
            .encode("utf-8")).hexdigest()

    def signature_payload(self, text: str, tag: str,
                          speed_mult: float = 1.0) -> str:
        """The exact string that gets hashed.

        Exposed separately so a test can inspect what actually goes into the
        key. Asserting a secret is absent from the sha1 DIGEST is a test that
        can never fail - a 40-char hex string cannot contain a credential - so
        the leak check has to run against this.
        """
        return json.dumps({
            "provider": self.name,
            "model": self.model,
            "voice": self.voice,
            "tag": tag,
            "text": text,
            # The RESOLVED controls already carry the speed bump, so the key
            # changes when a line is re-fitted and the old audio is not served.
            "controls": self.controls_for(tag, speed_mult),
        }, sort_keys=True, ensure_ascii=False)

    def synthesize(self, text: str, tag: str, out: Path,
                   speed_mult: float = 1.0) -> None:
        raise NotImplementedError

    # ---- shared HTTP helper ---------------------------------------------- #
    def _post(self, url: str, headers: dict, body: dict,
              attempts: int = 3, timeout: int = 120) -> bytes:
        data = json.dumps(body).encode("utf-8")
        last = None
        for i in range(attempts):
            req = urllib.request.Request(url, data=data, method="POST")
            for k, v in headers.items():
                req.add_header(k, v)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return r.read()
            except urllib.error.HTTPError as e:
                detail = ""
                try:
                    detail = e.read().decode("utf-8", "replace")[:400]
                except Exception:
                    pass
                last = SynthesisFailed(f"HTTP {e.code}: {detail}")
                # 4xx other than 429 will not fix itself; stop retrying.
                if e.code != 429 and 400 <= e.code < 500:
                    raise last
            except Exception as e:  # noqa: BLE001 - transient network
                last = SynthesisFailed(str(e))
            if i < attempts - 1:
                time.sleep(2.0 * (i + 1))
        raise last if last else SynthesisFailed("no response")


# --------------------------------------------------------------------------- #
# 1. Edge - the baseline, and the thing being measured against
# --------------------------------------------------------------------------- #
class EdgeProvider(Provider):
    """Rate / pitch / volume. That is the whole instrument.

    Kept as the honest baseline: the mapping is pulled straight from
    config.TTS_DELIVERY so this is exactly what the pipeline ships today.
    """

    def synthesize(self, text: str, tag: str, out: Path,
                   speed_mult: float = 1.0) -> None:
        import asyncio
        try:
            import edge_tts
        except ImportError as e:
            raise ProviderUnavailable(f"edge-tts not installed: {e}") from e
        c = self.controls_for(tag, speed_mult)

        async def go():
            last = None
            for i in range(4):
                try:
                    comm = edge_tts.Communicate(
                        text, voice=self.voice, rate=c["rate"],
                        pitch=c["pitch"], volume=c["volume"])
                    await comm.save(str(out))
                    if out.exists() and out.stat().st_size > 0:
                        return
                    last = SynthesisFailed("empty audio written")
                except Exception as e:  # noqa: BLE001
                    last = e
                if out.exists() and out.stat().st_size == 0:
                    out.unlink()
                if i < 3:
                    await asyncio.sleep(2.0 * (i + 1))
            raise SynthesisFailed(str(last))

        asyncio.run(go())


def _edge() -> EdgeProvider:
    # Mirror the shipped presets exactly; no second source of truth.
    deliv = {}
    for t in TAGS:
        p = dict(config.TTS_DELIVERY.get(t, {}))
        p.setdefault("rate", config.DEFAULT_TTS_RATE)
        p.setdefault("pitch", "+0Hz")
        p.setdefault("volume", "+0%")
        deliv[t] = {"rate": p["rate"], "pitch": p["pitch"],
                    "volume": p["volume"]}
    return EdgeProvider(
        name="edge", model="edge-tts", voice=config.DEFAULT_TTS_VOICE,
        env_var=None,
        control_kind="rate/pitch/volume only - cannot act",
        docs="https://github.com/rany2/edge-tts",
        commerce=Commerce(
            usd_per_million_chars=0.0,
            monetize_youtube="unknown",
            min_tier_for_commercial="n/a (undocumented, unofficial endpoint)",
            notes="Free and unmetered, but it is Microsoft's Read-Aloud "
                  "endpoint reached through an unofficial client. There is no "
                  "TTS licence granting broadcast rights and no terms page "
                  "covering this use. Zero cost, non-zero legal risk - the "
                  "risk is the reason to move, as much as the flat delivery."),
        delivery=deliv)


# --------------------------------------------------------------------------- #
# 2. ElevenLabs eleven_v4_turbo - inline audio tags + voice_settings
# --------------------------------------------------------------------------- #
class ElevenProvider(Provider):
    def synthesize(self, text: str, tag: str, out: Path,
                   speed_mult: float = 1.0) -> None:
        k = self.key()
        if not k:
            raise ProviderUnavailable(f"{self.env_var} not set")
        c = self.controls_for(tag, speed_mult)
        cue = c.get("cue") or ""
        body = {
            "text": (cue + " " + text).strip() if cue else text,
            "model_id": self.model,
            "voice_settings": {
                "stability": c["stability"],
                "similarity_boost": c["similarity_boost"],
                "style": c["style"],
                "speed": c["speed"],
                "use_speaker_boost": True,
            },
        }
        url = (f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice}"
               f"?output_format=mp3_44100_128")
        audio = self._post(url, {"xi-api-key": k,
                                 "Content-Type": "application/json"}, body)
        out.write_bytes(audio)


def _eleven(voice: str = "JBFqnCBsd6RMkjVDRZzb",
            voice_label: str = "George") -> ElevenProvider:
    # Audio tags go inline in `text`. v4/v4-turbo/v3 support them; the older
    # multilingual_v2 does NOT, so changing the model silently disables all
    # the direction below - hence model id is part of the cache key.
    # `speed` is hard-limited to 0.7-1.2 by the API; staying inside that.
    D = {
      "normal":  dict(cue="",             stability=0.50, style=0.00, speed=1.00),
      "tense":   dict(cue="[nervous]",    stability=0.35, style=0.45, speed=1.08),
      "sad":     dict(cue="[sighs]",      stability=0.65, style=0.35, speed=0.90),
      "reveal":  dict(cue="[excited]",    stability=0.30, style=0.60, speed=0.94),
      "mystery": dict(cue="[whispers]",   stability=0.60, style=0.40, speed=0.92),
      "hook":    dict(cue="[curious]",    stability=0.35, style=0.55, speed=1.02),
      "intro":   dict(cue="",             stability=0.50, style=0.20, speed=1.00),
      "outro":   dict(cue="",             stability=0.60, style=0.25, speed=0.96),
      "action":  dict(cue="[shouting]",   stability=0.25, style=0.70, speed=1.15),
    }
    for v in D.values():
        v["similarity_boost"] = 0.75
    return ElevenProvider(
        name=f"elevenlabs-{voice_label.lower()}", model="eleven_v4_turbo",
        # Voice ids confirmed present on this account via GET /v1/voices -
        # not guessed. The first write hardcoded "Will", a young
        # conversational voice, which is the wrong register for narration.
        voice=voice, voice_label=voice_label,
        env_var="ELEVENLABS_API_KEY",
        control_kind="inline [audio tags] + stability/style/speed",
        docs="https://elevenlabs.io/docs/best-practices/prompting/eleven-v3",
        commerce=Commerce(
            usd_per_million_chars=40.0,     # $0.04 per 1k chars
            monetize_youtube="yes, paid tier",
            min_tier_for_commercial="Starter $6/mo",
            notes="Flat per-character price across tiers. Free tier is "
                  "NON-COMMERCIAL: ToS s1(c) limits free users to "
                  "non-commercial use, so the 20k free monthly characters "
                  "cannot be used for a monetized video. Docs conflict on "
                  "whether eleven_v4_turbo is reachable from the plain "
                  "/v1/text-to-speech endpoint or only Text-to-Dialogue - "
                  "call GET /v1/models and check can_do_text_to_speech first.",
            bills_direction_text=None),
        delivery=D)


# --------------------------------------------------------------------------- #
# 3. Fish Audio - s2.1-pro and drama-3
# --------------------------------------------------------------------------- #
class FishProvider(Provider):
    def synthesize(self, text: str, tag: str, out: Path,
                   speed_mult: float = 1.0) -> None:
        k = self.key()
        if not k:
            raise ProviderUnavailable(f"{self.env_var} not set")
        c = self.controls_for(tag, speed_mult)
        cue = c.get("cue") or ""
        body = {
            "text": (cue + " " + text).strip() if cue else text,
            "format": "mp3",
            "mp3_bitrate": 128,
            "temperature": c["temperature"],
            "top_p": 0.7,
            "prosody": {"speed": c["speed"], "normalize_loudness": True},
        }
        if self.voice:
            body["reference_id"] = self.voice
        audio = self._post(
            "https://api.fish.audio/v1/tts",
            {"Authorization": f"Bearer {k}",
             "Content-Type": "application/json",
             # The model is an HTTP HEADER, not a body field. If it is
             # omitted or misspelled Fish SILENTLY falls back to s2.1-pro and
             # bills as s2.1-pro - so a typo here would quietly test the
             # wrong model and still return plausible audio.
             "model": self.model},
            body)
        out.write_bytes(audio)


def _fish(model: str = "s2.1-pro") -> FishProvider:
    # Bracket cues on the S2 family are free-form natural language, not a
    # fixed token set - but every cue below is drawn from Fish's own
    # documented expression list so none of this depends on that leniency.
    # NOTE: (parenthesis) markers are s1-only legacy syntax; sending them to
    # S2 reads them aloud as literal text.
    D = {
      "normal":  dict(cue="",                     temperature=0.70, speed=1.00),
      "tense":   dict(cue="[nervous]",            temperature=0.80, speed=1.06),
      "sad":     dict(cue="[sad]",                temperature=0.60, speed=0.92),
      "reveal":  dict(cue="[surprised]",          temperature=0.85, speed=0.95),
      "mystery": dict(cue="[curious][whispering]",temperature=0.70, speed=0.93),
      "hook":    dict(cue="[confident]",          temperature=0.80, speed=1.02),
      "intro":   dict(cue="[calm]",               temperature=0.65, speed=1.00),
      "outro":   dict(cue="[satisfied]",          temperature=0.65, speed=0.96),
      "action":  dict(cue="[in a hurry tone]",    temperature=0.90, speed=1.14),
    }
    if model == "drama-3":
        # drama-3's whole reason to exist is plain-language stage direction
        # rather than emotion labels, so it gets a different mapping instead
        # of the same brackets - otherwise we would be paying 3.3x list price
        # to use a cheaper model's feature set.
        D = {
          "normal":  dict(cue="",                                              temperature=0.70, speed=1.00),
          "tense":   dict(cue="[tight, controlled, holding something back]",   temperature=0.80, speed=1.06),
          "sad":     dict(cue="[quiet and heavy, grief just under the words]", temperature=0.60, speed=0.92),
          "reveal":  dict(cue="[letting the realisation land, unhurried]",     temperature=0.85, speed=0.95),
          "mystery": dict(cue="[low and confiding, like sharing a secret]",    temperature=0.70, speed=0.93),
          "hook":    dict(cue="[direct and certain, daring you to look away]", temperature=0.80, speed=1.02),
          "intro":   dict(cue="[warm, settling the listener in]",              temperature=0.65, speed=1.00),
          "outro":   dict(cue="[reflective, drawing to a close]",              temperature=0.65, speed=0.96),
          "action":  dict(cue="[urgent, driving forward]",                     temperature=0.90, speed=1.14),
        }
    promo = model == "drama-3"
    return FishProvider(
        name=f"fish-{model}", model=model,
        voice="",   # no reference_id -> Fish's default voice
        env_var="FISH_API_KEY",   # NOT FISH_AUDIO_API_KEY
        control_kind=("plain-language [stage directions] + <whisper> word tags"
                      if promo else "documented [emotion] cues + temperature"),
        docs="https://docs.fish.audio/developer-guide/core-features/emotions",
        commerce=Commerce(
            usd_per_million_chars=10.0 if promo else 15.0,
            monetize_youtube="yes, paid tier",
            min_tier_for_commercial="Plus ~$11/mo",
            notes=("drama-3 LIST price is $50/M - 3.3x s2.1-pro. The $10/M "
                   "used here is a launch promotion ending 2026-11-12, after "
                   "which 20k chars goes from $0.20 to $1.00. Budget for "
                   "list, not promo."
                   if promo else
                   "Billed per UTF-8 BYTE, so non-ASCII text costs more than "
                   "the character count suggests.") +
                  " Fish's own pages contradict each other on free-tier "
                  "commercial rights: the ToS and the FAQ both say paid-only, "
                  "while the pricing page's Free card lists 'Commercial use'. "
                  "The FAQ also scopes commercial rights to 'verified voices "
                   "that you own', which may exclude public library voices.",
            bills_direction_text=None),
        # Passing this was missed on the first write, which left BOTH Fish
        # providers with an empty mapping - every tag would have raised at
        # synthesis time. Self-test [1] caught it before any key existed to
        # run it with.
        delivery=D)


# --------------------------------------------------------------------------- #
# 4. Inworld inworld-tts-2 - inline steering instructions
# --------------------------------------------------------------------------- #
class InworldProvider(Provider):
    def synthesize(self, text: str, tag: str, out: Path,
                   speed_mult: float = 1.0) -> None:
        k = self.key()
        if not k:
            raise ProviderUnavailable(f"{self.env_var} not set")
        c = self.controls_for(tag, speed_mult)
        cue = c.get("cue") or ""
        body = {
            "text": (cue + " " + text).strip() if cue else text,
            "voiceId": self.voice,
            "modelId": self.model,
            "deliveryMode": c["delivery_mode"],
            "audioConfig": {"audioEncoding": "MP3", "bitRate": 128000,
                            "sampleRateHertz": 44100,
                            "speakingRate": c["speaking_rate"]},
        }
        raw = self._post(
            "https://api.inworld.ai/tts/v1/voice",
            # The key from Inworld's portal is ALREADY base64(id:secret).
            # Base64-encoding it again is the documented way to get a 401.
            {"Authorization": f"Basic {k}",
             "Content-Type": "application/json"},
            body)
        import base64
        payload = json.loads(raw.decode("utf-8"))
        b64 = payload.get("audioContent")
        if not b64:
            raise SynthesisFailed(f"no audioContent in response: "
                                  f"{str(payload)[:200]}")
        out.write_bytes(base64.b64decode(b64))


def _inworld() -> InworldProvider:
    # Steering is free-form English prose inside `text`; there is no separate
    # style field. Two traps encoded here:
    #  - a tag PERSISTS from its position until another tag or [reset], unlike
    #    Fish's per-sentence convention. One cue at the head of a single-line
    #    request therefore covers the whole line, which is what we want.
    #  - instructions must be ENGLISH regardless of the script's language.
    #  - inworld-tts-2-flash ignores steering silently. Do not "optimise" the
    #    model id to flash; you would lose all direction and see no error.
    # RATES ARE CALIBRATED FROM MEASUREMENT, not chosen to look sensible.
    # First attempt read the 191-word passage at 137.7 WPM against a 185
    # target. A one-variable-at-a-time sweep on a fixed 28-word line found
    # the cause was this mapping, not the engine:
    #     plain text, rate 1.0, BALANCED .... 181.7 WPM   (already on target)
    #     + deliveryMode CREATIVE .......... 165.8 WPM   (-16)
    #     + a steering cue ................. 127.9 WPM   (-38 more)
    # So a cue costs roughly 23% of pace on its own, and CREATIVE another 9%.
    # Two corrections follow from that:
    #  1. BALANCED is the default now. CREATIVE is kept only for sad and
    #     mystery, where its slower, more expressive read is what we want
    #     anyway rather than a cost.
    #  2. Every cued tag carries a speaking_rate ABOVE 1.0 to buy back what
    #     the cue spends. These look high; they are not aggressive, they are
    #     compensating for a measured loss.
    # The reveal cue also lost the words "slow and deliberate" - it was
    # literally instructing the slowdown it was then being blamed for.
    # Inworld caps speakingRate at 1.5; nothing here goes near it.
    # 2026-10-27, ONE NARRATOR. The table above this comment used to vary
    # deliveryMode, cue and speaking_rate per tag, and the result sounded like
    # two or three different readers (measured: sad 151 WPM vs tense 267, a
    # 1.77x spread). The compensation scheme was self-defeating - it bought back
    # the pace a cue costs by making each tag a different speed.
    #
    # Now: one mode, one rate, and cues that may ask ONLY for pauses and
    # emphasis. Nothing here may instruct tempo ("fast", "clipped", "driving",
    # "slow") or alter the voice's character ("whisper", "low tone", "with
    # force") - pipeline/voice_check.py asserts that against a banned-word list,
    # so the old cues cannot come back one tag at a time.
    #
    # Every tag carries a cue, `normal` included. A cue costs ~23% of pace
    # whatever it says, so an uncued tag would read 23% faster than the rest -
    # the exact spread this is fixing. Uniform cue presence buys uniform pace.
    # 2026-10-29, THE PACE CORRECTION. The flat-rate version of this table
    # measured 134.6 WPM against a 185 target, and the budget was wrongly
    # re-cut downward to match. Two measurements fixed the direction:
    #
    #   1. A PAUSE INSTRUCTION COSTS 27% OF PACE. The same `sad` lines at the
    #      same speaking_rate read 159.0 WPM with "[longer pauses, gentle
    #      emphasis]" and 202.1 WPM with "[gentle emphasis]". The pauses were
    #      the slowdown, not the engine.
    #   2. INWORLD HARD-CAPS speakingRate AT 1.5 - confirmed by an HTTP 400,
    #      not by a comment. So a pause-led cue cannot be rate-compensated back
    #      to 185: `sad` would need 1.74.
    #
    # So the cues are EMPHASIS-led and uniform in KIND, and the per-tag
    # speaking_rate exists only to CANCEL each cue's measured pace cost, so
    # that the DELIVERED rate is the same for every tag. That is the opposite
    # of the original defect, where rates differed in order to create
    # different tempos: here they differ so the tempo does not.
    #
    # Emotion is carried by emphasis, by the mood cue underneath, and by the
    # writing - not by making one tag slower than another. The honest cost:
    # "longer pauses" as a direction is gone, because at 185 WPM with a 1.5
    # engine ceiling it is unaffordable.
    #
    # Every rate below was SOLVED BY MEASUREMENT (tools/calibrate_rate.py
    # --solve-per-tag), never computed. Re-run it after touching any cue.
    _M = config.VOICE_DELIVERY_MODE
    _RT = config.VOICE_TAG_SPEAKING_RATE
    _R = config.VOICE_BASE_SPEAKING_RATE
    D = {
      "normal":  dict(cue="[even phrasing]",                     delivery_mode=_M, speaking_rate=_RT.get("normal", _R)),
      "tense":   dict(cue="[emphasis on the action words]",      delivery_mode=_M, speaking_rate=_RT.get("tense", _R)),
      "sad":     dict(cue="[gentle emphasis]",                   delivery_mode=_M, speaking_rate=_RT.get("sad", _R)),
      "reveal":  dict(cue="[emphasis on the final phrase]",      delivery_mode=_M, speaking_rate=_RT.get("reveal", _R)),
      "mystery": dict(cue="[emphasis on the key words]",      delivery_mode=_M, speaking_rate=_RT.get("mystery", _R)),
      "hook":    dict(cue="[emphasis on the opening phrase]",    delivery_mode=_M, speaking_rate=_RT.get("hook", _R)),
      "intro":   dict(cue="[even phrasing, clear consonants]",   delivery_mode=_M, speaking_rate=_RT.get("intro", _R)),
      "outro":   dict(cue="[emphasis on the closing phrase]",    delivery_mode=_M, speaking_rate=_RT.get("outro", _R)),
      "action":  dict(cue="[emphasis on the impacts]",           delivery_mode=_M, speaking_rate=_RT.get("action", _R)),
    }
    return InworldProvider(
        name="inworld", model="inworld-tts-2",
        # "Warren" - "mature, resonant male voice with a classic announcer
        # quality", confirmed in the 303 voices returned by GET
        # /tts/v1/voices. The first write used "Dennis" from a docs example,
        # which was never checked against the live list.
        voice="Warren", voice_label="Warren",
        env_var="INWORLD_API_KEY",
        control_kind="inline [steering instructions] + deliveryMode",
        docs="https://docs.inworld.ai/tts/capabilities/steering",
        commerce=Commerce(
            usd_per_million_chars=25.0,    # On-Demand (free) tier rate
            monetize_youtube="yes",
            min_tier_for_commercial="On-Demand (free) - no paid plan needed",
            notes="The only provider here whose ToS ASSIGNS output rights to "
                  "you (s4) and whose pricing page check-marks 'Commercial "
                  "license' on every tier including free. $25/M is the "
                  "On-Demand rate; Creator $25/mo drops it to $20/M and the "
                  "Batch API is 20% cheaper again. Steering tags ARE BILLED - "
                  "docs say the tag and its trailing space count as input - so "
                  "direction-heavy narration costs more than its word count.",
            bills_direction_text=True),
        delivery=D)


# --------------------------------------------------------------------------- #
# 5. Alibaba Qwen - natural-language instruction + inline tags
# --------------------------------------------------------------------------- #
class QwenProvider(Provider):
    def synthesize(self, text: str, tag: str, out: Path,
                   speed_mult: float = 1.0) -> None:
        k = self.key()
        if not k:
            raise ProviderUnavailable(f"{self.env_var} not set")
        c = self.controls_for(tag, speed_mult)
        cue = c.get("cue") or ""
        body = {
            "model": self.model,
            "input": {
                "text": (cue + text) if cue else text,
                "voice": self.voice,
                "format": "mp3",
                "sample_rate": 24000,
                "language_hints": ["en"],
            },
        }
        if c.get("instruction"):
            body["input"]["instruction"] = c["instruction"]
        raw = self._post(
            "https://dashscope-intl.aliyuncs.com/api/v1/services/audio/tts/"
            "SpeechSynthesizer",
            {"Authorization": f"Bearer {k}",
             "Content-Type": "application/json"},
            body)
        payload = json.loads(raw.decode("utf-8"))
        # Non-streaming returns a URL, not bytes. The URL expires in 24h.
        url = (((payload.get("output") or {}).get("audio") or {})
               .get("url"))
        if not url:
            raise SynthesisFailed(f"no audio url in response: "
                                  f"{str(payload)[:300]}")
        with urllib.request.urlopen(url, timeout=120) as r:
            out.write_bytes(r.read())


def _qwen() -> QwenProvider:
    # Qwen is the only provider here with BOTH a natural-language instruction
    # field AND inline tags, so it gets both: the tag sets the local emotion,
    # the instruction holds the narrator persona steady underneath.
    # Every bracket cue below is from Alibaba's documented tag list.
    base = "Speak as a film documentary narrator: clear, grounded, unhurried."
    D = {
      "normal":  dict(cue="",            instruction=base),
      "tense":   dict(cue="[serious]",   instruction=base + " Tighten the pace, keep the tension controlled."),
      "sad":     dict(cue="[sad]",       instruction=base + " Slow down, soften, let it sit."),
      "reveal":  dict(cue="[amazed]",    instruction=base + " Slow down and let the realisation land."),
      "mystery": dict(cue="[whispers]",  instruction=base + " Confiding, as if sharing a secret."),
      "hook":    dict(cue="[serious]",   instruction=base + " Direct and certain, command attention."),
      "intro":   dict(cue="[serious]",   instruction=base + " Warm, settling the listener in."),
      "outro":   dict(cue="[empathetic]",instruction=base + " Reflective, drawing to a close."),
      "action":  dict(cue="[very fast]", instruction=base + " Urgent and driving."),
    }
    return QwenProvider(
        name="qwen",
        # -flash, not -plus, DELIBERATELY: the 15 premium English voices live
        # on flash, while -plus's flagship voices are Chinese-oriented. Both
        # support instruction + tags. The cost of that choice is that flash is
        # TOKEN-billed, so its price per character is not computable - see
        # Commerce.usd_per_million_chars = None below.
        model="qwen-audio-3.1-tts-flash", voice="Brian_v3.1",
        env_var="DASHSCOPE_API_KEY",
        control_kind="natural-language `instruction` + documented inline tags",
        docs="https://www.alibabacloud.com/help/en/model-studio/"
             "non-realtime-tts-user-guide",
        commerce=Commerce(
            usd_per_million_chars=None,
            monetize_youtube="yes",
            min_tier_for_commercial="pay-as-you-go; no non-commercial clause "
                                    "found, including on the free quota",
            notes="UNKNOWN BY DESIGN, not by omission: qwen-audio-3.1-tts-"
                  "FLASH is billed per TOKEN ($0.23/M in + $1.87/M out, "
                  "Singapore) and Alibaba publishes no characters-to-tokens "
                  "ratio, so a per-character cost cannot honestly be derived. "
                  "If you want a predictable bill use qwen-audio-3.1-tts-plus "
                  "at $0.30/10k chars = $0.60 per 20k, but its system voices "
                  "are Chinese-oriented. Terms permit commercial use and do "
                  "not claim output IP; they forbid reselling the service or "
                  "training a competing model. Keys are REGION-SCOPED - a "
                  "Singapore key will not work against the Beijing endpoint.",
            bills_direction_text=True),
        delivery=D)


# --------------------------------------------------------------------------- #
# 6. Hume Octave - the no-tags contrast
# --------------------------------------------------------------------------- #
class HumeProvider(Provider):
    def __init__(self, *a, octave_version: int = 2, **kw):
        super().__init__(*a, **kw)
        self.octave_version = octave_version

    def synthesize(self, text: str, tag: str, out: Path,
                   speed_mult: float = 1.0) -> None:
        k = self.key()
        if not k:
            raise ProviderUnavailable(f"{self.env_var} not set")
        c = self.controls_for(tag, speed_mult)
        utt: dict = {"text": text,
                     "voice": {"name": self.voice, "provider": "HUME_AI"},
                     "speed": c["speed"],
                     "trailing_silence": c["trailing_silence"]}
        # The contrast being tested: NO direction at all on Octave 2. The
        # model is supposed to infer the performance from the prose itself.
        # This is also forced, not just chosen - Hume's docs state the
        # `description` acting field is Octave 1 ONLY and is still "coming
        # soon" for Octave 2. So "Octave 2 with acting instructions" is not a
        # combination that exists today.
        if self.octave_version == 1 and c.get("description"):
            utt["description"] = c["description"]
        body = {"utterances": [utt], "format": {"type": "mp3"},
                "version": self.octave_version}
        audio = self._post(
            "https://api.hume.ai/v0/tts/file",
            {"X-Hume-Api-Key": k, "Content-Type": "application/json"},
            body)
        out.write_bytes(audio)


def _hume(octave_version: int = 2) -> HumeProvider:
    # speed is 0.5-2.0 nominally but Hume warns <0.75 or >1.5 destabilises;
    # everything here stays well inside that.
    D = {
      "normal":  dict(speed=1.00, trailing_silence=0.0, description=""),
      "tense":   dict(speed=1.06, trailing_silence=0.0, description="urgent, tightly controlled"),
      "sad":     dict(speed=0.92, trailing_silence=0.3, description="quiet, heavy, grieving"),
      "reveal":  dict(speed=0.95, trailing_silence=0.4, description="let the realisation land"),
      "mystery": dict(speed=0.93, trailing_silence=0.2, description="hushed, confiding"),
      "hook":    dict(speed=1.02, trailing_silence=0.2, description="direct, certain, arresting"),
      "intro":   dict(speed=1.00, trailing_silence=0.1, description="warm, welcoming"),
      "outro":   dict(speed=0.96, trailing_silence=0.3, description="reflective, closing"),
      "action":  dict(speed=1.15, trailing_silence=0.0, description="driving, breathless"),
    }
    return HumeProvider(
        name="hume", model=f"octave-{octave_version}", voice="Male English Actor",
        env_var="HUME_API_KEY",
        control_kind=("script-inferred acting, NO tags (Octave 2)"
                      if octave_version == 2
                      else "natural-language `description` acting (Octave 1)"),
        docs="https://dev.hume.ai/docs/text-to-speech-tts/acting-instructions",
        commerce=Commerce(
            usd_per_million_chars=None,
            monetize_youtube="yes, paid tier",
            min_tier_for_commercial="Creator+ (Free AND Starter both barred)",
            notes="DO NOT ADOPT. Hume's docs state the TTS and EVI APIs shut "
                  "off 2026-11-13 and account data is deleted after that - "
                  "about three weeks out. Its pricing page has already been "
                  "replaced by unrelated marketing, so no per-character rate "
                  "is published any more and the cost of 20k chars cannot be "
                  "stated. Kept only as the script-inference contrast. Also "
                  "note its ToS s4.1 says 'internally' only and never "
                  "mentions commercial tiers; the YouTube permission exists "
                  "solely in an FAQ.",
            bills_direction_text=False),
        delivery=D,
        octave_version=octave_version)


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
def all_providers() -> dict:
    """Every provider, keyed by the label used in output filenames."""
    return {
        "edge": _edge(),
        # Three narrator-register voices, all confirmed on the account:
        # George is labelled narrative_story, Daniel is a steady British
        # broadcaster, Brian is the deep American closest to Edge's Andrew so
        # the comparison against the current baseline is like-for-like.
        "elevenlabs-george": _eleven("JBFqnCBsd6RMkjVDRZzb", "George"),
        "elevenlabs-daniel": _eleven("onwK4e9ZLuTAKqWW03F9", "Daniel"),
        "elevenlabs-brian": _eleven("nPczCjzI2devNBz1zQrb", "Brian"),
        "fish-s21pro": _fish("s2.1-pro"),
        "fish-drama3": _fish("drama-3"),
        "inworld": _inworld(),
        "qwen": _qwen(),
        "hume-octave2": _hume(2),
        "hume-octave1": _hume(1),
    }


# --------------------------------------------------------------------------- #
# Cached synthesis
# --------------------------------------------------------------------------- #
def synthesize_cached(p: Provider, text: str, tag: str, out: Path,
                      cache_dir: Path,
                      speed_mult: float = 1.0) -> tuple[bool, float]:
    """Synthesize unless an identical request is already on disk.

    Returns (was_cached, duration_seconds).

    `speed_mult` is part of the cache key via the resolved controls, so
    re-fitting one line's rate re-synthesizes exactly that line.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = cache_dir / "_cache.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        manifest = {}

    sig = p.cache_signature(text, tag, speed_mult)
    mkey = str(out.name)
    if out.exists() and out.stat().st_size > 0 and manifest.get(mkey) == sig:
        return True, audio_duration(out)

    p.synthesize(text, tag, out, speed_mult)
    if not out.exists() or out.stat().st_size == 0:
        raise SynthesisFailed(f"{p.name} wrote no audio for tag '{tag}'")
    manifest[mkey] = sig
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True),
                             encoding="utf-8")
    return False, audio_duration(out)
