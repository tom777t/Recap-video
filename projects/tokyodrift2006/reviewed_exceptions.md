# Reviewed exceptions — The Fast and the Furious: Tokyo Drift (2006)

Findings **looked at and deliberately kept**. Each still prints on every run
and stays visible in the report; it just is not counted as a problem.

Not a mute button: the key names the exact finding, never the gate; a blanket
entry is refused by the parser; an entry with no date or reason is refused;
and if the finding stops occurring the run reports it **STALE** and asks for
deletion, so a leftover note cannot cover the next one.

```reviewed-exceptions
REVEAL-TIMING | R2 L103 | 2026-09-11 | The matched term is "dies" in the sentence "Then the old man just sits there in silence, and the smile dies." It is about a smile on DK's face during the Kamata meeting at 01:07:09, not about a person. R2 protects Han's death, which lands at 01:15:07, eight minutes later. REVEAL-TIMING is a literal-term scan and says so in its own output; it cannot tell a dying smile from a dying man. Verified by reading every line from 01:05:24 to 01:15:07: nothing in that stretch foreshadows the crash, refers to Han in the past tense, or hints that the chase is his last. Rewording the sentence purely to silence the gate would be editing prose to satisfy a regex.
```

## Why this one is kept

The reveal-map on this film is deliberately strict — four protected facts,
two of them (Sean taking the crown, and the final-scene cameo) landing in the
last four minutes. That strictness is what makes a false positive worth
recording rather than quietly rewritten: the alternative is a habit of
rephrasing whenever a gate complains, which over time removes the gate's
ability to mean anything.

## What was verified before keeping it

- Every draft line between `01:05:24` and `01:15:07` read in full.
- No past-tense reference to Han anywhere before the crash.
- The word "dead" first appears at `01:15:39`, after the land.
- "stealing" first appears at `01:07:29.823`, exactly on R1's land.

## Not reviewed — left live on purpose

`[NAME-LEAK]` currently reports ten tokens that are real-world proper nouns
rather than characters: *Ken, Barbie, Japan, Hulk, Donkey Kong, Corolla,
Australian, Kabukicho, Ford's*. These are the gate's "verify this is real
on-screen text" class and they are correct to fire — each one is a claim about
the world that a reader should be able to check. They are **not** suppressed.
