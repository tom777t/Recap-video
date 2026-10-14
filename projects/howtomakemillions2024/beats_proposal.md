# How to Make Millions Before Grandma Dies (2024) - beats proposal

depth_target: video_essay
Target: 18-22 min

Source runtime: 7607.4s (126.8 min). Transcript: 1456 segments, last at 7473.3s.
Detected scene cuts: 616 (4.9/min - the lowest of any film catalogued here;
Superbad is 16.3/min). The film holds shots. Catalogue the holds as moments.

Sources read before cataloguing (A7): Wikipedia **Plot** and **Cast** only.
Production, Themes, Reception, Accolades and Legacy were not opened.
Where the plot summary and the frames disagree, **the frames win**.

The transcript is Whisper `--translate`, Thai audio straight to English. It is
usable to locate scenes and to check who speaks. It is NOT usable to establish
what happens. Probed: one run of 7 identical consecutive lines (a hallucination
under silence); the rest is localised noise rather than a general pattern.


## Naming

`names.json` holds 13 characters. Canonical forms used in `chars`:

| Use in `chars` | Notes |
|---|---|
| `M` | the lead. **One letter.** |
| `Amah Saejiu` | listed twice in names.json as `Mengju Amah Saejiu` and `Amah Saejiu`. Use `Amah Saejiu` - the bare `Amah` is NOT a canonical entry and validation rejected it. Not added to names.json to make it pass (RULES B8: never edit the name list to quiet a check). |
| `Sew` | M's mother, Amah's daughter |
| `Kiang` | Amah's eldest son, wealthy |
| `Soei` | Amah's younger son, gambling debt |
| `Mui` | M's cousin, carer of the paternal grandfather |
| `Agong` | M's paternal grandfather |

**`M` is not checked by any gate.** The `[NAME]` guard scans `[A-Z][a-z]{2,}` -
three characters minimum - so a one-letter name is never read: not validated,
not flagged, invisible. Widening the pattern was measured and makes it worse
(with `m` known, every stray capital passes). `recap.py draft` now prints an
explicit "one-letter name(s) are NOT checked" warning. Every line naming M
needs a human eye. See docs/TAGGING_GUIDE.md.


## A8 - zone split

**SETUP zone** - effectively the whole film, from the Qingming opening through
the caregiving, the family manoeuvring, the house being put up for sale and
Amah's decline. Unusually for this pipeline, ~95% of the runtime is plainly
tellable.

**REVEAL zone** - narrow, and at the very end.

**CORRECTED 2026-08-23 (pass 6).** This paragraph used to say "the house sale",
which pass 5's plant audit could find no shot for and provisionally called an
unsupported claim. That verdict was wrong in one direction and the wording was
wrong in another. Resolved below under "A8 house-sale claim - resolved".


## Reveal-map (PROTECTED)

| # | Beat | Why protected |
|---|---|---|
| R1 | **The passbook and the childhood flashback** (B54-B55, `clip:01:52:32.3` and `clip:01:53:28.0`): Amah had been setting money aside in M's name since he was a child, from when he said he wanted to buy her a new house | Unknown to the audience AND to M. Lands last. Retroactively reframes every mercenary thing M did, and the film's whole title. This is the film's one real surprise. |
| R2 | Amah nursed her own parents until they died and inherited nothing - surfaced at her brother's house when he refuses her the money | Weaker: recontextualises rather than surprises. Protect the *placement*, not the fact - do not let the recap state it before the brother scene plays. |

R1 is the only beat where early disclosure destroys something irreplaceable.

### R1 - CORRECTED 2026-08-23 (pass 6): what the film actually shows

This row used to read "The bank call". **There is no bank call on screen.** The
entry was written from the plot summary before the footage was catalogued, and
it named a scene the film does not contain. Corrected against the frames:

| What R1 is made of | Shot | Verified |
|---|---|---|
| **The object.** A green savings passbook held open - BANK OF SIAM, A/C NO. 826-006-1525-8, a name filled in by hand. The account number is legible on screen. | `clip:01:52:32.3` | `frames/zoom/01-52-33` |
| **The memory.** Amah years younger in a full dark perm, walking a small boy in school uniform down a lane, over audio about buying her a new house. | `clip:01:53:28.0`, `clip:01:53:58.0` | `frames/zoom/01-53-34` |
| **The connective tissue.** M outside with a phone to his ear, before and after the flashback. He is on a phone; nothing of the call is dramatised, and no second party is ever seen or shown. | `clip:01:52:40.1`, `clip:01:54:13.0` | page 038-039 |

**The reveal is an object and a memory, not a conversation.** The film withholds
the sentence and lets the passbook and the child carry it - the same
show-don't-tell move recorded for `clip:01:06:26.3` (the bald reveal).

**MANDATORY for the draft.** A line written as *"then the bank calls him and he
finds out..."* would be **narrating something absent** - a scene that exists in
the plot summary and not in the footage. That is an S4 violation (audio without
video) of the precise kind the IT 2017 regression cases were about, and it would
be committed on the single most important beat in the recap. Two consequences:

- Do NOT write the reveal as a phone call, a conversation, or a disclosure by a
  third party. There is no bank clerk, no voice on the line, no counter.
- DO write it against what is on screen: he is going through her things, he
  finds a savings book with his own name in it, and he remembers.

The phone shots are bindable, but only for what they show: a young man standing
outside on his phone. They will not support a claim about what was said.


## DELIBERATELY NOT PROTECTED

Recorded per H1 so a later editor does not "helpfully" add these to the
reveal-map. Both are mechanically reveals - a hidden truth becoming visible -
and both fail H1's tests.

| Beat | Mechanically a reveal because | Why NOT protected |
|---|---|---|
| **Amah's cancer diagnosis** (late-stage colorectal, ~1 year, concealed from her by the family) | A hidden truth, actively concealed, disclosed later to the person it concerns | **The title states it before the audience presses play.** *How to Make Millions Before Grandma Dies* tells you she is dying in the title card. Protecting it misreads the film. It also fails H1's second test: it is a reveal to the *characters*, not the audience - the audience is told before Amah is. |
| **Amah's death** | The event the whole structure moves toward | **The title states it before the audience presses play.** Same reason, more bluntly. The film is not asking whether she dies; it is asking what M becomes while she does. |

H1's rule, applied: *does a viewer who has not seen the film know this before
pressing play, and do they know it before the characters do?* Both answer yes
on at least one. Neither enters the reveal-map.

Consequence for the hook (H2): the pull here is not surprise, so do not build a
thriller-shaped hook. The hook can state the premise flatly - a grandson
volunteers to nurse his dying grandmother for the inheritance - because the
tension is moral, not informational.


