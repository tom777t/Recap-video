"""Censor coverage across the WHOLE finished video - not just bound lines.

WHY THIS MODULE EXISTS
----------------------
Blur used to be resolved in exactly one place: the clip loop, keyed off a draft
line's (clip_start, clip_end). That covers footage a LINE is bound to and
nothing else. But the finished video also contains footage that no line owns:

  * the intro MONTAGE (pick_moments chooses catalogued shots freely)
  * the FILM-INTRO block (a slice of the film's opening plays under the facts)
  * montage segments inside a line (`montage: [...]`)
  * pool / B-roll windows resolved at render time

A shot flagged `censor` in shots.json that reached the final cut through any of
those paths rendered COMPLETELY UNBLURRED, and the only report was a line
saying "N flagged shot(s) have NO line bound - nothing will blur for them",
which reads like an all-clear. It is the opposite: "no line bound" is fine ONLY
if the shot is also absent from the video. If the footage is in the video and
unblurred, that is a publish-blocking failure.

So this module keeps two lists and compares them:

  flagged_shots(pdir)  -> every shot shots.json says must be blurred
  UsedFootage          -> every source window that ENTERS the final video,
                          each tagged with whether it will be blurred

audit() classifies each flagged shot as:

  BLURRED          - in the video, censor applied            (fine)
  NOT IN VIDEO     - no overlap with any used window         (fine, informational)
  USED UNBLURRED   - in the video with no censor applied     (ERROR - stop)

and the caller stops the render on the third class.

Prevention comes first, though: the intro paths pick their own footage, so they
ASK this module to avoid flagged windows (avoid_windows / is_flagged) rather
than relying on the audit to catch them afterwards.
"""
from __future__ import annotations

from pathlib import Path

from rich.console import Console

console = Console()

# Overlap below this many seconds is treated as a touch, not a use: shot
# windows and clip windows are both authored by hand and routinely abut by a
# frame or two. A real appearance of flagged footage is far longer than this.
MIN_OVERLAP_SEC = 0.35


def _pt(ts) -> float:
    from pipeline.draft import parse_ts
    return parse_ts(ts)


# --------------------------------------------------------------------------- #
# What must be blurred
# --------------------------------------------------------------------------- #
def flagged_shots(pdir: Path) -> list[dict]:
    """Every shots.json shot with censor != none, as
    {key, a, b, level, region}. Sorted by start time.

    Reads shots.json only; shots_machine.json is a catalogue draft and does not
    carry reviewed censor decisions.
    """
    import json
    sp = Path(pdir) / "shots.json"
    if not sp.exists():
        return []
    try:
        sd = json.loads(sp.read_text(encoding="utf-8-sig"))
    except Exception as e:
        console.print(f"[yellow]Censor: could not read shots.json ({e}).[/]")
        return []
    out = []
    for s in sd.get("shots", []):
        cs, ce = s.get("clip_start"), s.get("clip_end")
        level = str(s.get("censor", "none") or "none")
        if level == "none" or not cs or not ce:
            continue
        try:
            a, b = _pt(cs), _pt(ce)
        except Exception:
            continue
        out.append({"key": (cs, ce), "a": a, "b": b, "level": level,
                    "region": s.get("censor_region"), "id": s.get("id")})
    out.sort(key=lambda r: r["a"])
    return out


def criteria_problems(pdir: Path, frame_w: int = 0, frame_h: int = 0
                      ) -> list[str]:
    """Flags that break the censor policy. Empty list = clean.

    Two rules, both learned from this film's 14 flags:
      * a flag must carry a REGION. All 14 had none, so all 14 would have been
        full-frame blurs - indistinguishable from losing the shot, while still
        costing the runtime. With no region the answer is to swap the shot.
      * a region covering most of the frame is a full-frame blur with extra
        steps, so it is reported as one.
    """
    import config
    out = []
    need_region = bool(getattr(config, "CENSOR_REQUIRE_REGION", True))
    allow_full = bool(getattr(config, "CENSOR_ALLOW_FULL_FRAME", False))
    cap = float(getattr(config, "CENSOR_REGION_MAX_FRACTION", 0.40))
    for f in flagged_shots(pdir):
        reg = f.get("region")
        if not reg:
            if need_region and not allow_full:
                out.append(
                    f"{f['key'][0]} ({f['level']}) has NO censor_region, so it "
                    f"would blur the whole frame. Either give it the box that "
                    f"covers the content, or swap the line to a different shot "
                    f"- a full-frame blur loses the shot anyway.")
            continue
        if frame_w and frame_h:
            try:
                frac = (int(reg["width"]) * int(reg["height"])) / float(
                    frame_w * frame_h)
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                continue
            if frac > cap:
                out.append(
                    f"{f['key'][0]} region covers {frac:.0%} of the frame, "
                    f"over the {cap:.0%} cap - that is a full-frame blur with "
                    f"extra steps. Tighten the box or swap the shot.")
    return out


def is_flagged(flagged: list[dict], a: float, b: float) -> dict | None:
    """The first flagged shot overlapping [a, b) by more than MIN_OVERLAP_SEC."""
    for f in flagged:
        if min(b, f["b"]) - max(a, f["a"]) > MIN_OVERLAP_SEC:
            return f
    return None


