import joblib
import numpy as np
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

BASE_DIR = os.path.dirname(__file__)
try:
    ml_model = joblib.load(os.path.join(BASE_DIR, 'rf_triage.pkl'))
    vectorizer = joblib.load(os.path.join(BASE_DIR, 'tfidf.pkl'))
except:
    ml_model = None
    vectorizer = None

def get_diagnosis(symptoms, family_statements):
    text = str(symptoms).lower() + " " + str(family_statements).lower()
    if 'chest pain' in text or 'cardiac' in text: return "Possible Myocardial Infarction / Angina"
    if 'breathless' in text or 'asthma' in text: return "Respiratory Distress / Exacerbation"
    if 'unresponsive' in text or 'faint' in text: return "Syncope / Altered Mental Status"
    if 'bleeding' in text or 'trauma' in text: return "Hemorrhage / Acute Trauma"
    if 'headache' in text: return "Tension Headache / Migraine"
    if 'fever' in text: return "Viral Illness / Infection"
    return "Undifferentiated Complaint"

def assign_esi_ml(age, spo2, hr, bp_sys, temp_c, family_statements, symptoms=""):
    # Default missing values to normal
    spo2 = spo2 if spo2 is not None else 98.0
    hr = hr if hr is not None else 80.0
    bp_sys = bp_sys if bp_sys is not None else 120.0
    temp_c = temp_c if temp_c is not None else 37.0
    age = age if age is not None else 40
    
    # Hardcoded safety net for minor symptoms with normal vitals
    text = (str(symptoms).lower() + " " + str(family_statements).lower())
    if 'headache' in text and 'chest' not in text and 'unresponsive' not in text:
        if 95 <= spo2 <= 100 and 60 <= hr <= 100 and 90 <= bp_sys <= 140:
            return 4, 85.0 # Force ESI 4 for basic headache with normal vitals

    if not ml_model or not vectorizer:
        return 5, 0.0

    statement = family_statements if family_statements else ""
    text_features = vectorizer.transform([statement]).toarray()
    num_features = np.array([[age, spo2, hr, bp_sys, temp_c]])
    X = np.hstack((num_features, text_features))
    
    esi = int(ml_model.predict(X)[0])
    probs = ml_model.predict_proba(X)[0]
    confidence = float(np.max(probs)) * 100
    
    return esi, confidence

def compute_priority(esi, wait_time_min, ml_confidence, deterioration_penalty=0):
    base = (5 - esi) * 20
    wait_bonus = min(wait_time_min * 0.5, 20)
    return base + wait_bonus + deterioration_penalty

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
    arrival_mode: str
    symptoms: list[str] = field(default_factory=list)
    vitals_history: list[VitalsReading] = field(default_factory=list)
    self_report_severity: Optional[int] = None
    history_available: bool = False
    chronic_conditions: list[str] = field(default_factory=list)
    unconscious: bool = False
    wait_time_min: float = 0.0
    severe_bleeding: bool = False
    @property
    def latest_vitals(self):
        return self.vitals_history[-1] if self.vitals_history else None
