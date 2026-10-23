# Narrator voice - measured, and adapted into English

Primary model: **SAKURA REVIEW** (Vietnamese), the channel the user watches to
the end. Baseline to beat: **Movie Recaps** (`@movierecapsofficial`) and
**TheCutFrame**, English channels the user finds bland. One **Vua Phim Review**
video is included as a second Vietnamese point.

Every number here is measured by `tools/measure_voice.py` from YouTube's own
auto-captions. Captions are gitignored (`references/`): the repo is public and
that text is someone else's copyright. **No line from any of these channels is
quoted in this document.** Every illustration is an invented English example
written to show a device, not a translation of anything they said.

## The corpus

| group | videos | runtime | words | source |
|---|---|---|---|---|
| SAKURA REVIEW | 3 | 18.1 / 20.0 / 21.7 min | 15,556 | `vi-orig` auto-captions |
| Vua Phim Review | 1 | 35.5 min | 9,673 | `vi-orig` |
| Movie Recaps | 4 | 8.8 / 12.8 / 15.5 / 17.3 min | 12,997 | `en-orig` |
| TheCutFrame | 1 | 25.8 min | 5,284 | `en-orig` |

Picked as: the two videos the user named, plus Sakura's two most-viewed
(2.79M, 1.93M) and Movie Recaps' two most-viewed (1.03M, 786K) and two most
recent. One correction worth recording: of the two links given as Sakura, only
`uq0E0qoZnnE` is his (8.81M views); `-aTw-3XAQFc` is **Vua Phim Review**
(9.89M). And `fT_pA_sX3VU` is **TheCutFrame**, not `@movierecapsofficial`.

### Three measurement limits, stated before any conclusion

1. **Vietnamese words are not English words.** Vietnamese is monosyllabic, so
   "260 words per minute" of Vietnamese is nothing like 260 WPM of English.
   Every cross-language WPM comparison below is therefore marked as *not
   comparable*; only within-group comparisons mean anything.
2. **Auto-captions usually carry no punctuation.** Two of three Sakura files
   and the Vua Phim file have none, so sentence-length statistics are
   impossible for them and the tool refuses to print a number rather than
   report YouTube's cue length wearing a sentence's name.
3. **Quoted film dialogue contaminates any pronoun count.** TheCutFrame first
   measured at 32 narrator markers per 1000 words - and every single one turned
   out to be inside quoted dialogue, marked `>>` in the captions. Corrected
   figures below exclude dialogue. This is the difference between a real
   finding and an artifact, and it inverted the result completely.

## What the numbers say

| measure | SAKURA | Vua Phim | Movie Recaps | TheCutFrame |
|---|---|---|---|---|
| words/min *(not comparable across languages)* | 257-264 | 272 | **236-245** | **205** |
| sentence-length SD | 10.2 \* | n/a | **5.3 - 6.3** | **12.0** |
| narrator first person /1000w | **5.4** | 3.1 | **0.0** | **0.0** |
| sentence-final particles /1000w | **4.5** | 3.8 | (no such device) | (no such device) |
| direct address to viewer /1000w | **1.9** | 1.7 | **~0** (CTA only) | **~0** |
| slang intensifiers /1000w | 1.0 | 0.4 | 0.0 | 0.0 |
| questions to viewer /1000w | 0.4 | 0.0 | 0.1 | 0.0 |
| role labels /1000w | 3.9 | 7.4 | 1.5 | 0.4 |
| capitalised names /1000w | 118 | 110 | 66 | 62 |
| film dialogue left audible | no | no | **yes** (136 markers) | **yes** (99) |

\* one Sakura file had punctuated captions; the other two could not be measured.

### The single decisive finding

Narrator presence across the timeline, in thirds:

| | 1st third | 2nd third | 3rd third |
|---|---|---|---|
| Movie Recaps (4 videos) | **0.0** | **0.0** | 0.8 - 2.2 |
| SAKURA (3 videos) | 4.6 - 7.7 | 2.4 - 10.0 | 8.1 - 12.8 |

**Movie Recaps has a narrator who does not exist.** Across 12,997 words there
is one instance of "I", four of "you", one question mark. The third-column
figures are not narration at all - they are the boilerplate subscribe request,
which is word-for-word identical across all four videos. With quoted dialogue
excluded, first person, direct address, stance adverbs, evaluative adjectives
and questions are all **zero**.

That is the whole answer to "what does Sakura do that they don't." He is in the
room. They are a plot-summary service.

## The devices, and how to do them in English

### 1. The narrator is a person with a name

Sakura refers to himself by the channel name in the third person at the moment
of reflection, as if the host were a character in his own video, then switches
back to "I" to ask for the like. Movie Recaps' narrator has no self at all.

