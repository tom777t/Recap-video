# Bad Genius / ฉลาดเกมส์โกง (2017) - Beat List Proposal (Stage 1.5 scaffolding)

Source: `projects/badgenius2017/source.mp4`, 7793.06s = 129.9 min container.
AUDIO IS THAI. Transcript was made with Whisper `--translate` (Thai -> English
directly), so per RULES I4 it is used ONLY to LOCATE scenes and to tell who is
speaking. It is NOT a source for what happens. Quality is visibly better than the
last Thai film - full sentences, clean turn-taking - but "better machine
translation" is still machine translation, and A7 (Wikipedia Plot) plus the
frames remain the two sources that count. Where the transcript and the frames
disagree, the frames win; where the transcript and Wikipedia disagree, Wikipedia
wins over the transcript and the frames win over both.

The transcript romanises the lead as "Lin". `names.json` says **Lynn**. Use
names.json everywhere - narration, `chars`, this file.

style: linear
depth_target: video_essay
Target: 18-22 min, ~3400-4200 words. Register B (Medium).
Director: Nattawut Poonpiriya. GDH 559 / Jorkwang Films.

RUNTIME ACCOUNTING (frame-verified from the overview grid):
  00:00:00 - 00:01:22   distributor idents, ratings card, title cards - NOT narrative
  00:01:22 - 02:03:55   NARRATIVE = 7353s = 122.6 min
  02:03:57 - 02:09:50   end credits - NOT narrative
All coverage percentages in this file are against **122.6 min**, not 129.9.

TIER RATIONALE: `video_essay`. This is a heist film whose engine is MECHANISM -
an eraser wrapper, four piano fingerings, two shuffled question sets, barcodes
printed down a pencil, and a time-zone gap. A10 applies with unusual force here:
"don't narrate every punch" does NOT license "let the set-piece be
unfollowable", and every one of this film's four set-pieces is a procedure the
viewer must be able to follow or the scene is just people filling in circles.
That is what buys the runtime, not padding. Per A11 this can still come DOWN: if
honest enrichment lands at the bottom of the band, keep video_essay only if the
mechanism is actually legible at that length - otherwise drop to fuller_recap
rather than stretch.

================================================================================
*** VERIFICATION HONESTY - READ THIS BEFORE TRUSTING ANY TIMESTAMP ***
================================================================================
The overview grid is **1 frame every 5 seconds** (44 pages x 36 frames).

Measured against `_cuts.json` (1814 detected cuts):

  mean shot length   4.30s
  median shot length 3.00s
  p25                1.88s
  **74% of this film's shots (1346 of 1813) are SHORTER than the 5s grid step.**

So the overview grid is **coarser than three quarters of this film's shots**.
That is not "sampling is a bit thin" - it means the grid demonstrably cannot see
most of the film, and for any window under ~10s it gives one or two frames, which
cannot satisfy the TAGGING_GUIDE checklist item 2 ("is the moment visible across
the WHOLE window"). This is B10 (Spider-Man, 2-minute miss after two rounds of
"frame-verified") with a number attached.

Consequence, and it is enforced in `shots.json`:

  - Every shot carries a verification token in its `action` text.
  - `[dense 0.75s]`  = a `--zoom` burst at 0.75s spacing was read across the
                       whole window. Required for anything inside a set-piece.
  - `[grid 5s]`      = seen ONLY in the 5s overview. Acceptable ONLY for long
                       held shots (the interview inserts, the round-table
                       dialogue scenes) where the grid gives 3+ frames inside
                       the window and the framing does not change.
  - No shot is in `shots.json` on the strength of the Wikipedia plot or the
    transcript. Everything was seen.

Dense bursts read so far: 00:09:00, 00:11:40, 00:32:10, 00:57:55, 01:35:45
(span 20s each). Every other set-piece phase below is marked
`NEEDS DENSE SCAN` and is deliberately NOT yet in `shots.json`.

