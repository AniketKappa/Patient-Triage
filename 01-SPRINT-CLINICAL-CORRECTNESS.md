# Sprint 01 — Clinical Correctness

Read `docs/triage-spec.md` and `docs/00-GAP-ANALYSIS.md` before starting. Section 6 of the gap analysis is the defect list this sprint closes.

These are patient-safety defects in the acuity path. Do not start any other sprint until every acceptance test here passes.

**Standing rules for this sprint (they are in `AGENTS.md`; re-read them):** composition is `min`, never a weighted sum. Models escalate only. No automatic downgrade. Do not collapse the gates into a scoring function.

---

## Task 1 — Build `TriageContext` (Layer 0)

Nothing in the acuity path may apply a threshold before this object exists. Several Gate B rules currently cannot fire because the fields they need don't exist.

Create `app/triage/context.py`:

```python
@dataclass(frozen=True)
class TriageContext:
    age_band: AgeBand           # NEONATE(<1mo) INFANT(1-12mo) TODDLER(1-3y)
                                # PRESCHOOL(3-5y) SCHOOL(5-12y) ADOLESCENT(12-18y) ADULT(>18y)
    age_years: float
    geriatric: bool             # >= 65
    pregnancy_state: Pregnancy  # NOT_PREGNANT | PREGNANT(weeks) | POSTPARTUM(days) | UNKNOWN
    immunocompromised: bool
    baseline_spo2: float | None
    on_home_oxygen: bool
    rate_blunting_meds: bool    # beta-blockers, CCBs
    immune_blunting_meds: bool  # corticosteroids
    anticoagulated: bool
    baseline_mental_status: str | None
    immunisations_current: bool | None
    history_depth: Literal["rich", "partial", "none"]
```

Three rules, each with its own test:

1. **Unknown ≠ normal.** `baseline_spo2 is None` must not default to 98. It means the baseline-relative test cannot run, so the absolute test applies *and* confidence narrows.
2. **Modifiers escalate only.** `rate_blunting_meds=True` explains why HR isn't elevated; it must never lower an acuity floor. Assert this in code.
3. **`history_depth` is derived**, not entered: `rich` if a prior encounter with vitals exists, `partial` if a record exists without baseline vitals, `none` if no MRN match.

Add the intake fields needed to populate it. Where a field is genuinely unknown, store `None`/`UNKNOWN` — never a default.

---

## Task 2 — Age-band Gate A (highest severity)

Gate A currently uses `HR < 40`, `adult HR > 150`, `adult SBP < 80`. These are adult numbers in the gate that catches dying patients. A neonate at HR 210 does not trigger. An infant at SBP 55 does not trigger. Bradycardia is a single adult threshold, when bradycardia in a neonate is <100.

Move **every** Gate A vital threshold into the same versioned age-banded config table that Gate D uses. Both tails for HR. Both tails for RR. Age-banded SBP.

Gate A must remain fully deterministic — no ML, no probability. Keep the `CRITICAL LOOK` bypass exactly as it is; it's correct.

Add these Gate A criteria if absent: active seizure, hypoglycaemia, flaccid infant, anaphylaxis, needs immediate adrenaline/naloxone/dextrose/atropine/adenosine.

Two implementation notes to encode as tests:
- Diagnostics are not interventions. A CT for suspected stroke does not make someone ESI 1.
- Disposition ≠ acuity. Hypoglycaemia and opioid overdose are ESI 1 even though many such patients are discharged the same day.

---

## Task 3 — Fix Gate D scope and behaviour

Four separate defects.

**3a. Scope.** Gate D currently evaluates only ESI 3 patients. ESI v5's headline change from v4 is that HR, RR and SpO2 are mandatory for **every** patient not already gated to 1 or 2, and out-of-range values force reassessment at **levels 4 and 5 as well**. Extend Gate D to all of 3, 4 and 5.

**3b. Add SpO2.** Gate D must check HR, RR **and SpO2 < 92%**.

