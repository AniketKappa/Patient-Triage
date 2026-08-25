# Sprint 04 — Governance, Data Protection, Scalability, Adoption

Prerequisite: Sprints 01–03 pass.

This sprint closes the four "Solutioning Areas" and the one Reference Parameter that currently have nothing built against them. These are cheap to implement and disproportionately weighted in judging, because most submissions skip them entirely.

---

## Task 1 — State the regulatory jurisdiction and derive everything from it

Brief requirement 3.4, verbatim: *State your assumed regulatory jurisdiction (e.g., HIPAA in the US, GDPR + national health law in the EU, or a named equivalent). **This affects your audit trail design, data retention policy, consent model, and what a clinician override must legally record.***

Nothing is currently stated. Pick **India**, and say so in the README, the `/about` page, and a new `docs/COMPLIANCE.md`:

- **Digital Personal Data Protection Act, 2023** as governing law
- **ABDM Health Data Management Policy** for health-data specifics

This is more defensible than a generic "HIPAA-compliant" claim from a team building in India, and it differentiates you from every other submission.

Then actually derive the four downstream items the brief names:

**1a. Consent model.** DPDP contains provisions for processing without prior consent in medical emergencies and threat-to-life situations. So your model is: **emergency processing at triage → notice and consent reconciliation at registration.** Implement it — a `consent_status` field (`EMERGENCY_PROCESSING` / `RECONCILED` / `WITHDRAWN`) and a reconciliation prompt in the registration flow. Say this explicitly in the docs; most teams won't.

**1b. Retention policy.** Two clocks, not one:
- Triage decision records and audit logs → retained per medical-record rules (state the period you assume).
- Raw model inputs → a **shorter, separate clock**, with a stated purpose (retraining) and a documented opt-out path.
Implement as a scheduled purge job with a dry-run mode.

**1c. Audit trail design.** Already strong. Add `model_version`, `rule_table_version`, and the **input snapshot hash** to every AI event so any past recommendation can be reproduced exactly.

**1d. What an override must legally record.** Enforce these as non-nullable on `HUMAN_OVERRIDE`: timestamp, actor identity, the AI recommendation being overridden, model version, structured reason, resulting action. Reject writes missing any of them.

---

## Task 2 — Data protection from unauthorised usage

Brief solutioning area 2.6 has two halves. You have started on "unfair"; "unauthorised" is untouched.

- **RBAC** — roles `TRIAGE_NURSE`, `CHARGE_NURSE`, `PHYSICIAN`, `ADMIN`, `AUDITOR`. Enforce at the API layer, not the UI.
- **Break-glass access** — permitted but loudly logged. Emergency access to a record outside the user's normal scope writes a `BREAK_GLASS_ACCESS` event and surfaces on an admin review queue.
- **Data minimisation** — triage needs vitals, complaint, and relevant history. It does not need a full record pull. Fetch by need and document which fields each gate actually consumes.
- **Encryption** — at rest and in transit. If SQLite makes at-rest encryption awkward, state that plainly as a known limitation rather than implying it's handled.
- **De-identification for the metrics endpoints** — `/api/metrics/*` must never return identifiable rows.

---

## Task 3 — Expand fairness monitoring (currently measuring the wrong primary metric)

`/api/metrics/fairness` computes wait times and override rates by gender. Both are useful secondary signals. Neither is the primary safety metric.

**Add undertriage rate stratified by subgroup** as the headline number. Then add these strata alongside gender:

- Age band (the paediatric/geriatric silent-safety-risk axis from brief requirement 1.2)
- `history_depth` — do zero-history patients get systematically worse triage?
- Language / interpreter required
- Presence of a behavioural-health flag — documented literature shows this cohort is especially prone to undertriage from stigma, so instrument it specifically

Also add:
- **Gate D dismissal rate by reason and by nurse** — the safety net's own failure mode.
- **Alert burden per nurse per hour** — alarm fatigue is an engineered harm, and it belongs on the fairness/safety dashboard, not in a log file.
- **Calibration drift** over the demo run.

For scale context in your write-up: a large multi-site retrospective study of 5.3M ED encounters found mistriage in roughly a third of visits — about 3% undertriaged and 29% overtriaged — with measurable racial disparities in both directions. That is the baseline being improved on, and it tells you the realistic goal is *shifting the error distribution*, not eliminating error.

---

## Task 4 — Scalability across hospital types

Brief solutioning area 2.7 and complexity 1.6. Answer with a **configuration surface**, not separate builds. Create `config/site.yaml` and document the portability boundary:

