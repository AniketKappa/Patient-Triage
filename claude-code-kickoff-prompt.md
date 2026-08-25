You have a repo containing an emergency-department triage assistant: FastAPI + SQLAlchemy backend, Alpine.js + Tailwind frontend with dual critical/standard patient queues. The current triage scoring logic is clinically wrong and is being replaced.

I've added `docs/triage-spec.md` — a full redesign spec grounded in the ESI Handbook 5th Edition (Emergency Nurses Association, 2023). **Read it in full before writing any code.** It is the source of truth. Where this message and the spec disagree, the spec wins.

## Do not do this yet

Do not touch the scoring logic. Do not refactor the gates. Do not write the rule tables. This session has exactly two deliverables, below, and then you stop and report.

## Deliverable 0 — repo orientation

There are duplicate module copies at the repo root and under `backend/` (`main.py`, `models.py`, `database.py` appear in both). Work out which set is actually imported at runtime and tell me which. Do not modify or delete either copy until I confirm. Also report anything else in the tree that looks like build output or a committed artifact rather than source code.

## Deliverable 1 — `CLAUDE.md` at the repo root

Write a concise `CLAUDE.md` (aim for under 100 lines) that any future session reads before working on triage code. It must state, as hard constraints:

**Three invariants that may never be violated:**
1. Acuity composition uses `min` (most-acute-wins), never a weighted sum, average, or blended score. Every evidence source may only assert an acuity *floor*.
2. No ML model may lower a floor asserted by a deterministic rule. Models are escalate-only.
3. No automatic downgrade of acuity, ever. A downgrade requires a named clinician, a structured reason, and an exception log entry.

**Structural facts about ESI that must not be re-derived or "simplified":**
- ESI is a strictly ordered four-gate cascade A → B → C → D, evaluated in order. It is not a scoring function. Do not collapse the gates into a single score "for simplicity" — that is the exact bug being removed.
- ESI 3/4/5 is a *resource-type count*, not a severity score: ≥2 distinct resource types → 3, exactly 1 → 4, none → 5. Do not reintroduce a numeric severity threshold here.
- All vital-sign thresholds are age-banded across seven bands. No adult-only threshold may appear anywhere in the acuity path.
- Heart rate is checked on *both* tails. Bradycardia is a Gate A criterion.
- Respiratory rate is mandatory for every patient not gated to ESI 1 or 2.
- Under uncertainty, escalate. Never round down at a class boundary.

**Also record:** the three quantities that must stay separate and must never be summed — acuity (ESI class), deterioration risk (early-warning trajectory), and queue position.

Derive the specifics from the spec; don't just copy my bullets verbatim if the spec is more precise.

## Deliverable 2 — the regression suite, written to fail

Create `tests/test_esi_gold_cases.py` with the nine gold-standard cases from §6.1 of the spec. These are worked examples from the ENA handbook with expert-assigned acuity levels, so the expected values are authoritative — do not adjust them.

Requirements:
- Each test asserts the final ESI level against the **current** production triage function, whatever its present signature is. Find it and call it; do not write a new engine to test against.
- Each test carries a docstring naming which gate or clinical principle it exercises and why the current logic is expected to fail it.
- Where the current function's input shape can't express a case (e.g. respiratory rate isn't collected, age bands don't exist), do **not** stub around it — mark the test `xfail` with a reason string naming the missing input. That gap is itself a finding I want recorded.
- Include a small helper that prints a comparison table (case, expected, actual, delta direction) so I can run it as a demo.

Then run the suite and report:
- The failure count and the full comparison table.
- For each failure, which specific line or rule in the current scoring code produced the wrong answer — cite file and line.
- The undertriage/overtriage split across the failures (undertriage is the safety-critical direction).

## Ground rules

- **Never edit a test to make it pass.** If a gold case seems wrong, stop and ask me — don't reconcile it yourself.
- Don't fix anything you find in the scoring code during this session. Note it and move on. I want the failing baseline intact as a before/after artifact.
- If the spec is ambiguous on something you need, ask rather than choosing.
- Read the existing code before assuming its structure; the frontend dual-queue design is staying, so don't propose replacing it.

After you report, I'll tell you which stage of the build order (spec §6.3) to start on next.