## Beats

Filled in per pass as the catalogue is verified. Nothing is listed here that
has not been seen in the frames.

### Act 1 (pass 1: pages 1-11, 00:00:00 - 00:33:00) - COMPLETE

57 shots, 16 beats, 1885.4s of 1980s covered (95.2%). Every entry verified
against the frame montages before writing. No beat has fewer than 2 shots.

| Beat | Window | Content |
|---|---|---|
| B01 | 00:00:52 - 00:04:59 | Qingming grave visit. Amah works the ritual; M sits apart on his phone. |
| B02 | 00:04:59 - 00:05:58 | Amah taken into hospital by wheelchair; family talk at the kerb. |
| B03 | 00:05:58 - 00:08:36 | M's life: the gaming rig, the stream, Sew pushing at him. |
| B04 | 00:08:36 - 00:10:28 | Agong dying at home. Mui does the bed care alone while M watches. |
| B05 | 00:10:33 - 00:12:13 | Agong's funeral; the paper offerings burning at night. |
| B06 | 00:12:13 - 00:14:29 | Bangkok. M crosses the city to the old neighbourhood. Title card. |
| B07 | 00:14:29 - 00:16:00 | M arrives at the green gate; first meeting with Amah in the shophouse. |
| B08 | 00:16:00 - 00:18:00 | The trackside stall; first meal together; Amah lies down among her medicines. |
| B09 | 00:18:00 - 00:24:05 | M reheats food, stands at the shrine, then takes a box across town to Mui at her hotel. The plan is made. |
| B10 | 00:24:05 - 00:25:58 | M packs, shops with Sew, moves in. Amah sets her terms in the gateway. |
| B11 | 00:25:58 - 00:27:57 | The cash tin, item by item. M explores the shophouse alone. |
| B12 | 00:27:57 - 00:28:45 | Stairs; night - Amah asleep on the daybed, M settling a cover over her. **First silence beat (6s).** |
| B13 | 00:28:45 - 00:30:02 | Dawn on the tracks; Amah and M work the congee pots together. |
| B14 | 00:30:02 - 00:31:02 | The paper-goods shop; Amah crosses the road alone and M takes her arm. |
| B15 | 00:31:02 - 00:31:59 | M washing up; Amah puts something into his hands at the cabinet. |
| B16 | 00:31:59 - 00:33:00 | Amah out in the lane, M crouched to her eye level. **Second silence beat (5s).** |

Two silence beats tagged (S9): B12 at 6s and B16 at 5s. Both are held two-shots
with no dialogue, and both are late enough in the act that the audience is
invested. They are NOT back to back (B12, then three beats, then B16). Each
still needs a matching silence DRAFT LINE at scripting stage or the render will
drop them.

**Not identifiable at overview resolution**, left out of `chars` rather than
guessed: the man holding the phone at the graveside (00:03:30) and the woman in
black at the funeral (00:10:58). Both are recorded in the shot `action` text as
unidentified. Use `recap.py frames --zoom` before naming either in a draft line.

### Act 2 (pass 2: pages 12-22, 00:33:00 - 01:06:00) - COMPLETE

51 shots, 12 beats (B17-B28), 1951.7s of 1980s covered (98.6%).

| Beat | Window | Content |
|---|---|---|
| B17 | 00:33:00 - 00:36:20 | The weekly family meal. Talk turns to Amah's care; M eats alone on the stairs. |
| B18 | 00:36:25 - 00:39:30 | The public pool. Amah and Sew talking in the water; M watching from the side. |
| B19 | 00:39:30 - 00:42:00 | Night. Car park, then a packed outpatient hall; Amah on a drip; M breaking down behind glass. |
| B20 | 00:42:00 - 00:45:00 | Amah's bedroom. M listening to her chest; the two of them asleep under the net; M waking in the dark. |
| B21 | 00:45:00 - 00:47:00 | **The empty-room hold** - 56s, one shot, nobody in frame. Then Amah asleep upright in a waiting room. |
| B22 | 00:47:00 - 00:50:50 | Care escalates: the stairs, the stove, washing her at the basin through the grille, the shrine, the bathroom, the laundry. |
| B23 | 00:50:50 - 00:53:47 | A male visitor makes a fuss of Amah in the lane. Night market. The drive out. |
| B24 | 00:53:47 - 00:56:58 | Kiang's house: the fitted-out room, the offer to M, Amah taking Kiang's hand. |
| B25 | 00:56:58 - 01:02:15 | The temple trip. Her feet out of her sandals; the long two-shot at the blue table; **the coffin-donation form**. |
| B26 | 01:02:15 - 01:03:11 | The train home. Amah at the window, M watching her. |
| B27 | 01:03:11 - 01:04:30 | **The shoe shop.** M on the floor fitting new shoes onto her feet. |
| B28 | 01:04:30 - 01:06:00 | Old photographs on his phone; M's head against her arm. |

**B26 is deliberately a single shot** (DEPTH-UNDER flagged and reviewed). The
train home is one held two-shot with no distinct sub-moments - splitting it
would invent boundaries the film does not have. S10 permits one shot when it is
a choice; this is the choice.

**Silence budget is now full.** Four beats tagged across passes 1-2:
`clip:00:28:20.0` (6s), `clip:00:32:32.0` (5s), `clip:00:45:33.0` (12s),
`clip:01:04:11.4` (6s). S9's budget is 2-4 per recap, so passes 3-4 must
DISPLACE one of these rather than add a fifth. Strongest two if forced to cut
to two: the empty-room hold and the shoe-shop close.

**Not identifiable at overview resolution**, left out of `chars`: the man in a
singlet who visits at 00:50:50 and carries Amah in the lane (likely Soei, but
not confirmed), and the young woman in a lilac uniform at the night market
(01:52:20). Zoom before naming either.

### SNAP-GRID - recorded per pass, before the gate runs

This film will score badly and that is the film, not a fault. Logged so the
number exists prior to any explanation.

| Pass | Window | Boundaries | On a cut (<=2.5s) | **No cut** | Cuts/min |
|---|---|---|---|---|---|
| 1 | 00:00 - 33:00 | 114 | 79 (69.3%) | **35 (30.7%)** | 5.6 |
| 2 | 33:00 - 66:00 | 102 | 71 (69.6%) | **31 (30.4%)** | 5.6 |
| cumulative | 00:00 - 66:00 | 216 | 150 (69.4%) | **66 (30.6%)** | 5.6 |