Adapted: our channel already has a name (`CHANNEL_NAME`). Use first person,
and let the narrator own an opinion.
*Illustration (invented):* "I've watched this scene four times and I still
can't tell you whether he meant to do it."

### 2. He ends on MEANING, then asks

Sakura's closers reach for a thesis before the call to action - in one video he
reaches outside the film entirely, recalling a famous line from a different
film to frame what this ending meant, and only then asks for the like.
Movie Recaps ends on the last plot event and cuts straight to the identical
boilerplate. No thesis, in any of the four.

This is exactly our `[INTRO-OUTRO]` rule (thesis sentence before CTA), and the
measurement supports it: the channel the user loves does it, the channels he
finds bland do not.
*Illustration (invented):* "He spent the whole film being moved on, and he only
wins the day he stops running. If that landed, tell me what to recap next."

### 3. He talks to the viewer as a relationship, not an algorithm

Sakura's address terms are warm and plural - he closes by calling the audience
something like "dear friends". Movie Recaps' only second-person use is the
subscribe line.

Adapted, without the sentimentality that does not survive into English: use
"you" for shared reasoning rather than for instructions.
*Illustration:* "You already know what's in the bag. He doesn't."

### 4. Sentence-final particles → English equivalents

This is the device that does **not** translate, and the one most likely to go
dead if translated literally. Vietnamese appends short particles that mark
attitude without adding meaning (4.5 per 1000 words in Sakura). English has no
particle slot.

Do **not** render these as "right?", "you know?", "huh?" scattered through the
narration - that reads as filler, not as voice. The English equivalents that
carry the same attitude are:

- a short appended clause: "...and that is the plan, such as it is."
- an em-dash afterthought: "He takes the deal - of course he takes the deal."
- a dry understatement as its own sentence: "It goes badly."
- a contraction where formality was expected: "He hasn't got a car. He hasn't
  got a plan either."

### 5. Rhythm actually varies

Movie Recaps' sentence-length SD is **5.3 to 6.3** across four videos - within
arm's reach of the metronome our own pre-craft draft produced (3.9), and a
third of the human reference (13.7). Sakura's measurable file is 10.2 and
TheCutFrame is 12.0.

Our `[RHYTHM]` SD floor of 9.0 therefore separates exactly the right things:
it fails the channels the user finds bland and passes the ones he does not.

### 6. They let the film talk; we never do

Both English channels keep the film's original dialogue audible and let it
carry whole exchanges - 136 and 99 dialogue markers respectively. Our pipeline
narrates over everything with film audio at -17 dB.

This is the one place the "bland" channels do something we do not, and it
interacts with two of our rules - see the conflicts section. It is also the
one device here that is a **production** change rather than a writing one.

### 7. Names over role labels, by a wide margin

Both groups name people far more than they describe them: Movie Recaps uses 44
names per role label, Sakura 30. The research report's claim that these
channels narrate by role label ("the invigilator", "the CEO") is **not what the
captions show**. Our `[SPINE]` warning, which pushes toward names and against
bare "the man", is supported.

## Hooks: the pattern, and why it is not a frame description

The hook is spoken **over the beat-cut intro montage** - on tokyodrift2006
that is 20 cuts in 13.7 seconds. Any line that describes a specific frame is
therefore describing something that is not on screen, or is on screen for
0.65 of a second. The old Tokyo Drift hook did exactly that: *"A kid in an
auto shop opens a drawer and lifts out jumper-cable clamps"* - a precise
account of one shot at 02:48, played over twenty different shots.

So the hook is a **trailer voice**, not a shot description. It sells the
premise and the stakes. This is a rule about the writing, enforced partly by
gate and finally by the auditor, and it applies to **any** line spoken during
the montage, not just the one tagged `hook`.

### The pattern

1. **Not bound to a shot.** The hook binds to the montage, which keeps cutting
   underneath it until the line ends. No `clip_start`.
2. **No visual description of any specific frame** - no objects, positions or
   actions seen on screen.
3. **Delivers the title's promise.** If the title sells Tokyo, jail, a debt
   and a race, the hook pays those off. A title and a hook pulling in
   different directions wastes both.
4. **First sentence <= 6 words, landing on the music drop.** Short sentences
   after it.
5. **The question is film-level** - will he survive, win, get out - never
   scene-level ("what is in the drawer?").
6. **No spoilers**: nothing from after the first reveal's land.
7. The first line **after** the montage is where narration starts binding to
   shots again, and it should read as *here is how it started*.

### Three examples of the PATTERN

