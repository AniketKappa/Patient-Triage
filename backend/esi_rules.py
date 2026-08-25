import re
import os
import joblib
from dataclasses import dataclass, field
from typing import Optional, List

try:
    vectorizer = joblib.load(os.path.join(os.path.dirname(__file__), 'resource_tfidf.pkl'))
    model = joblib.load(os.path.join(os.path.dirname(__file__), 'resource_rf.pkl'))
    RESOURCE_CLASSES = joblib.load(os.path.join(os.path.dirname(__file__), 'resource_classes.pkl'))
    outcome_model = joblib.load(os.path.join(os.path.dirname(__file__), 'outcome_rf.pkl'))
except:
    vectorizer, model, outcome_model, RESOURCE_CLASSES = None, None, None, []

@dataclass(frozen=True)
class TriageContext:
    age_yr: float
    age_band: str           
    geriatric: bool         
    pregnancy_state: str    
    immunocompromised: bool
    baseline_spo2: Optional[float]
    on_home_oxygen: bool
    rate_blunting_meds: bool
    immune_blunting_meds: bool
    anticoagulated: bool
    baseline_mental_status: Optional[str]
    immunisations_current: Optional[bool]
    history_depth: str      
    critical_look_override: bool = False

@dataclass
class TriageResult:
    level: int
    gate: str
    evidence: List[str]
    pending_prompt: Optional[str] = None
    confidence_label: str = "High"
    admissible_set: List[int] = field(default_factory=list)
    missing_inputs: List[str] = field(default_factory=list)
    is_insufficient_data: bool = False
    advisory_alerts: List[str] = field(default_factory=list)

NEGATION_TERMS = r"\b(no|not|denies|without|negative for|ruled out|resolved|history of)\b"

def detect_clinical_flags(text: str, keywords: List[str]) -> bool:
    phrases = re.split(r'[.,;!\n]', text.lower())
    for phrase in phrases:
        for kw in keywords:
            kw_match = re.search(r'\b' + re.escape(kw) + r'\b', phrase)
            if kw_match:
                neg_match = re.search(NEGATION_TERMS, phrase)
                if neg_match and neg_match.start() < kw_match.start():
                    continue
                return True
    return False

def get_age_band(age_yr: float) -> str:
    if age_yr < 1/12: return '<1m'
    if age_yr < 1: return '1-12m'
    if age_yr < 3: return '1-3y'
    if age_yr < 5: return '3-5y'
    if age_yr < 12: return '5-12y'
    if age_yr < 18: return '12-18y'
    return '>18y'

def gate_a_lifesaving(ctx: TriageContext, obs: dict, text: str) -> List[str]:
    evidence = []
    if ctx.critical_look_override:
        evidence.append("CRITICAL LOOK triggered by clinician")
        return evidence
    if obs.get('spo2') is not None and obs['spo2'] < 90:
        if ctx.baseline_spo2 is None or obs['spo2'] < ctx.baseline_spo2 - 2:
            evidence.append(f"SpO2 {obs['spo2']}% below safe baseline")
            
    hr = obs.get('hr')
    if hr is not None:
        if ctx.age_band == '<1m' and (hr < 80 or hr > 220): evidence.append(f"Neonate HR {hr} out of safe bounds")
        elif ctx.age_band in ['1-12m', '1-3y', '3-5y', '5-12y', '12-18y'] and hr < 60: evidence.append(f"Pediatric bradycardia ({hr} bpm)")
        elif ctx.age_band == '1-12m' and hr > 220: evidence.append(f"Infant extreme tachycardia ({hr} bpm)")
        elif ctx.age_band in ['1-3y', '3-5y', '5-12y'] and hr > 180: evidence.append(f"Child extreme tachycardia ({hr} bpm)")
        elif ctx.age_band == '>18y' and (hr < 40 or hr > 150): evidence.append(f"Adult severe HR ({hr} bpm)")

    sbp = obs.get('sbp')
    if sbp is not None and sbp < 80 and ctx.age_band == '>18y': 
        evidence.append(f"Profound hypotension (SBP {sbp})")
    if obs.get('avpu') in ['P', 'U']: 
        evidence.append(f"AVPU: {obs['avpu']}")

    gate_a_keywords = [
        'apneic', 'apnoeic', 'occluded airway', 'intubation', 'nippv',
        'pulseless', 'hypoperfusion', 'active seizure', 'seizing', 'hypoglycemia', 'hypoglycaemia',
        'adrenaline', 'epinephrine', 'naloxone', 'narcan', 'dextrose', 'atropine', 
        'adenosine', 'dopamine', 'penetrating trauma', 'flaccid', 'anaphylaxis', 
        'cardiac arrest', 'unresponsive', 'coma', 'comatose'
    ]
    if detect_clinical_flags(text, gate_a_keywords):
        evidence.append("Requires immediate life-saving intervention (Text Indicator)")
    return evidence
    if obs.get('spo2') is not None and obs['spo2'] < 90:
        if ctx.baseline_spo2 is None or obs['spo2'] < ctx.baseline_spo2 - 2:
            evidence.append(f"SpO2 {obs['spo2']}% below safe baseline")
    hr = obs.get('hr')
    if hr is not None:
        if hr < 40: evidence.append(f"Severe bradycardia ({hr} bpm)")
        if ctx.age_band == '>18y' and hr > 150: evidence.append(f"Severe tachycardia ({hr} bpm)")
    sbp = obs.get('sbp')
    if sbp is not None and sbp < 80 and ctx.age_band == '>18y': 
        evidence.append(f"Profound hypotension (SBP {sbp})")
    if obs.get('avpu') in ['P', 'U']: 
        evidence.append(f"AVPU: {obs['avpu']}")

    gate_a_keywords = [
        'apneic', 'apnoeic', 'occluded airway', 'intubation', 'nippv',
        'pulseless', 'hypoperfusion', 'active seizure', 'seizing', 'hypoglycemia', 'hypoglycaemia',
        'adrenaline', 'epinephrine', 'naloxone', 'narcan', 'dextrose', 'atropine', 
        'adenosine', 'dopamine', 'penetrating trauma', 'flaccid', 'anaphylaxis', 
        'cardiac arrest', 'unresponsive', 'coma', 'comatose'
    ]
    if detect_clinical_flags(text, gate_a_keywords):
        evidence.append("Requires immediate life-saving intervention (Text Indicator)")
    return evidence

