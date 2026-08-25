# Regulatory & Governance Profile

**Target Jurisdiction:** India (DPDP Act 2023 + ABDM Health Data Management Policy)

## Data Protection Framework
- **Consent (Emergency Processing):** Under DPDP 2023 Section 7, explicit consent is waived for medical emergencies to preserve life. Reconciliation and formal consent capture occur at ED Registration once the patient is stabilised.
- **Data Minimisation:** The triage engine pulls only baseline vitals and relevant problem lists. It does not fetch full unstructured clinical notes from the EHR adapter unless specifically requested via a Break-Glass workflow.
- **Audit Logging:** Every AI decision and human override is logged in an immutable, append-only `EventLog` table.
- **Override Records:** Legally, an override log captures: `Actor ID`, `Previous ESI`, `New ESI`, and a `Structured Clinical Reason`. Overrides lacking a structured reason are rejected at the API layer.

## Software as a Medical Device (SaMD) Classification
This system is strictly classified as **Clinical Decision Support Software (CDSS)**. It is an advisory layer intended to support, not replace, a human clinician. It does not control life-support equipment or directly formulate a diagnosis.
