"""
Render one ~60s passage through every TTS provider so they can be compared.

    python tools/voice_test.py --project tokyodrift2006
    python tools/voice_test.py --selftest

Takes three real lines out of the draft - one hook, one reveal, one sad -
concatenates each provider's reading into voice_test/<provider>_<voice>.mp3,
and measures the delivered words-per-minute against the 185 target.

A provider with no key in the environment is SKIPPED and named in the report.
It is never a crash, and it is never silently omitted either.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from pipeline import tts_providers as tp  # noqa: E402

TARGET_WPM = 185.0

# One hook, one reveal, one sad, chosen from tokyodrift2006/draft.json to land
# near 60s: 28 + 60 + 103 = 191 words, which at the 185 WPM target is 62.0s.
# Line 1 is the only `hook` in the draft, so there was no choice there.
PASSAGE_IDS = (1, 60, 184)


def _words(s: str) -> int:
    return len(str(s).split())


def load_passage(project: str, ids=PASSAGE_IDS) -> list[dict]:
    pdir = config.ensure_project(project)
    # The brief said draft_compressed.json, falling back to draft.json. The
    # compressed file does not exist in this tree, so draft.json it is - and
    # the fallback is reported rather than assumed.
    src = pdir / "draft_compressed.json"
    if not src.exists():
        src = pdir / "draft.json"
    if not src.exists():
        raise SystemExit(f"no draft found in {pdir}")
    draft = json.loads(src.read_text(encoding="utf-8"))
    by_id = {l["id"]: l for l in draft["lines"]}
    out = []
    for i in ids:
        if i not in by_id:
            raise SystemExit(f"line {i} not in {src.name}")
        ln = by_id[i]
        out.append({"id": i, "tag": str(ln.get("delivery") or "normal"),
                    "text": str(ln["narration"]).strip()})
    print(f"Passage from {src.name}: "
          + ", ".join(f"line {p['id']} <{p['tag']}> {_words(p['text'])}w"
                      for p in out)
          + f"  = {sum(_words(p['text']) for p in out)} words "
            f"({sum(_words(p['text']) for p in out)/TARGET_WPM*60:.1f}s "
            f"at {TARGET_WPM:.0f} WPM)")
    return out


def concat(parts: list[Path], out: Path) -> None:
    """Join the three readings into one file.

    Audio is RE-ENCODED, not stream-copied. A stream-copy concat of mp3
    fragments produced a file whose audio duration was double its real
    content elsewhere in this repo; re-encoding is cheap on 60 seconds and
    removes the whole failure mode.
    """
    lst = out.parent / f"_{out.stem}_list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts),
                   encoding="utf-8")
    r = subprocess.run(
        [config.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
         "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100", str(out)],
        capture_output=True, text=True)
    lst.unlink(missing_ok=True)
    if r.returncode != 0:
        raise RuntimeError(f"concat failed: {(r.stderr or '')[-300:]}")


def run(project: str, only: list[str] | None) -> int:
    passage = load_passage(project)
    total_words = sum(_words(p["text"]) for p in passage)
    vdir = Path.cwd() / "voice_test"
    vdir.mkdir(exist_ok=True)

    provs = tp.all_providers()
    if only:
        provs = {k: v for k, v in provs.items() if k in only}

    rendered, skipped, failed = [], [], []

    for label, p in provs.items():
        ok, why = p.available()
        if not ok:
            skipped.append((label, p, why))
            print(f"[skip] {label:<13} {why}")
            continue
        print(f"[run ] {label:<13} {p.model} / {p.voice}  ({p.control_kind})")
        parts, per_line, bad = [], [], None
        for pz in passage:
            out = vdir / "_parts" / f"{label}_line{pz['id']:03d}.mp3"
            out.parent.mkdir(parents=True, exist_ok=True)
            try:
                cached, dur = tp.synthesize_cached(
                    p, pz["text"], pz["tag"], out,
                    vdir / "_parts")
            except tp.ProviderUnavailable as e:
                bad = f"unavailable mid-run: {e}"
                break
            except Exception as e:  # noqa: BLE001
                bad = f"{type(e).__name__}: {e}"
                break
            parts.append(out)
            wpm = _words(pz["text"]) / dur * 60 if dur else 0.0
            per_line.append((pz["id"], pz["tag"], dur, wpm))
            print(f"         line {pz['id']:>3} <{pz['tag']:<7}> {dur:5.2f}s "
                  f"{wpm:6.1f} WPM {'cached' if cached else 'new'}")
        if bad:
            failed.append((label, p, bad))
            print(f"   [fail] {label}: {bad}")
            continue

        vname = (p.voice_label or p.voice).replace(" ", "-")
        final = vdir / f"{label}_{vname}.mp3"
        concat(parts, final)
        dur = tp.audio_duration(final)
        wpm = total_words / dur * 60 if dur else 0.0
        rendered.append((label, p, dur, wpm, per_line))
        print(f"   -> {final.name}  {dur:.2f}s  {wpm:.1f} WPM "
              f"(target {TARGET_WPM:.0f}, {wpm-TARGET_WPM:+.1f})")

    # ---------------- report ------------------------------------------------
    print("\n" + "=" * 72)
    print(f"RENDERED {len(rendered)}   SKIPPED {len(skipped)}   "
          f"FAILED {len(failed)}")
    print("=" * 72)
    if rendered:
        print(f"\n{'provider':<14}{'dur':>7}{'WPM':>8}  delivery control")
        for label, p, dur, wpm, _ in rendered:
            print(f"{label:<14}{dur:7.2f}{wpm:8.1f}  {p.control_kind}")
    if skipped:
        print("\nSKIPPED - no key in the environment:")
        for label, p, why in skipped:
            print(f"  {label:<14} set {p.env_var}")
    if failed:
        print("\nFAILED:")
        for label, p, why in failed:
            print(f"  {label:<14} {why}")

    print(f"\n{'provider':<14}{'$/20k chars':>13}  {'monetize':<18} min tier")
    for label, p in tp.all_providers().items():
        c = p.commerce.cost_for(20_000)
        cs = "unknown" if c is None else f"${c:.2f}"
        print(f"{label:<14}{cs:>13}  {p.commerce.monetize_youtube:<18}"
              f"{p.commerce.min_tier_for_commercial}")
    return 0 if not failed else 1


# --------------------------------------------------------------------------- #
# Self-tests
# --------------------------------------------------------------------------- #
def selftest() -> int:
    fails: list[str] = []

    def chk(name, cond, detail=""):
        print(f"  {'PASS' if cond else 'FAIL'}  {name}"
              + (f"   {detail}" if detail and not cond else ""))
        if not cond:
            fails.append(name)

    provs = tp.all_providers()
    print(f"\n[1] every provider maps all {len(tp.TAGS)} tags")
    for label, p in provs.items():
        missing = [t for t in tp.TAGS if t not in p.delivery]
        chk(f"{label}: all tags mapped", not missing, f"missing {missing}")

    print("\n[2] known tag resolves, unknown tag RAISES (both directions)")
    for label, p in provs.items():
        try:
            p.controls_for("reveal")
            pos = True
        except Exception:
            pos = False
        chk(f"{label}: known tag 'reveal' resolves", pos)
        try:
            p.controls_for("definitely_not_a_tag")
            neg = False
        except tp.UnknownTag:
            neg = True
        except Exception:
            neg = False
        chk(f"{label}: unknown tag raises UnknownTag", neg)

    print("\n[3] a provider must not flatten every tag to the same thing")
    # A provider whose nine tags all resolve identically would look wired up
    # and change nothing - exactly the class of defect this module exists to
    # prevent. Edge is included and must still pass: it has only rate/pitch,
    # but it does at least vary them.
    for label, p in provs.items():
        sigs = {json.dumps(p.controls_for(t), sort_keys=True)
                for t in tp.TAGS}
        chk(f"{label}: tags produce {len(sigs)} distinct control sets",
            len(sigs) >= 5, f"only {len(sigs)} distinct - tags barely matter")

    print("\n[4] cache key reacts to text, voice, tag AND control changes")
    # Resolved dynamically: hardcoding "elevenlabs" broke this test the moment
    # the registry gained one key per narrator voice. A test that breaks when
    # a voice is added is a test nobody will keep.
    el_label = next(k for k in provs if k.startswith("elevenlabs"))
    p = provs[el_label]
    base = p.cache_signature("hello there", "normal")
    chk("same input -> same signature",
        base == p.cache_signature("hello there", "normal"))
    chk("text change -> different signature",
        base != p.cache_signature("hello therf", "normal"))
    chk("tag change -> different signature",
        base != p.cache_signature("hello there", "sad"))
    p2 = tp._eleven()
    p2.voice = "some-other-voice-id"
    chk("voice change -> different signature",
        base != p2.cache_signature("hello there", "normal"))
    # The one the brief's text+voice+tag key would have missed: retuning the
    # mapping leaves text, voice and tag identical, so a weaker key would
    # serve stale audio and the retune would appear to do nothing.
    p3 = tp._eleven()
    p3.delivery["normal"]["speed"] = 1.19
    chk("control retune -> different signature (text/voice/tag unchanged)",
        base != p3.cache_signature("hello there", "normal"))
    p4 = tp._eleven()
    p4.model = "eleven_multilingual_v2"
    chk("model change -> different signature",
        base != p4.cache_signature("hello there", "normal"))

    print("\n[5] missing key = skip, not crash (both directions)")
    victim = "ELEVENLABS_API_KEY"
    had = os.environ.pop(victim, None)
    try:
        q = tp._eleven()
        ok, why = q.available()
        chk("no key -> available() is False", ok is False, why)
        try:
            q.synthesize("x", "normal", Path("nope.mp3"))
            raised = False
        except tp.ProviderUnavailable:
            raised = True
        except Exception:
            raised = False
        chk("no key -> synthesize raises ProviderUnavailable", raised)
        os.environ[victim] = "FAKE-SENTINEL-KEY-NOT-REAL"
        ok2, _ = tp._eleven().available()
        chk("key present -> available() is True", ok2 is True)
    finally:
        os.environ.pop(victim, None)
        if had is not None:
            os.environ[victim] = had

    print("\n[6] no key value is ever written to the cache manifest")
    # Negative control with a sentinel: if a key ever leaked into a cache
    # signature or manifest, this finds it. The signature is built from the
    # resolved controls, which must never contain credentials.
    sentinel = "SENTINEL-abc123-SHOULD-NEVER-APPEAR"
    had2 = os.environ.pop("FISH_API_KEY", None)
    os.environ["FISH_API_KEY"] = sentinel
    try:
        f = tp._fish("s2.1-pro")
        # Inspect the PRE-HASH payload, not the digest. Checking a sha1 hex
        # string for a secret is a test that cannot fail, which is worse than
        # no test because it reports PASS.
        payload = f.signature_payload("some narration text", "sad")
        blob = json.dumps({k: f.controls_for(k) for k in tp.TAGS})
        chk("sentinel key absent from signature payload",
            sentinel not in payload)
        chk("sentinel key absent from resolved controls",
            sentinel not in blob)
        chk("sentinel key absent from provider repr", sentinel not in repr(f))
        # Prove the check above can actually fail: plant the key where a
        # careless mapping would put it and confirm the same assertion fires.
        leaky = tp._fish("s2.1-pro")
        leaky.delivery["sad"]["cue"] = f"[sad] {os.environ['FISH_API_KEY']}"
        chk("leak check CAN fail (negative control)",
            sentinel in leaky.signature_payload("some narration text", "sad"))
    finally:
        os.environ.pop("FISH_API_KEY", None)
        if had2 is not None:
            os.environ["FISH_API_KEY"] = had2

    print("\n[7] Edge mapping stays identical to config.TTS_DELIVERY")
    e = provs["edge"]
    drift = []
    for t in tp.TAGS:
        want = dict(config.TTS_DELIVERY.get(t, {}))
        want.setdefault("rate", config.DEFAULT_TTS_RATE)
        got = e.controls_for(t)
        if got["rate"] != want["rate"]:
            drift.append(f"{t}: rate {got['rate']} != config {want['rate']}")
    chk("no second source of truth for Edge rates", not drift, str(drift))

    print("\n[8] cost table: a None rate reports unknown, never $0.00")
    for label, pp in provs.items():
        c = pp.commerce.cost_for(20_000)
        if pp.commerce.usd_per_million_chars is None:
            chk(f"{label}: unpriced -> None (not a guess)", c is None)
        else:
            chk(f"{label}: priced -> a number", isinstance(c, float))
    # Edge really is free, and that is a measured 0.0, not a missing value.
    chk("edge is genuinely $0.00, distinct from unknown",
        provs["edge"].commerce.cost_for(20_000) == 0.0)

    print("\n[9] the three passage lines exist and carry the intended tags")
    try:
        psg = load_passage("tokyodrift2006")
        got_tags = [x["tag"] for x in psg]
        chk("passage is hook + reveal + sad",
            got_tags == ["hook", "reveal", "sad"], str(got_tags))
        w = sum(_words(x["text"]) for x in psg)
        chk(f"passage is near 60s at target WPM ({w} words)",
            45 <= w / TARGET_WPM * 60 <= 75,
            f"{w/TARGET_WPM*60:.1f}s")
    except SystemExit as e:
        chk("passage loads", False, str(e))

    print("\n" + "=" * 60)
    if fails:
        print(f"RESULT: {len(fails)} SELF-TEST FAILURE(S)")
        for f_ in fails:
            print(f"  - {f_}")
        return 1
    print("RESULT: ALL SELF-TESTS PASS")
    return 0


SWEEP_TEXT = ("He built the car from the block up, and he never once said "
              "why he did it.")


def tag_sweep(label: str) -> int:
    """Read ONE fixed sentence under all nine tags and measure each.

    The three-line passage cannot answer "does the tag change the delivery",
    because each line is a different text: line 60 <reveal> came out at 221.9
    WPM against line 184 <sad> at 196.9, which looks like reveal is the faster
    tag when it is actually just shorter words. Holding the text constant is
    the only way to see what the tag itself does - and for Edge, the spread it
    produces is the measurement of how little rate and pitch can act.
    """
    p = tp.all_providers()[label]
    ok, why = p.available()
    if not ok:
        print(f"{label} unavailable: {why}")
        return 1
    vdir = Path.cwd() / "voice_test" / "_sweep"
    vdir.mkdir(parents=True, exist_ok=True)
    w = _words(SWEEP_TEXT)
    print(f"\nTag sweep - {label} / {p.voice}, same {w}-word sentence:\n")
    print(f"  {'tag':<9}{'sec':>7}{'WPM':>8}   controls")
    rows = []
    for t in tp.TAGS:
        out = vdir / f"{label}_{t}.mp3"
        _, dur = tp.synthesize_cached(p, SWEEP_TEXT, t, out, vdir)
        wpm = w / dur * 60 if dur else 0.0
        rows.append((t, dur, wpm))
        print(f"  {t:<9}{dur:7.2f}{wpm:8.1f}   "
              f"{json.dumps(p.controls_for(t), sort_keys=True)}")
    wpms = [r[2] for r in rows]
    spread = max(wpms) - min(wpms)
    print(f"\n  WPM spread across all nine tags: {spread:.1f} "
          f"({min(wpms):.1f} - {max(wpms):.1f})")
    print(f"  mean {sum(wpms)/len(wpms):.1f} WPM")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="tokyodrift2006")
    ap.add_argument("--tag-sweep", metavar="PROVIDER", default=None,
                    help="read one fixed sentence under all nine tags")
    ap.add_argument("--only", nargs="*", default=None,
                    help="restrict to these provider labels")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.tag_sweep:
        return tag_sweep(a.tag_sweep)
    return run(a.project, a.only)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
