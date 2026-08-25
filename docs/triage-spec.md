# ED Triage Assistant — Architecture Redesign

Reference standard throughout: **ESI Handbook, 5th Edition (Emergency Nurses Association, 2023)**. All acuity logic below maps to a named clause of that document. Where ESI deliberately leaves something undefined (reassessment intervals, time-to-provider targets), the gap is filled from CTAS and stated as such.

---

## Part 0 — Diagnosis: three category errors in the current build

Before the fixes, the three mistakes that everything else follows from. These aren't tuning problems; they're the wrong shape of computation.

### Error 1 — You replaced a decision procedure with an arithmetic one

ESI is a **strictly ordered four-gate cascade (A → B → C → D)**. Each gate is a yes/no question. A patient who fails gate A never reaches gate B. The gates are lexicographic, not additive.

Your engine computes `Net Score = 0.4 × vitals + 0.6 × NLP`, then thresholds it. This means:

- A strong danger signal in the text can be **arithmetically diluted** by normal vitals. In a real triage this is exactly backwards — a normal heart rate does not neutralise "worst headache of my life."
- Conversely, mildly abnormal vitals can push a benign complaint upward, generating noise.
- The number 35 has no clinical referent. Nobody can defend it in an M&M review, and no auditor can trace it.

**The correct composition operator is `min` (most-acute-wins), not a weighted sum.** Every evidence source may only assert an *acuity floor*. Final level = the most acute floor asserted by any source. This gives you the "bias toward escalation under uncertainty" requirement as a **structural property of the algorithm**, not a hyperparameter someone can quietly re-tune.

### Error 2 — You deleted Decision Point C

ESI 3/4/5 is **not** a severity judgement. It is a *resource-count prediction*:

| Distinct resource types predicted | Level |
|---|---|
| 2 or more | ESI 3 |
| exactly 1 | ESI 4 |
| none | ESI 5 |

A "resource" is a *type*, not a test. CBC + electrolytes + coags = **one** resource (labs). CBC + chest X-ray = **two**. History and physical, point-of-care testing, oral meds, tetanus shot, prescriptions, simple wound care, crutches/splints/slings are **not** resources. A simple procedure counts 1; a complex procedure (e.g. procedural sedation) counts 2.

Your `Net Score >= 35 → ESI 3` replaces a defined, auditable, EHR-verifiable criterion with an invented scale. This is the single most consequential structural flaw, and fixing it is also what gives you the "what does this patient need" output for free (Part 3).

### Error 3 — Priority and acuity are the same variable in your system

```
Priority = ESI Base + AI Net Score + (Wait × 1.5) + Deterioration Penalty
```

With ESI 1 = 100 and a wait multiplier of 1.5/min, an **ESI 5 patient who has waited 67 minutes outranks a just-arrived ESI 1**. At 50 minutes they outrank an ESI 2. Your documentation presents the leapfrog behaviour as a feature; it is a patient-safety defect that a single reviewer will find in thirty seconds.

Waiting does not make a patient sicker. Waiting means **you no longer know** whether they are sicker. The correct response to a long wait is a *mandatory reassessment* — which may legitimately uptriage them — not a scalar bonus.

Three quantities must stay separate and must never be summed:

| Quantity | Type | Changes when |
|---|---|---|
| **Acuity (ESI)** | ordinal class, 1–5 | a documented re-triage event occurs |
| **Deterioration risk** | continuous trajectory (EWS) | every new observation set |
| **Queue position** | derived ordering | continuously, but *strictly within* acuity class |

---

## Part 0b — Specific defects, itemised

| # | Current behaviour | Why it's wrong | Fix |
|---|---|---|---|
| 1 | `SpO2 < 90 → ESI 1` | ESI 1 requires SpO2 below 90 **that is not the patient's baseline, with other signs of respiratory compromise**. A COPD patient on home O2 sitting at 90% is their normal. | Baseline-relative; require corroborating compromise |
| 2 | `HR > 130 → ESI 1`, `HR > 100 → ESI 2` | Only checks the tachycardic tail. **Bradycardia is missed entirely** — the handbook's own example is an alert elderly patient with HR 32 who is ESI 1. And HR 102 with everything else normal is ESI 3 in the handbook's worked example, not ESI 2. | Two-tailed, age-banded, at the gate-D table values |
| 3 | **Respiratory rate is never collected** | RR is the strongest single vital predictor of deterioration; in the Iranian up-triage study cited by ENA, ~89% of patients uptriaged 3→2 had an elevated RR. ESI v5 makes HR/RR/SpO2 mandatory for every non-1/2 patient. | RR is a required field. No triage completes without it. |
| 4 | All thresholds adult-calibrated | ESI v5's gate-D table is banded across 7 age groups. Your `HR > 130 → ESI 1` classifies a **healthy 15-month-old (normal HR 90–180) as requiring resuscitation**. Meanwhile `SBP < 80` misses a shocked adolescent. | Age-band resolution before any threshold is applied |
| 5 | `Age > 50 + "chest pain" → ESI 2` | Hard-codes the exact bias ENA added a whole section to warn about. Chest pain suspicious for ACS is ESI 2 **at any age**, and the handbook specifically flags atypical presentation in women (fatigue, nausea, weakness). | Presentation-based rule, no age gate; age is a *modifier that can only escalate* |
| 6 | `Temp > 39 → ESI 2` for everyone | Adult fever alone is not an ESI 2 criterion. Paediatric fever is, with narrow age-specific rules (<28 days & T>38 → at least ESI 2; <90 days is a red flag; T<36 at any age is concerning for sepsis). | Delete the adult rule; implement the paediatric fever ladder properly |
| 7 | Decision Point B is ~4 keywords | Missing: stroke signs, AMS, suicidal/homicidal ideation, sexual assault, immunocompromise or transplant + fever, needlestick exposure, thunderclap headache, stridor / inability to manage secretions, testicular or ovarian torsion, ectopic pregnancy, postpartum haemorrhage, pregnancy with SBP <90 or >150, epistaxis on anticoagulants, button-battery ingestion, high-risk trauma mechanism (fall ≥20 ft, ejection, mechanical extrication), neurovascular compromise / compartment syndrome. | Full rule table, Part 1 |
| 8 | TF-IDF + RF on **synthetic** text | Circular: the model learns your generator's assumptions and validates against them. TF-IDF also has **no negation handling** — "denies chest pain," "no chest pain," "chest pain resolved yesterday" all fire the same feature. | Real retrospective data; negation/uncertainty detection (NegEx/ConText class); or a clinical encoder |
| 9 | `SpO2 drop > 2%` = deteriorating | Typical pulse oximeter accuracy is ±2%. This threshold sits **inside the noise floor** — it will fire constantly and train nurses to dismiss it. | Confirmed repeat, rate-of-change, and an aggregate EWS rather than a single-variable delta |
| 10 | `HR spike > 20 bpm` = deteriorating | 60→81 is meaningless; 110→131 is alarming. Absolute delta ignores where you started. | EWS band transitions, not raw deltas |
| 11 | Deterioration only detected when a nurse presses "Re-Assess" | The system is passive exactly where it should be driving. It also can't distinguish "patient is fine" from "nobody has looked at this patient in 90 minutes," which is a different and equally dangerous state. | Reassessment clock with due/overdue/breach states |
| 12 | No confidence output | The brief explicitly requires that no score is returned without a confidence indicator. `predict_proba` from an RF is uncalibrated and is not a confidence measure. | Three-axis confidence + conformal prediction set, Part 1.6 |
| 13 | Admit/Discharge "instantly removes the patient" | Destroys the record. There is no audit trail, no override capture, no way to reconstruct what the system recommended versus what the clinician did. | Append-only event log, Part 4.8 |
| 14 | Deterioration adds `+15 priority` | A patient whose vitals have crossed a danger threshold has *changed acuity class*. A scalar nudge inside the same queue is not the right response. | Deterioration triggers **re-triage**, which changes ESI, which changes class |
| 15 | Ambulance path = a status flag | Pre-arrival is a fundamentally different information state (prehospital vitals *series*, interventions already given, mechanism, ETA) and should produce different actions (room reservation, team pre-alert, equipment staging). | Distinct pre-arrival lane, Part 4.1 |

