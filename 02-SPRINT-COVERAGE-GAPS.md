# Sprint 02 — Coverage Gaps

Prerequisite: every acceptance criterion in Sprint 01 passes.

Read `docs/triage-spec.md` and `docs/00-GAP-ANALYSIS.md` first. This sprint builds five modules that are entirely absent, four of which map to explicit requirements.

---

## Task 1 — Ambulance / pre-arrival lane (regression — this was dropped)

The original build had an Ambulance Dispatch mode. The rebuild has no pre-arrival path at all. This is a core requirement: the system must be able to triage a patient who is en route.

Pre-arrival is a genuinely different information state, not a status flag on a normal patient.

**Intake fields:**
- Mechanism of injury / presenting complaint
- **Prehospital vitals as a time series with timestamps** — not a snapshot. The trend between two ambulance readings is the signal.
- Interventions already administered (O2, fluids, adrenaline, naloxone, splinting)
- ETA
- Crew's own acuity impression

**Outputs:**
- A **provisional ESI**, stored with `is_provisional=True` and rendered visually distinct (dashed border, "PRE-ARRIVAL" chip). It must be impossible to mistake for a completed triage.
- Room reservation + team pre-alert for provisional 1/2.
- Equipment staging list (from the Task 3 needs planner).
- **Protocol clocks pre-started** — this is where the minutes actually are. Capture last-known-well time for stroke *before* the patient arrives.

**Hard rule:** on arrival, the provisional level must be explicitly **confirmed or amended** by a nurse. It never silently becomes the triage level. Write an `ARRIVAL_CONFIRMED` or `ARRIVAL_AMENDED` event. Prehospital data is thinner and older; treating it as equivalent produces a stale, anchored acuity.

Add a test: a provisional patient who arrives and is never confirmed appears in an "unconfirmed on arrival" safety panel after 5 minutes.

---

## Task 2 — Explanation layer

Brief requirement 1.4: decisions must be **explainable within seconds by a clinician managing several other patients**. Nothing currently exists for this.

Design constraint: readable in under five seconds. Not a SHAP plot. One line, one colour, one number, detail on tap.

Every patient row shows:

```
ESI 2   ⬆ from 3
WHY     RR 26 > 20 (adult threshold) · "cough ×3 days" · SpO2 90%
RULE    ESI v5 Decision Point D — high-risk vital signs
IF      RR were < 20 and SpO2 ≥ 92 → ESI 3
CONF    High · complete vitals · rule and model agree
                                          [ Accept ]  [ Override ]
```

Four components, all required:

1. **Which gate fired**, by name.
2. **The evidence** — specific vital values, and for NLP flags the **highlighted text span** that triggered it. Your regex negation handler already locates spans; surface them.
3. **The rule citation** — the ESI v5 clause, from the `source` field of the YAML rule table.
4. **The counterfactual** — "if RR were <20 this would be ESI 3." This is what makes the recommendation *checkable* rather than merely readable: the nurse can verify the logic against the patient in front of them at a glance.

This layer is also a compliance artefact, not just UX. A CDSS whose basis a clinician can independently review sits in a materially lighter regulatory risk category than one emitting opaque scores. Note that in the code comments.

---

## Task 3 — Needs / resource planner (staff-facing)

Gate C already predicts nine resource types. Right now that prediction is consumed only to compute a level and then discarded. Surface it — this is the highest value-per-line-of-code item in the whole build.

Render a prep card per patient:

```
┌─ P-2291 · 62F · ESI 2 (uptriaged from 3 — RR 26) ─────────────┐
│ PLACEMENT   Monitored bed · resus-adjacent                    │
│ EQUIPMENT   Cardiac monitor · O2 · 2× large-bore IV            │
│ PROTOCOL    ⏱ Sepsis bundle — lactate + cultures before abx    │
│             Antibiotic clock: 47 min remaining                 │
│ PREDICTED   Labs · ECG · CT · IV fluids · IV abx (5 resources) │
│ STAFF       Interpreter (Odia) · ISOLATION Droplet             │
│ CONFIDENCE  High · complete vitals · rule/model agree          │
└───────────────────────────────────────────────────────────────┘
```