**3c. Use the ESI v5 table verbatim.** You currently reference PALS bands. Use the values in `docs/triage-spec.md` §1.4, in versioned config, so the citation matches what's implemented:

| Age band | HR above | RR above |
|---|---|---|
| < 1 month | 190 | 60 |
| 1–12 months | 180 | 55 |
| 1–3 years | 140 | 40 |
| 3–5 years | 120 | 35 |
| 5–12 years | 120 | 30 |
| 12–18 years | 100 | 20 |
| > 18 years | 100 | 20 |

**3d. Replace the advisory string with a decision prompt.** Currently Gate D appends "Consider upgrading to ESI 2" — passive text nobody has to act on. Replace with a blocking-but-one-tap prompt:

- Names the specific parameter and value: "RR 26 exceeds the >18y threshold of 20."
- **Uptriage is the pre-selected default.** One tap accepts.
- Dismissal requires a structured reason from a fixed list: `CHRONIC_BASELINE`, `ANXIETY_RESOLVED_ON_RECHECK`, `MEDICATION_EFFECT`, `MEASUREMENT_ARTEFACT_RECHECKED`, `OTHER` (+ free text).
- Every dismissal writes a `GATE_D_DISMISSED` event with the reason.
- Expose dismissal rate per reason at `/api/metrics/gate-d-dismissals`. This is a QA metric — the standard's own worked examples show how easily abnormal vitals get wrongly blamed on a patient's chronic disease.

---

## Task 4 — Rebuild the deterioration engine

Delete `SpO2 drop > 2%` and `HR spike > 20 bpm`. A pulse oximeter is ±2% accurate, so the first threshold fires on measurement noise; the second treats 60→81 and 110→131 as identical events.

Replace with:

**4a. Early warning scores.**
- Adults (≥16): **NEWS2** — RR, SpO2 (with scale 2 where hypercapnic respiratory failure is documented), supplemental O2, systolic BP, pulse, ACVPU, temperature. Bands 0–4 low, 5–6 medium, ≥7 high, **plus a single-parameter score of 3 escalating regardless of aggregate**.
- Paediatrics: NEWS2 is invalid. Use an age-banded PEWS-family score against the same age-band table.
- Store the full score trajectory, not just the latest value.

**4b. Trigger set for re-triage.**

| Trigger | Condition |
|---|---|
| Hard criterion | any Gate A or Gate B condition now met |
| Vital band | any Gate D parameter now out of range for age |
| Aggregate | NEWS2 ≥ 5, or any single parameter scoring 3 |
| Delta | rise of ≥2 from the patient's **own ED baseline** |
| Trend | two consecutive readings moving the same direction beyond measurement noise |
| Subjective | new symptom reported by patient, family, or waiting-room staff |
| Time | reassessment clock breach |

**4c. Noise handling.**
- Compare against the patient's own ED baseline, not the immediately previous reading (which may itself be the artefact).
- A single out-of-band reading raises a **recheck task**, not an alert. Two consecutive confirm it.
- Use **rate of change**, not raw delta — a 5% SpO2 fall over four hours and over twenty minutes are different clinical events.
- Cap alerts per nurse per hour and expose the count at `/api/metrics/alert-burden`. An ignored alert is functionally no alert.

---

## Task 5 — Deterioration triggers re-triage, not a priority penalty

The current spec says deterioration "applies a priority penalty (boosting them in the queue)." That is the scalar-priority bug returning, and it directly contradicts "sorted strictly by ESI level first."

Delete the priority penalty. On a deterioration trigger:

1. Re-run the full gate cascade with the new observations.
2. If the result is more acute, **change the ESI level** — the patient moves queue class as a consequence.
3. Tighten the reassessment interval automatically to the new level's.
4. Write a `RE_TRIAGE` event: change in condition, trigger that fired, previous and new level, whether AI or human initiated.
5. If the result is *less* acute, **do nothing to the level.** No automatic downgrade, ever.