**What to keep:** FastAPI + SQLAlchemy is fine. The dual-queue UI (critical vs standard) is a genuinely good decision and matches how EDs actually visually manage a board — keep it. The reminders panel concept is right, the trigger logic underneath is not.

---

## Part 1 — The corrected triage engine

### 1.0 Layer 0: patient context resolution (runs before any gate)

Nothing downstream may apply a threshold until this object exists. This is what eliminates the "single adult-calibrated model" silent safety risk.

```python
@dataclass(frozen=True)
class TriageContext:
    age_band: AgeBand           # <1mo | 1-12mo | 1-3y | 3-5y | 5-12y | 12-18y | >18y
    geriatric: bool             # >=65: blunted compensation, higher undertriage risk
    pregnancy_state: Pregnancy  # not_pregnant | pregnant(weeks) | postpartum(days) | unknown
    immunocompromised: bool     # chemo, transplant, steroids, known immunodeficiency
    baseline_spo2: float | None # home O2, COPD — from prior encounter or caregiver report
    on_home_oxygen: bool
    rate_blunting_meds: bool    # beta-blockers, calcium channel blockers
    immune_blunting_meds: bool  # corticosteroids
    anticoagulated: bool
    baseline_mental_status: str | None
    immunisations_current: bool | None   # paediatric
    history_depth: Literal["rich", "partial", "none"]
```

Three rules govern this object:

1. **Unknown ≠ normal.** `baseline_spo2 = None` does not mean 98%. It means the baseline-relative test cannot run, so the absolute test applies *and* confidence narrows.
2. **Modifiers escalate only.** A beta-blocker explains why the heart rate isn't high; it never justifies lowering acuity. Same for steroids masking fever. The handbook is explicit that medication-mediated "normal" vitals can conceal serious illness.
3. **`history_depth` is a first-class output.** Roughly half your arrivals will be history-poor. The system must say "I am working with less" rather than silently producing an equally confident-looking number.

---

### 1.1 Gate A — Immediate lifesaving intervention required → ESI 1

**Deterministic rules only. No ML. No score. No probability.**

This gate must be reachable in under five seconds without the nurse filling in a form — implement it as a single **CRITICAL LOOK** button on the intake screen that jumps straight to ESI 1 and fires the resus pre-alert. ENA is explicit that care must not be delayed to obtain a full set of vitals on an obviously decompensating patient.

| Domain | Trigger |
|---|---|
| Airway | apnoeic, occluded airway, requires assisted ventilation or intubation, surgical airway, emergent NIPPV |
| Breathing | severe respiratory distress; SpO2 < 90% **not** the documented baseline **and** with signs of respiratory compromise |
| Circulation | pulseless; profound hypotension with hypoperfusion signs; severe bradycardia or tachycardia (age-banded, **both tails**); needs significant fluid resuscitation, blood products, or external haemorrhage control |
| Disability | AVPU = P or U; acutely nonverbal and not following commands; active seizure; hypoglycaemia |
| Immediate drugs | needs adrenaline (incl. IM for anaphylaxis), naloxone, dextrose, atropine, adenosine, dopamine |
| Trauma | penetrating trauma to head/neck/chest/abdomen requiring a lifesaving intervention |
| Other | flaccid infant; anaphylaxis; arrest or imminent arrest |

Two implementation notes:

- **Diagnostics are not interventions.** A CT for suspected stroke, or the cath lab for a haemodynamically stable patient, does not make someone ESI 1.
- **Disposition ≠ acuity.** Hypoglycaemia, opioid overdose, and anaphylaxis are ESI 1 even though many of those patients walk out the same day. Do not let a "they'll be discharged anyway" heuristic leak into the model.

---

### 1.2 Gate B — High-risk situation / new AMS / severe distress → ESI 2

