# `censor` in the tagging loop — SUPERVISED ONLY

Added to `tools/tag_prompt.md` on 2026-09-06 and measured the same day.
**Status: usable, but every non-`none` and every `none` on a shot that could
plausibly carry content must be read by a human before render.**

---

## The criterion, set before the run

> A miss on explicit content is not offset by any number of correct `none`s.
> If there is even one miss on explicit content, the field is not safe to use
> unreviewed.

Asymmetric by construction: a wrong `blur` costs one degraded frame; a wrong
`none` ships explicit content.

## The result — superbad2007, all 183 shots, blind

Human catalogue carries `censor` on all 183; 11 are `blur`.

```
flagged by both          9 / 11
MISSES (human flagged, machine none)   2  -> one TRUE, one UNTESTED
EXTRAS (machine flagged, human none)   2
machine tagged HIGHER than human       5
machine tagged LOWER  than human       0     <- the dangerous direction
```

Every nudity / sexual-content shot was caught: `shot009` magazine cover,
`shot017` porn trailer, `shot029`+`shot031` drawings, `shot152` undressing,
`shot154` sex, `shot155` dressing, `shot156` post-sex, `shot162` torch.
The canonical failure — the `shot009` cover that **shipped legible** at
`blur_light` — came back `blur_heavy`, two levels above where it shipped.

## ⚠️ The one TRUE miss: `shot114` — and why it matters more than the count

```
shot114  01:08:00   human=blur   machine=none
         "Close on Seth's trouser leg: the dark red smear Jacinda left on him"
```

Checked by eye: the stain is **plainly visible** in the supplied frame
`shot114_01` (01:08:05), a dark red smear on grey trousers, and it is the
subject of the shot. The machine saw it and returned `none`.

**The failure mode is reasoning from CONTENT TYPE rather than COVERAGE.**
Menstrual blood on clothing is not "gore with visible wounds", so it did not
match a listed category, and the model answered from the category list instead
of from the two questions S7.1 actually asks (how much of the frame, is it
legible/identifiable).

> **S7.1 was rewritten in August 2026 precisely to stop content-type reasoning**
> — after a pornographic magazine cover was tagged `blur_light` because the old
> wording permitted "light nudity (partial, non-sexual context)". The rule fix
> worked for the human catalogue. **It did not transfer to the model.** Writing
> the corrected rule into the prompt was not sufficient to change how the model
> decides; it still fell back to "is this in the list of explicit things".
>
> A rule that has been fixed in the guide is not thereby fixed in the tagger.

## `shot030` — UNTESTED, not passed

```
shot030  00:18:42   human=blur   machine=none
         "young Seth hunched over the notebook, drawing through the whole class"
```

**This is not a field result.** All three supplied frames were opened:
`18:40` is the present-day cafeteria (before the window begins), `18:45` is
Seth from behind, `18:50` has a pencil box covering the page. **The notebook
appears in none of them.** The machine answered correctly for what it was shown.

Recorded as **untested**. It must not be counted as a pass, and it must not be
counted as a miss.

> Generalises: an explicit element visible for less than one frame-step can fall
> entirely between sampled frames, and the tagger will honestly return `none`.
> The frame step is therefore a censor-safety parameter, not just a coverage one.

## Resolution caveat — the figure is a CEILING on the miss rate, not the rate

superbad2007 has no `source.mp4`. Frames were recovered by cropping cells out of
the `frames/overview` contact sheets: **320x180 native**, upscaled to 640x360.
The real pipeline tags at 768px.

**Low resolution biases toward misses.** `shot154` and `shot009` were
unambiguous even at 320x180, so it is not fatal — but the true-miss rate at
768px is **unmeasured** and is probably lower than 1-in-11.

### Attempted re-run at 768px — NOT POSSIBLE

A Superbad source was recovered at `D:\Downloads\...Superbad (2007)...mp4`
(0.74 GB, 1280x692). It is **a different cut**:

```
recovered source        7120s = 118.7 min   (unrated)
catalogue last clip_end 6812s = 113.5 min   (theatrical)
```

Spot checks: at `00:04:45` the source shows the magazine rack, seconds from the
catalogue's held-magazine frame — early offset is small. At `01:08:05` the
source shows Seth walking at the party, and the trouser-stain insert is not
within +/-60s. **The offset drifts**, which is the signature of inserted scenes,
not a constant shift.

Re-testing at 768px would require re-deriving all 183 timestamps against the
unrated cut. Not done. **The resolution caveat therefore stands unresolved.**

## What supervision means in practice

1. Read **every** non-`none` tag and its `censor_note` before render.
2. Read the `none`s on any shot whose `action` text mentions a body, a screen,
   a magazine, a bed, blood, or a bathroom.
3. Treat `blur_light` from a machine tag as suspect by default — S7.1's measured
   limit says if it mattered enough to tag, it needs `blur` or higher.
4. `recap.py render` reports how many LINES render censored, not how many shots
   carry a flag. Read that number (TAGGING_GUIDE S7, "verify the outcome").
