# Advisory: 2026 platform/legal risk — changes to impose

Handoff review for the code side. Source research: `reports/Recap film copyright
safety.md` + notes in `research_notes/Recap film copyright safety/`. Each item
names the file/gate to touch and the evidence behind it. Nothing here changes
craft rules; it changes what YouTube's bots and rights-holders' lawyers see.

Context in one paragraph: July 17 2026, KADOKAWA v. recap YouTubers (N.D. Cal.)
ruled narrated/TTS recaps are **not fair use** ("describe and narrate", not
criticism) and unmasked three 350–550k-sub channels; appeal pending. Cordova v.
Huneault (N.D. Cal., Jan 2026) made stream-ripping footage a DMCA §1201
violation independent of fair use. YouTube's "inauthentic content" policy (Jul
2025, clarified Jul 16 2026) demonetized template farms — the Jan–Feb 2026
purge removed 4.7B+ views and 35M cumulative subs by Jul 2026. Daily reality is
milder: 2.5B Content ID claims in 2025, >90% monetized-not-blocked, <1% of
escalations become lawsuits. We survive by reading as "authored critical
review", not "mass-produced re-narration".

## 1. Ingest sourcing guard — §1201 exposure

- **Where:** `pipeline/download.py` / `recap.py ingest` (README accepts a
  YouTube URL as a first-class source).
- **Change:** when the source URL is a YouTube (or other streaming) link, print
  a §1201 warning and require an explicit `--i-own-the-risk` style flag; store
  the source type in project state. Document in `SHIP_CHECKLIST.md` stage 1:
  preferred source is a copy we own (disc/purchase/file), not a rip of an
  official channel — *including free official channels* (Youku/GMMTV upload
  free-to-earn ad revenue; ripping theirs both triggers clean reference-file
  claims and adds §1201 exposure).
- **Evidence:** Cordova (Jan 2026); notes `asian_drama_enforcement.md`.

## 2. Music provenance gate — most consistent claimant class

- **Where:** `pipeline/music.py`, `pipeline/stems.py`, render timeline.
- **Change:** add `[MUSIC-PROVENANCE]` gate — every music cue in the final
  timeline must resolve to our licensed/self-produced library; any cue sourced
  from the film's own audio stems fails hard. If current renders already carry
  original score under narration, that is the single highest-probability claim
  on every video.
- **Evidence:** every claim Dead Meat (7M subs) absorbed came from music
  publishers (UMPG), zero studio strikes. Notes `studio_claim_behavior.md`.

## 3. Cross-project variation gate — the missing gate class

- **Where:** new `tools/cross_variation.py` + report hook. All ~115 existing
  gates validate *within* one film; YouTube's policy judges similarity *across*
  videos on the channel.
- **Change:** read the last N finished projects and flag when consecutive
  videos share: intro wording/structure, outro wording/structure, opener
  phrasing, title formula, or an identical PACING-CONTOUR shape. The slot
  architecture (`9647169`, `33bf259`, `daf3f9f` — intro/outro/reaction share/
  opener "by construction") fixes per-video compliance but makes every video
  structurally identical — exactly the "minimal variation across videos" clause
  named in the Jul 2026 policy. Ship as WARN first (observability), enforce
  after 3 projects of data. Slots must carry per-project variation seeds.
- **Evidence:** policy text + TechCrunch Jul 20 2026; purge data in
  `banned_channels_policy.md`.

## 4. PERSONA band: make room for visible review segments

- **Where:** `pipeline/pacing_gates.py` (`PERSONA_JUDGMENT_SHARE_MAX = 0.35`,
  `PERSONA_JUDGMENT_RUN_MAX = 2`, window checks), `config.py`.