This is where nurses are weakest (published accuracy at this gate is around 43%) and therefore where the assistant earns its keep. It is **rule-first with ML escalation**.

**B.1 — Rule table.** Not `if/elif` in a service function. A versioned, hospital-configurable data table:

```yaml
- id: B.CARDIAC.ACS
  applies_to: [all_ages]
  trigger: complaint_in [chest_pain, chest_pressure, jaw_pain, arm_pain,
                         epigastric_pain, unexplained_dyspnoea,
                         unexplained_nausea_weakness_diaphoresis]
  floor: 2
  actions: [ECG_within_10_min, monitored_bed, troponin]
  source: "ESI v5 Ch.4, Cardiovascular"
  note: "No age gate. ENA flags atypical presentation, esp. in female patients."

- id: B.OB.HTN
  applies_to: [pregnant, postpartum]
  trigger: sbp < 90 OR sbp > 150
  floor: 2
  actions: [OB_consult, repeat_bp_5min]
  source: "ESI v5 Ch.4, Obstetrical — floor applies even with no other symptoms."

- id: B.PEDS.NEONATE_FEVER
  applies_to: [age < 28d]
  trigger: temp_c > 38.0
  floor: 2
  actions: [sepsis_workup, isolation_consider]
  source: "ESI v5 Ch.6, Pediatric Temperatures"
```

Minimum coverage — every one of these is named in ESI v5 Ch.4 and every one is currently absent from your build:

- **Neuro** — thunderclap headache; headache + fever/vomiting/neck stiffness/AMS; stroke signs not meeting level 1 (capture **last-known-well time**, it drives the thrombolysis window); post-ictal state
- **Cardiac** — ACS-suspicious presentation (above); abnormal ECG at triage
- **Resp** — increasing respiratory effort; stridor; unable to manage secretions; 2–3-word sentences; tripoding; paediatric grunting/retractions/belly breathing
- **OB/GYN** — possible ectopic; pregnancy or postpartum with SBP <90 or >150; heavy vaginal bleeding; postpartum haemorrhage; pregnancy with chest pain, dyspnoea, abdominal pain, or headache
- **GU** — testicular/scrotal pain (torsion is time-critical, organ-loss risk); unilateral lower-quadrant pain in a patient with ovaries; severe flank pain; UTI symptoms in an elderly patient or with back pain/rigors (urosepsis)
- **Infectious/immune** — immunocompromised or transplant recipient with fever or any sign of infection; sepsis-suspicious presentation
- **Trauma** — fall ≥20 ft (6 m); ejection from vehicle; mechanical extrication; sexual assault; penetrating torso/head/neck trauma without instability; any extremity injury with neurovascular compromise or compartment syndrome signs; partial/complete amputation. **Add a geriatric modifier**: injury severity in older adults routinely exceeds what the mechanism predicts, and occult hypoperfusion with normal vitals is associated with age >55
- **ENT** — brisk posterior epistaxis, or epistaxis with thrombocytopenia / clotting disorder / warfarin or DOAC use
- **Paeds** — button battery or earth-magnet ingestion (extremely time-sensitive, high morbidity); **any** subtle mental-status change in a child
- **Tox** — suspected toxic ingestion, especially with AMS, breathing changes, or unexplained rhythm change
- **Mental/behavioural** — suicidal ideation/plan/attempt; homicidal ideation; psychosis; violence risk; acute grief; sexual or domestic violence survivor; distress after assault; combativeness. ENA flags that this cohort is *especially* prone to undertriage from stigma, so build a QA counter on it specifically
- **Occupational** — needlestick in a healthcare worker (PEP window)

**B.2 — Severe pain, done properly.** This is the most commonly botched ESI criterion and a place your system can be visibly smarter than a naive one:

- Pain ≥ 7/10 is a trigger for *consideration*, **not** an automatic ESI 2.
- Pain from **systemic disruption** (renal colic, sickle cell crisis, cancer pain) → ESI 2.
- **Isolated orthopaedic** pain with intact neurovascular status → accept the patient's rating, treat at triage (ice, elevation, analgesia under standing order), and **continue to Gate C**. The system should prompt the comfort measure, not the uptriage.
- Psychological distress counts as distress. This is not a softer criterion.

**B.3 — ML escalation layer (two models, both escalate-only).**

1. **Clinical NLP flagger.** Reads symptom text and family statements, proposes gate-B flags, returns **evidence spans**. Must handle negation and hedging; must treat family/bystander statements as a distinct evidence class (a caregiver saying "he's just not himself" is a high-value AMS signal that a patient will not self-report). This model may raise the floor to 2. It may never lower it.
2. **Outcome-risk model.** Following the e-triage approach validated by Levin et al. across ~173k visits: predict, in parallel, P(critical care), P(emergency procedure), P(inpatient admission) from vitals + coded complaint + active history. Where risk exceeds the calibrated ESI-2 threshold, raise the floor to 2. This is what breaks up the undifferentiated ESI-3 bucket — in that study over 10% of ESI-3 patients were identified as warranting up-triage and had markedly higher rates of critical care and admission.

Both are **advisory floors** feeding the same `min` operator.

---

### 1.3 Gate C — Resource prediction → ESI 3 / 4 / 5

This is the only gate where ML is the *primary* mechanism, and it's also the gate that produces your staff-facing "what does this patient need" output. Same model, two consumers.

**Model:** multi-label classifier over resource *classes*, not a regression on a count.

```
labels = {
  labs,            # blood + urine together = 1
  ecg,
  plain_radiograph,
  advanced_imaging,  # CT / MRI / US / angiography
  iv_fluids,
  parenteral_meds,   # IV / IM / nebulised
  specialty_consult,
  simple_procedure,  # counts 1
  complex_procedure  # counts 2
}
count = |{labels predicted above threshold}|   (complex_procedure contributes 2)
```

