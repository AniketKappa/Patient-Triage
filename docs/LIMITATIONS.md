# System Limitations & Constraints

1. **Simulated Training Data:** The multi-label Random Forest resource model (Gate C) is trained on ~23 duplicated synthetic rows. **Consequence:** It has no real retrospective intuition, its probability outputs are not meaningfully calibrated, and it should not be trusted for real clinical use without a site-specific calibration run on local EHR data.
2. **Regex NLP Engine:** We use a robust regex heuristic for negation (e.g., catching "denies chest pain"). **Consequence:** It will miss complex scoping like "chest pain resolved yesterday but now short of breath." A true deployment requires a deep learning clinical encoder (like BioBERT).
3. **Outcome-Risk Placeholders:** The Step 6 thresholds (>10% ICU, >60% admission) are placeholder values pending real calibration data.
4. **Mocked Integrations:** FHIR (R4) and HL7v2 adapters are demonstrated via interface stubs, not live integrations. 
5. **No Prospective Validation:** This tool is an early-stage prototype for a CDSS and has not been evaluated on real patients.

> Most of this system's safety value is rule-based and arrives before any model does. Gates A, B and D are deterministic implementations of a published clinical standard (ENA ESI v5) and are explainable line by line. Machine learning earns its place in exactly two places: predicting resource requirements, and breaking up the undifferentiated ESI-3 bucket. We report this split deliberately rather than claiming an accuracy figure our training data cannot support.