================================================================================
names.json - CORRECT SPELLINGS (use these, not the transcript's)
================================================================================
  Lynn          (Chutimon Chuengcharoensukying) - scholarship student, the lead
  Bank          (Chanon Santinatornkul)         - the other top student, poor
  Pat           (Teeradon Supapunpinyo)         - rich client, Grace's boyfriend
  Grace         (Eisaya Hosuwan)                - Lynn's first friend, an actress
  Lynn's father (Thaneth Warakulnukroh)         - a teacher

NOT in names.json, appear repeatedly, must NOT be named in narration (S5 - if
you cannot name them from names.json, describe the role instead):
  - the school director (woman, navy blouse) - the fee scene and the expulsion
  - the exam supervisor in the hall (man, green desk lamp)
  - the STIC administrator in Sydney (older man, dark suit, red tie)
  - Bank's mother (the laundry)

================================================================================
*** REVEAL-ZONE BEAT-MAP (SPOILER DISCIPLINE, A8) ***
================================================================================
This film is NOT twist-driven. It is a procedural: you watch the scheme get
built, run, and collapse. Most of it is unprotected and should be told plainly -
including the cheating itself, which is the premise, the title and the poster.

SETUP ZONE: 00:01:22 - 01:10:40. Everything may be told plainly - the fee, the
eraser, the piano code, the two question sets, Bank informing on her, the lost
scholarship, the STIC scheme, the time-zone plan, the barcode pencils, and the
fact that Bank is beaten and misses his exam. The audience SEES the beating
happen at 00:57:45; only the WHO is withheld.

REVEAL ZONE: 01:10:40 - 02:03:55.

R1. PAT PAID FOR THE BEATING. Bank was put in a landfill and lost his
    scholarship exam so that he would have no future left to refuse with.
    - Lands 01:10:40, inside B44. The film shows the assault at 00:57:45 with
      the attackers in silhouette and NO principal in frame - that framing is
      deliberate and it is the thing to protect.
    HOLD: across B33-B43 the beating must be narrated as what it looks like at
    the time - a robbery, or bad luck, the thing that empties Bank out and makes
    him available. Do not write "the attack that Pat arranged" anywhere before
    01:10:40. Do not foreshadow with "conveniently", "as if someone wanted",
    "no coincidence".

R2. BANK COMES BACK CORRUPTED. The boy who informed on Lynn out of principle
    ends the film blackmailing her into a bigger scheme.
    - Lands 01:58:45 - 02:01:00, inside B50/B51. The laundry has a new sign, a
      new bike and his name on it before he says a word - the image reveals it
      first.
    HOLD: through B45-B49 Bank is the one who paid the worst price. Let that
    stand. His denial of Lynn at 01:49:20 must read as him taking the fall, not
    as the first sign of the turn - at that moment it IS him taking the fall.

```reveal-map
R1 | land: 01:10:40 | hold: Pat paid, Pat arranged, Pat ordered, hired the men, paid the men, paid to have him beaten, set him up, arranged the beating, ordered the attack, no coincidence, conveniently beaten, wanted him desperate
R2 | land: 01:58:45 | hold: turns on her, blackmails her, becomes the villain, ends up worse, corrupted, no better than, sells her out, threatens to expose
```

DELIBERATELY NOT PROTECTED (H1) - each is mechanically a reveal; none is a
spoiler. Recorded here so a later pass does not "helpfully" add them:

  - **That Lynn cheats at all** (00:09:00 onward). This is the premise, the
    title and the marketing image. Protecting it would mean not being able to
    describe the film.
  - **Bank informing on Lynn** (00:39:40 / 00:40:00). Mechanically a reveal -
    hidden agent exposed - but the audience watched him watch her hands at
    00:33:00 and knows before the office scene does. This is convergence, not
    surprise: the Fogell-out-of-the-patrol-car case from H1. Narrate it as the
    thing arriving, not as a shock.
  - **The two question sets** (00:32:04). A reveal TO LYNN inside the exam. The
    audience gets it in the same shot she does, off an insert of the paper, so
    there is nothing to hold - and holding it would make the best set-piece in
    the film incomprehensible.
  - **That Lynn confesses at the end** (02:03:24; the beat map said 02:02:30
    until the 2s pass showed that timestamp is still the white corridor). The film OPENS on the
    interview room at 00:01:25 and returns to it eight times. The frame story
    is the film telling you where this ends; the question it poses is "how",
    not "whether". Treating the confession as a twist would misread the
    structure. (See STRUCTURE NOTE below.)

AMBIGUITY-HOLD (G2): **none in this film.** Checked explicitly at the reveal-map
step rather than skipped. The ending is not open - Lynn signs a confession and
the last shot is her giving it to camera. There is no deliberate unknown to
reconstruct, so no `ambiguity-hold` entry is declared. Recording the negative so
a later pass does not invent one.

================================================================================
STRUCTURE NOTE - the frame story (affects S2)
================================================================================
The film is NOT linear. It opens inside a STIC investigation interview
(00:01:25) and cuts back to that room at least eight times, with FOUR different
interviewees, before resolving there at 02:02:30:

  00:01:25 Lynn (striped top)      00:08:50 Lynn      00:29:15 Lynn
  00:24:40 Bank (blue shirt)       00:45:45 Bank      00:46:05 Bank
  00:48:10 Grace                   01:10:10 Pat       02:02:30 Lynn (white room)

These inserts are a SEPARATE visual register - black surround, single figure,
front-on, no cutting - and they are among the only long held shots in a film
whose median shot is 3.0s.

Recap consequence: the body of the recap still follows source-film time (S2),
and any interview insert used out of its source position MUST carry
`narrative_jump: true`. The cleanest use is the hook (S2 allows 1-2 out-of-order
lines): open on the interview room, then drop into 00:02:55 and run forward.
That is the film's own opening move, so it is not a liberty.

================================================================================
SET-PIECE RANGES (A10 / S6 / C2 gate SET-PIECE COVERAGE)
================================================================================
Four set-pieces plus one assault. Each is a PROCEDURE, and the test from A10 is
"could a first-time viewer follow it?" - not "is the fill high". Each range is
given with the stage breakdown that S6 wants (initiation / escalation / peak /
aftermath) and the current verification state.

SP1 | 00:09:00 - 00:14:00 | THE MIDTERM (the eraser)              | 5.0 min
     initiation  00:09:00 midterm card; Grace panics
     escalation  00:11:30 Lynn writes the answers on the eraser wrapper
     peak        00:11:41 the eraser goes back over her shoulder
     aftermath   00:12:40 the shoe relay under the desks; it works
     verified    DENSE at 00:09:00, 00:11:40. Remainder NEEDS DENSE SCAN.

SP2 | 00:22:25 - 00:23:45 | THE PIANO CODE, FIRST RUN             | 1.3 min
     initiation  00:22:25 "ข้อสอบปลายภาค 2/2557" card
     escalation  00:22:30 four fingerings, four answers, hands on desks
     peak        00:22:45 the code running across the whole room
     aftermath   00:23:45 payment, and Lynn's new standing
     verified    NEEDS DENSE SCAN (grid only).

SP3 | 00:30:45 - 00:39:20 | THE HALL EXAM (two question sets)     | 8.6 min
     THE BEST SEQUENCE IN THE FILM and the one most damaged by compression.
     initiation  00:30:45 the empty hall; both Lynn and Bank sitting it
     complication 00:32:04 Q40 asks which set you have - there are TWO papers
     escalation  00:32:30 Lynn runs both codes at once, one per hand
     peak        00:33:00 Bank watches her hands and understands
     aftermath   00:36:30 - 00:39:20 the last minutes, the eraser, the clock
     verified    DENSE at 00:32:10. Four other phases NEED DENSE SCAN.

SP4 | 00:57:40 - 00:59:10 | THE ASSAULT ON BANK                   | 1.5 min
     Not a "set-piece" in the pleasure sense; staged and multi-phase, so S6
     applies. initiation 00:57:40 the bike at night / escalation 00:57:46 the
     gate, the laundry basket, figures closing / peak 00:57:53 he is taken
     (silhouetted) / aftermath 00:58:30 the landfill, the walk out.
     verified    DENSE at 00:57:55.
     CENSOR: `none`. Frame-checked: the violence is in silhouette against a
     backlit gate, attackers unlit, no injury detail; the landfill shot at
     00:58:30 shows a bloodied face in a wide, non-graphic frame. S7 explicitly
     lists "dark/silhouette violence (already obscured by lighting)" under when
     NOT to censor. Tagging this would be reflex, not judgement.

SP5 | 01:21:00 - 01:49:20 | THE STIC OPERATION                    | 28.3 min
     The film's climax and by far the largest structure. Sub-phases:
       01:21:33 both of them hide a bagged phone inside a cubicle wall fitting
       01:22:30 the clock hits 8:30, the exam starts
       01:23:00 sections 1-2: memorise, transmit
       01:25:05 Bangkok receives; couriers, the queue
       01:28:45 the pencils being printed mid-exam
       01:30:35 Bank is watched, followed, stopped
       01:32:00 the phone into the toilet
       01:33:10 Bank taken out; Lynn sees it
       01:34:35 Section 4 alone - nothing to write on
       01:35:40 THE PIANO IN HER HEAD  <-- signature image, [S9]
       01:38:20 she makes herself sick to get out
       01:40:40 the administrator comes after her
       01:42:00 Redfern station - the chase (Wikipedia Filming confirms this
                was shot in the underground section of Redfern station)
       01:47:00 the last letters sent from the platform
       01:49:20 brought back; Bank denies knowing her
     verified    DENSE at 01:35:45 only. THIRTEEN of fourteen phases NEED
                 DENSE SCAN. This is the single biggest outstanding job.

================================================================================
BEAT MAP
================================================================================
KEY: [S6] multi-shot action/climax beat. [S9] silence candidate.
[S7] censor. chars = expected on screen, verified at catalogue.

ACT 1 - the eraser (00:01:22 - 00:24:00)
B01 | 00:01:25 | HOOK / frame story: Lynn alone at the interview table, a sealed bag of pencils and erasers pushed in front of her | Lynn | setup, establishing
B02 | 00:02:00 | Answer sheets, a student file, a crossword-champion clipping - who she is on paper | (none) | setup
B03 | 00:02:28 | The admission interview: her father presents the record, the director offers a scholarship | Lynn, Lynn's father | dialogue
B04 | 00:03:35 | The "development fee" - 120,000 - written on the air between them | Lynn, Lynn's father | discovery
B05 | 00:05:05 | New school, new uniform, the nickname on the form: Lin | Lynn | transition
B06 | 00:05:15 | Grace adopts her in the red corridor, straightens her glasses | Lynn, Grace | dialogue, emotion
B07 | 00:06:50 | The library floor: Lynn coaches Grace through set theory and it does not take | Lynn, Grace | dialogue, setup
B08 | 00:09:00 | MIDTERM. Grace, two seats away, is drowning | Lynn, Grace | setup [S6]
B09 | 00:11:30 | Lynn writes the answers onto an eraser wrapper | Lynn | action [S6]
B10 | 00:11:41 | The eraser goes back over her shoulder | Lynn, Grace | action [S6]
B11 | 00:12:40 | The shoe relay under the desks - the answers cross the room | Grace | action [S6]
B12 | 00:13:45 | It worked, and neither of them looks troubled by it | Lynn, Grace | emotion
B13 | 00:14:05 | Grace introduces Pat at the hotel; the pool at night | Lynn, Grace, Pat | setup
B14 | 00:15:16 | Pat's offer: a price per answer. Lynn listens and does not say no | Lynn, Pat | dialogue
B15 | 00:18:00 | At home she finds the receipts - the school took the fee anyway | Lynn | discovery
B16 | 00:18:40 | The piano: four fingerings, four answers | Lynn | setup
B17 | 00:21:20 | The clients in her living room, learning to read her hands | Lynn, Grace, Pat | dialogue
B18 | 00:22:25 | FINAL EXAM: the code runs at scale | Lynn, Grace, Pat | action [S6]
B19 | 00:23:12 | It pays. The money, and what it buys | Lynn, Grace | aftermath, emotion

ACT 2 - the informant (00:24:00 - 00:48:40)
B20 | 00:24:00 | Bank: the other top student, cleaning the school building on his scholarship | Bank | setup
B21 | 00:26:26 | Teen Genius - the school's two prospects side by side on a quiz set | Lynn, Bank | setup
B22 | 00:27:00 | The director puts them both up for the overseas scholarship | Lynn, Bank | dialogue
B23 | 00:28:30 | Bank's home: the laundry, the presses, the night shift | Bank | establishing
B24 | 00:30:45 | THE HALL EXAM begins - hundreds of desks, both of them in it | Lynn, Bank | establishing [S6]
B25 | 00:32:04 | Question 40 asks which paper you were given. There are two | Lynn | discovery [S6]
B26 | 00:32:30 | She runs both sets at once, one per hand | Lynn | action [S6]
B27 | 00:33:00 | Bank watches her hands long enough to understand | Bank, Lynn | discovery [S6]
B28 | 00:36:30 | The last minutes: the eraser, the sheet, the supervisor | Lynn | action [S6]
B29 | 00:39:00 | Outside: the clients pay, the messages land, it worked | Lynn, Grace, Pat | aftermath
B30 | 00:39:40 | Bank walks into the office with a sheet of paper | Bank | action
B31 | 00:40:00 | The office: the evidence on the desk, Bank standing there | Lynn, Bank | dialogue
B32 | 00:41:05 | Her father arrives and hears all of it | Lynn, Lynn's father | reaction
B33 | 00:42:30 | Scholarship suspended; the overseas application withdrawn | Lynn, Lynn's father | dialogue, aftermath
B34 | 00:45:28 | The corridor afterwards. Neither of them has anything to say | Lynn, Bank | emotion [S9]
B35 | 00:46:15 | Home, at the round table: her father, disappointed and gentle | Lynn, Lynn's father | dialogue, emotion

ACT 3 - STIC (00:48:40 - 01:18:00)
B36 | 00:48:40 | M6. She has stopped. Grace and Pat come back with something larger | Lynn, Grace, Pat | setup
B37 | 00:49:35 | Dinner with Pat's parents: Boston, and what a place there costs | Lynn, Pat, Grace | dialogue
B38 | 00:51:45 | STIC - one exam, sat all over the world on one day | Lynn | discovery
B39 | 00:54:20 | New York. Dubai. Sydney. The time difference is the whole plan | Lynn | discovery
B40 | 00:55:25 | The print shop: the map, a flag on Australia, the shape of it | Lynn, Grace, Pat | dialogue
B41 | 00:57:40 | Bank is taken at a gate at night and does not make his exam | Bank | action [S6]
B42 | 00:58:30 | He wakes in a landfill and walks out of it | Bank | aftermath, emotion
B43 | 01:00:30 | Pat sells the scheme to a hall of paying students | Pat | dialogue
B44 | 01:01:30 | The mechanism: a barcode down the side of a pencil | (none) | setup
B45 | 01:03:30 | Lynn goes to the laundry. Bank says no, then names a price | Lynn, Bank | dialogue
B46 | 01:06:00 | The rehearsal: sections, timings, the pencil run | Lynn, Bank, Grace, Pat | dialogue [S6]
B47 | 01:09:05 | The money on the table the night before the flight | Lynn, Bank, Grace, Pat | dialogue
B48 | 01:10:40 | *** R1 LANDS *** Pat lets slip that he paid for the beating | Lynn, Bank, Grace, Pat | reveal
B49 | 01:11:40 | Bank goes for him across the print shop | Bank, Pat | action [S6]
B50 | 01:13:25 | Lynn and Grace watch it. Bank walks out | Lynn, Grace | reaction
B51 | 01:16:34 | Bank comes back to the footbridge and tells her to finish it | Lynn, Bank | dialogue

ACT 4 - Sydney (01:18:00 - 02:03:55)
B52 | 01:18:30 | The harbour, the day before. The last quiet hour they get | Lynn, Bank | emotion [S9]
B53 | 01:20:10 | The morning: the mirror, the news, the walk in | Lynn, Bank | setup
B54 | 01:21:33 | In two cubicles at once they take down a wall fitting, tape a bagged phone inside it and put it back | Lynn, Bank | action [S6]
B55 | 01:22:30 | 8:30. The exam starts | (none) | setup [S6]
B56 | 01:23:00 | Sections 1 and 2: memorise, transmit, keep pace | Lynn, Bank | action [S6]
B57 | 01:25:05 | Bangkok wakes: the couriers, the queue, the printed shirts | Grace, Pat | action [S6]
B58 | 01:26:48 | Bank raises his price in the middle of the exam - another million, from a locked cubicle - and Bangkok pays it | Bank, Grace, Pat | dialogue
B59 | 01:28:45 | The pencils being printed while the exam is still running | Grace, Pat | action
B60 | 01:30:35 | Bank is watched, then followed, then stopped | Bank | action [S6]
B61 | 01:32:00 | The phone into the toilet | Bank | action [S6]
B62 | 01:33:10 | Bank is taken out of the hall. Lynn sees it happen | Lynn, Bank | reaction [S6]
B63 | 01:33:43 | At the water cooler she takes something out of the top of her boot and puts it in the water she then drinks | Lynn | action
B64 | 01:34:35 | Section 4, alone. Thirty questions and nothing to write on | Lynn | action [S6]
B65 | 01:35:40 | She plays them on a piano that is not there | Lynn | emotion [S9]
B66 | 01:38:20 | She makes herself sick to be let out of the room | Lynn | action
B67 | 01:39:30 | Out through the building, still sending | Lynn | action [S6]
B68 | 01:40:40 | The administrator comes after her | Lynn | action [S6]
B69 | 01:42:00 | Redfern: the crowd, the escalators, the platform | Lynn | action [S6]
B70 | 01:44:30 | Bangkok: the answers land and the couriers ride | Grace, Pat | action [S6]
B71 | 01:47:00 | The last letters, sent from the platform | Lynn | action
B72 | 01:49:20 | Brought back. Bank in the next room says he does not know her | Lynn, Bank | dialogue
B73 | 01:51:30 | Don Mueang: Pat and Grace with flowers and a score | Lynn, Grace, Pat | aftermath
B74 | 01:53:20 | Her father at the barrier | Lynn, Lynn's father | emotion [S9]
B75 | 01:54:30 | The party she is not at | Grace, Pat | montage
B76 | 01:57:20 | Mister Bank: a new sign, a new bike, his name on it | Lynn, Bank | establishing
B77 | 01:58:45 | *** R2 LANDS *** GAT/PAT, nationwide. He wants her back in | Lynn, Bank | dialogue, reveal
B78 | 02:00:30 | She says no; he tells her what he will do about it | Bank, Lynn | dialogue
B79 | 02:02:05 | Her father, and the truth, in a white room | Lynn, Lynn's father | emotion [S9]
B80 | 02:03:24 | The confession, to camera. The frame closes | Lynn | reveal, emotion

================================================================================
SUB-MOMENT ENUMERATION (S10) - done for the beats catalogued so far
================================================================================
B08-B11 (SP1, the midterm) sub-moments:
  main_action:  the answers move from Lynn's desk to Grace's without a word
  reactions:    Grace's hand at her temple; Lynn's flat calm
  motifs:       the red eraser (returns at 00:36:30 and again as the STIC pencil)
  setting:      a bright ordinary classroom, one supervisor, no drama
  -> shots: setup (Grace drowning), action (writing the wrapper), action (the
     pass), action (the shoe relay), emotion (afterwards). 5 shots.

B24-B28 (SP3, the hall exam) sub-moments:
  main_action:  two papers defeat a code built for one, and she solves it live
  reactions:    Bank's slow understanding; the supervisor noticing nothing
  motifs:       hands - the whole film is hands; the clock
  setting:      an enormous hall, hundreds of desks, one green lamp
  -> shots: establishing (the hall), discovery (Q40), action (both hands),
     discovery (Bank sees), action (the last minutes). 5 shots.
     ONLY the Q40 shot is dense-verified so far.

================================================================================
OPEN QUESTIONS FOR THE NEXT PASS
================================================================================
1. SP5 needs thirteen dense bursts before any of it may enter shots.json.
2. `chars` on SP1: at 0.75s spacing I still could not tell Lynn from Grace with
   confidence in the over-the-shoulder pass at 00:11:41-00:11:47 (both are in
   identical uniform, both shot from behind, faces out of frame or soft). A5
   says admit uncertainty and flag rather than guess, so the pass shot is
   currently catalogued with `chars: ["Lynn"]` for the writing half only and the
   receiving half is left OUT of shots.json pending a face-visible frame.
3. Whether the interview inserts should be one reusable "interview" family or
   separate per interviewee - affects MAX_FAMILY_USES if the recap returns to
   the room more than twice.


================================================================================
REVIEWED DEPTH WARNINGS THAT ARE STAYING (S10: do not invent a shot to silence)
================================================================================
- DEPTH-REACTION on B59 (01:28:45, the pencils being printed while the exam
  runs). The gate is right that the beat has action coverage and no reaction
  shot, and right that the beat declares two characters. But the beat IS the
  machine: the press, the heap, the barcode going down the shaft. The only
  candidate reaction frame in the window (01:28:38, Grace and Pat's faces
  close together) sits between two press inserts and is cut against Sydney,
  so it is not a clean single-moment shot. Keeping one shot here is the right
  answer; the warning stands reviewed.
- DEPTH-REACTION on B54 was NOT left standing - the gate pointed at a real gap
  and the 0.75s burst turned out to contain the missing shot (01:21:39, Lynn's
  reflection in the open panel). Added. This is the gate working.


BEAT-MAP RETIMES (2026-08-31, from the 2s pass + the outline's BEAT-COVERAGE reading):
  B03: 00:02:55 -> 00:02:28
  B14: 00:15:30 -> 00:15:16
  B19: 00:23:45 -> 00:23:12
  B21: 00:26:45 -> 00:26:26
  B34: 00:45:30 -> 00:45:28
  B51: 01:16:40 -> 01:16:34
  B80: 02:02:30 -> 02:03:24 (recorded earlier)
In each case the beat header named a moment whose verified footage
starts earlier than the pass-1 estimate. The shots were not moved; the
headers were corrected to the footage.


============================================================

================================================================================
A11 TIER DECISION - RETRACTED 2026-09-05
================================================================================
This file previously recorded a drop video_essay -> fuller_recap under A11,
reasoning that honest enrichment had stopped at 16.3 min / 68% fill and that the
only capacity left sat on shot types A9 and I2 say to leave alone.

THAT DECISION WAS UNSOUND AND IS WITHDRAWN. The 68% was computed against
hand-authored word ceilings worth 61% of the value the engine derives. On the
settled basis the draft is at 41% fill, and the supporting claim - "everything
else is already in band: dialogue 73%, reaction 74%, setup 75%, discovery 81%" -
was an artefact of the same tight denominator. The real figures are dialogue 44%,
reaction 46%, setup 47%, discovery 50%, establishing 46%. Nothing is in band.

There are 915 unused words on dialogue shots and 485 on reaction shots. A9 calls
those coverage gaps, not honest slack. Enrichment stopped early because a bad
denominator reported it as nearly finished.

Tier restored to video_essay. The draft stands at 16.4 min / 41% fill and is
correctly flagged DRAFT-UNDER-TARGET and DRAFT-UNDERFILL. Enrichment must
resume; it is not finished.

A11 itself is not implicated - the rule is sound. What failed was the
measurement it was applied to. Recorded because an A11 drop that is really a
measurement error looks exactly like an A11 drop that is correct, and this one
arrived with three paragraphs of confident justification.

================================================================================
ENRICHMENT STOP (2026-09-05, after the capacity basis was settled)
================================================================================
Four acts enriched, validated after each (A1). Result:

  real-rate 16.4 -> 17.5 min   ABOVE the video_essay floor of 17.0
  fill       41% -> 45%        DRAFT-UNDERFILL still fires (threshold 65%)
  dialogue   44% -> 54%        reaction 46% -> 54%
  lines      150 (unchanged - deepened, never added; adding lowers fill)

Stopping here. Where the remaining capacity sits:

  action  31%, 1294 unused - A9 says unused capacity on action shots is HONEST
          provided the sequence is followable, and SP5's sixteen stages are all
          narrated. Leave it.
  emotion 37%, 628 unused  - A9 no longer covers emotional shots; I2 does. The
          A9/I2 disambiguation test: cutting these costs the sense of having sat
          in the moment, not an event. Leave it.
  dialogue/reaction both at 54% after enrichment - the A9-eligible categories,
          which is where this pass was aimed.

THE HONEST STATUS OF THIS DECISION. The tier-deciding number - runtime against
the floor - is MET, and that is a measurement. "Further filling would be
padding" is a JUDGEMENT and is not.

It is deliberately a weaker claim than the one made here yesterday and
retracted. Yesterday's claim was that categories were "already in band" at
73-81%; those figures were artefacts of a broken denominator and the true ones
were 44-50%. Today's claim is only that the runtime floor is met and that the
remaining slack sits in two categories two rules independently say to leave.
That is checkable, and B9/I3 both warn that fill is blind - it must never be the
thing being optimised.

If a later pass disagrees, the thing to re-examine is whether `action` at 31% is
really followable, not whether the number 45% is large enough.