**Labels come from the retrospective EHR** — what was actually ordered before disposition — not from a synthetic generator and not from historical ESI assignments. This matters enormously: ESI labels inherit the 40% error rate of the nurses who produced them, whereas order records are near-ground-truth. It is the difference between learning triage and learning to imitate mistriage.

**Boundary handling under asymmetric cost.** The count is uncertain, so:

- Produce a predictive distribution, not a point estimate.
- If the credible interval straddles the 1/2 boundary (ESI 4 vs 3), **assign 3** and mark the decision low-confidence.
- Never round down at a boundary. Overtriage costs a bed-minute; undertriage costs a patient.

**Structural note:** the resource count is *only* consulted after gates A and B have both returned no. Never compute it as an input to acuity for a level 1 or 2 patient.

---

### 1.4 Gate D — High-risk vital signs → reassess the acuity decision

ESI v5's most important change from v4: HR, RR, and SpO2 are mandatory for **every** patient not already classified 1 or 2, and out-of-range values force a **reassessment** at levels 4 and 5 too, not just level 3.

Exact table from ESI v5 (implement these values verbatim, in config, versioned):

| Age band | HR above | RR above |
|---|---|---|
| < 1 month | 190 | 60 |
| 1–12 months | 180 | 55 |
| 1–3 years | 140 | 40 |
| 3–5 years | 120 | 35 |
| 5–12 years | 120 | 30 |
| 12–18 years | 100 | 20 |
| > 18 years | 100 | 20 |

Plus **SpO2 < 92%** at any age.

**Behavioural subtlety that most implementations get wrong:** the handbook says *reassess the acuity decision*, not *auto-uptriage*. So the correct output is a **decision prompt**, not a silent state change:

> ⚠ **RR 26 exceeds the >18y threshold of 20.** ESI 3 → 2?
> [ Uptriage to 2 ]   [ Explained by baseline — document reason ]

- "Uptriage" is the pre-selected default (one tap).
- Dismissal requires a structured reason (chronic COPD at documented baseline, anxiety resolved on recheck, medication effect, measurement artefact — recheck required).
- **Every dismissal is logged and counted.** ENA's own worked examples show how easy it is to wrongly attribute abnormal vitals to a patient's chronic disease — their COPD-plus-infected-cat-bite example ends in an uptriage precisely because the tempting explanation was the wrong one. So dismissal-rate per nurse, per reason, and per patient subgroup becomes a live QA metric. This is not surveillance of staff; it's the mechanism by which the safety net stays a net.

---

### 1.5 The composition rule

```python
def assign_esi(ctx, obs, text) -> TriageResult:
    floors = []

    if gate_a(ctx, obs, text):                 # deterministic
        return TriageResult(level=1, gate="A", ...)

    floors += gate_b_rules(ctx, obs, text)     # deterministic rule table
    floors += nlp_flagger(ctx, text)           # advisory, escalate-only
    floors += outcome_risk_model(ctx, obs)     # advisory, escalate-only

    if floors:
        return TriageResult(level=min(f.level for f in floors),
                            gate="B", evidence=floors, ...)

    level_c, conf_c = gate_c_resources(ctx, obs, text)   # 3 / 4 / 5
    level_d_prompt = gate_d_vitals(ctx, obs)             # may prompt uptriage

    return TriageResult(level=level_c, gate="C",
                        pending_prompt=level_d_prompt, confidence=conf_c, ...)
```

Three invariants, enforced in code and covered by tests:

1. **`min`, never `mean`.** No weighted blend anywhere in the acuity path.
2. **No model may lower a rule-derived floor.** Assert it.
3. **No automatic downgrade, ever.** ENA is unambiguous: before provider evaluation, the only change that should be made is an *increase* in acuity, and once a provider has seen the patient the ESI should not be changed at all. A downgrade requires a named clinician, a reason, and an exception log entry.

Invariant 3 is the cleanest possible encoding of the asymmetric-cost requirement in your brief, and you can point at the standard when defending it.

---

### 1.6 Uncertainty — never a bare number

Three independent axes, surfaced separately because they demand different responses:

| Axis | Measures | Nurse's response |
|---|---|---|
| **Data completeness** | which required inputs are missing or stale | *go get the missing datum* |
| **Model confidence** | calibrated probability over the level (isotonic / temperature-scaled, not raw `predict_proba`) | *weigh the recommendation less* |
| **Rule–model agreement** | did the rule table and the ML layer converge? | *look harder — this is the interesting case* |

**Conformal prediction** is the right formalism for the headline output. Produce a *set* of admissible levels at guaranteed coverage (e.g. 95%), then:

- recommend the **most acute member** of the set;
- display the set width as the confidence indicator;
- when the set spans a class boundary, say so explicitly.

```
ESI 3   ·   admissible {2, 3}   ·   moderate confidence
Recommending 2 — the set crosses the 2/3 boundary and we escalate on ties.
Most informative missing input: respiratory rate.
```

That last line is worth building carefully. Compute the **expected value of information** for each missing field and name the single one that would most narrow the set. It converts "the AI is unsure" from a shrug into an instruction.

Also required: an explicit **`INSUFFICIENT_DATA`** state. It is not a level. It routes the patient to immediate nurse assessment rather than emitting a low-confidence guess into a queue.

---

## Part 2 — Dynamic acuity: re-triage, deterioration, and queue order

### 2.1 The reassessment clock

ESI deliberately does **not** define time-to-provider or reassessment intervals — unlike ATS, CTAS, and MTS, which build wait times into the scale. So take the intervals from CTAS and label them as such in your config:

| Level | Nursing reassessment interval (CTAS) |
|---|---|
| 1 | continuous |
| 2 | every 15 min |
| 3 | every 30 min |
| 4 | every 60 min |
| 5 | every 120 min |

Each waiting patient carries a clock with three states:

- **due** — approaching interval; appears in the worklist
- **overdue** — interval exceeded; escalated styling
- **breach** — 2× interval; becomes a **safety event**, notifies the charge nurse, and is recorded permanently

The distinction that your current build cannot express: **"patient is stable" and "nobody has looked at this patient in 90 minutes" are different states.** The second one is arguably more dangerous, because it looks like the first.

