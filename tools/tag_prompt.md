# tag_prompt.md — instructions for a single-shot tagging subagent

You tag **ONE** shot. You have no memory of any other shot and you do not need
one. Everything you need is below.

The caller gives you: `PROJECT`, `SHOT` (e.g. `shot07`), and `FRAMES` (a list of
image paths).

---

## 1. Blindness — non-negotiable

Do **NOT** read any of these. They contain the answers:

- `projects/<PROJECT>/shots.json`
- `projects/<PROJECT>/_vision_truth.json`
- `projects/<PROJECT>/VISION_EVAL.md`
- any file under `projects/<PROJECT>/` ending in `_truth.json`

You **may** read `projects/<PROJECT>/names.json` — cast list only, no answers.

If you cannot identify a character from the frames, write `(khong ro)`. An
honest `(khong ro)` is correct; a name obtained by reading an answer file is a
false positive that also breaks the eval.

> ⚠️ **UNDER RE-VERIFICATION, 2026-09-05.** Cast-list access was removed for
> about ten minutes on evidence that turned out to be produced by a broken
> check, and has been restored. See below. Do not remove it again without
> redoing the verification correctly.

### The A/B result — solid, and NOT by itself grounds for removal

55 Bad Genius shots where the human catalogue left `chars` empty, tagged twice —
once with `names.json` available, once without. Identical shots, identical
frames, one difference:

```
name-instances in BOTH arms   :  0
ONLY with names.json          : 39   (Lynn 19, Bank 9, Pat 6, Grace 5)
ONLY without                  :  0
```

Without the list the agent named **nobody, on any shot**. That part is solid:
the list is the sole source of every name.

**But "sole source" is not "invented", and conflating the two was an error.**

### The verification that was wrong

Ten shots were checked against the frames by eye and three were called plainly
fabricated — a wide classroom of backs of heads tagged `Lynn`, a hall of ~60
distant students tagged `Bank`, a lobby with a signboard tagged `Lynn, Grace`.

**All three verdicts were wrong.** Each shot was judged from ONE frame of a
multi-frame window, and these windows **span cuts**:

| shot | frame I looked at | frame I did not |
|---|---|---|
| `shot105` | `_02` school lobby | `_00` **two schoolgirls on a rooftop, faces clear** |
| `shot008` | `_01` wide classroom, backs of heads | `_00` **a woman alone at a table in a dark room, face centred** |
| `shot049` | `_02` wide hall, distant students | `_00` and `_03` **a young man's face, one in extreme close-up** |

In every case the agent was describing the part of the window I had not looked
at. The scenes were real and the faces were there.

> A shot window is **not** a single image. Judging a multi-frame description
> against one frame measures the sampler, not the description. Any future check
> of `chars` or `action` must look at **every frame the tagger was given**.

### Where that leaves it

`names.json` access is **restored**. The A/B numbers stand, but they only show
the list is load-bearing — not that what it produces is false. The honest
current state is that the accuracy of those 39 names is **unmeasured**, because
the measurement was invalid.

The cost of removal is real and known: the control arm produced `(khong ro)`
every time, never a better guess. `shot063` (tight close-up of a schoolgirl's
face, tagged `Lynn`) is very likely correct and would have been lost.

The concern that motivated the test still stands and is still unresolved:
`chars` and `claim.subject` are written by the same agent, so `binding_audit`
compares a fabrication against itself and passes.

## 2. Read the frames

Use the `Read` tool on each path in `FRAMES`. They are JPEGs from a single
continuous shot, in time order.

## 3. `depicts` — TWO axes, and you owe one label from each side

| axis | meaning | labels |
|---|---|---|
| **VISIBLE** | what the camera literally shows | `action`, `dialogue`, `establishing`, `montage`, `reaction`, `transition` |
| **STORY** | what the scene does for the plot | `aftermath`, `discovery`, `emotion`, `reveal`, `setup` |

**You MUST include at least one VISIBLE label.** You MAY add STORY labels.

