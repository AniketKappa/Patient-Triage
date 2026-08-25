# Sprint 03 — Minimum Prototype Expectations

Prerequisite: Sprints 01 and 02 pass.

This sprint builds the five items the submission is explicitly scored against. Treat each as a checkbox that a judge will tick or not tick. Every one must be **demonstrable in the running UI**, not just present in the database.

---

## Task 1 — The 20-patient demo cohort

The ~23 rows currently in the repo are *training* data for the resource model. That is a different thing. Build a separate, curated **demo cohort** in `seed_demo.py` with 20 records, each carrying an `expected_esi` and an `exercises` field naming what it tests.

Required composition (the brief names the first three explicitly):

| Case | Content | Tests |
|---|---|---|
| **Ambiguous** | Elderly patient, "just not feeling right," family reports confusion, vitals near-normal | AMS detected from a **family statement**; geriatric occult hypoperfusion; low-confidence handling |
| **Ambiguous 2** | Young woman, fatigue + nausea + jaw discomfort, normal vitals | Atypical ACS; no age gate; the presentation that undertriage literature is built on |
| **Paediatric** | 3-week-old, T 38.2, well-appearing otherwise | ESI 2 on age alone |
| **Paediatric 2** | 15-month-old, liquid stools, T 38, HR 158, RR 42, cap refill 3s | Age-banded thresholds; Gate D uptriage |
| **Geriatric** | 78M, blunt abdominal trauma, on warfarin, normal vitals | Mechanism + anticoagulation floor despite reassuring numbers |
| **Zero-history** | Unidentified patient, no MRN, chest pain | `history_depth=none`, wider set, escalate at the boundary |
| **Bradycardia** | 70F, dizziness, HR 32 | Gate A both-tails. Your pre-rebuild logic scored this ESI 5 — include the before/after |
| **Isolated ortho** | Ankle injury, pain 8/10, intact neurovascular | Correctly **not** ESI 2 |
| **Pregnancy** | 28F, 8 weeks, abdominal pain, HR 120, BP 92/50 | Ectopic; OB floor |
| **COPD baseline** | 72F on home O2, infected cat bite, SpO2 91% (baseline 90–91) | Baseline-relative SpO2; steroid-blunted immune response |
| **Fast-track** | Healthy 19-year-old, sore throat, normal vitals | Gate C = 1 resource → ESI 4 |
| **Non-urgent** | 42-year-old, lost rescue inhaler, asymptomatic | Prescription refill is not a resource → ESI 5 |

Fill the remaining 8 with ordinary ESI 3s so the cohort's level distribution looks like a real ED rather than a parade of edge cases.

**Half the cohort must have prior records and half must not** (brief reference parameter 3.3). Make this explicit in the seed data.

Ship a `/api/demo/cohort-report` endpoint returning expected vs. actual level for all 20 with a pass/fail column.

---

## Task 2 — 3× surge simulator

Brief requirement, currently absent entirely.

Build a replayable surge mode: `POST /api/demo/surge?multiplier=3` injects arrivals at 3× the baseline rate. Baseline should be derived from the brief's stated parameter of **100–500 visits/day** — state which figure you used.

**What must NOT change under surge** (and the demo must prove it):

| Unchanged | Changed |
|---|---|
| Acuity criteria and gate thresholds | Streaming: fast-track / vertical care / provider-in-triage activation |
| Model calibration | Reassessment **modality** — degrade from full vitals to visual sweep + targeted spot-check |
| Queue ordering rules | Staffing signal: acuity-burden distribution surfaced to charge nurse |
| **Reassessment intervals** | Waiting-room **aggregate risk** — sum of predicted deterioration probabilities |

Add a **surge banner** that states what did not change:

> **Volume 3× · Acuity criteria unchanged · Fast-track activated · Reassessment intervals unchanged**

This is a trust feature and a scoring feature. The fifth edition of the standard specifically removed language from Decision Point B because nurses were assigning acuity based on **bed availability rather than physiology**, and colleagues pressuring the triage nurse to downgrade during crowding is a documented dangerous practice. Your system must be structurally incapable of participating in that, and the banner is how you show it.

Report acuity distribution as **percentages by level, never a mean** — ESI is ordinal and cannot be meaningfully averaged.

Add a test: run the surge, assert that every threshold constant and every reassessment interval is byte-identical before and after.

---

## Task 3 — Confidence on every score, everywhere

