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
devices above. **Facts only from the film** - nothing invented, no dialogue put
in anyone's mouth that the transcript does not support. Each pair names the
device it is demonstrating.

**1. Opening race** — device 5 (rhythm: long then punch) + device 3 (shared "you")
> *flat:* They line up in a half-built housing tract and tear away down the dirt street.
>
> *voiced:* They line up in a housing development nobody has finished building, which tells you how much either of them cares where this ends. Then the dirt takes them.

**2. The detective's arithmetic** — device 1 (narrator has a view) + device 4 (dry understatement)
> *flat:* Ken and Barbie walk free; their parents are hooked up. Screw-ups like him are a guaranteed conviction, and his car is already crushed.
>
> *voiced:* Clay and Cindy go home, because their parents know people. Sean is a guaranteed conviction, and his car is already scrap. Same crash. Two different countries of consequence.

**3. Twinkie's minivan** — device 4 (play the joke, don't report it)
> *flat:* Off the lift comes a minivan painted Hulk green, a monster toy at the wheel.
>
> *voiced:* What comes down the lift is a minivan. Hulk green, with a fist on the tailgate. He is so proud of it, and I am not going to be the one to tell him.

**4. The name reveal** — device 5 (punch) + withholding
> *flat:* In the lift down, Twinkie spells out what DK stands for. Not Donkey Kong. Drift King.
>
> *voiced:* Sean has been calling him Donkey Kong all night. On the way down, Twinkie explains what DK actually stands for, and it is the kind of correction you only need once. Drift King.

**5. Kamata at the table** — device 7 (name + role, never "the gangster")
> *flat:* The gangster leans across the table, grinning. By the end Han has dropped his eyes.
>
> *voiced:* Kamata runs the turf every one of these races happens on, and he is smiling the whole way through this conversation. By the end of it Han is the one looking at the table.

**6. Han's warning** — device 1 (opinion) + keeping the film's own phrase
> *flat:* Blood at his mouth, Neela at his shoulder. He did not just play with fire, Han says - he soaked the matches in gasoline.
>
> *voiced:* Sean has blood at his mouth and Neela at his shoulder, and Han gives him the only telling-off in this film worth quoting: he didn't just play with fire, he soaked the matches in gasoline. Han would know. He has been doing it for months.

**7. The skim** — device 5 (long mechanism, then punch)
> *flat:* In the blue-lit office DK hears it: his own partner has been stealing from the operation. Han has been taking money out of the books.
>
> *voiced:* Kamata goes through the books in front of his nephew and explains, without raising his voice, that the partner Takashi built all of this with has been taking money out of it for months. He finds out from his uncle. That is the part that costs Han his life.

**8. Walking into the alley** — device 3 ("you") + dropping the place-opener
> *flat:* Night, steam venting over a crowded street. In dark clothes Sean turns into an alley where men are already waiting.
>
> *voiced:* Sean turns into an alley that is already full of men waiting for him, carrying a bag of a dead man's money, to ask a yakuza boss for a favour. You can see him deciding not to think about it.

**9. The rebuild** — device 1 + device 4 (afterthought clause)
> *flat:* Hands polish the finished tail - black, twin white stripes, a Japanese plate. The Mustang is whole again.
>
> *voiced:* His father's wrecked Mustang goes back together around the engine out of Han's drift car - American shell, Japanese heart, built in the same room by both of them. It is the best idea the film has, and it never says a word about it.

**10. The outro** — device 2 (thesis, then ask)
> *flat:* The kid who was shipped to Tokyo to stay out of jail is the one everybody lines up against now. And this race, for once, he never went looking for.
>
> *voiced:* Sean spent his whole life being moved on, and he only wins the day he stops running. Han paid for that, and the film lets him stay. If that landed, tell me what to recap next.

Two notes on what these deliberately avoid:

- No scattered "right?" or "you know?" — the literal rendering of Vietnamese
  final particles, and the fastest way to make this sound like filler rather
  than voice (device 4).
- No invented dialogue. Pair 6 keeps the film's own line because it is better
  than a paraphrase; pair 7 states the outcome of a scene whose dialogue the
  transcript does carry.

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