These are illustrations of the shape, written for *The Fast and the Furious:
Tokyo Drift*. **They are examples of a pattern, not a library.** Never copy one
for another film, and never copy one into a Tokyo Drift draft either - the
writer generates its own hook and the auditor checks it. They are here so the
shape is unambiguous:

> **A.** "Strike three. One more crash and he goes to jail. So they send him to
> the one city on earth where the cars drive sideways."

> **B.** "He's in Tokyo to stay out of jail. He can't drift. And after one race,
> he owes a stranger a car."

> **C.** "Sean Boswell never backs down from a race. In Arizona, that got him a
> criminal record. In Tokyo, it gets him a race against the yakuza."

What to read off them:

- Openers are **2, 8 and 7 words** - A's "Strike three." is the one that lands
  hardest on a drop, and it is two words.
- Every one states a **consequence** (jail, a debt, the yakuza), not a sight.
- "the cars drive sideways" and "he can't drift" are about the *premise* - the
  kind of film this is - not about a frame. That is the line the rule draws:
  a generic property of the world is allowed, a specific thing happening in a
  specific shot is not.
- None of them names an object you could point at in one cut.
- All three would still be true if the montage cut to entirely different
  footage, which is the practical test.

### The practical test

**Would this line still be true if the montage cut to twenty different
shots?** If yes, it is a hook. If no, it is a shot description wearing a
hook's tag.

## Titles: the formula, measured (item A6)

The English corpus, with views:

| views | title |
|---|---|
| 1.03M | Soldier Finds Kids Living Alone During a Zombie Apocalypse Unaware They Are Far More Dangerous |
| 808K | 200 + IQ Hacker Took Revenge on the Bank That Fired His Mother |
| 786K | In 1381, 1,000,000 Peasants Are Hunting the King After He Raises Taxes by 0.1% |
| 97K | Secret Underground Game Where You Can Gamble Your Life for Any Wish You Want |
| 79K | Soldier Discovers His Body is Being Used to Commit Crimes While He Sleeps |

Every one of them, with no exceptions in the sample:

1. **No film title and no character name.** The subject is a *role*: Soldier,
   Hacker, Peasants.
2. **Present tense**, even for a period film: *Finds*, *Are Hunting*,
   *Discovers*, *Took* being the one exception.
3. **A number when one exists**, and the more absurdly precise the better:
   200+ IQ, 1381, 1,000,000, 0.1%.
4. **The twist is withheld in a trailing clause** - the title stops exactly
   before the outcome: *...Unaware They Are Far More Dangerous*, *...While He
   Sleeps*, *...After He Raises Taxes by 0.1%*.
5. Length 11-16 words.

So the generator formula is:

```
[ROLE, never a name] + [present-tense verb] + [extraordinary situation,
stated as plain fact] + [trailing clause that withholds the outcome]
```

Sakura's titles follow a different, brand-wrapped shape - `REVIEW PHIM` +
premise + `|| SAKURA REVIEW` - with the premise in the middle. Since the user
asked the generator to match the **English** formula, that is what is specified
above.

Applied to our two films, as a check that the formula produces something:

- *Tokyo Drift*: "Teenager Is Shipped to Tokyo to Avoid Jail and Ends Up Owing
  the Yakuza a Car He Cannot Pay For"
- *Bad Genius*: "Straight-A Student Sells Exam Answers Across a Time Zone
  Before Anyone Notices the Clock"

Current title gate requires a verb and rejects `<Film> (<year>)`. Both of the
above pass it; neither names the film, so the gate is compatible with the
formula but does not yet enforce it.

## Conflicts with our current gates - FOR THE USER TO DECIDE

Flagged, not resolved.

### C1. Narration speed - our PHASE 2 change may have gone the wrong way

The research report's central production claim is that Mystery Recapped runs
**121 WPM** and that our `+22%` (198 WPM) was ~64% too fast. On that basis the
base rate was lowered to `-15%`, about **150 WPM**.

Measured here, on captions, with duration cross-checked against `info.json` and
a single isolated 60-second window as a second method:

| | WPM |
|---|---|
| Movie Recaps, 4 videos | 236, 239, 239, 245 |
| TheCutFrame | 205 |
| our OLD rate | 198 |
| our NEW rate | ~150 |
| report's figure for Mystery Recapped | 121 |

Every English channel in this sample is **faster than our old rate**, and
50-95% faster than our new one. The report's own text flags that the 121 figure
came from a third-party site's declared word count and was never independently
verified.

Honest caveat: **I did not sample Mystery Recapped.** It is possible that
channel really is slower and that these two are not representative of it. But
on the channels actually measured, the direction of our change is wrong.