### 2.2 Deterioration detection

Replace the two-variable delta with a proper early warning score plus trend logic.

**Adults (≥16):** NEWS2 — RR, SpO2 (with the hypercapnic-respiratory-failure scale where applicable), supplemental O2, systolic BP, pulse, consciousness (ACVPU), temperature. Standard risk bands: 0–4 low, 5–6 medium, ≥7 high, with a **single-parameter score of 3 escalating regardless of aggregate**. Note the honest caveat in the literature: NEWS/NEWS2 was designed for ward patients and is not formally validated as an ED triage instrument, and patients scoring below 5 can still deteriorate — so it is a *trigger*, never a discharge clearance.

**Paediatrics:** NEWS2 is invalid. Use an age-banded PEWS-family score against the ESI v5 normal-range table (HR, RR, SBP by age band).

**Trigger set for re-triage:**

| Trigger | Condition |
|---|---|
| Hard criterion | any Gate A or Gate B condition now met |
| Vital-sign band | any Gate D parameter out of range for age |
| Aggregate | NEWS2 ≥ 5, **or** any single parameter scoring 3 |
| Delta | rise of ≥ 2 from the patient's own ED baseline |
| Trend | two consecutive readings moving the same direction beyond measurement noise |
| Subjective | new symptom reported by patient, family, or waiting-room staff |
| Time | reassessment breach |

**Noise handling — the fix for your ±2% SpO2 problem:**

1. Compare against the **patient's own ED baseline**, not the previous reading (which may itself be an artefact).
2. Require **confirmation**: a single out-of-band reading raises a *recheck* task, not an alert. Two confirms it.
3. Use **rate of change**, not raw delta. A 5% SpO2 fall over four hours and over twenty minutes are different clinical events; your current formula cannot tell them apart.
4. Cap alert volume per nurse per hour and monitor it. **Alert burden is a safety metric, not a UX metric** — an ignored alert is functionally equivalent to no alert, and you will have engineered the failure yourself.

**On re-triage firing:** the ESI level changes (upward only), the patient moves queue class, the reassessment interval tightens automatically, a timestamped record captures the change in condition, the reason, the resulting action, and whether AI or human initiated it. ENA requires exactly this documentation triad for any acuity change.

### 2.3 Queue ordering — the fixed formula

```
sort key = (
    esi_level,                    # 1 before 2 before 3 ... ALWAYS. Never crossed.
    not deteriorating,            # within class: deteriorating patients first
    time_to_target_breach,        # then most-at-risk-of-breach
    arrival_time                  # then FIFO
)
```

No scalar addition. No cross-class promotion by waiting.

**Anti-starvation, done correctly.** When an ESI 4 or 5 patient exceeds a wait threshold, the system does **not** promote them. It:

1. fires a **mandatory reassessment** — if they've genuinely deteriorated, the re-triage engine will uptriage them on clinical grounds, which is the legitimate route upward;
2. flags them for **fast-track / vertical care / provider-in-triage** eligibility — the real solution to low-acuity starvation is a parallel pathway, not queue-jumping;
3. surfaces them in a **"longest waiting, lowest acuity"** panel so the charge nurse can act on flow rather than the algorithm silently reordering.

This preserves the ESI ordering guarantee while genuinely solving the problem you were trying to solve.

### 2.4 Surge behaviour (3× volume)

ENA's fifth edition made a pointed change here: language was removed from decision point B specifically because nurses were assigning acuity based on **bed availability rather than physiology**, and colleagues pressuring the triage nurse to downgrade during crowding is a known dangerous practice. Your system must be structurally incapable of participating in that.

Therefore, under surge:

| Does NOT change | Does change |
|---|---|
| the acuity scale | streaming: fast-track eligibility, vertical care, provider-in-triage activation |
| gate thresholds | reassessment *modality* — degrade from full vitals to visual sweep + targeted spot-check, but **never** lengthen the interval |
| model calibration | staffing signal: acuity-burden distribution surfaced to charge nurse (by percentage, never a mean — ESI is ordinal and cannot be meaningfully averaged) |
| ordering rules | the **waiting-room aggregate risk** metric — the sum of predicted deterioration probabilities across waiting patients, which is a far better surge indicator than headcount |

Add a **surge banner** that states what did *not* change: "Volume 3×. Acuity criteria unchanged. Fast-track activated. Reassessment intervals unchanged." This is a trust feature — it tells the nurse the tool isn't quietly moving the goalposts under pressure.

---

## Part 3 — The needs/resource planner (the "what does this patient require" output)

Gate C already predicts the resource set. Expand it into the staff-facing prep card. This is the highest-value feature in the whole build and you get most of it for free.

```
┌─ P-2291 · 62F · ESI 2 (uptriaged from 3 — RR 26) ─────────────┐
│ PLACEMENT   Monitored bed · resus-adjacent                    │
│ EQUIPMENT   Cardiac monitor · O2 · 2× large-bore IV            │
│ PROTOCOL    ⏱ Sepsis bundle — lactate + cultures before abx    │
│             Antibiotic clock: 47 min remaining                 │
│ PREDICTED   Labs · ECG · CT · IV fluids · IV abx (5 resources) │
│ STAFF       — · ISOLATION Droplet (cough + fever)              │
│ CONFIDENCE  High · complete vitals · rule/model agree          │
└───────────────────────────────────────────────────────────────┘
```

Components:

- **Placement** — resus / monitored / standard / vertical / fast-track, derived from level + resource profile
- **Equipment** — monitor, O2 delivery, IV access, warming, crash cart pre-position
- **Isolation** — respiratory/contact/droplet precautions inferred from symptoms + immunisation status. ENA specifically flags fever with non-petechial rash and incomplete immunisations as an isolation prompt at triage
- **Staff needs** — interpreter, security, paediatric-competent nurse, chaperone, safeguarding
- **Time-critical protocol clocks** — these are the highest-leverage items on the whole board:
  - **STEMI**: ECG within 10 minutes of arrival for chest-pain concerns
  - **Stroke**: last-known-well timestamp, CT clock, thrombolysis window countdown
  - **Sepsis**: lactate, cultures-before-antibiotics, antibiotic clock
  - **Trauma**: activation criteria, blood product pre-alert
  - **PEP**: needlestick / sexual assault prophylaxis window
