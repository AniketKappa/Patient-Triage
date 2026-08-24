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
    text = (str(symptoms) + " " + str(family_statements)).lower()
    if 'chest pain' in text or 'cardiac' in text: return "Possible Myocardial Infarction / Angina"
    if 'breathless' in text or 'asthma' in text: return "Respiratory Distress / Exacerbation"
    if 'unresponsive' in text or 'faint' in text: return "Syncope / Altered Mental Status"
    if 'bleeding' in text or 'trauma' in text: return "Hemorrhage / Acute Trauma"
    if 'headache' in text: return "Tension Headache / Migraine"
    if 'fever' in text: return "Viral Illness / Infection"
    return "Undifferentiated Complaint"

def assign_esi_ml(age, spo2, hr, bp_sys, temp_c, family_statements, symptoms=""):
    spo2 = float(spo2) if spo2 is not None else 98.0
    hr = float(hr) if hr is not None else 80.0
    bp_sys = float(bp_sys) if bp_sys is not None else 120.0
    temp_c = float(temp_c) if temp_c is not None else 37.0
    age = float(age) if age is not None else 40.0
    
    text = (str(symptoms) + " " + str(family_statements)).lower()
    
    # HARD CLINICAL RULES (Critical Pass Queue)
    if spo2 < 90 or hr > 130 or bp_sys < 80 or 'unresponsive' in text:
        return 1, 99.0
    if spo2 < 95 or hr > 100 or bp_sys < 90 or temp_c > 39.0 or (('chest pain' in text or 'cardiac' in text) and age > 50):
        return 2, 95.0

    # For non-critical patients, calculate a Weighted Score (40% Vitals, 60% NLP)
    
    # 1. Vitals Score (Out of 100) - Higher is worse
    vitals_score = 0
    if spo2 < 97: vitals_score += 30
    if hr > 90: vitals_score += 20
    if bp_sys > 140 or bp_sys < 110: vitals_score += 20
    if temp_c > 37.5 or temp_c < 36.0: vitals_score += 30

    # 2. NLP Score (Out of 100) - ML Prediction
    if not ml_model or not vectorizer:
        nlp_score = 0
    else:
        statement = text.strip()
        text_features = vectorizer.transform([statement]).toarray()
        num_features = np.array([[age, spo2, hr, bp_sys, temp_c]])
        X = np.hstack((num_features, text_features))
        
        predicted_class = int(ml_model.predict(X)[0])
        # Convert predicted class (1-5) to a 0-100 score where 1 is 100
        nlp_score = (5 - predicted_class) * 25
        
        # Boost NLP score based on confidence
        probs = ml_model.predict_proba(X)[0]
        confidence = float(np.max(probs))
        nlp_score = min(nlp_score * confidence * 1.5, 100)

    # 3. Combined Score mapped to ESI 3, 4, 5
    net_score = (vitals_score * 0.40) + (nlp_score * 0.60)
    
    if net_score > 60:
        return 3, round(net_score, 1)
    elif net_score > 30:
        return 4, round(net_score, 1)
    else:
        return 5, round(net_score, 1)

def compute_priority(esi, wait_time_min, net_score, deterioration_penalty=0):
    # ESI 1 and 2 get massive base points, ESI 3-5 use the net_score + base
    base = (5 - esi) * 25
    wait_bonus = wait_time_min * 1.5 
    return round(base + net_score + wait_bonus + deterioration_penalty, 2)

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