def gate_b_high_risk(ctx: TriageContext, obs: dict, text: str) -> List[str]:
    evidence = []
    if detect_clinical_flags(text, ['chest pain', 'chest pressure', 'jaw pain', 'arm pain', 'epigastric pain', 'unexplained dyspnea']):
        evidence.append('B.CARDIAC: High-risk cardiac presentation')
    if detect_clinical_flags(text, ['stroke', 'facial droop', 'weakness', 'slurred speech', 'hemiparesis', 'thunderclap', 'altered mental', 'confused', 'lethargic']):
        evidence.append('B.NEURO: High-risk neurological or AMS')
    if detect_clinical_flags(text, ['suicidal', 'homicidal', 'psychosis', 'combative', 'overdose']):
        evidence.append('B.BEHAVIORAL: High-risk psychiatric/toxicologic')
    if detect_clinical_flags(text, ['stridor', 'tripoding', 'retractions', 'grunting', 'unable to manage secretions']):
        evidence.append('B.RESP: High respiratory effort')
    if detect_clinical_flags(text, ['ectopic', 'heavy vaginal bleeding', 'postpartum hemorrhage', 'testicular torsion', 'scrotal pain']):
        evidence.append('B.OBGYN_GU: High-risk genitourinary')
    if detect_clinical_flags(text, ['severe pain', 'flank pain', 'renal colic', 'sickle cell']):
        evidence.append('B.PAIN: Severe systemic pain')
    if detect_clinical_flags(text, ['ejected', 'extrication', 'amputation', 'sexual assault', 'compartment syndrome', 'needlestick', 'button battery', 'fall > 20']):
        evidence.append('B.TRAUMA: High-risk mechanism/environmental')
    if detect_clinical_flags(text, ['sepsis', 'septic']):
        evidence.append('B.INFECTIOUS: Sepsis suspicious')
    
    if ctx.pregnancy_state in ['pregnant', 'postpartum']:
        sbp = obs.get('sbp')
        if sbp is not None and (sbp < 90 or sbp > 150):
            evidence.append('B.OB.HTN: Abnormal BP in pregnancy')
    if ctx.age_band == '<1m' and obs.get('temp_c') is not None and obs['temp_c'] > 38.0:
        evidence.append('B.PEDS: Neonate with fever > 38.0C')
    if ctx.immunocompromised and obs.get('temp_c') is not None and obs['temp_c'] > 38.0:
        evidence.append('B.IMMUNE: Immunocompromised with fever')
    return evidence