---

## Task 6 — Fix the queue sort key

```python
sort_key = (
    esi_level,          # ALWAYS first. Never crossed by any other factor.
    not deteriorating,  # within class only
    time_to_breach,
    arrival_time,       # FIFO tiebreak
)
```

No scalar addition anywhere. Add a test asserting that no combination of wait time and deterioration can place an ESI 5 above an ESI 4.

**Anti-starvation, done correctly.** When an ESI 4/5 patient exceeds a wait threshold, do **not** promote them. Instead: fire a mandatory reassessment (which may legitimately uptriage them on clinical grounds), flag them as fast-track eligible, and surface them in a "longest waiting, lowest acuity" panel for the charge nurse.

---

## Task 7 — Complete the Gate B rule table

Convert the current category list into a versioned YAML rule table (`app/triage/rules/gate_b.yaml`), one entry per rule with `id`, `applies_to`, `trigger`, `floor`, `actions`, `source`.

Add every rule below — each requires `TriageContext` from Task 1, which is why they cannot currently fire:

| Rule | Trigger | Floor |
|---|---|---|
| Neonate fever | age < 28d AND temp > 38.0°C | 2 |
| Pregnancy hypertension/hypotension | pregnant or postpartum AND (SBP < 90 OR SBP > 150) | 2 |
| Immunocompromised infection | immunocompromised or transplant AND (fever OR any sign of infection) | 2 |
| Anticoagulated head injury | anticoagulated AND head injury | 2 |
| Button battery / magnet ingestion | suspected ingestion | 2 |
| Testicular / ovarian torsion | testicular or scrotal pain; unilateral LQ pain in a patient with ovaries | 2 |
| Needlestick | occupational exposure (PEP window) | 2 |
| Thunderclap headache | sudden-onset severe headache | 2 |
| Epistaxis on anticoagulants | epistaxis AND (anticoagulated OR thrombocytopenia) | 2 |
| Geriatric trauma modifier | geriatric AND any trauma mechanism | 2 |

Also **remove the age gate on chest pain.** ACS-suspicious presentation is a floor of 2 at any age — an age threshold bakes in exactly the documented bias against younger and female patients presenting atypically.

**Severe pain carve-out.** Pain ≥7/10 is a trigger for *consideration*, not an automatic 2:
- Systemic disruption (renal colic, sickle cell crisis, cancer pain) → floor 2.
- **Isolated orthopaedic pain with intact neurovascular status → no floor.** Prompt the comfort measure (ice, elevation, analgesia under standing order) and continue to Gate C.

---

## Acceptance criteria

Every one of these must pass before Sprint 02:

1. The nine gold cases from `docs/triage-spec.md` §6.1 all pass.
2. A 3-week-old with T 38.2 and otherwise normal vitals → **ESI 2** (currently would not).
3. A neonate at HR 210 → **Gate A / ESI 1** (currently would not fire).
4. A 70-year-old with dizziness and HR 32 → **ESI 1**.
5. A pregnant patient with SBP 88 and no other symptoms → **ESI 2**.
6. A 25-year-old with ACS-suspicious chest pain → **ESI 2** (no age gate).
7. An isolated ankle fracture with pain 8/10, intact pulses → **ESI 3 or 4 via Gate C**, not 2.
8. An ESI 4 patient repeatedly reassessed with SpO2 oscillating 96/98/96/97 → **zero deterioration alerts**.
9. An ESI 4 patient waiting 180 minutes → still sorts below every ESI 3. Reassessment fires; level unchanged unless clinically triggered.
10. An ESI 5 patient whose repeat RR is 24 → Gate D prompt fires (proving Gate D now covers 4 and 5).
11. Property test: for 1000 random patients, no evidence source ever lowers a floor set by another.

Report which acceptance criteria failed before your changes and which pass after. Do not modify any acceptance criterion — if one looks wrong, stop and ask.