- **Predicted resources** — the Gate C output, shown as the list, not just the count

**Probable diagnosis: delete it, or change it fundamentally.** Your current keyword-map version ("breathless" → Respiratory Distress) is the single most dangerous UI element in the build, because it **anchors** the clinician. A named diagnosis on screen measurably reduces the probability that anyone considers alternatives, and it will be wrong in exactly the atypical presentations where anchoring hurts most. If you keep anything here, invert it: show **"cannot be excluded yet"** — the time-critical differentials this presentation is consistent with, framed as a rule-out list. That aids the clinician instead of substituting for them.

---

## Part 4 — Full module architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  INTAKE                                                             │
│  ┌──────────┐  ┌────────────────┐  ┌───────────────────────────┐    │
│  │ Walk-in  │  │ Ambulance      │  │ Provider-in-triage /      │    │
│  │          │  │ (pre-arrival)  │  │ direct-to-bed             │    │
│  └────┬─────┘  └───────┬────────┘  └────────────┬──────────────┘    │
└───────┼────────────────┼────────────────────────┼───────────────────┘
        └────────────────┴────────────────────────┘
                         ▼
        ┌────────────────────────────────┐
        │ 2. IDENTITY & HISTORY RESOLVER │  → history_depth: rich/partial/none
        └────────────────┬───────────────┘
                         ▼
        ┌────────────────────────────────┐
        │ 3. ASSESSMENT CAPTURE          │  vitals · coded complaint · free text
        │    + CRITICAL LOOK fast path ──┼──────────────► ESI 1, resus pre-alert
        └────────────────┬───────────────┘
                         ▼
        ┌────────────────────────────────┐
        │ 4. TRIAGE ENGINE  A→B→C→D      │  min() composition · conformal set
        └────────────────┬───────────────┘
                         ▼
   ┌─────────────────────┼─────────────────────┐
   ▼                     ▼                     ▼
┌────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ 5. EXPLAIN │  │ 6. NEEDS PLANNER │  │ 7. REASSESS &    │
│    LAYER   │  │                  │  │    DETERIORATION │
└─────┬──────┘  └────────┬─────────┘  └────────┬─────────┘
      └──────────────────┼─────────────────────┘
                         ▼
        ┌────────────────────────────────┐
        │ 8. OVERRIDE & AUDIT (append-only event log)  │
        └────────────────┬───────────────┘
                         ▼
        ┌────────────────────────────────┐
        │ 9. MONITORING & GOVERNANCE     │  fairness · calibration · alert burden
        └────────────────────────────────┘
                         │
        ┌────────────────▼───────────────┐
        │ 10. INTEGRATION (FHIR/HL7)  ·  DEGRADED MODE  │
        └────────────────────────────────┘
```

### 4.1 Intake — three lanes, not one

**Walk-in.** Standard path. The critical-look button precedes the form.

**Ambulance / pre-arrival.** A genuinely different information state, and your biggest differentiator:

- **Input:** mechanism, prehospital vitals as a **time series** (not a snapshot — the trend is the signal), interventions already given, ETA, receiving-facility capability match
- **Output:** a **provisional** ESI, visually distinct and explicitly labelled as pre-arrival; room reservation; team pre-alert; equipment staging; protocol clock pre-started (LKW for stroke is captured *before* arrival, which is where the minutes actually are)
- **Hard rule:** on arrival the provisional level must be **confirmed or amended** by a nurse. It never silently becomes the triage level. Prehospital data is thinner and older; treating it as equivalent is how you get an anchored, stale acuity.

**Provider-in-triage / direct-to-bed.** Surge and high-acuity bypass. Must still generate a triage record.

### 4.2 Identity & history resolution

MRN match → prior encounters, problem list, active meds, allergies, baseline vitals from last visit, prior ESI distribution. Degrade explicitly: `rich | partial | none`. In `none` mode the models run on observed data only and the conformal sets widen automatically — which is the correct behaviour and is visible to the nurse.

### 4.3 Assessment capture

Structured chief complaint (CEDIS presenting-complaint list or SNOMED CT), free text, vitals (device-integrated where possible — manual transcription is an error source), pain score, AVPU/ACVPU or GCS, pregnancy status, glucose if AMS, immunisation status if paediatric. **RR is mandatory.** No triage record can be finalised without HR, RR, and SpO2 for any patient not gated to 1 or 2.

### 4.5 Explanation layer

Design constraint: **readable in under five seconds by someone managing four other patients.** Not a SHAP plot.

```
ESI 2   ⬆ from 3
WHY     RR 26 > 20 (adult threshold) · "cough ×3 days" · SpO2 90%
RULE    ESI v5 Decision Point D — high-risk vital signs
IF      RR were < 20 and SpO2 ≥ 92 → ESI 3
CONF    High · complete vitals · rule and model agree
                                              [ Accept ]  [ Override ]