def gate_d_vitals(ctx: TriageContext, obs: dict) -> Optional[str]:
    hr = obs.get('hr')
    rr = obs.get('rr')
    spo2 = obs.get('spo2')
    band = ctx.age_band
    hr_limit = { '<1m': 190, '1-12m': 180, '1-3y': 140, '3-5y': 120, '5-12y': 120, '12-18y': 100, '>18y': 100 }
    rr_limit = { '<1m': 60, '1-12m': 55, '1-3y': 40, '3-5y': 35, '5-12y': 30, '12-18y': 20, '>18y': 20 }
    
    prompts = []
    if hr and hr > hr_limit.get(band, 100): prompts.append(f"HR {hr} > {hr_limit.get(band, 100)}")
    if rr and rr > rr_limit.get(band, 20): prompts.append(f"RR {rr} > {rr_limit.get(band, 20)}")
    if spo2 and spo2 < 92: prompts.append(f"SpO2 {spo2}% < 92")
    if prompts:
        return "Danger Vitals: " + " | ".join(prompts) + " -> Consider ESI 2"
    return None

def assign_esi_v5(age: float, obs: dict, text: str, critical_look: bool = False) -> TriageResult:
    ctx = TriageContext(
        age_yr=age, age_band=get_age_band(age), geriatric=age >= 65,
        pregnancy_state='not_pregnant', immunocompromised=False, baseline_spo2=None,
        on_home_oxygen=False, rate_blunting_meds=False, immune_blunting_meds=False,
        anticoagulated=False, baseline_mental_status=None, immunisations_current=True,
        history_depth='partial', critical_look_override=critical_look
    )
    
    missing_inputs = []
    if obs.get('hr') is None: missing_inputs.append('heart rate')
    if obs.get('rr') is None: missing_inputs.append('respiratory rate')
    if obs.get('spo2') is None: missing_inputs.append('SpO2')
    
    if not text.strip() and len(missing_inputs) == 3 and not critical_look:
        return TriageResult(level=0, gate="NONE", evidence=[], is_insufficient_data=True)

    a_evidence = gate_a_lifesaving(ctx, obs, text)
    if a_evidence:
        return TriageResult(level=1, gate="A", evidence=a_evidence, admissible_set=[1])
        
    b_evidence = gate_b_high_risk(ctx, obs, text)
    if b_evidence:
        return TriageResult(level=2, gate="B", evidence=b_evidence, admissible_set=[2])
        
    # Gate C (Conformal Set logic)
    if vectorizer and model:
        features = vectorizer.transform([text]).toarray()
        proba_list = model.predict_proba(features) 
        
        min_count = 0
        max_count = 0
        predicted_resources = []
        
        for i, p_array in enumerate(proba_list):
            p = p_array[0][1]
            weight = 2 if RESOURCE_CLASSES[i] == "Complex Procedure" else 1
            if p > 0.65:
                min_count += weight
                max_count += weight
                predicted_resources.append(RESOURCE_CLASSES[i])
            elif p > 0.25:
                max_count += weight
                
        def count_to_esi(c):
            if c >= 2: return 3
            if c == 1: return 4
            return 5
            
        esi_most_severe = count_to_esi(max_count)
        esi_least_severe = count_to_esi(min_count)
        
        admissible_set = list(range(esi_most_severe, esi_least_severe + 1))
        level_c = esi_most_severe
        
        if len(admissible_set) == 1:
            conf_label = "High"
        elif len(admissible_set) == 2:
            conf_label = "Moderate"
        else:
            conf_label = "Low"
            
        evidence_text = f"Predicted {min_count} to {max_count} resources"
        if predicted_resources:
            evidence_text += f" ({', '.join(predicted_resources)})"
    else:
        text_len = len(text.split())
        level_c = 3 if text_len > 15 else (4 if text_len > 5 else 5)
        admissible_set = [level_c]
        conf_label = "Low"
        evidence_text = "Predicted based on heuristic (model fallback)"
        
    d_prompt = gate_d_vitals(ctx, obs)
    
    # Step 6: Outcome-Risk Advisory Layer
    advisory_alerts = []
    if outcome_model and vectorizer and level_c > 2:
        out_preds = outcome_model.predict_proba(features)
        # out_preds is list of 2 arrays (Admit, ICU)
        p_admit = out_preds[0][0][1]
        p_icu = out_preds[1][0][1]
        
        if p_icu > 0.10:
            advisory_alerts.append(f"AI ADVISORY: {p_icu*100:.0f}% risk of ICU. Consider ESI 2 override.")
        elif p_admit > 0.60:
            advisory_alerts.append(f"AI ADVISORY: {p_admit*100:.0f}% risk of admission. Monitor closely.")

    return TriageResult(
        level=level_c, 
        gate="C", 
        evidence=[evidence_text], 
        pending_prompt=d_prompt,
        confidence_label=conf_label,
        admissible_set=admissible_set,
        missing_inputs=missing_inputs,
        advisory_alerts=advisory_alerts
    )
