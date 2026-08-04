"""
Build burned-in captions as a styled .ass file, synced to narration timing.

We use ASS (not plain SRT) so we control font, outline, shadow and wrapping for
readability — exactly the 'clear, readable captions' requirement.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import config


def _wrap(text: str) -> str:
    """Wrap to MAX_CHARS_PER_LINE, at most MAX_LINES lines, ASS newline = \\N."""
    wrapped = textwrap.wrap(
        text, width=config.CAPTION_MAX_CHARS_PER_LINE,
        break_long_words=False, break_on_hyphens=False)
    if len(wrapped) > config.CAPTION_MAX_LINES:
        head = wrapped[:config.CAPTION_MAX_LINES - 1]
        tail = " ".join(wrapped[config.CAPTION_MAX_LINES - 1:])
        wrapped = head + [tail]
    wrapped = [w.replace("{", "(").replace("}", ")") for w in wrapped]
    return "\\N".join(wrapped)


def _ass_time(seconds: float) -> str:
    cs = int(round(seconds * 100))
    h = cs // 360000
    m = cs % 360000 // 6000
    s = cs % 6000 // 100
    c = cs % 100
    return f"{h:d}:{m:02d}:{s:02d}.{c:02d}"


def build_ass(timeline: list[dict], out_path: Path) -> Path:
    """
    timeline: list of dicts with keys: start, end, text  (seconds, absolute,
    on the FINAL narration timeline).
    """
    bold = config.CAPTION_BOLD
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1920\n"
        "PlayResY: 1080\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Recap,{config.CAPTION_FONT},{config.CAPTION_FONT_SIZE * 2},"
        f"{config.CAPTION_PRIMARY_COLOUR},&H000000FF,{config.CAPTION_OUTLINE_COLOUR},"
        f"{config.CAPTION_BACK_COLOUR},{bold},0,0,0,100,100,0,0,1,"
        f"{config.CAPTION_OUTLINE},2,80,80,{config.CAPTION_MARGIN_V},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )

    animate = getattr(config, "CAPTION_ANIMATE", True)
    fade_ms = getattr(config, "CAPTION_FADE_MS", 120)

    events = []
    for item in timeline:
        start = _ass_time(item["start"])
        end = _ass_time(item["end"])
        text = _wrap(item["text"])
        if animate:
            anim = (f"{{\\fad({fade_ms},{fade_ms})\\fscx92\\fscy92\\t(0,"
                    f"{fade_ms},\\fscx100\\fscy100)}}")
            text = anim + text
        events.append(f"Dialogue: 0,{start},{end},Recap,,0,0,0,,{text}")

    out_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return out_path