Options are the user's: keep 150 for comprehension, go back toward ~200, or
sample Mystery Recapped before deciding.

### C2. Judgment ceiling may be calibrated to the wrong model

`[NARRATOR-VOICE]` caps judgment at **15% of lines**, set from the Bad Genius
human draft (7.5%). If Sakura is the model rather than that draft, the ceiling
is probably too low - his narrator presence runs 4.6-12.8 per 1000 words and
*rises* to its maximum in the final third, where ours is capped flat.

Also: the two measures are not the same unit. Ours counts *lines carrying a
judgment*; this study counts *markers per 1000 words*. Before any bar moves,
one of the two needs converting to the other, or the comparison is cosmetic.

### C3. Letting the film talk vs `[SPEECH-BLIND]`

Both English channels hand whole exchanges to the film's own dialogue. Our
`[SPEECH-BLIND]` gate does the opposite: it *fails the build* for narrating
around dialogue without saying what was said, which pushes every exchange into
narrator paraphrase.

These are not strictly contradictory - "say what was said" and "let the
original line play" can coexist - but the pipeline currently has no way to
express "hold narration here and let the film speak". `narration_silence_seconds`
is the nearest mechanism and it is reserved for reveals, deaths and climaxes,
3-6 per film.

### C4. Our naming rule is supported, not conflicted

Recorded because the research report says the opposite: measured, both groups
overwhelmingly use names. `[SPINE]` stands.

## Flat → voiced: ten pairs from the old Tokyo Drift draft

Left column is the shipped pre-craft line, unedited. Right column applies the
devices above. Each pair names the device it demonstrates.

### These were wrong the first time, and how

The first version of this section invented facts and leaked reveals in 4 of 10
pairs. Recording it because it is the exact failure the punch-up pass will have
by default, and it is why the two audits below exist:

| pair | what I wrote | what the data says |
|---|---|---|
| 5 | named the man at 00:39:25 **"Kamata"** | `chars` are *the man in the black T-shirt, the long-haired man in the dark jacket*. Kamata appears at **01:07** in a white suit and panama hat. Wrong person by 28 minutes |
| 6 | "He has been doing it **for months**" | invented duration, **and** it leaks R1 (the skim) 4.5 min before its land at 01:07:29 |
| 7 | "That is the part that **costs Han his life**" | foreshadows R2 7.6 min before its land at 01:15:07 |
| 9 | "the engine out of **Han's drift car**" | tags confirm a *Nissan Twin Cam 24-valve* in *the Ford's bay* - they never say whose car it came from |

Two more found on re-check, which nobody had flagged:

| pair | what I wrote | what the data says |
|---|---|---|
| 3 | "a **fist on the tailgate**" | the tag says *a shaggy green monster toy propped up in the driver's seat* |
| 4 | "calling him Donkey Kong **all night**" | another invented duration; the tag for that shot is two people standing in a lift in silence |

Every claim below was checked against `shots.json` `chars`/`action`, the
transcript, and the reveal-map land times. Line 104 turns out to sit at 4050s
with R1 landing at 4049s - so naming the skim there is legal by one second,
which is worth knowing rather than guessing.

**1. Opening race** (line 7, 309s) — device 5 (long then punch) + device 3
> *flat:* They line up in a half-built housing tract and tear away down the dirt street.
>
> *voiced:* They line up at a billboard for a housing development nobody has finished building, which tells you how much either of them cares where this ends. Then the dirt takes them.

*Checked:* tag names a `Shang-Ri-La Estates` billboard at a half-built tract.

**2. The detective's arithmetic** (line 13, 623s) — device 1 + device 4
> *flat:* Ken and Barbie walk free; their parents are hooked up. Screw-ups like him are a guaranteed conviction, and his car is already crushed.
>
> *voiced:* The detective calls the other two Ken and Barbie, and says their parents are connected enough that they go home tonight. Sean is a guaranteed conviction. Same crash, two different countries of consequence.

*Checked:* keeps the detective's own words rather than asserting which
characters he means - the tag for this shot shows only him and Sean.

**3. Twinkie's minivan** (line 29, 1254s) — device 4 (play the joke)
> *flat:* Off the lift comes a minivan painted Hulk green, a monster toy at the wheel.
>
> *voiced:* What comes out of the lift is a minivan. Hulk green, with a shaggy green monster propped up in the driver's seat. He is so proud of it, and I am not going to be the one to tell him.

*Checked:* the monster toy in the driver's seat is in the tag. The tailgate
fist I invented first time round is not.

