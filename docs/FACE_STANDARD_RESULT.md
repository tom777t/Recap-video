# Result — face-availability audit of arm-A names, 2026-09-05

Standard pinned in `FACE_STANDARD.md` before any frame was opened. Not revised
mid-run. 30 arm-A shots that produced a name; **every frame the tagger was
given** was opened, 86 frames total.

## Counts

| batch | FACE | AMBIG | NO-FACE |
|---|---|---|---|
| 1 | 8 | 2 | 0 |
| 2 | 8 | 0 | 2 |
| 3 | 10 | 0 | 0 |
| **total** | **26** | **2** | **2** |

**Named with no identifiable face: 2 of 30 (7%).**

- `shot098` → `Bank`. Both frames are a night street: a distant motorbike rider
  in a helmet, then a car. No face resolvable in either.
- `shot110` → `Lynn`. A dark auditorium wide, presenter silhouetted and tiny
  against a projection screen; second frame is the screen alone.

`AMBIG` (2): `shot029` face in focus but head ~8-10% of frame; `shot032` face
turned to heavy rear-three-quarter.

## The binary does not hold — and not for the reason we expected

Only 2 cases landed in `AMBIG`, so the *size/focus* boundary was workable. The
binary fails somewhere else entirely:

> **A face being present does not mean the name attached to it is right.**

`shot163` → `Bank` and `shot165` → `Pat` both score **FACE**, cleanly and
unambiguously: large, sharp, unobstructed faces. The faces belong to **two
Western men in suits** in a corridor — the overseas exam officials. `Bank` and
`Pat` are Thai teenagers.

These pass the test this experiment was designed around, and they are wrong.

## Consequence

Three populations, not two:

| | count | detectable by a face-availability guard? |
|---|---|---|
| name with no face | 2 | **yes** |
| name on a face that is not that person | ≥2 | **no** |
| name on the right face | ≤26 | — |

A guard built on face availability would catch 2 of ≥4 demonstrable errors and
pass the other half **with a clean signal**, which is worse than no guard: it
would launder `shot163` as verified.

The upper bound of 26 is an upper bound only. Face *presence* was verified for
all 26; face *identity* was verified for none, and was explicitly out of scope
because it cannot be done by eye without the film open.

## What this does NOT say

- It does not say `names.json` should be removed. 26 of 30 had a face available
  to identify, and the control arm produced `(khong ro)` every time — never a
  better guess.
- It does not say the 26 are correct. Unmeasured.
- It does not say the rate is 7%. The sample is the empty-`chars` subset of one
  film, chosen precisely because it was expected to be face-poor. It was not:
  28 of 30 had a usable face, which is itself a finding about the catalogue.

## Bearing on the original concern

The reason the question was asked: `chars` and `claim.subject` are written by
the same agent, so `binding_audit` compares a fabrication against itself and
passes. `shot163` is exactly that failure with a face in frame to make it look
sound. **Unresolved, and face-availability is not the instrument that resolves
it.**