- **Placement** — resus / monitored / standard / vertical / fast-track, derived from level + resource profile.
- **Equipment** — monitor, O2, IV access, warming, crash cart pre-position.
- **Isolation** — respiratory/contact/droplet inferred from symptoms + immunisation status.
- **Staff** — interpreter, security, paediatric-competent nurse, chaperone, safeguarding.
- **Time-critical protocol clocks** (highest leverage items on the board): STEMI (ECG within 10 min of arrival), stroke (last-known-well → CT clock → thrombolysis window countdown), sepsis (lactate, cultures-before-antibiotics, antibiotic clock), trauma activation, PEP window for needlestick/assault.
- **Predicted resources** — the list, not just the count.

**Also: delete or invert "Smart Probable Diagnosis" if it still exists anywhere.** A keyword map printing "Possible Myocardial Infarction" under a patient's name is the most dangerous element in the UI, because it **anchors** the clinician and will be wrong in exactly the atypical presentations where anchoring hurts most. If you keep anything, invert it: show a **"cannot be excluded yet"** rule-out list of time-critical differentials consistent with the presentation. That aids the clinician instead of substituting for them.

---

## Task 4 — History depth and zero-history handling

Brief reference parameter 3.3: assume roughly half of arrivals have a prior record and half do not. Currently unmodelled.

- Implement MRN matching → prior encounters, problem list, active meds, allergies, **baseline vitals from last visit**, prior ESI distribution. This is what supplies the `baseline_spo2` that Gate A already claims to use.
- Populate `history_depth` (`rich` / `partial` / `none`) on `TriageContext`.
- In `none` mode: models run on observed data only, **conformal/admissible sets widen automatically**, and the UI shows a visible "no prior records" chip. The widening must be a real consequence of missing features, not a cosmetic label.
- Add a `/api/patients/{id}/history-depth` endpoint and show the state on the patient card.

Test: the same clinical presentation submitted with and without history must produce a **wider** admissible set in the no-history case, and where the set crosses a boundary, a **more acute** recommendation.

---

## Task 5 — Reassessment worklist (replace the notification panel)

A panel that lists every condition shows nothing. Replace the reminders panel with a **ranked, bounded worklist**:

> **Next 3 patients to check**
> 1. P-2291 · ESI 2 · overdue 4 min · NEWS2 rose 3→6
> 2. P-2304 · ESI 3 · due now · routine
> 3. P-2288 · ESI 4 · overdue 12 min · routine

- Bounded (3–5 items), ordered, actionable, and it **clears** when done.
- Three clock states per patient: **due** → **overdue** → **breach** (2× interval; a logged safety event that notifies the charge nurse).
- Add **ESI 1 = continuous** to the CTAS timer table; it is currently missing.
- The distinction the current build cannot express: "patient is stable" and "nobody has looked at this patient in 90 minutes" are different states, and the second is more dangerous because it looks like the first.

---

## Acceptance criteria

1. A pre-arrival patient can be created, receives a provisional ESI, is visually distinct, and cannot be silently converted to a confirmed triage.
2. A stroke pre-alert captures last-known-well time before arrival and starts the clock.
3. Every patient row displays gate, evidence, rule citation, counterfactual, and confidence.
4. NLP-triggered flags highlight the exact text span that fired them.
5. The needs card renders for every patient with a resource prediction.
6. No diagnosis label appears anywhere in the UI (or it appears only as a rule-out list).
7. Zero-history and rich-history versions of the same presentation produce measurably different set widths.
8. The worklist is bounded, ranked, and clears on completion.
9. Reassessment clocks show three distinct states and breaches are logged as events.