The rate is stable across both passes, which is the point: it is a property of
the film's shooting style, not of one act or of tagging drift. Superbad runs
16.3 cuts/min; this film runs 5.6. Roughly a third of catalogued boundaries
land where the film simply does not cut, because the shot is still going.

### Act 3 (pass 3: pages 23-25 ONLY, 01:06:00 - 01:15:00) - PARTIAL

25 shots, 6 beats (B29-B34), 535.8s of 540s covered (99.2%).

**Pass 3 was scoped to pages 23-33 and stopped at page 25.** Pages 26-33 were
not read and nothing from 01:15:00 onward is catalogued. The remaining pages
were not summarised from the plot, because a catalogue entry written from the
plot is indistinguishable from a verified one once it is in the file.

| Beat | Window | Content |
|---|---|---|
| B29 | 01:06:04 - 01:07:24 | A train under a full rainbow. **Amah's hair is gone** - first shot showing the treatment on her. The congee pot, M working the paddle. |
| B30 | 01:07:24 - 01:09:19 | Counting the day's takings at the green table. Amah alone in close-up; M watching her. |
| B31 | 01:09:19 - 01:11:10 | The warmest stretch in the film so far - her smile, his face, cooking, an old photograph on his phone. |
| B32 | 01:11:10 - 01:12:05 | Out to an apartment block; M crouching alone by a motorbike wheel. |
| B33 | 01:12:05 - 01:13:30 | The moustached man sits down with him; the repair yard; back to the sinks. |
| B34 | 01:13:30 - 01:15:00 | A man in a maroon shirt calls at the green gate. Amah looks through the bars and does not open it. |

### SCRIPTING NOTE - `clip:01:06:26.3` (not a reveal)

Amah's hair is gone. It is the first shot in which the treatment is visible on
her, and the film delivers it with no dialogue and no announcement: she is
simply at the table, and she is bald.

**This does NOT go in the reveal-map, and the distinction matters.** A reveal
protects *hidden information* - something the audience does not know and would
be robbed of. Her decline is not hidden. The diagnosis is in the DELIBERATELY
NOT PROTECTED list, the title states the ending, and the audience has watched
her get weaker for an hour. Nothing here is being concealed.

What the film is doing is choosing to **show rather than tell**. The
information was always available; the filmmaking withholds the *sentence* and
lets the image carry it.

Consequence for the draft, which is the only reason this is recorded:

- **Do not narrate over it.** A line like "the treatment is taking its toll" or
  "by now the chemotherapy has taken her hair" converts the film's strongest
  move into subtitling. The image has already said it, faster and better.
- If the recap needs to mark the passage of time or the progression of the
  illness, do it on an ADJACENT shot, not this one.
- This is a strong silence candidate (S9) - but the budget is already full at
  four (see below), so taking it means displacing one. If it displaces
  `clip:00:32:32.0` (the lane close-up, 5s), that is a defensible trade.

The general form, worth carrying to the next film of this kind: *a shot that
shows what a line would otherwise state is not a reveal to protect, it is a
line to delete.* The reveal-map has no category for this and does not need one -
it belongs in scripting discipline, not spoiler discipline.

### --zoom results (run before pass 4, as required)

Both unidentified people were zoomed. **Neither resolved to a name.** Both stay
unnamed and no draft line may name either.

| Who | Zoom | Outcome |
|---|---|---|
| Man in singlet, lane 00:51:35 | `frames/zoom/00-51-35` | Appearance now clear - middle-aged, moustache, bum bag, physically affectionate with Amah, and clearly NOT Kiang. By elimination among Amah's children he is probably Soei, but elimination is inference, not sight. He recurs at 01:12:05. **Unnamed.** |
| Young woman, night market 00:53:05 | `frames/zoom/00-53-05` | Resolved a factual error instead: she is **staff working the stall** in uniform with a ladle, not a companion eating with M. The `action` text on `clip:00:52:20.7` was corrected. Still no name match against names.json. **Unnamed.** |

The second zoom is the argument for doing these before rather than after: the
overview reading had her as a companion, which would have carried a wrong
relationship into any line bound to that shot.

### SNAP-GRID by pass

| Pass | Window | Boundaries | On a cut (<=2.5s) | **No cut** | Cuts/min |
|---|---|---|---|---|---|
| 1 | 00:00 - 33:00 | 114 | 79 (69.3%) | **35 (30.7%)** | 5.6 |
| 2 | 33:00 - 66:00 | 102 | 71 (69.6%) | **31 (30.4%)** | 5.6 |
| 3 | 66:00 - 75:00 | 31 candidates | 10 (32.3%) | **21 (67.7%)** | - |

Pass 3 is measured on candidate boundaries rather than final ones (the pass is
partial), so it is not strictly comparable to passes 1-2. But the direction is
sharp and worth flagging before pass 4: **the off-cut rate roughly doubles** in
01:06-01:15. That stretch is the film's warmest and slowest - the counting, the
smile, the photograph - and it is shot in very long takes. If the trend holds
into the final act, the cumulative SNAP-GRID figure will get worse, and it will
get worse precisely where the film is at its best.

### Pass 4 (page 26 ONLY, 01:15:00 - 01:18:00) - PARTIAL

10 shots, 2 beats (B35-B36), 180.0s of 180s covered (100%).

**Pass 4 was scoped to pages 26-33 and then 34-43. It stopped at page 26.**
Pages 27-43 were not read and nothing from 01:18:00 onward is catalogued.

| Beat | Window | Content | chars (derived from shots.json) | tags |
|---|---|---|---|---|
| B35 | 01:15:00 - 01:16:45 | Amah in the rocking chair; M gets her up and steadies her; M in a white shirt sitting close while she puts her hand to his face. |  |  |
| B36 | 01:16:45 - 01:18:00 | **The pomegranate.** One red fruit on the vine at the green gate; Amah reaches for the branch, sits down beside him with it, opens it with a knife and talks to him across it. | Amah Saejiu, M |  |

**B36 is the pomegranate beat** the Plot section describes as her giving him a
reserved fruit and telling him to stand on his own feet. It is now catalogued
from frames: the fruit on the vine (`clip:01:16:45.0`), her hands on it
(`clip:01:17:20.0`), and the two-shot over the opened fruit
(`clip:01:17:45.0`).

Note for whoever writes the draft: this is a **second instance of the Gap 3
problem**, and it was visible in real time. The pomegranate is load-bearing -
the Plot confirms it - but there is no earlier catalogued shot of that vine to
link it back to. Either the plant is in a lane shot I catalogued without
noticing the fruit, or the film never establishes it. I did not go back to
check, and that uncertainty is exactly the state the missing field would
resolve.

