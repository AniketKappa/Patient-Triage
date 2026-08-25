# PatientTriage.ai — Gap Analysis Against the Problem Statement

Reference document. Not a task prompt — this is what sprints 01–04 are derived from. Keep it in `docs/` so any agent session can check its work against it.

Status key: **✅ done** · **⚠️ partial** · **❌ missing** · **🔴 regression** (was correct in the spec, has come back wrong)

---

## Section 1 — "Real-World Complexities to Consider"

| # | Problem statement requirement | Status | What's actually there | What's missing |
|---|---|---|---|---|
| 1.1 | Overlapping/ambiguous symptoms; patients under-report; presentation differs by age or condition | ⚠️ | NLP flagger with regex negation; conformal-ish admissible sets | No `TriageContext` layer, so "differs by age or condition" is only handled at Gate D. No under-reporting compensation (family/bystander statements are not weighted as a distinct evidence class). No ambiguous-presentation demo case. |
| 1.2 | **Thresholds differ across pediatric / adult / geriatric; single adult-calibrated model = silent safety risk** | 🔴 | Age-banding exists **only at Gate D** | **Gate A is adult-only**: `HR < 40`, `adult HR > 150`, `adult SBP < 80`. A neonate at HR 210 or an infant at SBP 55 does not trigger Gate A. This is precisely the silent safety risk the brief names, and it currently sits in the highest-acuity gate. Also no geriatric modifier (blunted compensation, occult hypoperfusion). |
| 1.3 | Data availability varies hugely — rich history vs. first-time patient | ❌ | `INSUFFICIENT_DATA` guard for missing vitals only | No `history_depth` concept (`rich`/`partial`/`none`). Gate A says SpO2 is "adjusted for baseline" but there is no mechanism that supplies a baseline. Confidence does not widen for history-poor patients. |
| 1.4 | **Decisions must be explainable, within seconds, by a clinician managing several patients** | ❌ | Advisory strings; conformal set logged | No explanation layer at all. No rule citation, no evidence spans, no counterfactual, no <5s-readable card. This is an explicit brief requirement with nothing built against it. |
| 1.5 | **Asymmetric cost; must bias toward escalation and demonstrate the choice explicitly in the prototype** | ⚠️ | Tie-break to most acute; Gate D advisory | The *bias* exists but is not **demonstrated**. The brief says teams must show the design choice explicitly. No asymmetric loss matrix, no undertriage-vs-overtriage split reported, no visible "we escalated here and here's why" surface. |
| 1.6 | Hospitals differ in scale, specialty mix, staffing | ❌ | — | No config surface, no adapter pattern, no site-calibration story. Thresholds appear hard-coded. |
| 1.7 | Recommendations reviewable and overridable; clear audit trail; health-data regulation compliance | ⚠️ | Event log with `actor_id`, `prev_esi`, `new_esi`, structured reason — genuinely good | No jurisdiction stated (see 3.4). No RBAC or break-glass. No visible audit-trail viewer in the UI. No second-look prompt on high-confidence **downward** overrides. |
| 1.8 | Integration with hospital systems; maturity varies | ❌ | Acknowledged as a limitation | No FHIR/HL7 adapter, not even a stub. No degraded mode. |

---

## Section 2 — "Solutioning Areas You Could Explore"