Brief requirement: *the prototype must not return a score without a confidence indicator.* This is absolute. Audit every surface — patient row, needs card, API response, event log entry — and confirm no acuity level appears anywhere without confidence adjacent to it.

Display three axes separately, because each demands a different response from the nurse:

| Axis | Measures | Nurse's response |
|---|---|---|
| **Data completeness** | which required inputs are missing or stale | go get the missing datum |
| **Model confidence** | calibrated probability over the level | weigh the recommendation less |
| **Rule–model agreement** | did rules and ML converge? | look harder — this is the interesting case |

Add the **most informative missing input** line. Compute expected value of information across missing fields and name the single one that would most narrow the set:

```
ESI 3   ·   admissible {2, 3}   ·   moderate confidence
Recommending 2 — the set crosses the 2/3 boundary and we escalate on ties.
Most informative missing input: respiratory rate.
```

That last line converts "the AI is unsure" from a shrug into an instruction.

**Fix the conformal claim while you're here.** What's currently implemented is probability thresholding, not conformal prediction — there is no calibration set and no coverage guarantee. Two acceptable options:

- **(a)** Implement split-conformal properly: hold out a calibration split, define a nonconformity score, produce sets with a stated coverage level, and report empirical coverage on the demo cohort.
- **(b)** Rename it to `AdmissibleSet` / "probability-threshold set" and say plainly in the docs that it is not a coverage-guaranteed conformal set.

Either is defensible. Claiming conformal without calibration is not, and an ML-literate judge will ask.

---

## Task 4 — Override capture and a visible audit viewer

The brief says *capture at least one clinician override and **show what the system logs***. You capture it; you don't show it.

Build an audit viewer at `/audit/{patient_id}` rendering the event log as a human-readable timeline:

```
14:02  INITIAL_TRIAGE   AI    ESI 3   gate=C  resources=2  conf=moderate  set={2,3}
14:02  GATE_D_PROMPT    AI    RR 26 > 20 (adult)  → suggest ESI 2
14:03  HUMAN_OVERRIDE   RN Sharma (id: 4471)  ESI 3 → 2
                        reason: GATE_D_ACCEPTED
14:31  RE_TRIAGE        AI    ESI 2 → 2 (no change)  NEWS2 5 → 6
14:45  STATUS_CHANGE    RN Sharma  WAITING → IN_TREATMENT
```

Add the **second-look prompt** for the safety-critical direction: when a clinician overrides **downward** and model confidence was high, show one extra confirmation tap (never blocking) and log `DOWNWARD_OVERRIDE_CONFIRMED`. Upward overrides get no friction — you never want to slow down escalation.

Seed at least one override into the demo cohort so it's visible without the judge having to create one.

---

## Task 5 — Demonstrate the asymmetric cost explicitly

The brief is specific: solutions *must be deliberately tuned to bias toward escalation under uncertainty rather than optimized for average accuracy, and teams must demonstrate this design choice explicitly in their prototype.* You have the bias; you have not demonstrated it.

Build `/metrics` showing:

1. **The asymmetric loss matrix itself**, rendered as a table. State that undertriage by one level costs roughly 5× overtriage by one level, and that undertriage across the 2/3 boundary costs far more. State these are stipulated design weights, not empirically derived.
2. **Undertriage and overtriage rates reported separately** — never a single accuracy figure. Accuracy hides the entire asymmetry the design is built around.
3. **Quadratic weighted kappa**, which respects ordinality. Plain kappa treats a 1-vs-5 error as equivalent to 3-vs-4.
4. **Boundary-specific undertriage at 2/3** — the boundary where decompensation risk lives and where published nurse accuracy is weakest.
5. **An "escalation events" counter**: how many times in the demo run the tie-break rule chose the more acute level. This is the single clearest visual proof of the design choice.

Add a one-paragraph plain-English note on the page explaining why you optimise this way, so a non-technical judge gets it without reading the code.

---

## Acceptance criteria

1. 20 curated demo records seed cleanly; cohort report shows expected vs. actual for each.
2. Ambiguous, paediatric, geriatric and zero-history cases are individually identifiable in the UI.
3. Surge mode runs at 3×; thresholds and intervals provably unchanged; banner displays.
4. No acuity level appears anywhere in the UI or API without a confidence indicator. Grep for it.
5. The conformal claim is either implemented properly or renamed.
6. Audit viewer renders a readable timeline for any patient.
7. At least one override is pre-seeded and visible.
8. `/metrics` shows the loss matrix, separated under/overtriage rates, QWK, and the escalation counter.
