# Reviewed exceptions — Bad Genius (2017), MACHINE pipeline

Findings **looked at and deliberately kept**. Each still prints on every run and
stays visible in the report; it just is not counted as a problem.

Not a mute button: the key names the exact finding, never the gate; a blanket
entry is refused by the parser; an entry with no date or reason is refused; and
if the finding stops occurring the run reports it **STALE** and asks for
deletion, so a leftover note cannot cover the next one.

```reviewed-exceptions
REVEAL-TIMING | R1 L119 | 2026-09-10 | Line 119 IS the R1 payoff, not a leak of it. R1 ("Pat paid for the beating") lands at beat B48, 01:10:40 = 70.67 min. Line 119 sits at ~70.6 min, four seconds earlier, because it is bound to the moment that STARTS at 01:10:35 - the shot in which the admission is spoken. The gate compares a line's start time against the beat's timestamp, so the line that delivers the reveal always reads as four seconds early. The reveal is dialogue-carried and this is the only moment in the catalogue that carries it; binding it later would put the narration after the audience has already heard it. Nothing before line 119 names Pat as the payer - verified by reading every line from 100 to 118.
```

## Why this one is not a spoiler

R1 is the film's first payoff and the thing the beat map protects. The gate is
doing exactly the right thing in principle: it scans for the protected term
appearing before its landing beat.

What it cannot distinguish is **the line that spoils a reveal** from **the line
that is the reveal**. Both contain the term, and the delivering line will always
start a few seconds before the beat timestamp, because the beat timestamp marks
the moment and the line is bound to the shot that contains it.

The check is a literal-term text scan and says so itself in its own output: it
cannot catch paraphrase or implied foreshadowing, and the Stage-7 watch remains
the backstop. This entry does not weaken that - it records one hit that was read
and kept, and leaves every other hit live.

## What was verified before keeping it

- Lines 100-118 read in full; none names Pat as the one who paid.
- Line 119's window is `01:10:35.125 -> ...`, note `B48`, the beat R1 lands on.
- The transcript for that window carries the admission, so the evidence for the
  claim is the speech in that moment and not a later one.