| Layer | Portable? |
|---|---|
| Gates A, B, D rule tables | **Yes** — clinical standard, identical everywhere |
| Gate C resource model | **Site-calibrated** — a rural ED without CT has a different resource profile. The standard notes resource *determination* is meant to be site-independent, so calibrate the model, not the definitions |
| Reassessment intervals | Config |
| Fast-track / streaming rules | Config |
| Available resources (does this site have CT? specialty consults?) | Config — and it must feed Gate C |
| Integration adapters | Pluggable |
| **Acuity thresholds** | **Never site-tunable by non-clinicians.** Threshold changes are a clinical governance decision with a versioned, signed changelog. |

Ship two example configs — `config/sites/large-urban.yaml` and `config/sites/small-rural.yaml` — and demonstrate the same engine running under both. That single demo answers the scalability question more convincingly than any slide.

---

## Task 5 — Integration adapters and degraded mode

Brief complexity 1.8. Currently listed as a limitation; a stub moves it to "designed for."

- **Adapter interface** — `EHRAdapter` with `fetch_patient_history()`, `push_triage_result()`, `fetch_bed_status()`. The triage engine must not import anything hospital-specific.
- **Three implementations**: `FHIRAdapter` (R4 — `Encounter`, `Observation`, `Condition`, `RiskAssessment`, `Task`, `Provenance`), `HL7v2Adapter` (ADT — most hospitals are still here), and `NullAdapter` (manual entry, for sites with no integration at all).
- FHIR and HL7 can be **thin stubs** that demonstrate the mapping without a live server. Say so honestly in the docs. A demonstrated mapping beats a claimed integration.
- **Degraded mode is mandatory.** This is an ED. If the adapter fails, the engine keeps running standalone on locally captured data, queues writes for replay, and shows a clear degraded banner. A triage tool that stops working during a network incident is one nurses will correctly refuse to depend on. Add a test that kills the adapter mid-run and asserts triage still completes.

---

## Task 6 — Adoption and change management

Brief solutioning area 2.5: *how you'd get a fatigued, time-pressured staff to actually trust the tool rather than work around it.* Nothing currently addresses this. Four concrete, buildable things:

1. **Bounded alerts.** The worklist from Sprint 02 plus the per-hour cap. Measure and display alert burden; treat a rising number as a defect.
2. **Zero-friction escalation, one-tap override.** Overriding upward must be faster than accepting. Never make the safe action the slow one.
3. **Show the tool's own error rate.** A "how often was this right" panel per nurse, drawn from override history. Counter-intuitive but it is what builds calibrated trust — staff trust a tool that admits its miss rate far more than one that presents every output as certain.
4. **Never silently change behaviour.** Any model or rule-table version change surfaces a changelog banner. The surge banner from Sprint 03 is the same principle.

Write these up in `docs/ADOPTION.md` with the reasoning, and implement 1–3.

---

## Task 7 — Rewrite the limitations section honestly

Your current limitations section is genuinely good — do not soften it. Expand it, and add what's missing:

- Resource model trained on ~23 duplicated synthetic rows. **State the consequence explicitly**, not just the fact: it has no real retrospective intuition, its probability outputs are not meaningfully calibrated, and any accuracy figure from it is an artefact of the generator.
- Regex negation rather than a clinical encoder — with the specific failure mode named (it will miss complex scoping like "chest pain resolved yesterday but now short of breath").
- SQLite, no cloud HA.
- FHIR/HL7 adapters are demonstrated mappings, not live integrations.
- Outcome-risk thresholds (>10% ICU, >60% admission) are **placeholder values pending calibration data** — say this in the UI next to the advisory, not just in the docs.
- No prospective clinical validation. **This is decision support, not a medical device, and has not been evaluated on real patients.**

Add one honest positioning paragraph, because it is a stronger claim than an accuracy number:

> Most of this system's safety value is rule-based and arrives before any model does. Gates A, B and D are deterministic implementations of a published clinical standard and are explainable line by line. Machine learning earns its place in exactly two places: predicting resource requirements, and breaking up the undifferentiated ESI-3 bucket. We report this split deliberately rather than claiming an accuracy figure our training data cannot support.

---

## Acceptance criteria

1. `docs/COMPLIANCE.md` exists, names DPDP 2023 + ABDM, and derives consent, retention, audit and override-record requirements from it.
2. Override writes are rejected if any legally-required field is missing.
3. RBAC enforced at the API layer; break-glass logged.
4. `/api/metrics/fairness` reports undertriage rate by age band, history depth, language, and behavioural-health flag.
5. Gate D dismissal rate and alert burden are exposed.
6. Two site configs run the same engine with different resource availability and different Gate C outputs.
7. Killing the adapter mid-run does not stop triage; degraded banner appears.
8. `docs/ADOPTION.md` exists; items 1–3 implemented.
9. Limitations section updated with consequences, not just facts.
