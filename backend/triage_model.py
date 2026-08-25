from esi_rules import assign_esi_v5

def assign_esi_ml(age: int, spo2: float, hr: float, sbp: float, temp_c: float, rr: float, family_statements: str, symptoms: str, critical_look: bool = False) -> tuple[int, float, str]:
    obs = {}
    if spo2 is not None: obs['spo2'] = float(spo2)
    if hr is not None: obs['hr'] = float(hr)
    if sbp is not None: obs['sbp'] = float(sbp)
    if temp_c is not None: obs['temp_c'] = float(temp_c)
    if rr is not None: obs['rr'] = float(rr)
    
    text_parts = []
    if symptoms: text_parts.append(str(symptoms))
    if family_statements: text_parts.append(str(family_statements))
    text = " ".join(text_parts)
    
    result = assign_esi_v5(float(age), obs, text, critical_look)
    
    if getattr(result, 'is_insufficient_data', False):
        return 0, 0.0, "INSUFFICIENT DATA: Proceed to immediate human assessment."
        
    conf_map = {"High": 95.0, "Moderate": 70.0, "Low": 40.0}
    conf = conf_map.get(result.confidence_label, 80.0)
    
    expl_lines = []
    expl_lines.append(f"Gate {result.gate}: {', '.join(result.evidence)}")
    
    if result.admissible_set and len(result.admissible_set) > 1:
        expl_lines.append(f"Admissible set {result.admissible_set} crosses boundaries; escalated to ESI {result.level}")
        
    if result.missing_inputs:
        expl_lines.append(f"Missing mandatory inputs: {', '.join(result.missing_inputs)}")
        
    if result.advisory_alerts:
        expl_lines.extend(result.advisory_alerts)
        
    if result.pending_prompt:
        expl_lines.append(f"Prompt: {result.pending_prompt}")
        
    return result.level, conf, " | ".join(expl_lines)

def get_diagnosis(symptoms: str, family_statements: str) -> str:
    text = f"{symptoms} {family_statements}".lower()
    if 'chest pain' in text: return 'Rule out ACS'
    if 'stroke' in text or 'facial droop' in text: return 'Rule out CVA'
    if 'fever' in text and 'cough' in text: return 'Respiratory Infection'
    if 'pain' in text: return 'Pain - Undifferentiated'
    return 'Undifferentiated'

def compute_priority(esi: int, time_to_breach: float, ml_confidence: float, deterioration_penalty: int) -> float:
    # We sort by ESI strictly in the outer layer. 
    # Inside the ESI bucket, we sort by priority.
    # The higher the priority, the closer they are to the top of their ESI group.
    # Negative time_to_breach means they are breached (e.g. -15 means 15 mins overdue).
    # So we want lower time_to_breach to equal higher priority.
    
    return (-time_to_breach) + deterioration_penalty

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
    arrival_mode: str = "walk-in"
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
    mental_status_change: bool = False
    family_statements: Optional[str] = None
    unconscious: bool = False
    severe_bleeding: bool = False
    
    @property
    def latest_vitals(self) -> Optional[VitalsReading]:
        return self.vitals_history[-1] if self.vitals_history else None
