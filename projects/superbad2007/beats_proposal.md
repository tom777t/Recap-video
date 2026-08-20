# Superbad (2007) - Beat List Proposal (Stage 1.5 scaffolding)

Source: projects/superbad2007/source.mp4. Audio is English; transcribed
--model small, NO --translate. Cut length: ~113:30 of story plus ~5 min of end
credits (transcript.json duration 7120.21s). Frames: frames/overview/, 40
montage pages x 36 frames, one frame every 5 seconds, continuous across the
whole film.

style: linear
depth_target: video_essay
Target: 18-22 min, ~3400-4200 words. Register B (Medium).
ts_format: HH:MM
Director: Greg Mottola. Screenplay: Seth Rogen & Evan Goldberg. Producer: Judd Apatow.

TIMESTAMP CONVENTION: every beat stamp below is written 3-part HH:MM:SS, which
_beat_ts_seconds() always reads as HH:MM:SS regardless of the header. The
`ts_format: HH:MM` line above is therefore a no-op for this map as written - it
is declared only so that if anyone later shortens a stamp to 2 parts it is read
as hours+minutes (this map's convention) instead of being guessed.

TIER RATIONALE: `video_essay`. This is not a mood film and not an action film -
it is a wall-to-wall dialogue comedy that runs THREE storylines in parallel from
00:48:00 to 01:41:00 (Seth at Mark's party, Evan on the phone and then trapped
on a couch, Fogell in the patrol car) and hard-cuts between them. Comprehension
requires walking all three; dropping one makes the convergence at B39 read as a
coincidence. The catalogue came in at 181 shots against the tier's nominal
110-130 band - the overage is real coverage, not padding (see shots.json
_depth_note). If the SCRIPT-stage DRAFT-TARGET gate later shows the recap does
not need this much, cut BEATS, do not thin the catalogue.

PRE-CATALOGUE reference (A7): read Wikipedia Plot + Cast ONLY. No reviews, no
ratings, no analysis. The Cast section was cross-checked against the film's own
end-credit crawl (frames pages 39-40), which is more precise than names.json for
minor roles and settles the one identification Wikipedia's prose leaves open:
"Francis the Driver" = Joe Lo Truglio (the motorist who hits Seth) and "Mark" =
Kevin Corrigan (the party host in the yellow Brazil jersey, who ejects Francis
and later brawls with Seth). Where Wikipedia and the frames disagree, the FRAMES
win.

KEY: chars = expected on-screen (verified at catalogue). [S6] = multi-shot
action/sequence coverage. [S7] = censor flag at catalogue. [S9] = silence shot.

================================================================================
names.json (verified at catalogue) - CORRECT SPELLINGS
================================================================================
AS FIRST PRESENTED (safe to name on sight):
  Seth (Jonah Hill) - a high-school senior, loud, anxious, two weeks from leaving
  Evan (Michael Cera) - Seth's best friend since childhood, quieter, decent
  Fogell (Christopher Mintz-Plasse) - their friend; the fake ID says "McLovin"
  Officer Slater (Bill Hader), Officer Michaels (Seth Rogen) - two patrolmen
  Jules (Emma Stone) - throwing the party; asks Seth to buy the liquor
  Becca (Martha MacIsaac) - Evan's friend and the girl he wants
  Mark (Kevin Corrigan) - hosts the first party; Jacinda's fiance
  Francis (Joe Lo Truglio) - the motorist who hits Seth and offers a ride
  Nicola (Aviva Baumann); Jacinda (Carla Gallo); Mindy (Erica Vittina Phillips,
  the liquor store cashier); Homeless Guy (Clement Blake); Jane (Stacy Edwards,
  Evan's mother); Mrs. Hayworth (Brooke Dillman); Greg (Dave Franco);
  Miroki (Roger Iwami); Buddy at Party (Danny McBride); Math Teacher (Steve
  Bannos); Liquor Store Clerk (Joe Nunez); young Seth (Casey Margolis);
  young Becca (Laura Marano)

CHARS NOTE: names.json lists "Fogell" and "McLovin" as separate entries for the
same actor and the same visible person. This map and shots.json use "Fogell"
ONLY in chars, so the binding audit never has to resolve one body into two
names. Narration may say McLovin freely; claim.subject must say Fogell.

Whisper garble to ignore: "Fogo"/"Fogel" for Fogell; the ASR mis-attributes the
name in the party-ejection scene at 00:52:40 - the transcript's "Mark, you
weren't invited" is spoken TO the man being thrown out, but the lines at
01:08:00 ("hey Mark right there", "kick his ass Mark", "dancing with my fiance")
place MARK as the host. Trust the frames and the 01:08 lines.

================================================================================
STYLE REMINDER (linear mode)
================================================================================
- Follow the FILM'S OWN ORDER. One cold-open hook exception allowed, then stay
  strictly chronological.
- Three parallel threads from B24 to B39. Do not let a thread go dark for more
  than one beat without a re-anchor, or the convergence at B39 stops reading.
- Name + role every key player on first appearance.
- SPOILER DISCIPLINE: see the reveal-zone map below. Only two beats are
  protected, but both are load-bearing and both are late.
- No invented backstory. Present what the film shows.

================================================================================
*** REVEAL-ZONE BEAT-MAP (SPOILER DISCIPLINE) ***
================================================================================
This is a comedy, and most of it is genuinely unprotected - the McLovin ID at
00:27:25 is the film's advertised hook and the whole middle act depends on the
audience already being in on it. There are exactly TWO withheld-information
beats, both in the last fifteen minutes, and both work by RE-WRITING behaviour
the audience has already watched and misread.

SETUP ZONE: 00:00:00 - 01:37:35. Everything may be told plainly: the two seniors
and their deadline, Jules' party and the liquor errand, Becca and Evan, the fake
ID and the McLovin name, the failed buy, the robbery, the two officers collecting
Fogell, the motorist, Mark's party, the brawl, the friendship fight, the cruiser
hitting Seth, the escape, Jules' party and its three parallel disasters, the bust.

REVEAL ZONE: 01:37:35 - 01:47:15.

R1. THE OFFICERS KNEW FOGELL WAS UNDERAGE THE WHOLE TIME and staged the entire
    night on purpose.
    - Lands at 01:38:50, inside B53. Transcript-locked: "You're not 25, man.
      We're not idiots, McLovin." / "Did you know the whole time?" / "We're your
      age... we hated cops... we just wanted to show you cops can have a fun
      time too."
    HOLD: through B20-B52 every police scene must be narrated as exactly what it
    looks like - two incompetents drinking on duty, letting a kid fire a service
    weapon and preparing to blame a crash on two teenagers. That misreading IS
    the joke the reveal cashes. Any early hint that they are in on it kills the
    single best-built thing in the film.

R2. SETH ALREADY KNEW EVAN AND FOGELL WERE ROOMING TOGETHER, and had known all
    night.
    - Lands at 01:45:04, inside B57. Transcript-locked: "I was in your room like
      three weeks ago... I saw your housing forms. So I knew you and Fogell were
      going to live together."
    HOLD: Seth's aggression across the whole night reads as selfishness until
    this line turns it into grief he could not name. Fogell's slip at B42
    (01:25:02) is the audience's first hint and is allowed to land as a surprise
    TO SETH - narrate his reaction there as fresh hurt, never as confirmation of
    something he already knew.

DELIBERATELY NOT PROTECTED (both are reveals mechanically; neither is a spoiler):
  - The McLovin ID, 00:27:25. A hidden identity becoming visible, so it is tagged
    `reveal` in shots.json - but it is the trailer image and the premise of the
    next hour. Treating it as protected would be a misread of the film.
  - Fogell stepping out of the patrol car, 01:17:45. A reveal to SETH AND EVAN,
    not to the audience, who have been watching the police thread for half an
    hour. Narrate it as convergence, not as surprise.

AMBIGUITY-HOLD (G2): none. The ending resolves cleanly on both pairs and on the
friendship; there is nothing deliberately left open to protect.

<!-- Machine-readable distillation for the REVEAL-TIMING gate. Terms are
     word-boundary matched. `land:` is given as a RAW HH:MM:SS rather than a beat
     id on purpose: B53 opens at 01:38:05 but the admission is at 01:38:50, and
     B57 opens at 01:44:40 but the confession is at 01:45:04. Landing on the beat
     id would leave a 45s and a 24s window in which a spoiler would pass the gate.
     The raw stamp is the stricter and correct anchor. -->
```reveal-map
R1 | land: 01:38:50 | hold: knew the whole time, knew all along, were in on it, in on it, playing along, played along, saw through the ID, never fooled, not fooled, weren't fooled, knew he was underage, staged the whole night, in on the joke, pretending to be fooled
R2 | land: 01:45:04 | hold: already knew, knew for weeks, three weeks ago, housing forms, saw the forms, knew they were rooming, knew about the rooming, been hiding it
```

================================================================================
ACT 1 - Two weeks out: the errand is set (00:00 - 00:30)
================================================================================
B01 | 00:00:25 | Animated title sequence, then Seth driving while Evan takes his call at home - two unpopular seniors, two weeks from graduating to different colleges | Seth, Evan | montage, dialogue
B02 | 00:03:00 | Seth collects Evan; Evan's mother leans into the car window and Seth stares openly; the drive in | Seth, Evan, Jane | dialogue, transition
B03 | 00:04:42 | The convenience store: Seth at the magazine rack, then the two of them working down the aisles insulting each other | Seth, Evan | setup, dialogue [S7]
B04 | 00:07:00 | Older boys needle them on the pavement; PE on the track; the school day grinding past | Seth, Evan, Math Teacher | setup, dialogue
B05 | 00:08:40 | Evan and Becca in the hallway - she mentions the party, he offers to bring alcohol before he has thought about it | Evan, Becca | setup, dialogue
B06 | 00:11:10 | Home economics: Seth argues with the teacher, then Jules invites him to her party and asks him to buy the liquor. The errand that drives the film | Seth, Mrs. Hayworth, Jules, Evan, Miroki | dialogue, setup
B07 | 00:14:48 | Fogell struts in and announces he has a fake ID. The promise Seth already made becomes possible | Fogell, Seth, Evan, Jules | setup, dialogue
B08 | 00:17:05 | Cafeteria planning, and the flashback to young Seth compulsively drawing penises until the whole class finds out | Seth, Evan, young Seth, young Becca | dialogue, setup [S7]
B09 | 00:21:00 | Seth intercepts Jules in the breezeway and promises far more than he can possibly get | Seth, Jules | dialogue
B10 | 00:22:35 | The PE field: Seth and Evan lock the night down, Evan already queasy about it | Seth, Evan, Greg | dialogue, setup
B11 | 00:25:05 | Evan and Becca at her locker, both plainly pleased with each other | Evan, Becca | dialogue, emotion
B12 | 00:26:30 | The ID itself - a Hawaii licence, organ donor, one name only, McLovin - and the argument that follows | Seth, Evan, Fogell | reveal, dialogue
B13 | 00:29:35 | Evan's bedroom: the two get changed and kill time on a video game before heading out | Seth, Evan | setup

================================================================================
ACT 2 - The errand fails, twice (00:30 - 00:48)
================================================================================
B14 | 00:30:20 | The bus across town and the car-park briefing, Fogell dressed as his idea of a twenty-five-year-old | Seth, Evan, Fogell | transition, dialogue
B15 | 00:31:48 | Seth stalls his way round the supermarket liquor aisle, pockets a bottle and is caught and thrown out by a guard | Seth, Evan, Fogell | setup, action [S6]
B16 | 00:33:57 | The bus to the second store; Fogell rehearses being McLovin on the pavement and walks in alone | Seth, Evan, Fogell | transition, dialogue
B17 | 00:36:05 | Fogell stalls at the coolers, Seth and Evan argue on the kerb, and the cashier looks at the licence and starts ringing the sale up anyway | Fogell, Liquor Store Clerk, Seth, Evan, Mindy | setup, dialogue
B18 | 00:39:43 | The robbery: a hooded man vaults the counter mid-transaction, knocks Fogell down and empties the register | Fogell | action, aftermath [S6]
B19 | 00:40:10 | Seth and Evan at the window, unable to work out what has just happened to their friend | Seth, Evan | reaction
B20 | 00:40:40 | Officers Slater and Michaels arrive and take statements, more interested in each other's theories than in the crime | Officer Slater, Officer Michaels, Mindy, Fogell | setup, dialogue
B21 | 00:43:15 | Seth backs into the road mid-argument and is hit by a car | Seth, Evan, Francis | dialogue, action [S6]
B22 | 00:44:20 | The officers turn the McLovin licence over, hand it straight back and offer him a lift instead of booking him | Fogell, Officer Slater, Officer Michaels | dialogue, emotion
B23 | 00:46:00 | Francis buys the boys' silence with a ride to a party where there is drink | Seth, Evan, Francis | dialogue, transition

================================================================================
ACT 3 - Three nights in parallel (00:48 - 01:15)
================================================================================
B24 | 00:48:05 | Night falls and the film splits: Francis driving the boys one way, the patrol car carrying Fogell the other | Seth, Evan, Francis, Fogell, Officer Slater, Officer Michaels | establishing, dialogue
B25 | 00:51:35 | Mark's party: Seth and Evan work out they are the youngest people in the house | Seth, Evan | establishing, setup
B26 | 00:52:40 | Mark catches Francis on his phone, throws a punch and puts him out of the house | Mark, Francis | dialogue, action [S6]
B27 | 00:53:55 | Evan wants to leave and Seth will not go without the drink; the two of them split up | Seth, Evan | dialogue
B28 | 00:54:38 | The officers take Fogell drinking at Bailey's, and a brawl goes off around them | Fogell, Officer Slater, Officer Michaels | establishing, action
B29 | 00:56:15 | Seth is cornered by a stranger, pushes into the crowd, and ends up dancing with a very drunk Jacinda | Seth, Buddy at Party, Jacinda | dialogue, action
B30 | 00:57:10 | Becca rings Evan from the other party to check that he is still coming | Evan, Becca | dialogue
B31 | 00:58:40 | Seth empties an ice tub into a detergent box and works the party filling it | Seth | action
B32 | 01:00:55 | The robbery plays on the bar television while the three of them talk and become properly friends | Fogell, Officer Slater, Officer Michaels | discovery, dialogue
B33 | 01:03:45 | Three threads at once: Seth hunting the back rooms, Becca driving over, Evan pinned on a couch by men who will not let him leave | Seth, Becca, Evan | setup, dialogue
B34 | 01:06:30 | The patrol car night: the radio, the siren, a service pistol, and three men emptying their guns at a road sign | Fogell, Officer Slater, Officer Michaels | emotion, action [S6]
B35 | 01:08:00 | The stain Jacinda left down Seth's leg, and Mark demanding to know why he was dancing with his fiancee | Seth, Mark, Evan | discovery, dialogue [S7]
B36 | 01:09:40 | The brawl goes off across the room and Seth swings the liquor free and runs | Seth, Mark | action [S6]
B37 | 01:12:05 | The friendship fight in the middle of an empty street - selfish, held back, years of it - ending with Evan shoving Seth into the road | Seth, Evan | dialogue, action [S6]
B38 | 01:13:55 | The patrol car, nobody watching the road, hits Seth | Fogell, Officer Slater, Officer Michaels, Seth | setup, action [S6]

================================================================================
ACT 4 - Convergence and the party (01:15 - 01:37)
================================================================================
B39 | 01:15:15 | The roadside: the officers settle on blaming the boys, put them face down in the headlights, Fogell climbs out of the car, and all three run | Seth, Evan, Officer Slater, Officer Michaels, Fogell | action, dialogue [S6]
B40 | 01:20:42 | The night bus, where an old man takes a bottle out of Seth's jug, drinks from it and throws it down the aisle | Seth, Evan, Fogell, Homeless Guy | transition, action
B41 | 01:22:40 | The last walk to Jules' house: the three back together and the two of them still not speaking | Seth, Evan, Fogell | emotion
B42 | 01:23:35 | Jules' party: Seth delivers and the room cheers him, and Fogell mentions in passing that he and Evan are rooming together | Evan, Becca, Seth, Fogell | establishing, discovery
B43 | 01:25:35 | Nicola picks Fogell out of the crowd | Fogell, Nicola | setup
B44 | 01:27:00 | Evan and Becca by the lit pool, Becca getting drunker and more forward with every exchange | Evan, Becca | dialogue
B45 | 01:28:35 | Seth finds Jules in the kitchen and starts drinking hard in front of her | Seth, Jules | dialogue
B46 | 01:29:18 | Upstairs: Becca takes Evan to bed and he stops it, because she is too drunk for it to be fair | Evan, Becca | action, dialogue [S7]
B47 | 01:31:15 | Seth and Jules alone in the garden room, talking straight to each other for the first time in the film | Seth, Jules | dialogue
B48 | 01:32:25 | Fogell and Nicola - the one plan of the entire night that works | Fogell, Nicola | action, emotion [S7]
B49 | 01:34:45 | Seth goes for the kiss and Jules turns him down: not while he is this drunk | Seth, Jules | dialogue
B50 | 01:35:22 | Seth folds face down over the bonnet of a car outside, finished, as a patrol car turns into the street | Seth | reaction
B51 | 01:35:50 | The bust: Seth finds Evan unconscious and carries him out as the officers come through the front door | Seth, Evan, Officer Slater, Officer Michaels | action, discovery [S6]
B52 | 01:37:38 | A torch beam finds Fogell in the upstairs bed and Nicola bolts past the officer | Fogell, Officer Slater | action [S7]

================================================================================
ACT 5 - What the night was actually for (01:38 - 01:53)
================================================================================
B53 | 01:38:05 | *** R1 LANDS 01:38:50 *** The officers stand over Fogell braced for arrest and tell him they clocked the fake ID in the first minute - they are his age, they hated police at his age, and the whole night was staged to show him otherwise | Fogell, Officer Slater, Officer Michaels | reveal, reaction
B54 | 01:40:28 | The staged perp walk: a handcuffed McLovin marched past his classmates, playing it to the crowd | Fogell, Officer Slater, Officer Michaels | action
B55 | 01:40:52 | Seth carries Evan home on his back down an empty street | Seth, Evan | emotion [S9]
B56 | 01:41:30 | The officers put Fogell behind the wheel, then wreck the cruiser and set it on fire | Fogell, Officer Slater, Officer Michaels | action, emotion [S6] [S9]
B57 | 01:44:40 | *** R2 LANDS 01:45:04 *** The sleeping bags: Seth admits he found the housing forms three weeks ago, Evan admits he was only frightened of living with strangers, and they say the rest of it out loud | Seth, Evan | discovery, emotion
B58 | 01:47:35 | Morning in the basement, and neither of them can look at the other | Seth, Evan | reaction, dialogue
B59 | 01:49:45 | The mall: the four of them meet, the apologies land, and the two pairs ride away from each other in opposite directions | Seth, Evan, Jules, Becca | dialogue, emotion [S9]

================================================================================
SET-PIECES
================================================================================
Superbad has no combat, but it has two multi-stage sequences a first-time viewer
must be able to FOLLOW, not merely be told about. B39 is the one that matters:
it is where all three storylines finally collide, and if the recap compresses it
the convergence reads as coincidence. B56 is the film's physical climax.

VERIFICATION IS HONEST, NOT FLATTERING: both are marked `sampled`, not `dense`.
The overview grid gives a frame every 5 seconds continuously, which is enough to
place a scene but NOT enough for a fast-cut sequence (see docs/RULES.md B10 -
sampling at this cadence is exactly how the Spider-Man MJ anchor came out 2
minutes wrong through two rounds of "frame-verified"). Both rows will warn on
the KEPT-but-sampled check. That warning is correct and should stay up until
someone runs a 1-2s dense scan over these two windows.

The party brawls are recorded as `drop` so the decision stays visible and is not
silently re-proposed: both are short, comic, and carry no plot the narration
needs the viewer to track.
```set-pieces
SP1 | Roadside cover-up, Fogell revealed, and the escape | 01:15:15 - 01:20:32 | verified: sampled | keep
SP2 | Wrecking and burning the patrol car | 01:42:15 - 01:44:35 | verified: sampled | keep
SP3 | Mark's party brawl | 01:09:40 - 01:10:34 | verified: sampled | drop
SP4 | Bailey's bar brawl | 00:55:35 - 00:56:12 | verified: sampled | drop
```

================================================================================
CENSOR NOTES
================================================================================
R-rated comedy: explicit content is frequent but mild and comic, and there is no
gore anywhere in the film. The car hits, the punches and the cruiser crash are
all played without injury detail and stay censor none. Flagged at catalogue:
- B03 (00:04:42) porn magazine cover - blur_light
- B05 (00:09:35) porn-site trailer on the laptop - blur_light
- B08 (00:18:10 - 00:19:52) young Seth's drawings, three shots - blur_light
- B35 (01:08:00) the period-blood stain, close-up - blur_light
- B46 (01:30:20, 01:33:25) Becca undressing / getting dressed again - blur_light
- B48 (01:32:25) Fogell and Nicola, the only actual sex scene - blur
- B48 (01:34:15) the two of them afterwards - blur_light
- B52 (01:37:38) Fogell shirtless as the torch finds him - blur_light
Total: 10 blur_light, 1 blur, 170 none across 181 shots.