| # | Area | Status | Gap |
|---|---|---|---|
| 2.1 | Data strategy — structure/weigh inputs despite inconsistent completeness | ⚠️ | Inputs are structured, but there is no weighting-under-incompleteness policy. Missing vitals block; missing *history* is silently ignored. |
| 2.2 | Decision model + representing the assistant's own uncertainty | ⚠️ | Hybrid cascade is right. **But "Conformal Prediction Sets" as described is probability thresholding, not conformal prediction** — there is no calibration set and no coverage guarantee. With ~23 training rows you cannot calibrate one. Either implement split-conformal properly or rename it. An ML-literate judge will catch this. |
| 2.3 | Workflow design — surfacing to a nurse, capturing overrides, **surge vs. quiet shift** | ❌ | Overrides captured. **Surge behaviour entirely absent** — and it is also a Minimum Prototype Expectation (3.6). |
| 2.4 | Safety-first defaults; monitoring waiting patients; re-assess on wait-time breach **or worsening vitals** | 🔴 | CTAS clocks are in, and queue ordering is now correct | **Deterioration detection still uses `SpO2 drop > 2%` and `HR spike > 20`.** Both sit inside measurement noise — pulse oximeters are ±2%, so this fires on nothing. No NEWS2, no age-banded PEWS, no confirmation repeat, no rate-of-change. Also **"deterioration applies a priority penalty (boosting them in the queue)"** reintroduces the scalar-priority bug: deterioration must trigger **re-triage** (an ESI class change), not a queue nudge. |
| 2.5 | Adoption & change management — fatigued, time-pressured staff | ❌ | — | No alert-burden cap or measurement, no worklist (a notification panel that lists everything shows nothing), no trust affordances. |
| 2.6 | Patient data protection from unfair and unauthorised usage | ❌ | Fairness endpoint (gender only) | "Unauthorised" is untouched: no RBAC, no break-glass logging, no encryption-at-rest statement, no data minimisation. "Unfair" is partly covered but measures the wrong thing (see 4.1). |
| 2.7 | Scalability across hospital size/specialty/maturity | ❌ | — | Same as 1.6. |

---

## Section 3 — "Reference Parameters" (things the brief asks you to *state*)

| # | Requirement | Status | Gap |
|---|---|---|---|
| 3.1 | Assume EDs of ~100–500+ visits/day | ❌ | Not stated anywhere. Needs to appear in README and drive the surge simulator's volume. |
| 3.2 | May reference a standard 5-level framework | ✅ | ESI v5, correctly cited |
| 3.3 | **Assume ~half of arrivals have prior records, half do not** | ❌ | Not modelled. Demo cohort must be ~50/50 and the system must behave visibly differently for each. |
| 3.4 | **State your regulatory jurisdiction — it affects audit trail, retention, consent, and what an override must legally record** | ❌ | Nothing stated | Explicit, checkable requirement. Pick **India: DPDP Act 2023 + ABDM Health Data Management Policy** — more defensible than a generic HIPAA claim and it differentiates you. Then derive retention, consent (emergency processing → reconciliation at registration), and override fields from it. |

---

## Section 4 — "Minimum Prototype Expectations" (the checklist you will be scored against)

| # | Expectation | Status | Gap |
|---|---|---|---|
| 4.1 | **15–20 simulated patient records** | ⚠️ | ~23 rows exist but that is *training* data. You need a separate, curated **demo cohort** of 20 records with known-correct expected levels. |
| 4.2 | **At least one ambiguous, one pediatric/geriatric, one zero-history case** | ❌ | Not curated | Must be explicit, labelled, and demonstrable in the UI. |
| 4.3 | **Behaviour under 3× surge** | ❌ | Nothing | Needs a replayable simulator plus a surge banner stating what did *not* change. |
| 4.4 | **Never return a score without a confidence indicator** | ⚠️ | Admissible set is computed and logged | Not clear it is *displayed on every patient row*. Requirement is absolute — no score anywhere in the UI without confidence next to it. |
| 4.5 | **Capture ≥1 clinician override and show what the system logs** | ⚠️ | Override is captured in the event log | "**Show** what the system logs" means a visible audit viewer in the UI, not a database table. |

---

## Section 5 — Requirements from your own original brief (not in the screenshot, but you asked for them)

| # | Requirement | Status | Gap |
|---|---|---|---|
| 5.1 | **Ambulance / en-route triage before arrival** | 🔴 | **Dropped entirely in the rebuild.** Your original build had an Ambulance Dispatch mode; the new spec has no pre-arrival lane. This was a core requirement in your first message and it is now absent. |
| 5.2 | **Tell staff what each patient requires (life support / resources / etc.)** | ⚠️ | Gate C predicts 9 resource types | The prediction exists but is used only to compute a level. It is not surfaced as a staff-facing prep card (placement, equipment, isolation, protocol clocks). This is nearly free — the model already runs. |
| 5.3 | AI reminds the nurse to re-check regularly | ⚠️ | CTAS clocks + breach alerts | ESI 1 = continuous is missing from the timer table. No three-state due/overdue/breach model. No ranked worklist. |