- **Change:** the body-of-video craft band stays as-is. Add a designated
  REVIEW-OUTRO slot (15–30s authored opinion) exempt from PERSONA-RUN and the
  CEILING but bounded by its own min/max, plus optional per-act "take" lines
  counted in a separate quota. Rationale: the KADOKAWA ruling turns on
  narration-vs-criticism; the channel needs commentary that is *audible and
  attributable*, not just within a 35% ceiling. An opinion-dense outro would
  trip PERSONA-RUN today.
- **Evidence:** KADOKAWA Jul 17 2026; allowed-example wording ("add a storyline
  and commentary", "critical review") in `banned_channels_policy.md`.

## 5. Voice policy: real voice for flagships

- **Where:** none in code — `--voice mine` already exists (README stage 8).
  `config.py` DEFAULT_TTS_VOICE stays for volume lanes.
- **Change:** document the tiering in SHIP_CHECKLIST: human voice for channel-
  defining videos (first uploads, brand videos), TTS acceptable for volume
  lanes. Original-voice-vs-AI-voice is the clearest line between YouTube's
  allowed and disallowed examples.

## 6. Claim-rate telemetry as a pipeline metric

- **Where:** `pipeline/final_report.py` + a small `claims.json` per project
  (manual entry or YouTube Studio export paste).
- **Change:** record per-video claim events (claimant, share diverted,
  resolved/not). No public claim-rate-by-studio dataset exists; our own data is
  the fastest rights-holder-behavior signal and is the gate for entering the
  K-drama lane (deferred per report — Kocowa/wavve Americas can copy the
  KADOKAWA playbook at will).

## 7. Package: no fixed title/thumbnail formula

- **Where:** `pipeline/package.py`.
- **Change:** title options and thumbnail composition must vary per project
  (feeds item 3). If any cross-posting to Shorts/TikTok exists or is planned:
  never ship the identical file — Shorts get a distinct edit (Sydney the Song
  Cat's suspected trigger for the AI-farm flag was identical cross-posting).

## 8. Dead-zone ingest warning (list supplied by research side)

- **Where:** `recap.py ingest` preflight warning only — not a block, editorial
  choice stays human.
- **List (2026-11):** anime anything (KADOKAWA litigation lane); current
  Hollywood blockbusters; Lionsgate / MGM / Warner catalogs (claim-heavy,
  Lionsgate+WB escalate to strikes); original score anywhere (item 2).
  Preferred lanes feeding film selection: Chinese xianxia/fantasy web films,
  DTV thriller/horror 2026, Lifetime-style, short-form app dramas
  (ReelShort/DramaBox), plus non-film lanes (manhwa/web-novel narration, true
  crime) that bypass film rights entirely.

## 9. Per-project runtime band override (P1 format) — UNBLOCKING doublelife2023

- **Where:** `config.py` (RECAP_RUNTIME_*), `tools/write_plan.py:word_band()`,
  `pipeline/draft.py` runtime gate.
- **Problem:** `[RUNTIME-BAND]` caps a recap at min(19 min, 20% of source
  length). The P1 vertical-drama format compiles a ~70-min source, so 20% =
  13.9 min — the band inverts (lo 2940 > hi 2919 words) and NO plan can
  validate, even a 15-minute one. The guard was calibrated for 2h+ features;
  every prior film clears it.
- **Change (agreed with Operator):** allow `projects/<p>/project.json` to
  override `RECAP_RUNTIME_MAX_MINUTES` and `RECAP_RUNTIME_PCT_HI` per project
  (global defaults untouched). Set for doublelife2023: MAX=27, PCT_HI=40 →
  band ≈ 2,809–5,420 words, matching the P1 niche target of 20–35 finished
  minutes. Gate logic itself unchanged — only the numbers become per-project.
- **Status:** plan.json for doublelife2023 is authored against this band and
  waits on this change to validate.

## Priority order

1 → 2 → 3 are existential (lawsuit lane, claim lane, policy lane). 4 → 5 make
the channel defensible. 6 → 8 are cheap and feed film selection. Item 3 is the
only large build; everything else is small.