### SNAP-GRID - now measured on FINAL boundaries for every pass

Passes 1-2 were already final-boundary measurements. Pass 3's earlier figure
(67.7%) was candidate-based; its true final-boundary figure is below.

| Pass | Window | Shots | Boundaries | On a cut (<=2.5s) | **No cut** |
|---|---|---|---|---|---|
| 1 | 00:00 - 33:00 | 57 | 114 | 79 (69.3%) | **35 (30.7%)** |
| 2 | 33:00 - 66:00 | 51 | 102 | 71 (69.6%) | **31 (30.4%)** |
| 3 | 66:00 - 75:00 | 25 | 50 | 19 (38.0%) | **31 (62.0%)** |
| 4 | 75:00 - 78:00 | 10 | 20 | 13 (65.0%) | **7 (35.0%)** |
| late (3+4) | 66:00 - 78:00 | 35 | 70 | 32 (45.7%) | **38 (54.3%)** |
| **cumulative** | 00:00 - 78:00 | 143 | 286 | 182 (63.6%) | **104 (36.4%)** |

**The 60-70% condition set for pass 4 was NOT met.** Pass 3 lands at 62.0%, but
pass 4 falls back to 35.0%. The late-film rate is genuinely elevated - 54.3%
against 30.5% in the first two passes, roughly 1.8x - but it is variable rather
than a sustained band, and pass 4's sample is only 20 boundaries, too small to
call a trend. The conditional finding is therefore recorded in
docs/STRESS_grandma.md in a weaker form than the condition specified, with the
numbers rather than the claim.

### Pass 5 (pages 027-036, 01:18:00 - 01:48:00) - COMPLETE

100 shots, 16 beats (B36 tail + B37-B51), 1800.0s of 1800s covered (100%).
Every entry verified against `frames/overview/page_027..036.jpg` before writing.
Four `--zoom` runs were made to settle identifications (below). Boundaries were
snapped mechanically, not by eye - see SNAP-GRID.

| Beat | Window | Content | chars (derived from shots.json) | tags |
|---|---|---|---|---|
| B36 (tail) | 01:18:00 - 01:18:22 | The pomegranate conversation closing out in reverse singles. |  |  |
| B37 | 01:18:22 - 01:22:02 | **The big house.** Karaoke and a family lunch, then Amah asks an elderly man for money across the long table and is refused. An empty hospital bed stands against the wall of the room she is refused in. | M, Amah Saejiu | [S6] |
| B38 | 01:22:02 - 01:23:58 | The way home: the train, then M and Amah walking away down the tree tunnel of the railway. | M, Amah Saejiu |  |
| B39 | 01:23:58 - 01:26:18 | The hospital. Sew and M take the news at the doctor's desk; Amah waits in a wheelchair; they crouch down and tell her. | Amah Saejiu, M, Sew |  |
| B40 | 01:26:18 - 01:27:03 | Night. M sitting on the floor beside her bed behind the pink net. | Amah Saejiu, M |  |
| B41 | 01:27:03 - 01:29:13 | **The deed.** Kiang and Sew on the hospital walkway; Sew relays it to M; documents handed over at the foot of the stairs. | Sew, M, Kiang | [S6] |
| B42 | 01:29:13 - 01:30:43 | The emptied ward room, M's face in a glass door, and two very long empty walkways. | Sew, M |  |
| B43 | 01:30:43 - 01:32:23 | **The wheelchair conversation.** M pushing Amah along the outside walkway, bald and capless, the two of them talking for ninety seconds. | M, Amah Saejiu |  |
| B44 | 01:32:23 - 01:32:58 | A train in full sun, the same sky at night, then blue dark inside the shophouse. |  |  |
| B45 | 01:32:58 - 01:35:08 | **Sew's salon.** She cuts M's hair, then lies on the couch while he works at her legs and they talk. | Sew, M |  |
| B46 | 01:35:08 - 01:38:48 | M drives out to see Mui. A long two-hander at the tea table; Mui talks until her face goes and M does not answer. | Mui, M |  |
| B47 | 01:38:48 - 01:39:48 | **Amah alone** - kitchen, chair, lane. Three shots, nobody else in any of them. | Amah Saejiu |  |
| B48 | 01:39:48 - 01:43:28 | **The care home.** Temple roof, grounds, ward. M sits at the bedside of an elderly bedridden man with a feeding tube and talks to him. | M |  |
| B49 | 01:43:28 - 01:44:28 | Home. The pomegranate ripe on the vine; the empty living room; M's gaming rig still on the desk with a hospital bed now on the floor beside it. | M |  |
| B50 | 01:44:28 - 01:45:33 | Sew in tears at her mother in the kitchen; Amah's face while it happens. | Sew, Amah Saejiu, M |  |
| B51 | 01:45:33 - 01:48:00 | **Chinese New Year.** Kiang stays in the car; the shophouse hung with lanterns; a hospital bed made up in red in the middle of the room. | M, Kiang, Amah Saejiu |  |

**Where I stopped and why.** Pass 5 was scoped to "pages 27 onward, as many as
you can verify". It stopped at the end of page 036 (01:48:00) because that is
the last page I actually read. **Pages 037-043 (01:48:00 - end, ~18.8 min) were
NOT opened.** Nothing from them is in `shots.json` and nothing about them is
described here.

Still outstanding, and explicitly NOT catalogued: M moving out for good, the
nursing-home placement, Amah's death, the funeral, and the bank call - **R1, the
film's only protected reveal, is still not in the catalogue.**

### Identifications made in pass 5

Four zooms were run before anything was written. Two resolved, two did not, and
two more people were matched against already-catalogued shots rather than guessed.

| Who | How settled | Outcome |
|---|---|---|
| The woman in the knitted cap, 01:19-01:22 | `frames/zoom/01-21-22` | **Amah.** Same face, same round gold glasses; the cap is over her bald head. She is covered up because she is out of the house. Named. |
| The karaoke object, 01:19:24 | `frames/zoom/01-19-24` | It is a **microphone** and there is a karaoke screen behind her. The beat opens warm before the ask - that matters for how the scene is narrated. |
| Man in the striped polo, 01:27:40-01:28:33 | compared against `clip:00:56:15`-era frames (page 019) | **Kiang.** Same face, same glasses, same build. Named. |
| Young woman at the tea table, 01:36-01:38 | compared against `clip:00:23:05`-era frames (page 008) | **Mui.** Named. |
| Woman in yellow floral, 01:44:28-01:45:33 | `frames/zoom/01-45-22` | **Sew.** Same actress as 01:24:40 and 01:27:45 - thin face, high cheekbones, hair pulled back. Named. |
| Bedridden man, 01:41:48-01:43:13 | `frames/zoom/01-42-23` | An elderly **man**, not Amah - heavy jaw, feeding tube. **Not identified. Not named.** See the plant audit. |