def avoid_windows(flagged: list[dict], windows: list, label: str) -> list:
    """Drop every window that overlaps a flagged shot, and SAY which.

    Used by the intro montage, which has free choice of footage: there is no
    reason to put footage that needs blurring into a montage when any other
    catalogued shot would do. `windows` is a list of (a, b) tuples.
    """
    keep, dropped = [], []
    for w in windows:
        a, b = float(w[0]), float(w[1])
        hit = is_flagged(flagged, a, b)
        (dropped.append((w, hit)) if hit else keep.append(w))
    if dropped:
        console.print(f"[yellow]Censor:[/] {label} skipped {len(dropped)} "
                      f"flagged window(s) - it picks its own footage, so it "
                      f"picks footage that needs no blur:")
        for w, hit in dropped[:6]:
            console.print(f"[yellow]      {w[0]:.1f}-{w[1]:.1f}s overlaps "
                          f"{hit['key'][0]} ({hit['level']})[/]")
    return keep


def safe_window(flagged: list[dict], want_len: float, lo: float, hi: float,
                label: str) -> tuple[float, float] | None:
    """A [start, start+want_len) window inside [lo, hi) touching no flagged shot.

    For the FILM-INTRO block, which plays a slice of the film's opening under
    the intro facts. If the film opens on flagged footage, slide past it rather
    than blurring the whole opening (or, worse, shipping it clear).
    """
    want = max(0.5, float(want_len))
    cands = [float(lo)] + [f["b"] + 0.05 for f in flagged
                           if float(lo) <= f["b"] < float(hi)]
    for st in sorted(cands):
        if st + want > float(hi):
            break
        if is_flagged(flagged, st, st + want) is None:
            if st > float(lo):
                console.print(f"[yellow]Censor:[/] {label} starts at "
                              f"{st:.1f}s, not {float(lo):.1f}s - the opening "
                              f"footage is flagged for blur.")
            return st, st + want
    console.print(f"[yellow]Censor:[/] {label} could not find {want:.1f}s of "
                  f"unflagged footage in {float(lo):.1f}-{float(hi):.1f}s.")
    return None


# --------------------------------------------------------------------------- #
# What is actually in the video
# --------------------------------------------------------------------------- #
class UsedFootage:
    """Every source window that enters the final video.

    add() is called from each footage path (clip loop, montage, pool, intro
    montage, film-intro) with `blurred` set to whether a censor filter is being
    applied to that window. Paths that cannot blur at all pass blurred=False -
    they must then AVOID flagged footage, and the audit proves they did.
    """

    def __init__(self):
        self.items: list[dict] = []

    def add(self, a: float, b: float, source: str, blurred: bool,
            line_id=None) -> None:
        try:
            a, b = float(a), float(b)
        except (TypeError, ValueError):
            return
        if b <= a:
            return
        self.items.append({"a": a, "b": b, "source": source,
                           "blurred": bool(blurred), "line_id": line_id})

    def overlaps(self, a: float, b: float) -> list[dict]:
        return [u for u in self.items
                if min(b, u["b"]) - max(a, u["a"]) > MIN_OVERLAP_SEC]

    def __len__(self) -> int:
        return len(self.items)


# --------------------------------------------------------------------------- #
# The audit
# --------------------------------------------------------------------------- #
def audit(flagged: list[dict], used: UsedFootage) -> dict:
    """Classify every flagged shot. Returns
    {blurred: [...], unused: [...], exposed: [(shot, [uses])]}.

    `exposed` is the publish-blocking class: the footage is in the finished
    video and nothing blurs it.
    """
    blurred, unused, exposed = [], [], []
    for f in flagged:
        hits = used.overlaps(f["a"], f["b"])
        if not hits:
            unused.append(f)
        elif all(h["blurred"] for h in hits):
            blurred.append(f)
        else:
            exposed.append((f, [h for h in hits if not h["blurred"]]))
    return {"blurred": blurred, "unused": unused, "exposed": exposed}


def report(result: dict, used: UsedFootage) -> bool:
    """Print the audit. Returns True if the render may continue.

    The old message said "N flagged shot(s) have NO line bound - nothing will
    blur for them", which conflated two opposite outcomes. This separates them.
    """
    n = (len(result["blurred"]) + len(result["unused"])
         + len(result["exposed"]))
    if not n:
        return True
    console.print(f"[cyan]Censor audit:[/] {n} flagged shot(s) vs "
                  f"{len(used)} footage window(s) in the final video - "
                  f"{len(result['blurred'])} blurred, "
                  f"{len(result['unused'])} not in the video, "
                  f"{len(result['exposed'])} EXPOSED")

    if result["unused"]:
        console.print(f"[dim]  {len(result['unused'])} flagged shot(s) are not "
                      f"used anywhere in the video - nothing to blur (fine):[/]")
        for f in result["unused"][:6]:
            console.print(f"[dim]      {f['key'][0]} -> {f['key'][1]} "
                          f"({f['level']})[/]")

    if result["exposed"]:
        console.print(f"[red]  {len(result['exposed'])} flagged shot(s) are IN "
                      f"THE VIDEO AND UNBLURRED. This is not a warning:[/]")
        for f, hits in result["exposed"][:10]:
            console.print(f"[red]      {f['key'][0]} -> {f['key'][1]} "
                          f"({f['level']}) appears via:[/]")
            for h in hits[:4]:
                _ln = f" line {h['line_id']}" if h["line_id"] is not None else ""
                console.print(f"[red]          {h['source']}{_ln} "
                              f"{h['a']:.1f}-{h['b']:.1f}s[/]")
        console.print("[red]  Fix: let the blur resolve for these windows, or "
                      "move the footage out of the cut. Rendering would "
                      "publish unblurred flagged content.[/]")
        return False
    return True