Why this rule exists: the vocabulary mixes two different questions, and an
answer made only of STORY labels scores zero on the visible axis even when it is
substantively right. Measured 2026-09-05: without this instruction, three of
nine shots came back STORY-only.

Pick the VISIBLE label for what **dominates the frames**:
- people talking to each other → `dialogue`
- physical movement driving the moment → `action`
- a place/scale shot orienting the viewer → `establishing`
- a face absorbing something → `reaction`

Do not pad. Two or three labels total is normal.

## 4. `chars`

Named characters **visible in these frames**. One actor may play more than one
named role — use the name appropriate to the scene. Use `(khong ro)` for a
person you cannot name. Do not list someone who is only spoken about.

## 4b. `censor` — explicit-content level

Return a `censor` value on **every** shot. Default `none`.

Decide by **frame coverage and legibility**, NOT by content type. Content type
alone has produced wrong tags in practice.

| what you see | level |
|---|---|
| nothing explicit | `none` |
| incidental background detail, not the subject, not readable | `blur_light` |
| ~a third of the frame or more, **or** it IS the subject of the shot | `blur` |
| fills the frame, or is the point of the shot | `blur_heavy` |

**Legibility raises the level and never lowers it.** Anything **readable**
(text, a magazine cover, a screen) or **anatomically identifiable** must NOT be
left at `blur_light`. Measured 2026-08-19: a pornographic magazine cover at
roughly a third of frame was tagged `blur_light`, and after boxblur=15 it was
still plainly legible in the rendered file. `blur_light` is for incidental
background detail only — **if the thing matters enough to tag, it needs `blur`
or higher.**

Tag for: nudity, sexual acts, readable explicit images, blood/gore with visible
wounds, active drug-use specifics, self-harm specifics.

Do NOT tag for: implied or off-screen violence; action without graphic injury;
violence already obscured by darkness or silhouette; stylised/cinematic
violence with no gore detail.

### The S7.0 flag — prefer re-binding over blurring

Blur is the **last** resort. A blurred patch tells the viewer exactly where to
look and what is hidden, and damages the shot for everyone.

You are tagging one shot and cannot see the others in its beat, so you cannot
perform the re-bind yourself. What you CAN do is say it is available. When you
tag anything other than `none`, also set:

```
"censor_note": "<one clause: what the explicit element is, roughly what
                fraction of frame, and whether it is the POINT of the shot
                or incidental to it>"
```

That note is what lets a later pass apply S7.0 — re-bind the line to a clean
shot in the same beat — instead of blurring. A shot whose explicit element is
incidental is a re-bind candidate; one where it is the point is not.

**When unsure, tag UP, not down.** A shot wrongly tagged `blur` costs one
slightly degraded frame. A shot wrongly tagged `none` ships explicit content.
These are not symmetric and must not be traded off against each other.

## 5. `action`

**One sentence** describing what is on screen. Frame-caption register is correct
here — this field records *what is in the shot*, not what it means.

Per rule I1 in `docs/RULES.md`, this text is **never** the source for narration
prose; it exists so a later pass knows what footage is available. Do not write
narration. Do not editorialise.

## 6. Write the result, then return

Write this JSON to `projects/<PROJECT>/shots.json.d/<SHOT>.json`
(create the directory if missing):

```json
{
  "shot": "shot07",
  "depicts": ["dialogue", "establishing"],
  "chars": ["Teddy Daniels", "Chuck Aule"],
  "censor": "none",
  "action": "One sentence."
}
```

`censor` is required on every shot. When it is not `none`, add `censor_note`:

```json
{
  "shot": "shot12",
  "depicts": ["action"],
  "chars": ["(khong ro)"],
  "censor": "blur",
  "censor_note": "magazine cover, readable, ~1/3 of frame, it is what the shot is about",
  "action": "One sentence."
}
```

Then your **entire final message** must be exactly:

```
ok <SHOT>
```

Nothing else. The caller has a limited context and does not want the content —
the file is the deliverable. If you failed, return `FAIL <SHOT> <short reason>`
and write no file, so the assembler can tell a gap from a bad answer.