**Ruled out from the frames, not from the plot:** the bedside at 01:42 is not a
flashback to Agong. M wears the same navy-and-white striped tee at 01:41:00 in
the care-home corridor, at 01:41:35 in the ward and at 01:42:00 at the bedside -
one continuous visit, same day.

### NOT NAMED in pass 5 - four people, on purpose

`chars` is empty or partial for these. No draft line may name any of them.

| Who | Where | Why not |
|---|---|---|
| **The elderly man in the maroon polo** | 01:19:20-01:22:00, the whole of B37 | The scene is unmistakably the refusal the Plot describes, and `names.json` has exactly one candidate - `Amah's brother`. But that entry is a *relation*, and a relation cannot be established by looking at a face. This is the same standard pass 3 applied to the moustached man ("elimination is inference, not sight"). **This is the highest-value unresolved identification in the film so far: R2 is his scene, and as things stand no line can say "her brother" and bind to it.** It needs a human ear on the Thai audio, not another zoom. |
| **The bedridden man at the care home** | 01:41:48-01:43:13 | No match, no plant, no name. M sits with him and talks to him at length and emotionally, which reads as someone the film has established - but I cannot find him in the existing catalogue. |
| **The bearded man with the shoulder bag** | 01:28:43-01:29:03 (hospital) and 01:40:58-01:41:33 (care home) | Recurs across two beats and hands over documents in both. Possibly the same moustached man as 00:51 / 01:12, possibly not - I could not tell them apart at overview resolution and did not zoom. Unnamed. |
| **The young woman doing a wai in the car** | 01:35:28-01:35:38 | Too small and too brief. Plausibly Mui greeting M on arrival, but "plausibly" is not a sighting. Unnamed. |

### PLANT AUDIT - payoffs in pages 027-036 whose plant is not in the catalogue

Run because pass 4 flagged the pomegranate and then deferred the check. Three
gaps, in descending order of how much they cost.

**1. The house sale and the title deed - NO PLANT AT ALL.**
At 01:28:17 the argument on the walkway turns on the *chanote* (the Thai land
title deed) - where it is, who holds it. At 01:33:04-01:35:01 in the salon the
conversation is about the house having already been sold and needing to be
packed up. Both scenes treat the sale as settled background.
Searching all 143 pre-existing shots for `sale|sell|sold|deed|buyer|agent|estate`
returns **one** hit, `clip:00:53:20.0`, which is a car driving out to a housing
estate and is a different thing. There is no catalogued shot of the house being
sold, of the deed, or of a buyer. The A8 section of this document asserts "the
house sale" is part of the SETUP zone; **no shot backs that claim.** Either the
sale is in a stretch that was catalogued without it being noticed, or it is in
the un-read 01:48:00+ range - but the 01:28 argument references it as already
known, so a plant before 01:28 is what is missing. Anything the draft wants to
say about the house being sold currently has no footage under it (S4).

**2. The pomegranate vine - still no plant, and now checked rather than assumed.**
Pass 4 wrote: "there is no earlier catalogued shot of that vine to link it back
to... I did not go back to check." I checked. Page 025 (01:12:00-01:15:00)
carries the two catalogued gate shots, `clip:01:13:45.0` and `clip:01:14:20.0`,
framed tight on the gate bars: **no vine and no fruit visible in frame.** The
other catalogued gate shots (`clip:00:14:29.2`, `clip:00:18:59.7`) are on page
005, which I did **not** re-open - so this is "not found where I looked", not
"proved absent".
Pass 5 does add a second appearance: `clip:01:43:29.4`, the fruit ripe and being
watered. So the vine is now a two-point motif (01:16:45 -> 01:43:29) with the
establishing beat still unlocated. **Whoever opens page 005 next should look at
the gate and settle it in one glance.**

**3. Amah's brother and the big house have no plant** - first appearance is
01:18:22. That is the film introducing him, not a gap; recorded only so nobody
later reads the absence as an oversight.

**Payoffs that DO have their plant - checked, not assumed:**

| Payoff (pass 5) | Plant (already catalogued) |
|---|---|
| M's gaming rig still on the desk with a hospital bed beside it, `clip:01:43:58.0` | `clip:00:05:57.8`, `clip:00:07:05.0`, `clip:00:08:00.0` (B03) |
| The care-home ward; M at a stranger's bedside, `clip:01:41:48.1`-`01:43:13.2` | `clip:00:08:36.4`-`clip:00:10:05.0` (B04, Agong's bed at home, Mui doing the care) |
| Kiang stays in the car and will not come in, `clip:01:46:12.7` | `clip:00:53:47.6`, `clip:00:54:47.6` (B24, the room he fitted out and showed off) |
| Amah singing karaoke at the big house, `clip:01:19:20.2` | `clip:00:53:47.6` - the room Kiang fitted out has a karaoke screen in it |
| Mui's long confession at the tea table, `clip:01:37:18.0`-`01:38:28.8` | `clip:00:22:01.4`, `clip:00:22:58.4` (B09, the hotel room) |

### SNAP-GRID - final boundaries, all five passes

| Pass | Window | Shots | Boundaries | On a cut (<=2.5s) | **No cut** |
|---|---|---|---|---|---|
| 1 | 00:00 - 33:00 | 57 | 114 | 79 (69.3%) | **35 (30.7%)** |
| 2 | 33:00 - 66:00 | 51 | 102 | 71 (69.6%) | **31 (30.4%)** |
| 3 | 66:00 - 75:00 | 25 | 50 | 19 (38.0%) | **31 (62.0%)** |
| 4 | 75:00 - 78:00 | 10 | 20 | 13 (65.0%) | **7 (35.0%)** |
| 5 | 78:00 - 108:00 | 100 | 200 | 135 (67.5%) | **65 (32.5%)** |
| late (3+4+5) | 66:00 - 108:00 | 135 | 270 | 167 (61.9%) | **103 (38.1%)** |
| **cumulative** | 00:00 - 108:00 | 243 | 486 | 317 (65.2%) | **169 (34.8%)** |