```

One line, one colour, one number. Detail on tap. The counterfactual ("if RR were <20…") is what makes the recommendation *checkable* rather than merely readable — the nurse can verify the logic against the patient in front of them in one glance.

This layer is also a **regulatory** feature, not just UX. A CDSS whose basis a clinician can independently review sits in a materially lighter risk category than one that emits opaque scores; the explanation is load-bearing for your compliance argument.

### 4.7 Reassessment engine — worklist, not notification stream

Your current "Action Reminders" panel lists conditions. A panel that shows everything shows nothing. Replace it with a **ranked worklist**: *"next 3 patients to check, in this order, here's why."* Bounded, ordered, actionable, and it clears.

### 4.8 Override & audit — append-only

Replace mutable patient rows with an event log:

```
event_id · patient_id · timestamp · actor(human|ai|system) · actor_id
event_type · payload · model_version · rule_table_version · prev_state · new_state
```

Nothing is deleted. Admit and discharge are **events**, not row deletions.

- Every AI recommendation is an event, with the model version and the input snapshot that produced it.
- Every human decision is an event.
- **Override requires a structured reason** from a short list + optional free text.
- **Downward overrides where model confidence was high** get a second-look prompt — one extra tap, no blocking. This is the safety-critical direction.
- The override corpus is your best QA dataset and your best retraining signal. It is also, in a bad outcome review, the record that shows the system behaved correctly.

### 4.9 Monitoring & governance

Track continuously, and **stratify every metric by subgroup** — age, sex, language, race/ethnicity where lawfully collected, behavioural-health history, insurance status. ENA devotes a full section of the fifth edition to documented bias in triage: undertriage of minority patients, of geriatric patients, of women with chest pain, and of patients with behavioural-health or substance-use histories, plus the finding that patients perceived as "difficult" are triaged less accurately. A model trained on historical assignments will reproduce all of it unless you are measuring.

| Metric | Why |
|---|---|
| Undertriage rate, **by subgroup** | the primary safety metric; must be reported disaggregated |
| Overtriage rate, by subgroup | the resource cost you're consciously accepting |
| Calibration drift | seasonal case-mix shifts silently break thresholds |
| Override rate + direction | acceptance is the trust signal; direction is the safety signal |
| Gate D dismissal rate, by reason | the safety net's own failure mode |
| Alert burden per nurse per hour | alarm fatigue is an engineered harm |
| Time-to-first-assessment by level | did any of this actually help? |
| LWBS rate | the outcome that low-acuity starvation actually produces |

For scale calibration, note that a large multi-site retrospective study of 5.3M ED encounters found mistriage in roughly a third of visits — around 3% undertriaged and 29% overtriaged — with measurable racial disparities in both directions. That is the baseline you are trying to beat, and it tells you the realistic target is *shifting the error distribution*, not eliminating error.

### 4.10 Integration and degraded mode

- **FHIR R4** resources: `Encounter`, `Observation` (vitals), `Condition`, `RiskAssessment`, `Task` (reassessments), `Provenance` (audit). **HL7 v2 ADT** for hospitals not yet on FHIR — most of them.
- **Adapter pattern.** The triage engine must not import anything hospital-specific. Small rural EDs will have no bed-management API at all; the same engine must run with a stubbed adapter and a manual bed list.
- **Degraded mode is mandatory.** This is an ED. If the EHR link drops, the triage engine keeps running standalone on locally captured data, queues writes, and shows a clear degraded banner. A triage tool that stops working during a network incident is a tool nurses will refuse to depend on — correctly.

### Scalability across hospital types

The scale question in your brief is answered by configuration surface, not by separate builds:

| Layer | Portable? |
|---|---|
| Gates A, B, D (rule tables) | **Yes** — clinical standard, identical everywhere |
| Gate C resource model | **Site-calibrated** — a rural ED without CT has a different resource profile; ESI itself notes resource *determination* is meant to be site-independent, so calibrate the model, not the definitions |
| Reassessment intervals | Config |
| Fast-track / streaming rules | Config |
| Integration | Adapters |
| Thresholds | **Never site-tunable by non-clinicians.** Threshold changes are a clinical governance decision with a versioned, signed changelog. |

---

## Part 5 — Data protection and regulatory posture

Your brief asks you to state the jurisdiction. Since you're building in India, name **India** — it's more defensible than a hand-wave at HIPAA and it differentiates you from every other submission that says "HIPAA-compliant."

- **DPDP Act 2023** as the governing law, with the **ABDM Health Data Management Policy** for health-data specifics. Note the practical point that matters for an ED: DPDP contains provisions for processing without consent in medical emergencies and for threat-to-life situations — so your consent model is *emergency processing now, notice and consent reconciliation at registration*, which is both lawful and operationally realistic. Say this explicitly; most teams won't.
- **Data minimisation** — triage needs vitals, complaint, relevant history. It does not need a full record pull. Fetch by need.
- **Retention** — triage-decision records and audit logs retained per medical-record rules; raw model inputs retained separately, on a shorter clock, with a stated purpose (retraining) and a documented opt-out path.
- **Access control** — role-based, with break-glass emergency access that is *permitted but loudly logged*.
- **What an override must legally record** — timestamp, actor identity, the AI recommendation being overridden, model version, structured reason, resulting action. This is what makes the override meaningful rather than decorative.
- **Positioning** — decision *support*, with the clinician able to independently review the basis of each recommendation. That framing, backed by the explanation layer in 4.5, is what keeps the system in a lighter risk classification and is why the explanation layer is a compliance artefact rather than a nicety.

---

## Part 6 — Validation and the demo build

### 6.1 Free gold-standard test cases

The ESI v5 handbook contains **worked examples with expert-assigned levels**. Use them as your first regression suite — the labels are authoritative and cost you nothing:

| Case | Correct level | Tests |
|---|---|---|
| 28F, abdominal pain, LMP 8 weeks ago, HR 120, RR 22, BP 92/50 | 3 → **2** | Gate D uptriage; possible ectopic |
| 15-month-old, liquid stools, T 38, HR 158, RR 42, BP 86/50, cap refill 3 s | 3 → **2** | Paediatric age-banded thresholds |
| 57M, cough, T 38.5, RR 26, HR 100, SpO2 90% | 3 → **2** | Gate D; your build's `HR>100` rule alone gets the right answer for the wrong reason |
| 34F, abdominal pain/vomiting/constipation, HR 102, all else normal | **3** | HR just over threshold, correctly *not* uptriaged — the case your `HR>100 → ESI 2` rule fails |
| 72F COPD on home O2, infected cat bite, HR 105, RR 24, SpO2 91% (baseline 90–91) | **2** | Baseline-relative SpO2, steroid-blunted immune response, the seductive wrong explanation |
| 22M, RLQ pain since morning, vitals normal | **3** | Gate C: ≥2 resources |
| Healthy 3-year-old, ear pain, immunisations current, vitals normal | **5** | Gate C: 0 resources |
| Healthy 19-year-old, sore throat, vitals normal | **4** | Gate C: exactly 1 resource |
| 42-year-old, lost rescue inhaler, asymptomatic | **5** | Prescription refill is *not* a resource |

Then extend to your 15–20 simulated records. Deliberate coverage:

| Required by the brief | Build this case |
|---|---|
| Ambiguous presentation | Elderly patient, "just not feeling right," family says confused, vitals near-normal → tests AMS detection from a *family statement*, geriatric occult hypoperfusion, and low-confidence handling |
| Paediatric | 3-week-old, T 38.2, otherwise well-appearing → **at least ESI 2** on age alone; your current build would score this benign |
| Geriatric | 78M, blunt abdominal trauma, on warfarin, normal vitals → mechanism + anticoagulation floor despite reassuring numbers |
| Zero-history | Unidentified patient, no MRN, chest pain, no records → history_depth=none, wide conformal set, escalate on the boundary |
| Bradycardia | 70F, dizziness, HR 32 → **ESI 1**. Your current build assigns this ESI 5. Include it; it's the most persuasive slide you'll have. |
| Override | High-confidence ESI 2 that a clinician downgrades → show the second-look prompt and the resulting log entry |
| Deterioration | ESI 3, waits 40 min, repeat vitals cross the RR band → re-triage to 2, class change, interval tightens, log entry |
| Surge | Replay 3× arrivals → show acuity criteria unchanged, fast-track activated, aggregate waiting-room risk rising, intervals held |

### 6.2 Metrics to report

Not accuracy. Accuracy hides the asymmetry that the whole design is built around.

- **Undertriage rate** overall and at the **2/3 boundary specifically** — that boundary is where decompensation risk lives, and it's where published nurse accuracy is weakest (around 41% in the KATE study, against 80% for the model)
- **Overtriage rate** — the cost you're consciously paying
- **Quadratic weighted kappa** — respects ordinality; plain kappa treats a 1-vs-5 error as equivalent to 3-vs-4
- **Conformal set coverage** — does the 95% set actually contain the truth 95% of the time?
- **Subgroup breakdown** of all of the above

For context when you present: a nurse-baseline of roughly 60% ESI accuracy against expert consensus, with ML+clinical-NLP reaching roughly 76%, is the published landscape. Don't claim you'll beat it on synthetic data — claim your *architecture* is the one that can be validated against it.

### 6.3 Build order

1. **Rule tables + Gates A, B, D as pure functions.** No ML. Ship this first — on the handbook's own examples it will already outperform your current system, and it's fully explainable from day one.
2. **Event-sourced data model + audit log.** Retrofitting this later is painful and you need the override corpus from the very first user.
3. **Reassessment clock + deterioration engine** (NEWS2 / age-banded PEWS). Still no ML. This is the "unfatigable" property your brief is really asking for, and it's rule-based.
4. **Gate C resource model.** The first place ML earns its place. Ships the needs-planner simultaneously.
5. **Explanation layer + conformal uncertainty.**
6. **NLP flagger and outcome-risk model** as escalate-only advisory layers.
7. **Fairness and calibration monitoring** — before any real deployment, not after.

Note what this ordering implies: **most of your safety value is rule-based and arrives before any model does.** The ML earns its keep on resource prediction and on breaking up the undifferentiated ESI-3 bucket. If your demo has to be honest about anything, be honest about that — it's a more sophisticated position than "we trained a classifier," and it's the one that survives questioning by a clinician.

---

## Key references

**Standard**
- Emergency Nurses Association (2023). *Emergency Severity Index Handbook, 5th Edition.* — https://californiaena.org/wp-content/uploads/2023/05/ESI-Handbook-5th-Edition-3-2023.pdf
- Canadian Association of Emergency Physicians. *CTAS Implementation Guidelines* (reassessment intervals) — http://ctas-phctas.ca/wp-content/uploads/2018/05/2004_revisions-to-the-canadian-emergency-department-triage-and-acuity-scale-implementation-guidelines.pdf

**ML triage**
- Levin S, Toerper M, Hamrock E, et al. (2018). Machine-learning-based electronic triage more accurately differentiates patients with respect to clinical outcomes compared with the Emergency Severity Index. *Ann Emerg Med* 71(5):565–574. — the e-triage / parallel-outcome-prediction architecture
- Ivanov O, Wolf L, Brecher D, et al. (2021). Improving ED Emergency Severity Index acuity assignment using machine learning and clinical NLP. *J Emerg Nurs* 47(2):265–278. — KATE; the 2/3 boundary result. Preprint: https://arxiv.org/abs/2004.05184
- Sax DR, et al. (2023). Emergency department mistriage rates and disparities. *JAMA Netw Open* — 5.3M encounter baseline
- Hinson JS, Martinez DA, Cabral S, et al. (2019). Triage performance in emergency medicine: a systematic review. *Ann Emerg Med* 74(1):140–152

**Deterioration**
- Royal College of Physicians. *NEWS2* — with the caveat that it is ward-derived and not ED-validated
- Meta-analysis of NEWS2 in prehospital and ED settings — https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9929743/

**ESI v5 specifically**
- *The Emergency Severity Index Version 5: Simulation of Predictive Validity and Triage Level Distribution.* J Emerg Med (2025) — https://www.jem-journal.com/article/S0736-4679(25)00288-4/fulltext

**LLMs in triage** (relevant if you add an LLM layer — and a reason for caution)
- Meta-analysis of ChatGPT accuracy in adult ED triage (2026), *BMC Emerg Med* — pooled accuracy ~0.51 (GPT-3.5), ~0.70 (GPT-4 family), ~0.81 (optimised) — https://link.springer.com/article/10.1186/s12873-026-01521-y
- Haim GB, et al. (2024). GPT-4 vs medical experts in ESI assignment. *J Clin Nurs* — documented systematic *over*-triage bias
