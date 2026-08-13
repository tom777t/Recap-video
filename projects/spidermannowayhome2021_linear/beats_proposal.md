# Spider-Man: No Way Home (2021) - Beat List Proposal (Stage 1.5 scaffolding)

Source: theatrical ~148 min. The local file is "Người Nhện - Không Còn Nhà
(Bản mở rộng)" = *The More Fun Stuff Version*. The ONLY difference from theatrical
is a bonus INTRO segment at the very start (Holland + Maguire + Garfield sitting and
chatting about the film); the rest is IDENTICAL to theatrical. So once we skip that
intro, Wikipedia's theatrical plot matches 1:1 and beat anchors line up.
AUDIO IS ENGLISH (only the filename is Vietnamese - same as the John Wick case).
Transcribe DIRECTLY as English: --model small, NO --translate.

*** EXCLUDE THE BONUS INTRO ENTIRELY *** Two reasons: (a) it is off-narrative -
actors chatting, not part of the story; (b) it SPOILS R4 - all three Spider-Men
appear together in that intro, which would blow the film's biggest reveal before it
is earned. The recap covers ONLY the film proper, starting at the real opening (the
Far From Home fallout - Peter's identity exposed). After ingest, CONFIRM the exact
timestamp where the real film begins; all beat anchors below are measured from THAT
point (= theatrical 00:00), not the file's 00:00.
style: linear
depth_target: fuller_recap
# Tier reverted video_essay -> fuller_recap (14-17 min): the final-act rework removed
# duplicate/mis-anchored lines (id531 didn't exist, id591/id60 were one beat, id56/id562
# overlapped), so the honest runtime landed at 16.9 min - a fuller recap. Tier fits the
# film, not the film to the tier; enriching back to 18 would be padding to hit a number.
Target: 14-17 min fuller recap, ~2800-3400 words. Register B (Medium).
Director: Jon Watts. Writers: Chris McKenna, Erik Sommers.

PRE-CATALOGUE reference: read Wikipedia (Plot + Cast) ONLY - names, who's-who,
structure. Did NOT read reviews/ratings/analysis (per style guide PRE-CATALOGUE
rule). Wikipedia is a MAP: where the extended cut's frames differ from the summary,
the FRAMES win.

Timestamps below are approximate story-order anchors; EVERY shot frame-verified at
Stage 2 (doubly important on an extended cut the summary does not describe).

*** FILM-START OFFSET (CONFIRMED at ingest) ***
The bonus intro runs from file 00:00:00.8 to ~00:00:59. Structure verified by
transcript + frames:
  - 0.8s - ~58.4s: Holland + Maguire + Garfield chatting ("I'm joined today by
    Tobey Maguire and Andrew Garfield... worth the wait"). ALL THREE SPIDER-MEN on
    screen together = the R4 spoiler. EXCLUDED from the recap entirely.
  - ~59-63s: black transition.
  - ~64s: SONY logo (the film's real opening title card).
  - 59.66s: the film's first audio begins - the news broadcast replaying Mysterio's
    death + exposing Peter ("We come to you now with revelations about last week's
    attack in London..."). This is exactly where Wikipedia's Plot opens.
THE FILM PROPER STARTS AT ~00:00:59.7 (treat as file 00:01:00).
=> FILM_START_OFFSET = +60s (approx). To convert a THEATRICAL timestamp (Wikipedia /
the beat anchors below, which are measured from theatrical 00:00) to a FILE
timestamp for catalogue: file_time = theatrical_time + ~60s. Frame-verify each shot
against the file; NEVER catalogue anything before file 00:01:00 (that is the intro).
Cold-open hook (B01) is drawn from the exposed-identity broadcast at file ~00:01:00,
NOT the actor intro.

KEY: chars = expected on-screen (verify at catalogue). [S6] = 4+ shots / micro-montage
(action set-pieces MUST be [S6]). [S7] = whole-frame censor. [S9] = silence shot.

================================================================================
names.json (fill/verify at catalogue) - CORRECT SPELLINGS from Wikipedia Cast
================================================================================
HEROES / ALLIES:
  Peter Parker / Spider-Man (Tom Holland) - "Peter-One" (this universe's Peter)
  MJ = Michelle Jones-Watson (Zendaya) - Peter's girlfriend
  Ned Leeds (Jacob Batalon) - Peter's best friend
  May Parker (Marisa Tomei) - Peter's aunt  [DIES - see REVEAL MAP]
  Happy Hogan (Jon Favreau) - Stark head of security
  Dr. Stephen Strange (Benedict Cumberbatch) - Master of the Mystic Arts
  Wong (Benedict Wong) - Sorcerer Supreme
  Flash Thompson (Tony Revolori) - classmate/rival
  Matt Murdock (Charlie Cox) - lawyer (Daredevil; cameo, do NOT over-name)

VILLAINS (multiverse, from earlier Spider-Man film franchises):
  Norman Osborn / Green Goblin (Willem Dafoe) - Raimi universe
  Otto Octavius / Doctor Octopus / "Doc Ock" (Alfred Molina) - Raimi universe
  Max Dillon / Electro (Jamie Foxx) - Webb / Amazing universe
  Flint Marko / Sandman (Thomas Haden Church) - Raimi universe
  Dr. Curt Connors / Lizard (Rhys Ifans) - Webb / Amazing universe

THE OTHER TWO SPIDER-MEN  [MAJOR REVEAL - see MAP]:
  "Peter-Two" = Tobey Maguire's Peter Parker (Raimi films) - organic webbing
  "Peter-Three" = Andrew Garfield's Peter Parker (Webb / Amazing films) - lost Gwen

CAMEO (mid-credits): Eddie Brock / Venom (Tom Hardy) - leaves symbiote piece.
Places/orgs: New York Sanctum, Department of Damage Control, Statue of Liberty
(climax), Mirror Dimension, MIT (the college subplot).

================================================================================
*** REVEAL-ZONE BEAT-MAP (SPOILER DISCIPLINE - the load-bearing section) ***
================================================================================
This film's ENTIRE marketing hid its reveals. Per prompts/style_linear_vn.md
SPOILER DISCIPLINE, each reveal below is KNOWLEDGE-TO-PROTECT. It stays hidden in
the narration until its named film beat, REGARDLESS of narration order. Narrate
every earlier scene with ONLY what a first-time viewer knows at that point - never
with hindsight. When in doubt, treat as a reveal and hold.

(Beat anchors reference the B## list below; timestamps are theatrical-cut
approximations and MUST be re-fixed to the extended cut at frame-verification.)

R1. THE VILLAINS ARE FROM OTHER UNIVERSES (and WHICH villains):
    - Doc Ock (Molina) first appears / attacks: reveal at B08 (~00:30). Hold his
      name+origin until he is on screen; do not pre-announce "Doctor Octopus."
    - Green Goblin (Dafoe) arrives same sequence: reveal at B08-B09 (~00:32).
    - Strange NAMES the multiverse cause (they're from other realities who know
      Spider-Man's identity): B10 (~00:35).
    - Electro (Foxx), Sandman (Church), Lizard (Ifans) captured/identified: B11
      (~00:38-00:42).
    HOLD: in ACT 1 (spell scenes, before B08) narration must NOT say villains or a
    multiverse are coming. The spell "goes wrong" - the viewer does not yet know
    into WHAT. Let B08 land the first villain.

R2. THE VILLAINS ARE PULLED FROM JUST BEFORE THEIR DEATHS:
    - Revealed in the Happy's-apartment discussion: B15 (~00:55). Hold until then;
      earlier villain scenes must not hint "they were about to die."

R3. MAY PARKER DIES (the emotional hinge / Uncle-Ben role):
    - Goblin's attack, May's death + "with great power..." line: B17 (~01:05).
    HOLD: May is present earlier (B02, B14) as a warm ally. Do NOT foreshadow her
    death. Her line lands only at B17.

R4. THE OTHER TWO SPIDER-MEN APPEAR (Maguire + Garfield) - THE headline reveal:
    - Ned's portal finds Peter-Two and Peter-Three: B19 (~01:15). This is the
      single most-protected beat. Nothing in ACT 1-2 narration may hint that other
      Spider-Men exist or are coming. Even the word "multiverse" earlier refers to
      villains only - do NOT extend it to "other Spider-Men" before B19.
    - Which is which: Peter-Two = Maguire (organic webbing, Raimi); Peter-Three =
      Garfield (lost Gwen, Amazing). Confirm identity by FRAME at catalogue.

R5. GARFIELD-PETER SAVES MJ (mirrors his failure to save Gwen):
    - Climax catch: B23 (~01:35). Hold the "he once failed to save Gwen" weight
      until it pays off here; if mentioned earlier it spoils the catch.

R6. ENDING: PETER ERASES HIMSELF FROM EVERYONE'S MEMORY:
    - Strange's final spell, the world forgets Peter: B25-B26 (~01:40). The
      bittersweet ending - hold it; do not telegraph "he'll be forgotten."

R7. MID-CREDITS: EDDIE BROCK / VENOM (Tom Hardy) cameo + symbiote piece left behind:
    - Post-B26 stinger. A cameo - hold; only include if we cover credits stingers,
      and never earlier.

<!-- Machine-readable distillation of the reveal-map above. The REVEAL-TIMING
     gate reads THIS block only. Terms are word-boundary matched; land is a beat
     id (resolved to the film's HH:MM beat time) or a raw timestamp, or
     mid-credits (= protect always). Split monster-vs-man where the civilian
     name is legitimately early (Osborn-the-man is NOT protected; the Goblin is). -->
```reveal-map
R1-ock  | land: B08 | hold: Doc Ock, Doctor Octopus, Otto Octavius
R1-gob  | land: B08 | hold: Green Goblin, the Goblin
R1-multi| land: B10 | hold: multiverse, other universes, other realities
R2      | land: B15 | hold: just before their deaths, about to die, pulled from before
R3      | land: B17 | hold: May dies, May's death, aunt's death
R4      | land: B19 | hold: Maguire, Garfield, Peter-Two, Peter-Three, other Spider-Men, two other Spider-Men
R5      | land: B23 | hold: Gwen
R6      | land: B25 | hold: erases himself, world forgets, forget him, forgotten by everyone
R7      | land: mid-credits | hold: Venom, Eddie Brock, symbiote
```

<!-- SET-PIECES: machine-PROPOSED (Wikipedia content list + S6 beats), then each
     range DENSE frame-verified (1-2s frames start-to-finish across every
     boundary and interior lull - NOT sampled; these exact Statue scenes drifted
     2 min under sampling twice) and HUMAN-CONFIRMED (keep = followability-
     critical; range signed off by eye). The SET-PIECE COVERAGE gate measures
     ONLY 'keep' rows, in SCRIPT stage only. A followable fight needs no long
     unnarrated stretch: within each kept range, no gap between consecutive
     narration lines (or from a range edge) may exceed the tier-relative
     max-gap = max(240s, 3x the recap's own median line gap). Non-combat
     stretches are DELIBERATELY unmarked (never measured), so the gate can never
     fire on a quiet/dialogue scene. verified: dense is required for trust; a
     'keep' row marked sampled/unverified warns (the gate is honest about its
     own foundation). Fields: id | name | start - end | verified | keep/drop. -->
```set-pieces
# method: ranges DENSE frame-verified (1-2s frames start-to-finish), not sampled
SP1 | Highway / Doc Ock      | 00:35:00 - 00:39:45 | verified: dense | keep
SP2 | Apartment / Goblin      | 01:21:10 - 01:24:58 | verified: dense | keep
SP3 | Statue of Liberty combat | 01:53:44 - 02:03:20 | verified: dense | keep
SP4 | Goblin rooftop fight     | 02:07:00 - 02:10:00 | verified: dense | keep
# UNMARKED non-combat (never measured): 01:50:40-01:53:44 Statue scaffold
# planning-dialogue; 02:03:20-02:07:00 Strange's spell VFX climax + MJ fall/catch
# (an emotional beat, already covered) - no combat is left unmeasured here.
# S6 candidate DROPPED (not followability-critical): B04 forget-spell (~00:14).
```

================================================================================
STYLE REMINDER (linear mode)
================================================================================
- Follow the FILM'S OWN ORDER. One cold-open hook exception allowed, then strictly
  chronological. The hook may use the identity-crisis premise WITHOUT leaking any
  R1-R7 reveal.
- Name + role every key player on first appearance - but only WHEN the film
  introduces them (villains as they arrive, the two Peters only at B19).
- Action set-pieces earn the most shots ([S6], 3-4+): the Sanctum/Mirror-Dimension
  chase, the highway Doc Ock fight, Happy's apartment, and the Statue of Liberty
  climax.
- Comprehension spine: WHO (Peter, exposed to the world), WHAT he wants (his old
  life / anonymity back), WHAT goes wrong (the spell), and the cost (May, then the
  choice to be forgotten).

================================================================================
ACT 1 - Exposed: the spell, and the wish to be forgotten (~00:00 - ~00:30)
================================================================================
B01  ~00:00  COLD-OPEN HOOK: Peter's identity as Spider-Man is public (fallout of
             Far From Home); the world turns on him, Damage Control arrests him.
             Open the gap: the most famous teenager alive has lost his whole life -
             what would you give to take it back? (No reveal leaked.) chars: Peter, MJ
B02  ~00:05  Fallout: Matt Murdock gets the charges dropped, but Peter, MJ, and Ned
             are hounded; their MIT applications are rejected because of the scandal.
             May supports him. chars: Peter, May, MJ, Ned, (Murdock brief)
B03  ~00:10  Desperate, Peter goes to the New York Sanctum and asks Dr. Strange to
             make the world FORGET he is Spider-Man. Introduce Strange + Wong.
             chars: Peter, Strange, Wong
B04  ~00:14  Strange casts the forget-spell - but Peter keeps interrupting ("let MJ
             remember, and Ned, and May..."), CORRUPTING it. Strange contains it.
             The mistake that breaks everything. chars: Peter, Strange  [S6]
B05  ~00:20  Peter chases the MIT administrator to re-plead MJ's and Ned's case
             (Strange's suggestion), driving on the highway. chars: Peter
B06  ~00:24  Set up normal-life stakes before the storm: Peter, MJ, Ned, their future.
             The calm before the multiverse cracks. chars: Peter, MJ, Ned

================================================================================
ACT 2 - The multiverse cracks: villains arrive (~00:30 - ~00:55)
================================================================================
B07  ~00:28  On the highway something is wrong - a mechanical-tentacle attack tears
             at Peter's suit. (Introduce the threat; villain named at B08.) chars: Peter
B08  ~00:30  [R1] DOC OCK (Otto Octavius) revealed - he rips the Iron Spider nano-
             tech, which bonds to his tentacles and lets Peter control them. Then the
             GREEN GOBLIN (Norman Osborn) arrives and attacks. Strange teleports Peter
             back and cells Octavius. chars: Peter, Octavius, Osborn  [S6]
B09  ~00:33  [R1] Osborn briefly reclaims himself from the Goblin, destroys the mask.
             The split personality established. chars: Osborn
B10  ~00:35  [R1] Strange explains: the corrupted spell summoned people from other
             universes who KNOW Spider-Man's identity. The multiverse cause named
             (villains only - NOT other Peters). Orders Peter/MJ/Ned to catch them.
             chars: Strange, Peter, MJ, Ned
B11  ~00:40  [R1] The hunt: capture MAX DILLON / ELECTRO and FLINT MARKO / SANDMAN
             at a military research facility; CURT CONNORS / LIZARD also identified/
             celled. chars: Peter, Dillon, Marko, (Connors)  [S6]
B12  ~00:48  May helps Peter reach Osborn (found adrift at a shelter). Peter starts
             to see the villains as people who can be CURED, not just sent back.
             chars: Peter, May, Osborn
B13  ~00:52  [R2 setup] The villains, comparing notes, sense they were taken from
             their own worlds at a strange moment. (Hold R2's "just before death"
             framing until B15.) chars: Osborn, Octavius, Dillon

================================================================================
ACT 3 - Cure or send back: May's death (~00:55 - ~01:10)
================================================================================
B14  ~00:53  Strange wants to reverse the spell and send them all back. Peter argues
             to CURE them first so they don't return to die. Peter steals the spell,
             traps Strange in the Mirror Dimension, takes the villains to Happy's
             apartment. chars: Peter, Strange  [S6 - the Mirror Dimension clash]
B15  ~00:55  [R2] At Happy's, the reveal lands: they were each pulled from just
             before their deaths. Peter cures Octavius with Stark tech (Doc Ock freed
             of the tentacles' control). chars: Peter, Octavius, villains
B16  ~01:00  The Goblin persona RETAKES Osborn. He turns the villains against Peter.
             chars: Peter/Goblin, villains  [S6]
B17  ~01:05  [R3] Goblin fatally wounds MAY. Dying, she tells Peter "with great
             power, there must also come great responsibility." The film's heart.
             chars: Peter, May, Goblin  [S9 - let May's death breathe]

================================================================================
ACT 4 - Three Spider-Men and the Statue of Liberty (~01:10 - ~01:35)
================================================================================
B18  ~01:10  Broken by May's death, Peter is ready to just send the villains home to
             die. Ned discovers he can make PORTALS with Strange's sling ring; he and
             MJ search for Peter. chars: Peter, Ned, MJ
B19  ~01:15  [R4] *** THE HEADLINE REVEAL *** Ned's portal brings "PETER-TWO"
             (Maguire) and "PETER-THREE" (Garfield) - alternate Spider-Men summoned
             by the spell. They meet Peter-One, share their losses (Uncle Ben; Gwen
             Stacy), and lift him to fight in May's honor. chars: Peter-One,
             Peter-Two (Maguire), Peter-Three (Garfield), MJ, Ned  [S6]
             DRIFT-CRITICAL: three near-identical Peters in suits - frame-verify
             WHICH Peter every shot shows (see DRIFT flag below).
B20  ~01:22  The three Peters work together, developing cures for the villains and
             luring them to the Statue of Liberty. chars: three Peters  [S6]
B21  ~01:26  STATUE OF LIBERTY BATTLE: cures administered - Lizard, Sandman, Electro.
             Octavius helps cure Dillon. chars: three Peters, villains  [S6 - stages]
B22  ~01:30  Ned frees Strange from the Mirror Dimension. Goblin unleashes the
             contained spell - the barriers between universes tear open, countless
             others who know Peter's identity start pulling through. chars: Strange,
             Goblin, three Peters  [S6]
B23  ~01:33  [R5] Enraged Peter-One nearly kills the Goblin; Peter-Two STOPS him.
             Meanwhile Peter-Three SAVES MJ from a fall - mirroring his failure to
             save Gwen. The three inject the Goblin with the cure, restoring Osborn.
             chars: three Peters, Goblin, MJ  [S6]

================================================================================
ACT 5 - The choice to be forgotten (~01:35 - ~01:45)
================================================================================
B24  ~01:37  With universes tearing open, Peter-One realizes the only fix is to make
             EVERYONE forget he exists. He asks Strange to cast it. Goodbyes with the
             two Peters. chars: Peter-One, Strange, Peter-Two, Peter-Three
B25  ~01:39  [R6] Peter promises MJ and Ned he'll find them and remind them. Strange
             casts the spell - the whole world forgets Peter Parker. Everyone returns
             to their universes. chars: Peter, MJ, Ned, Strange  [S9 - the erasure]
B26  ~01:42  Two weeks later: Peter visits MJ and Ned to reintroduce himself - and
             decides NOT to. At May's grave he talks with an unknowing Happy, and
             resolves to carry on. New homemade suit; back to being Spider-Man, alone.
             chars: Peter, MJ, Ned, Happy  [S9 candidate - the quiet ending]
   [R7] MID-CREDITS stinger (optional, only if we cover stingers): Eddie Brock /
        Venom (Tom Hardy) in a bar, returns to his universe leaving a symbiote piece.
        Hold entirely until here.

================================================================================
DRIFT RISK FLAG (Stage 2 catalogue - HIGH PRIORITY per user)
================================================================================
Two catalogue traps in this film, both high-risk for binding narration to the
WRONG character's footage:

1. THREE PETER PARKERS, all in Spider-suits (B19-B24). Holland, Maguire, and
   Garfield are visually similar in-mask and the film intercuts them constantly.
   MITIGATION: frame-verify WHICH Peter each shot shows before tagging.
   Distinguishing cues to confirm at frames:
     - Suit design differs (MCU Iron-Spider/red-black vs Raimi classic vs Amazing
       Webb suit); unmasked faces are the surest tell.
     - Maguire (Peter-Two): organic webbing, older, Raimi-classic suit.
     - Garfield (Peter-Three): the Amazing/Webb suit, leaner, most talkative/quippy.
   Do NOT tag a generic "Spider-Man" in the three-Peter scenes - specify which.

2. FIVE VILLAINS from different universes, intercut in group scenes (Happy's
   apartment B15-B16, Statue of Liberty B21-B23). Electro/Sandman/Lizard/Goblin/
   Doc Ock share frames. MITIGATION: frame-verify each villain per shot; tag the
   specific villain, not "the villains," wherever narration names one.

Both are exactly the SCENE_DISCONNECT / wrong-character binding class from prior
films (Joker findings) - budget extra frame-verify time for B15-B24.

================================================================================
COVERAGE / DEPTH CHECKLIST (Stage 2 must satisfy)
================================================================================
- 26 beats over 5 acts. For fuller_recap (90-110 shots) that is ~3-4 shots/beat.
  Dialogue/setup beats run 2-3; the ACTION beats (B04, B08, B11, B14, B16, B19-B23)
  MUST run 3-4+ ([S6]).
- This is a talky, plot-dense film (unlike John Wick) - it should FILL the
  fuller_recap tier comfortably; the risk is UNDER-catalogue on the emotional beats
  (May's death, the two-Peters meeting) and the multi-character battles, not thin
  content. Frame-verify > memory on the extended cut.
- HOOK (B01): open the "most famous teen alive lost everything" gap; do NOT leak any
  R1-R7 reveal (no villains, no multiverse, no other Spider-Men, no May death).
- SPOILER re-check before drafting each act: does any line describe a later reveal
  with hindsight? If yes, hold it to its R-beat.