**The pass-4 finding does not survive a bigger sample, and is withdrawn here.**
Pass 4 recorded a "genuinely elevated" late-film off-cut rate - 54.3% against
30.5% early, roughly 1.8x - while noting its own 20-boundary sample was too
small to call a trend. Pass 5 is 200 boundaries over 30 minutes and lands at
**32.5%, i.e. level with passes 1-2 (30.6%)**. Pooling all three late passes
drags the late figure down from 54.3% to 38.1%, and most of what is left is
pass 3 alone.

So the honest statement is now: **pass 3's window (01:06-01:15) is a local
outlier at 62%, not the leading edge of a late-film trend.** The film's
off-cut rate is a stable ~31-33% property of its shooting style across 108
minutes, exactly as passes 1-2 claimed.

Two supporting numbers, recorded because they cut against the intuition:

- Detected cuts per minute do **not** explain the variation. Pass 1's window
  runs 5.58 cuts/min, pass 3's 5.00, pass 4's 6.00, pass 5's 4.73. Pass 5 has
  the *fewest* cuts per minute of any pass and one of the *lowest* off-cut
  rates. Off-cut rate is a property of where the tagger put boundaries relative
  to the takes, not of how often the film cuts.
- The off-cut is not spread evenly - it pools. Per-beat, pass 5 runs 82-100%
  on-cut through B37, B39, B44, B50, and collapses to **17% on-cut in B42**
  (the emptied ward room, the reflection, the two long empty walkways). That
  single beat contributes 10 of pass 5's 65 off-cut boundaries. The film holds
  hardest exactly where nothing is happening, which is also where the recap
  will most want to cut into it.

### Silence budget - still full at four, nothing added

Pass 5 tagged **no** `narration_silence_seconds`. S9's budget is 2-4 per recap
and passes 1-2 already used four, so a fifth cannot be added - only traded.
Recording the pass-5 candidates so the trade is an informed one:

| Candidate | Length available | Why it earns it |
|---|---|---|
| `clip:01:21:19.8` - Amah taking the refusal, held close-up | ~20s window, 6-8s hold | The face after the money is refused. No dialogue. The strongest single image in the pass. |
| `clip:01:23:30.0` - the two of them tiny at the end of the green tunnel | ~28s window, 10-15s hold | Iconic composition, already a held shot in the film, and it follows a heavy plot turn. This is the S9 "8-15s for an iconic shot" case. |
| `clip:01:31:58.0` - Amah's face in profile from the wheelchair | ~25s window, 6-8s hold | Peak emotional beat, but the scene around it is plot-carrying, so silence here risks losing the viewer. Weakest of the three. |

If one is taken, the defensible displacement is still `clip:00:32:32.0` (the
lane close-up, 5s), as pass 3 already argued. Note that pass 3 also wanted that
slot for `clip:01:06:26.3` (the bald reveal) - **there is now one slot and three
claimants, and that conflict is not resolved here.**

### DEPTH / TIER - the problem got bigger, and is not being hidden

243 shots over 108 minutes catalogued. `depth_target: video_essay` is 110-130.
The catalogue is at **1.9x the top of its declared band with ~18.8 min of film
still unread**, and `--coverage` duly reports `243 [over target]`.

Density by pass: p1 1.73/min, p2 1.55/min, p3 2.78/min, p4 3.33/min, p5 3.33/min.
The step up at pass 3 is the S10 depth discipline being applied and pass 5 holds
that line rather than inventing a new one. It is **not** explained by the film
cutting faster - pass 5's window has the fewest cuts per minute of any pass.

This is left as an authoring problem, not fixed by deleting entries. Which shots
get bound is a draft-stage decision; frame-verified coverage is the one thing
that cannot be reconstructed later without re-reading the frames. Either
re-declare the tier or select at authoring time - but do not trim the catalogue
to hit a number.

**WARNING - the Stage 2 depth audit has never actually run on this project, and
its "Depth gates clean" line is meaningless here.** `--coverage` prints
`Beats (numbered): 0`. `pipeline/catalogue.py:265` matches beat entries with
`^\s*(B_?\w+?)\s*(?:\|\s*|[~]?\d{1,2}:\d{2})` - the id must open the line. Every
beat in this document is a markdown **table row**, so it opens with `|` and the
regex never matches. `parse_beats()` returns 0 beats, so DEPTH-UNDER,
DEPTH-CLIMAX, DEPTH-REACTION and DEPTH-MOTIF have nothing to iterate and cannot
fire. This has been true for all five passes; it is not a pass-5 regression.

Depth was therefore checked by hand against `shots.json` instead:

- 51 beats, 243 shots, **one** beat under the floor of 2 - `B26` at 1 shot,
  which is the deliberate single-shot train-home beat already argued for above.
- All 16 pass-5 beats carry 3+ shots. Per beat: B36 6, B37 14, B38 6, B39 8,
  B40 3, B41 8, B42 6, B43 4, B44 3, B45 6, B46 8, B47 4, B48 13, B49 4, B50 4,
  B51 8.
- B37 (the refusal) and B48 (the care home) are the two S6 sequences in this
  pass and carry 14 and 13 shots, well clear of the 3-4 floor.

Fixing the parser is out of scope for a catalogue pass, but until it is fixed
**nobody should read a clean `--coverage` run on this project as evidence of
anything.** *(FIXED in pass 6 - see "The depth gates now run" below.)*

### Pass 6 (pages 037-040, 01:48:00 - 01:59:05.8) - COMPLETE. CATALOGUE CLOSED.

37 shots, 7 beats (B51 tail + B52-B57), 665.8s of 665.8s covered (100%).

**The film's narrative ends at 01:59:05.8** - the cut to black at `_cuts.json`
7145.833. Pages 041, 042 and 043 were opened and read in full: they are **text
credits only**, Thai and international, ending at 02:06:40. There is no
mid-credit and no post-credit footage. They are deliberately catalogued as
nothing, and that is a finding rather than an omission - the film is 126.8 min
long but only **119.1 min of it is story**, and any runtime maths that used
126.8 was wrong by 7.7 minutes.