---

## Section 6 — Clinical correctness defects found in the current spec

Ordered by severity. Sprint 01 fixes all of these.

1. **Gate A is not age-banded** (§1.2 above). Highest severity — it is the gate that catches dying patients.
2. **Gate D only evaluates ESI 3 patients.** ESI v5's headline change from v4 is that HR/RR/SpO2 are mandatory for *every* patient not already gated to 1 or 2, and out-of-range values force reassessment at **levels 4 and 5 too**. Restricting Gate D to ESI 3 is v4 behaviour.
3. **Gate D produces a passive advisory string.** It should be a decision prompt with uptriage as the pre-selected default, a structured dismissal reason, and a logged dismissal counted as a QA metric.
4. **Gate D appears to omit SpO2 < 92%** — the table needs HR, RR, *and* SpO2.
5. **Deterioration thresholds are inside the noise floor** (§2.4).
6. **Deterioration produces a priority penalty rather than a re-triage** (§2.4).
7. **No `TriageContext` / Layer 0** — pregnancy state, immunocompromise, baseline SpO2, rate-blunting medications, anticoagulation, geriatric flag. Without it, several Gate B rules in the spec cannot fire at all.
8. **Gate B rule coverage is category-level, not rule-level.** Named categories are ACS, stroke, respiratory, systemic pain, trauma, OB/GYN, psych. Absent: neonate fever (<28d, T>38 → floor 2), pregnancy SBP <90 or >150, immunocompromised/transplant + fever, anticoagulated head injury, button battery or magnet ingestion, testicular/ovarian torsion, needlestick PEP window, thunderclap headache, brisk epistaxis on anticoagulants.
9. **No isolated-orthopaedic-pain carve-out.** Pain ≥7 with intact neurovascular status and no systemic disruption → treat at triage, continue to Gate C. Without this you will over-triage every ankle fracture.
10. **Queue sort key is incomplete.** Currently ESI → time_to_breach. Should be ESI → deteriorating → time_to_breach → arrival_time (FIFO). And the "priority penalty" from defect 6 directly contradicts "sorted strictly by ESI level first" — one of the two is not doing what the spec says.
11. **PALS bands vs. ESI v5 bands.** Use the ESI v5 handbook's own table values verbatim, in versioned config. They are close to PALS but you want to cite the standard you claim to implement.
12. **Fairness endpoint measures the wrong primary metric.** Wait time and override rate are useful secondary signals; the primary safety metric is **undertriage rate by subgroup**. Gender only is also too narrow — add age band and history_depth at minimum.
13. **"Conformal Prediction Sets" is a misnomer** (§2.2).
14. **Outcome-risk thresholds (>10% ICU, >60% admission) are arbitrary** and trained on ~23 rows. Either derive them from a calibration split or state plainly in the UI that they are placeholder thresholds pending real data.

---

## Section 7 — What is genuinely right (do not let an agent "improve" these)

- The four-gate cascade structure with `min`-style escalation.
- Append-only event log with actor, previous state, new state, structured reason. This is the strongest part of the build.
- Gate C as a multi-label resource-type model rather than a severity heuristic.
- Queue sorted by ESI class first.
- Dual critical/standard dashboard.
- `INSUFFICIENT_DATA` (ESI 0) as a distinct state rather than a guessed level.
- The honest limitations section. Keep it; expand it (Sprint 04) rather than softening it.

---

## Sprint order

| Sprint | File | Why this order |
|---|---|---|
| 01 | `01-SPRINT-CLINICAL-CORRECTNESS.md` | Safety defects. Nothing else matters if Gate A misses a shocked infant. |
| 02 | `02-SPRINT-COVERAGE-GAPS.md` | Ambulance lane, explanation layer, needs planner, history depth, worklist. |
| 03 | `03-SPRINT-DEMO-REQUIREMENTS.md` | The scored checklist: cohort, surge, confidence display, override viewer. |
| 04 | `04-SPRINT-GOVERNANCE.md` | Jurisdiction, data protection, scalability, fairness, honest docs. |

Run them in order. Each is a separate agent conversation.