**4. The name reveal** (line 39, 1596s) — device 5 (punch)
> *flat:* In the lift down, Twinkie spells out what DK stands for. Not Donkey Kong. Drift King.
>
> *voiced:* On the way down, Twinkie explains what the DK everybody keeps saying actually stands for. It is not Donkey Kong. Drift King.

*Checked:* no duration asserted. The tag is two people in a lift; the content
comes from the beat, not from anything I added.

**5. The table** (line 60, 2365s) — device 7, with no name available
> *flat:* The gangster leans across the table, grinning. By the end Han has dropped his eyes.
>
> *voiced:* One of the men at the table leans across it, grinning, and asks when a shipment is arriving. Han tells him to sit pretty and let him handle it. Watch who is comfortable in this room, and who is answering questions in it.

*Checked:* `chars` give no name for this man, so he gets none. The shipment
exchange is in the transcript at 2372.9-2378.7. The closing judgment is about
the power in the room, deliberately **not** about Han having a secret - that
would foreshadow R1, 28 minutes early.

**6. Han's warning** (line 94, 3779s — 4.5 min before R1) — device 1
> *flat:* Blood at his mouth, Neela at his shoulder. He did not just play with fire, Han says - he soaked the matches in gasoline.
>
> *voiced:* Sean is on the asphalt with blood at his mouth and Neela steadying his shoulder, and Han gives him the only telling-off in this film worth quoting: he didn't just play with fire, he soaked the matches in gasoline.

*Checked:* the line is verbatim in the transcript at 3786.5. Nothing is added,
because anything added here about Han's own position leaks R1.

**7. The skim** (line 104, 4050s — R1 lands at 4049s) — device 5
> *flat:* In the blue-lit office DK hears it: his own partner has been stealing from the operation. Han has been taking money out of the books.
>
> *voiced:* In a blue-lit office Takashi stands in front of his uncle's armchair while the accusation lands: the partner he built all of this with has been taking money out of the books. He does not deny it. He drops his eyes, which tells you he did not know either.

*Checked:* legal by one second. No duration, and no reference forward to R2.
"Drops his eyes" is in the tag; the inference from it is reasoning, not a fact
claim.

**8. Walking into the alley** (line 134, 4831s — after R2) — device 3
> *flat:* Night, steam venting over a crowded street. In dark clothes Sean turns into an alley where men are already waiting.
>
> *voiced:* Sean turns off a crowded street into a narrow alley where men are already waiting for him, carrying a bag of a dead man's money, to ask a yakuza boss for a favour. You can watch him decide not to think about it.

*Checked:* 4831s is after R2's land at 4507s, so "a dead man's money" is legal
here. It would not have been eleven minutes earlier.

**9. The rebuild** (line 155, 5195s) — device 1 + device 4
> *flat:* Hands polish the finished tail - black, twin white stripes, a Japanese plate. The Mustang is whole again.
>
> *voiced:* Hands polish the finished tail, black with twin white stripes and a Japanese plate on the back of a Mustang. A Nissan twin-cam sitting in a Ford's engine bay. It is the best idea the film has, and it never says a word about it.

*Checked:* tags at 01:25:24 and 01:25:34 give *Nissan motor sitting in the
Ford's bay* and *Nissan Twin Cam 24-valve cover*. They do **not** say the motor
came from Han's car, so that is gone.

**10. The outro** — device 2 (thesis, then ask)
> *flat:* The kid who was shipped to Tokyo to stay out of jail is the one everybody lines up against now. And this race, for once, he never went looking for.
>
> *voiced:* Sean spent his whole life being moved on, and he only wins the day he stops running. Han paid for that, and the film lets him stay. If that landed, tell me what to recap next.

*Checked:* last line of the draft, so every reveal has already landed.

Three things these deliberately avoid:

- **No invented durations.** "For months", "all night" - both were in the first
  version, both are the same error, and neither is in any tag or transcript.
- **No scattered "right?" or "you know?"** - the literal rendering of Vietnamese
  final particles, and the fastest way to make this read as filler (device 4).
- **No judgment that points forward.** The opinion in pair 5 is about the room,
  not about Han, precisely because an opinion can foreshadow without using any
  of R1's protected keywords.

## What this document does not establish

- No retention data. Nobody measured whether any device keeps anyone watching;
  the user's own preference is the only evidence that Sakura works and Movie
  Recaps does not.
- Sample is 9 videos, and only 3 are the primary model.
- Sentence-length SD exists for 1 of 3 Sakura videos. The 10.2 figure is one
  video.
- Reveal staging and action compression were **not** measured. Doing it
  properly needs the films themselves aligned to the narration, not captions
  alone; a caption file cannot tell you where a reveal lands in the plot.
  Listed in the task brief, not delivered - saying so rather than guessing.
