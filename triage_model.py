import joblib
import numpy as np
import os

# Load ML models
BASE_DIR = os.path.dirname(__file__)
try:
    ml_model = joblib.load(os.path.join(BASE_DIR, 'rf_triage.pkl'))
    vectorizer = joblib.load(os.path.join(BASE_DIR, 'tfidf.pkl'))
except:
    ml_model = None
    vectorizer = None

def assign_esi_ml(age, spo2, hr, bp_sys, temp_c, family_statements):
    if not ml_model or not vectorizer:
        return 5, 0.0 # fallback

    # Default missing values to normal
    spo2 = spo2 if spo2 is not None else 98.0
    hr = hr if hr is not None else 80.0
    bp_sys = bp_sys if bp_sys is not None else 120.0
    temp_c = temp_c if temp_c is not None else 37.0
    age = age if age is not None else 40
    
    statement = family_statements if family_statements else ""
    
    # NLP Transform
    text_features = vectorizer.transform([statement]).toarray()
    
    # Num Features
    num_features = np.array([[age, spo2, hr, bp_sys, temp_c]])
    
    # Combine
    X = np.hstack((num_features, text_features))
    
    # Predict
    esi = int(ml_model.predict(X)[0])
    
    # Confidence (max probability)
    probs = ml_model.predict_proba(X)[0]
    confidence = float(np.max(probs)) * 100
    
    return esi, confidence

def compute_priority(esi, wait_time_min, ml_confidence):
    # ESI 1 is highest priority.
    # We invert ESI (5-esi)*20 to get a base score of 0-80
    base = (5 - esi) * 20
    # Add wait time (longer wait = higher priority)
    wait_bonus = min(wait_time_min * 0.5, 20)
    return base + wait_bonus

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

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