| Beat | Window | Content | chars (derived from shots.json) | tags |
|---|---|---|---|---|
| B51 (tail) | 01:48:00 - 01:48:30 | The New Year gathering closing round the bed; Kiang leaning down over Amah. |  |  |
| B52 | 01:48:30 - 01:51:20 | **The last night.** A lamp, M asleep, then a long rack-focus vigil with Amah's head out of focus in the foreground. Their hands and the gold ring. M talking to her and getting no answer, held for the best part of a minute. | M, Amah Saejiu | [S6] |
| B53 | 01:51:20 - 01:52:26 | **The funeral.** Gold catafalque, banks of white wreaths, stacked chairs, mostly empty. M lighting incense; M and Sew in mourning black; M alone on the phone in the hall. | M, Sew |  |
| B54 | 01:52:26 - 01:52:40 | **The passbook.** M going through her things at the bed, then a green BANK OF SIAM savings book held open - account 826-006-1525-8, a name written in by hand. | M | [S6] |
| B55 | 01:52:40 - 01:54:33 | **The call and the flashback.** M outside on the phone; then Amah years younger in a dark perm walking a small boy in school uniform down the lane; then back to M as a train goes past. | M, Amah Saejiu | [S6] |
| B56 | 01:54:33 - 01:57:28 | **The procession.** The gold coffin roped to a flatbed truck, the family riding with it out through Bangkok - the arch, the trackside market, the skyline, then the country. M against the coffin in the sun, laughing into the wind. | M, Sew |  |
| B57 | 01:57:28 - 01:59:05.8 | **Back at the grave.** The hillside cemetery the film opened on. M tending the family plot while a small girl plays around him, then sitting down on the grass and looking up. Cut to black. | M |  |

**B57 closes the circle B01 opened.** `clip:00:00:52.8` is a wide over this same
hillside cemetery, and B01's content is "Amah works the ritual; M sits apart on
his phone." In B57 M does the ritual and a child plays nearby. The rhyme is in
the footage, not in the plot summary, and it is the single strongest structural
fact available to whoever writes the ending of the recap.

### R1 is now catalogued - and it is a passbook, not a phone call

The reveal-map calls R1 "the bank call". What is actually on screen is:

1. `clip:01:52:32.3` - the green savings book, held open, **legible**: BANK OF
   SIAM, A/C NO. 826-006-1525-8, and a handwritten name. Verified at
   `frames/zoom/01-52-33`.
2. `clip:01:53:28.0` - the flashback: Amah with a full dark perm walking a small
   boy in school uniform. Verified at `frames/zoom/01-53-34`.
3. The phone call is the *connective tissue* around them
   (`clip:01:52:40.1`, `clip:01:54:13.0`), not the reveal itself.

So the reveal is **an object and a memory**, not a conversation. That matters for
scripting: a line written as "then the bank calls him" describes something the
film does not show. The film shows a book and a child.

**The flashback identification, stated at its true strength.** Naming Amah in
`clip:01:53:28.0` and `clip:01:53:58.0` rests on scene logic and physical
continuity - elderly woman, glasses, walking a schoolboy, over audio about
buying her a new house - **not** on a clean facial match, because she is in a
period wig and mostly three-quarters away from camera. It is the same standard
that named Kiang and Mui in pass 5, applied to a harder shot. If a draft line
leans its whole weight on "this is Amah as a young woman", zoom-confirm first.

### A8 house-sale claim - RESOLVED (the plant exists; the catalogue was mute)

Pass 5 grepped 143 shots for `sale|sell|sold|deed|buyer|agent|estate`, found one
unrelated hit, and concluded the A8 claim had no footage under it. **That
conclusion was wrong, and the method is the lesson: it searched the
catalogue's own words, and the catalogue never writes down what it hears.**

Searching the *transcript* instead finds it immediately, and it lands inside a
beat pass 4 had already catalogued:

- **`clip:01:13:45.0` / `clip:01:14:20.0` (B34, 01:13:45-01:14:39).** The man in
  the maroon shirt at the green gate is a **prospective buyer**. He says he saw
  the house listed for sale, that nobody answered his message, and asks after
  *"someone named M. Thanapat"*. Amah answers **"This house isn't for sale"** and
  **"I don't know him."** She is being shown her own home advertised by her
  grandson, and she denies knowing his name.
- **`clip:00:20:27.8` (B09).** Mui is living in a hotel because she **sold the
  house Agong left her** - "I want to keep the money I got from selling my house,
  that's why I stayed at the hotel for months." That is the model M is copying,
  and it is the reason B09 exists at all.

Both were catalogued with `action` text that is visually accurate and
semantically empty: "he holds a phone up to the gate to show her something",
"Mui hangs clothes on a rolling rack". The footage was seen. The point was not.

**What was actually amended.** Only one thing, and only because it is *visible*:
`clip:01:14:20.0` was re-zoomed (`frames/zoom/01-14-26`) and the phone screen
does carry a legible listing-style card with a photograph of a building on it.
The `action` now says so. Everything else the buyer and Amah *say* stays out of
`action` - `action` describes what the viewer sees, and that rule is not bent to
record a plot point.

**A8's wording was also wrong, mildly.** The house is not sold in the setup zone;
it is secretly **listed** by M and a buyer turns up at the gate. "the house sale"
has been changed to "the house being put up for sale" above.

**The transferable lesson, and it is not a small one:** a plant audit that greps
`action` text can only ever find plants that are *pictorial*. Anything a film
plants in dialogue is invisible to it, and will be reported as a missing plant
with total confidence. Grep the transcript too, or the audit will keep producing
confident false negatives.

### SNAP-GRID - final boundaries, all six passes

| Pass | Window | Shots | Boundaries | On a cut (<=2.5s) | **No cut** |
|---|---|---|---|---|---|
| 1 | 00:00 - 33:00 | 57 | 114 | 79 (69.3%) | **35 (30.7%)** |
| 2 | 33:00 - 66:00 | 51 | 102 | 71 (69.6%) | **31 (30.4%)** |
| 3 | 66:00 - 75:00 | 25 | 50 | 19 (38.0%) | **31 (62.0%)** |
| 4 | 75:00 - 78:00 | 10 | 20 | 13 (65.0%) | **7 (35.0%)** |
| 5 | 78:00 - 108:00 | 100 | 200 | 135 (67.5%) | **65 (32.5%)** |
| 6 | 108:00 - 119:06 | 37 | 74 | 47 (63.5%) | **27 (36.5%)** |
| late (3+4+5+6) | 66:00 - 119:06 | 172 | 344 | 214 (62.2%) | **130 (37.8%)** |
| **FINAL** | 00:00 - 119:06 | **280** | **560** | **364 (65.0%)** | **196 (35.0%)** |

Pass 6 lands at 36.5%, close to pass 5's 32.5% and to the 30.6% of passes 1-2.
This further confirms the correction pass 5 made to pass 4's withdrawn "late-film
elevation" finding: **pass 3 (62.0%) remains a single local outlier**, and the
film's off-cut rate is a stable ~30-37% property across all 119 minutes.

Two per-beat pockets are worth naming, because they are where the recap will
fight the footage:

- **B57 - 25% on cut (2 of 8).** The closing cemetery sequence is four very long
  held takes. Every boundary inside it is a boundary the film does not offer.
