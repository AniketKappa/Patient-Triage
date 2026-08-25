# Adoption & Change Management

Getting fatigued, time-pressured ED staff to trust and use an AI triage system requires careful UX and operational engineering.

1. **Bounded Alerts:** We cap the alert burden per nurse to avoid alarm fatigue. The worklist only surfaces the most critical pending items and clears instantly.
2. **Zero-Friction Escalation:** Overriding upward (e.g., changing an ESI 3 to an ESI 2) is a one-tap action. The safest action must never be the slowest.
3. **Transparent Error Rates:** The UI embraces transparency by exposing the "Conformal Admissible Set" instead of pretending to have 100% confidence. It explicitly tells nurses when the rules cross boundaries.
4. **No Silent Behaviour Changes:** Any change to the model version or the clinical rule table triggers a mandatory changelog banner.
