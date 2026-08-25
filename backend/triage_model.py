from esi_rules import assign_esi_v5

def assign_esi_ml(age: int, spo2: float, hr: float, sbp: float, temp_c: float, rr: float, family_statements: str, symptoms: str, critical_look: bool = False) -> tuple[int, float, str]:
    """
    Adapter bridging the old signature to the new v5 pure-function engine.
    Now returns (esi, confidence, explanation)
    """
    obs = {
        'spo2': spo2,
        'hr': hr,
        'sbp': sbp,
        'temp_c': temp_c,
        'rr': rr
    }
    text = f"{symptoms} {family_statements}"
    
    result = assign_esi_v5(float(age), obs, text, critical_look)
    
    # We return the new level, and a mock confidence value
    # In a full implementation, confidence would come from the conformal prediction set
    conf = 95.0 if result.gate in ['A', 'B'] else 80.0
    
    explanation = f"Gate {result.gate}: " + ", ".join(result.evidence)
    if result.pending_prompt:
        explanation += f". {result.pending_prompt}"
        
    return result.level, conf, explanation

def compute_priority(esi: int, wait_time_min: float, confidence: float, deterioration_penalty: int) -> float:
    """
    NEW QUEUE ORDERING (Replaces score-based arithmetic)
    ESI 1 is always above ESI 2.
    Inside an ESI bucket, deterioration penalty is the highest weight.
    Wait time only factors in *after* deterioration.
    """
    priority = deterioration_penalty * 1000  # Deteriorating patients always float to top of their bucket
    priority += wait_time_min  # Wait time is a secondary sort key within the bucket
    
    return round(priority, 2)

def get_diagnosis(symptoms: str, family_statements: str) -> str:
    # We are returning "Needs Assessment" to prevent clinician anchoring, 
    # as advised in the redesign spec (Part 3)
    text = str(symptoms).lower() + " " + str(family_statements).lower()
    
    if "chest pain" in text:
        return "R/O ACS / Cardiac"
    if "stroke" in text or "droop" in text or "weakness" in text:
        return "R/O CVA / Stroke"
    if "breath" in text:
        return "R/O Respiratory Compromise"
        
    return "Undifferentiated — Assess"

# Legacy dataclasses for seed.py / demo_data.py compatibility
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

@dataclass
class VitalsReading:
    timestamp: datetime
    hr: int
    rr: int
    spo2: int
    temp_c: float
    bp_sys: int
    bp_dia: int
    pain_score: int = 0

@dataclass
class Patient:
    patient_id: str
    age: int
    gender: str = "Unspecified"
    arrival_mode: str = "walk-in" # walk-in, ambulance
    symptoms: List[str] = field(default_factory=list)
    chronic_conditions: List[str] = field(default_factory=list)
    vitals_history: List[VitalsReading] = field(default_factory=list)
    esi_base: Optional[int] = None
    ml_confidence: float = 0.0
    net_score: float = 0.0
    priority: float = 0.0
    status: str = "queue"
    wait_time_min: int = 0
    self_report_severity: int = 0
    history_available: bool = True
    unconscious: bool = False
    severe_bleeding: bool = False
    mental_status_change: bool = False
    family_statements: Optional[str] = None
    
    @property
    def latest_vitals(self) -> Optional[VitalsReading]:
        return self.vitals_history[-1] if self.vitals_history else None