- **B52 - 62%, B53 - 60%, B55 - 40%.** The death, the funeral and the flashback.
  The film slows down exactly where the recap most needs to cut.

For contrast **B56 runs 82% on cut** - the procession is the most conventionally
edited sequence in the last twenty minutes.

### The death plays almost wordless - a scripting fact, not a transcript fault

The Whisper transcript across 01:48:00-01:52:44 returns the same three lines over
and over ("Your son is here", "I'm holding your hand", "You're so lucky that
you've made it") at 01:48:01, 01:50:42, 01:52:11 and 01:52:39. That is the
hallucination-under-silence pattern this document flagged at the top, and here it
is diagnostic rather than annoying: **there is almost no dialogue in the death
sequence.** The film plays it on held images and score.

Consequence for the draft: this is the one stretch where narration is competing
with nothing, and therefore the one stretch where narration is most likely to
ruin what is already working. Say less here than feels comfortable.

### Silence budget - now three claimants for one slot, and a fourth arrived

Pass 6 tagged **no** `narration_silence_seconds`. The budget (S9: 2-4 per recap)
was filled in passes 1-2 and pass 5 recorded three candidates for one tradeable
slot. Pass 6 adds the strongest candidate in the film:

| Candidate | Hold | Why |
|---|---|---|
| `clip:01:58:52.0` - M looking up from the grave, the last image before black | 8-12s | The film's final image, on the location it opened on, with no dialogue under it. If any shot in this recap earns silence, it is this one. |
| `clip:01:50:23.8` - M talking to Amah and getting no answer, held ~57s | 10-15s | Peak emotional beat, already wordless in the film. |

**This is now four claimants for one slot and it is not resolvable at catalogue
stage.** Recorded so the draft author makes the trade knowingly rather than
discovering the cap at render time. My reading, offered as opinion and not as a
finding: the ending shot should take the slot, and `clip:00:32:32.0` (the lane
close-up, 5s) should give it up.

### The depth gates now run - what they actually say

`parse_beats()` was fixed in `pipeline/catalogue.py` to accept markdown table
rows (this file's shape) alongside the two shapes it already took. Before the
fix this project parsed to **0 beats**; it now parses **51** (B01-B51 - the
pass-6 beats B52-B57 are in the table above and will parse on the next run).
Verified against all ten projects in `projects/`: nine are **byte-identical**
before and after, so nothing else moved.

**`chars` and `[S6]` columns were then added to the B36-B57 beat rows** - the
range this session catalogued and verified. `chars` is the **derived union** of
each beat's shots in `shots.json`, not a fresh assertion: those shots were
frame-verified, so the union is too. `[S6]` was applied only where a TAGGING_GUIDE
S6 category genuinely applies - decisive confrontations (B37, B41), the death
sequence (B52, the S6 "suicide moments" analogue) and the reveal (B54, B55).

**B01-B35 were deliberately left with empty chars cells and no tags**, so they
sit outside the unit counts and are reported as such. Earlier passes catalogued
them and I did not verify them this session; inventing that metadata to raise a
gate's unit count would be exactly the sin the gate exists to catch. Read every
unit count below as *"over the B36-B57 range"*, not *"over the film"*.

Result of the first real run:

| Gate | Status | Result |
|---|---|---|
| `DEPTH-UNDER` | measured over 57 beats | **1 warning: B26 has 1 shot** |
| `DEPTH-CLIMAX` | measured over 5 `[S6]` beats | **1 warning: B54 has 2 shots** |
| `DEPTH-REACTION` | measured over 16 beats with 2+ chars and 1+ shot | pass |
| `DEPTH-TOTAL` | measured over 1 tier band | pass (280 is over, not under, the floor) |

**Both warnings reviewed, both stand as deliberate:**

**`DEPTH-UNDER` / B26** - the single-shot train home. Pass 2 argued for it and
reviewed it; the gate has now found it unaided, which is the right outcome for a
gate that previously could not see it at all.

**`DEPTH-CLIMAX` / B54** - the passbook beat carries 2 shots (M going through her
things; the passbook itself). S6 wants a reveal to run setup + reveal + reaction.
The setup and the reveal are both in B54. **The reaction is not, because the film
does not put one there** - it cuts from the passbook straight out to the railway
and the phone, and M's response to what he has read is the whole of B55. Read as
one sequence, the reveal carries 7 shots across B54+B55 and is amply covered.

I did not manufacture a third shot to clear the flag (the passbook window could
be split into "closed cover" and "open page" - both real images, both zoomed -
but that split would exist to satisfy a gate, not to describe the film). And I
did not move the `[S6]` tag onto B55 alone, which would have hidden the same
fact more quietly. **The flag is correct, its cause is a beat boundary, and the
per-beat gate cannot see across one.** That limitation is worth knowing the next
time DEPTH-CLIMAX fires on a two-shot beat.

**`DEPTH-MOTIF` no longer appears because it has been RETIRED** estate-wide -
four gates now, not five. The argument, the measurements and the "do not rebuild
it" requirements are in `docs/TAGGING_GUIDE.md`. The part that matters for this
film: the gate would have **passed** the pomegranate (the word is in four shots'
action text) while the plant was genuinely missing, and it was structurally
blind to the house-sale plant because that plant lives in dialogue. It was not
capable of catching either of the two motif problems this film actually had.

### CATALOGUE CLOSED

280 shots, 57 beats, 00:00:00 - 01:59:05.8, 98.2% of the narrative covered.
Every entry was verified against a frame montage before it was written; nothing
was entered from the Wikipedia plot.

Four people remain deliberately unnamed and no draft line may name them - the
full argument is in the pass 5 section, and pass 6 adds nothing that resolves
them:

1. **The elderly man in the maroon polo** (all of B37, the R2 refusal scene).
   Still the highest-value unresolved identification in the film. The credits do
   confirm the role exists - the Vietnamese dub cast on page 043 lists *"Anh trai
   bà Mengju"*, Mengju's elder brother - but a cast list names an actor, not a
   face on screen, so it does not settle which man he is. Needs a human ear on
   the Thai audio.
2. **The bedridden man at the care home** (B48).
3. **The bearded man with the shoulder bag** (B41, B48, and again riding the
   truck at `clip:01:56:08.4` in B56 - he recurs three times and is never
   identified).
4. **The young woman doing a wai in the car** (B46).

The remaining open question for the draft is not coverage. It is the tier: 280
shots against a declared `video_essay` band of 110-130. That is a selection
problem to solve at authoring time, and deleting verified coverage is not the
way to solve it.
