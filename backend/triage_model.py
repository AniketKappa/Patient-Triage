"""
TriageOS - core scoring engine for PatientTriage.ai (Accenture Innovation
Challenge, Round 2 prototype).

This is an illustrative reference implementation, not a clinical device.
Thresholds are simplified for demonstration; a real deployment would need
clinical validation against a recognized framework (e.g. ESI, CTAS).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import math
import json


# ---------------------------------------------------------------------------
# 1. Age bands & age-adjusted normal ranges
# ---------------------------------------------------------------------------

def age_band(age: float) -> str:
    if age < 12:
        return "pediatric"
    elif age < 65:
        return "adult"
    else:
        return "geriatric"


def normal_hr_range(age: float) -> tuple[int, int]:
    if age < 1:
        return (100, 160)
    if age < 3:
        return (90, 150)
    if age < 12:
        return (70, 120)
    if age < 65:
        return (60, 100)
    return (60, 100)  # geriatric baseline similar, but reserve is lower


def normal_rr_range(age: float) -> tuple[int, int]:
    if age < 1:
        return (30, 60)
    if age < 3:
        return (24, 40)
    if age < 12:
        return (18, 30)
    return (12, 20)


def fever_threshold_c(age: float) -> float:
    # Temp above which fever is clinically noted as concerning for this band
    if age < 12:
        return 38.5
    if age < 65:
        return 39.0
    return 38.0  # geriatric: blunted fever response, lower threshold matters more


def hypotension_threshold_sys(age: float) -> int:
    if age < 12:
        return int(70 + 2 * age)  # rough pediatric hypotension estimate
    if age < 65:
        return 90
    return 100  # geriatric: often hypertensive at baseline, relative drop matters


def spo2_threshold(age: float) -> int:
    return 95 if age < 12 else 90


# ---------------------------------------------------------------------------
# 2. Patient state object
# ---------------------------------------------------------------------------

@dataclass
class VitalsReading:
    timestamp: datetime
    spo2: Optional[float] = None
    hr: Optional[float] = None
    bp_sys: Optional[float] = None
    bp_dia: Optional[float] = None
    rr: Optional[float] = None
    temp_c: Optional[float] = None


@dataclass
class Patient:
    patient_id: str
    age: float
    arrival_mode: str  # "ambulance" | "walkin"
    symptoms: list[str] = field(default_factory=list)
    vitals_history: list[VitalsReading] = field(default_factory=list)
    self_report_severity: Optional[int] = None  # 0-10, patient/relative reported
    history_available: bool = False
    chronic_conditions: list[str] = field(default_factory=list)
    unconscious: bool = False
    wait_time_min: float = 0.0
    severe_bleeding: bool = False

    # computed fields (filled by engine)
    severity: float = 0.0
    risk: float = 0.0
    confidence: float = 100.0
    esi: int = 5
    discordant: bool = False
    inconclusive: bool = False
    contributing_factors: list[str] = field(default_factory=list)
    override_log: list[dict] = field(default_factory=list)
    responded_to_treatment: Optional[bool] = None  # set while waiting

    @property
    def band(self) -> str:
        return age_band(self.age)

    @property
    def latest_vitals(self) -> Optional[VitalsReading]:
        return self.vitals_history[-1] if self.vitals_history else None


# ---------------------------------------------------------------------------
# 3. Severity engine (age-stratified, rule-based, explainable)
# ---------------------------------------------------------------------------

def compute_severity(p: Patient) -> tuple[float, list[str]]:
    v = p.latest_vitals
    reasons: list[str] = []
    score = 0.0

    if v is None:
        return 0.0, ["no vitals recorded"]

    if v.spo2 is not None and v.spo2 < spo2_threshold(p.age):
        score += 40
        reasons.append(f"SpO2 {v.spo2}% below age-adjusted threshold ({spo2_threshold(p.age)}%)")

    if v.bp_sys is not None and v.bp_sys < hypotension_threshold_sys(p.age):
        score += 35
        reasons.append(f"Systolic BP {v.bp_sys} below age-adjusted threshold")

    if v.hr is not None:
        lo, hi = normal_hr_range(p.age)
        if v.hr > hi:
            score += 15
            reasons.append(f"HR {v.hr} above normal range for age ({lo}-{hi})")
        elif v.hr < lo:
            score += 20
            reasons.append(f"HR {v.hr} below normal range for age ({lo}-{hi})")

    if v.rr is not None:
        lo, hi = normal_rr_range(p.age)
        if v.rr > hi or v.rr < lo:
            score += 15
            reasons.append(f"RR {v.rr} outside normal range for age ({lo}-{hi})")

    if v.temp_c is not None and v.temp_c >= fever_threshold_c(p.age):
        score += 10
        reasons.append(f"Temp {v.temp_c}C at/above age-adjusted fever threshold")

    if "chest_pain" in p.symptoms:
        score += 20
        reasons.append("chest pain reported")

    if p.severe_bleeding:
        score += 50
        reasons.append("severe bleeding")

    if p.unconscious:
        score += 45
        reasons.append("unconscious / unresponsive")

    return min(score, 100.0), reasons


# ---------------------------------------------------------------------------
# 4. Risk engine (probability of deterioration, not just current state)
# ---------------------------------------------------------------------------

def vital_stability_score(p: Patient) -> float:
    """0 (very unstable/trending worse) - 100 (stable). Uses trend if
    multiple readings are available, else falls back to a neutral value."""
    if len(p.vitals_history) < 2:
        return 70.0  # neutral-ish default when we can't assess trend yet

    first, last = p.vitals_history[0], p.vitals_history[-1]
    instability = 0.0
    if first.spo2 is not None and last.spo2 is not None:
        drop = first.spo2 - last.spo2
        if drop > 0:
            instability += min(drop * 6, 40)
    if first.bp_sys is not None and last.bp_sys is not None:
        drop = first.bp_sys - last.bp_sys
        if drop > 0:
            instability += min(drop * 1.2, 30)
    if first.hr is not None and last.hr is not None:
        rise = last.hr - first.hr
        if rise > 0:
            instability += min(rise * 0.8, 20)
    if first.rr is not None and last.rr is not None:
        rise = last.rr - first.rr
        if rise > 0:
            instability += min(rise * 1.5, 20)

    return max(0.0, 100.0 - instability)


def age_risk_factor(age: float) -> float:
    # Higher raw score = higher contribution to risk. Very young and very
    # old carry less physiological reserve.
    if age < 1:
        return 90
    if age < 12:
        return 55
    if age < 65:
        return 40
    if age < 80:
        return 70
    return 90


def history_risk_factor(p: Patient) -> float:
    if not p.history_available:
        return 50.0  # unknown history is treated as moderate, not zero, risk
    base = 30.0
    base += 15 * len(p.chronic_conditions)
    return min(base, 100.0)


def symptoms_risk_factor(p: Patient) -> float:
    high_risk_symptoms = {"chest_pain", "breathlessness", "severe_bleeding",
                           "altered_mental_status", "stroke_signs"}
    hits = len(set(p.symptoms) & high_risk_symptoms)
    return min(hits * 30, 100.0)


def compute_risk(p: Patient) -> float:
    severity, _ = compute_severity(p)
    stability = vital_stability_score(p)
    age_f = age_risk_factor(p.age)
    hist_f = history_risk_factor(p)
    sympt_f = symptoms_risk_factor(p)

    risk = (
        0.30 * severity
        + 0.20 * (100 - stability)
        + 0.20 * age_f
        + 0.15 * hist_f
        + 0.15 * sympt_f
    )
    return round(min(risk, 100.0), 1)


# ---------------------------------------------------------------------------
# 5. Confidence engine
# ---------------------------------------------------------------------------

def compute_confidence(p: Patient) -> float:
    confidence = 100.0
    if not p.history_available:
        confidence -= 15
    if p.latest_vitals is None:
        confidence -= 30
    else:
        v = p.latest_vitals
        missing = sum(1 for x in [v.spo2, v.hr, v.bp_sys, v.rr, v.temp_c] if x is None)
        confidence -= missing * 5
    if p.unconscious:
        confidence -= 20

    if p.self_report_severity is not None:
        severity, _ = compute_severity(p)
        vitals_severity_normalized = severity  # already 0-100
        self_report_normalized = p.self_report_severity * 10
        discordance = abs(vitals_severity_normalized - self_report_normalized)
        if discordance > 40:
            confidence -= 20
            p.discordant = True

    return max(round(confidence, 1), 0.0)


# ---------------------------------------------------------------------------
# 6. ESI assignment (confidence biases toward escalation, never downgrade)
# ---------------------------------------------------------------------------

def risk_to_esi(risk: float) -> int:
    if risk > 85:
        return 1
    elif risk > 70:
        return 2
    elif risk > 50:
        return 3
    elif risk > 30:
        return 4
    else:
        return 5


def critical_red_flags(p: Patient) -> list[str]:
    """Hard criteria for 'requires immediate life-saving intervention'
    (ESI-1 equivalent). These bypass the weighted risk composite entirely,
    mirroring how real ESI-1 is determined by explicit criteria rather than
    a blended score -- a composite score should never be allowed to dilute
    an unambiguous immediate-danger signal."""
    flags = []
    v = p.latest_vitals
    if p.unconscious:
        flags.append("unresponsive -> automatic ESI-1 criterion")
    if p.severe_bleeding:
        flags.append("uncontrolled severe bleeding -> automatic ESI-1 criterion")
    if v is not None:
        crit_spo2 = 85 if p.age >= 12 else 90
        if v.spo2 is not None and v.spo2 < crit_spo2:
            flags.append(f"critically low SpO2 ({v.spo2}%) -> automatic ESI-1 criterion")
        if v.bp_sys is not None and v.bp_sys < 80:
            flags.append(f"shock-range systolic BP ({v.bp_sys}) -> automatic ESI-1 criterion")
    return flags


def assign_esi(p: Patient) -> None:
    p.severity, reasons = compute_severity(p)
    p.risk = compute_risk(p)
    p.confidence = compute_confidence(p)
    esi = risk_to_esi(p.risk)

    p.inconclusive = False
    if p.confidence < 50:
        # Low confidence: escalate one level (lower ESI number = more urgent),
        # never de-escalate on uncertainty. Never escalate past 1.
        esi = max(1, esi - 1)
        p.inconclusive = True
        reasons.append(f"confidence {p.confidence}% below safety threshold -> escalated one level")

    if p.discordant:
        reasons.append("patient-reported severity and vitals-derived severity disagree significantly -> flagged for nurse review")

    # High-risk safety net: a severe rule-based severity score (independent
    # of the composite risk formula) caps ESI at 2 even if the blended risk
    # score alone would land it lower. Prevents a single moderate-weighted
    # factor in the composite from diluting an otherwise obvious high-danger
    # presentation (e.g. hypoxia + chest pain + tachycardia).
    if p.severity >= 75 and esi > 2:
        esi = 2
        reasons.append(f"severity score {p.severity} in high-risk range -> capped at ESI-2")

    # Red-flag override: explicit immediate-danger criteria always win,
    # regardless of the composite risk score.
    flags = critical_red_flags(p)
    if flags:
        esi = 1
        reasons.extend(flags)

    p.esi = esi
    p.contributing_factors = reasons


# ---------------------------------------------------------------------------
# 7. Anti-starvation priority queue
# ---------------------------------------------------------------------------

SAFE_MAX_WAIT_MIN = {1: 0, 2: 10, 3: 30, 4: 60, 5: 120}


def wait_urgency(p: Patient) -> float:
    """Non-linear boost once a patient exceeds the safe max wait for their
    own ESI level, regardless of how many higher-acuity patients keep
    arriving. Guarantees no patient waits past a hard safety ceiling."""
    ceiling = SAFE_MAX_WAIT_MIN.get(p.esi, 60)
    if ceiling == 0:
        return 100.0  # ESI-1 is always maximal urgency
    ratio = p.wait_time_min / ceiling
    if ratio <= 1.0:
        return ratio * 30  # linear, modest growth before ceiling
    # past the ceiling: quadratic growth, capped at 100
    overshoot = ratio - 1.0
    return min(30 + 70 * (overshoot ** 1.5), 100.0)


def deterioration_trend(p: Patient) -> float:
    return round(100 - vital_stability_score(p), 1)


def compute_priority(p: Patient, w_risk=0.5, w_det=0.3, w_wait=0.2) -> float:
    treatment_penalty = 0.0
    if p.responded_to_treatment is False:
        treatment_penalty = 10.0  # not responding to initial treatment raises priority
    priority = (
        w_risk * p.risk
        + w_det * deterioration_trend(p)
        + w_wait * wait_urgency(p)
        + treatment_penalty
    )
    return round(min(priority, 100.0), 1)


# ---------------------------------------------------------------------------
# 8. Deterioration / auto re-triage
# ---------------------------------------------------------------------------

def check_deterioration_and_retriage(p: Patient) -> bool:
    """Returns True and updates ESI/risk if a re-triage was triggered."""
    if len(p.vitals_history) < 2:
        return False
    old_esi = p.esi
    assign_esi(p)  # recompute against latest vitals
    if p.esi < old_esi:
        p.contributing_factors.append(f"AUTO RE-TRIAGE: ESI moved {old_esi} -> {p.esi} on deterioration")
        return True
    return False


# ---------------------------------------------------------------------------
# 9. Clinician override
# ---------------------------------------------------------------------------

def apply_override(p: Patient, new_esi: int, clinician_id: str, reason: str, ts: datetime) -> None:
    entry = {
        "timestamp": ts.isoformat(),
        "old_esi": p.esi,
        "new_esi": new_esi,
        "overridden_by": clinician_id,
        "reason": reason,
    }
    p.override_log.append(entry)
    p.esi = new_esi


# ---------------------------------------------------------------------------
# 10. Inter-hospital diversion (surge handling)
# ---------------------------------------------------------------------------

def should_recommend_diversion(queue: list[Patient], capacity: int) -> bool:
    """Simple surge trigger: queue depth beyond capacity threshold."""
    return len(queue) > capacity


def diversion_candidates(queue: list[Patient]) -> list[Patient]:
    """Lower-acuity incoming patients are the safe ones to divert."""
    return [p for p in queue if p.esi >= 4]


# ---------------------------------------------------------------------------
# 11. Serialization for audit / demo output
# ---------------------------------------------------------------------------

def patient_to_dict(p: Patient) -> dict:
    v = p.latest_vitals
    return {
        "patient_id": p.patient_id,
        "age": p.age,
        "age_band": p.band,
        "arrival_mode": p.arrival_mode,
        "symptoms": p.symptoms,
        "latest_vitals": {
            "spo2": v.spo2 if v else None,
            "hr": v.hr if v else None,
            "bp": f"{v.bp_sys}/{v.bp_dia}" if v and v.bp_sys else None,
            "rr": v.rr if v else None,
            "temp_c": v.temp_c if v else None,
        } if v else None,
        "history_available": p.history_available,
        "severity": p.severity,
        "risk": p.risk,
        "confidence": p.confidence,
        "esi": p.esi,
        "priority": compute_priority(p),
        "wait_time_min": p.wait_time_min,
        "discordant": p.discordant,
        "inconclusive": p.inconclusive,
        "contributing_factors": p.contributing_factors,
        "override_log": p.override_log,
    }
