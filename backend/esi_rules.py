from dataclasses import dataclass
from typing import Optional, List, Literal

@dataclass(frozen=True)
class TriageContext:
    age_yr: float
    age_band: str           # '<1m' | '1-12m' | '1-3y' | '3-5y' | '5-12y' | '12-18y' | '>18y'
    geriatric: bool         # >=65
    pregnancy_state: str    # 'not_pregnant' | 'pregnant' | 'postpartum' | 'unknown'
    immunocompromised: bool
    baseline_spo2: Optional[float]
    on_home_oxygen: bool
    rate_blunting_meds: bool
    immune_blunting_meds: bool
    anticoagulated: bool
    baseline_mental_status: Optional[str]
    immunisations_current: Optional[bool]
    history_depth: str      # 'rich' | 'partial' | 'none'

@dataclass
class TriageResult:
    level: int
    gate: str
    evidence: List[str]
    pending_prompt: Optional[str] = None
    confidence: str = "High"

def get_age_band(age_yr: float) -> str:
    if age_yr < 1/12: return '<1m'
    if age_yr < 1: return '1-12m'
    if age_yr < 3: return '1-3y'
    if age_yr < 5: return '3-5y'
    if age_yr < 12: return '5-12y'
    if age_yr < 18: return '12-18y'
    return '>18y'

def gate_a_lifesaving(ctx: TriageContext, obs: dict, text: str) -> bool:
    # Deterministic ESI 1 check
    # obs: spo2, hr, rr, sbp, temp_c, avpu
    
    # 1. Airway / Breathing
    if obs.get('spo2') is not None and obs['spo2'] < 90:
        if ctx.baseline_spo2 is None or obs['spo2'] < ctx.baseline_spo2 - 2:
            return True
            
    # 2. Circulation (Severe brady/tachycardia or hypotension)
    hr = obs.get('hr')
    if hr is not None:
        if hr < 40: return True  # Severe bradycardia
        if ctx.age_band == '>18y' and hr > 150: return True # Severe tachycardia adult
    
    sbp = obs.get('sbp')
    if sbp is not None and sbp < 80 and ctx.age_band == '>18y': return True
        
    # 3. Disability
    if obs.get('avpu') in ['P', 'U']: return True
    
    # Text triggers
    text_lower = text.lower()
    if 'unresponsive' in text_lower or 'cardiac arrest' in text_lower or 'overdose' in text_lower or 'anaphylaxis' in text_lower:
        return True
        
    return False

def gate_b_high_risk(ctx: TriageContext, obs: dict, text: str) -> List[str]:
    # Returns a list of evidence strings if ESI 2 rules hit
    evidence = []
    text_lower = text.lower()
    
    # B.CARDIAC.ACS
    acs_keywords = ['chest pain', 'chest pressure', 'jaw pain', 'arm pain']
    if any(k in text_lower for k in acs_keywords):
        evidence.append('High-risk cardiac presentation (ACS protocols)')
        
    # B.OB.HTN
    if ctx.pregnancy_state in ['pregnant', 'postpartum']:
        sbp = obs.get('sbp')
        if sbp is not None and (sbp < 90 or sbp > 150):
            evidence.append('Obstetric patient with abnormal BP (<90 or >150)')
            
    # B.PEDS.NEONATE_FEVER
    if ctx.age_band == '<1m' and obs.get('temp_c') is not None and obs['temp_c'] > 38.0:
        evidence.append('Neonate (<28 days) with fever > 38.0C')

    # B.NEURO
    if 'stroke' in text_lower or 'facial droop' in text_lower or 'weakness' in text_lower or 'thunderclap' in text_lower or 'suicidal' in text_lower:
        evidence.append('High-risk neurological or behavioral presentation')

    # B.PAIN
    if 'severe pain' in text_lower and ('flank' in text_lower or 'testicular' in text_lower or 'sickle' in text_lower):
        evidence.append('Severe systemic pain presentation')
        
    return evidence

def gate_d_vitals(ctx: TriageContext, obs: dict) -> Optional[str]:
    # Returns prompt if vitals out of range
    hr = obs.get('hr')
    rr = obs.get('rr')
    spo2 = obs.get('spo2')
    
    band = ctx.age_band
    hr_limit = { '<1m': 190, '1-12m': 180, '1-3y': 140, '3-5y': 120, '5-12y': 120, '12-18y': 100, '>18y': 100 }
    rr_limit = { '<1m': 60, '1-12m': 55, '1-3y': 40, '3-5y': 35, '5-12y': 30, '12-18y': 20, '>18y': 20 }
    
    prompts = []
    if hr and hr > hr_limit.get(band, 100):
        prompts.append(f"HR {hr} exceeds {band} threshold of {hr_limit.get(band, 100)}")
    if rr and rr > rr_limit.get(band, 20):
        prompts.append(f"RR {rr} exceeds {band} threshold of {rr_limit.get(band, 20)}")
    if spo2 and spo2 < 92:
        prompts.append(f"SpO2 {spo2}% < 92%")
        
    if prompts:
        return " Danger Vitals: " + " | ".join(prompts)
    return None

def assign_esi_v5(age: float, obs: dict, text: str) -> TriageResult:
    ctx = TriageContext(
        age_yr=age,
        age_band=get_age_band(age),
        geriatric=age >= 65,
        pregnancy_state='not_pregnant', # Default for now
        immunocompromised=False,
        baseline_spo2=None,
        on_home_oxygen=False,
        rate_blunting_meds=False,
        immune_blunting_meds=False,
        anticoagulated=False,
        baseline_mental_status=None,
        immunisations_current=True,
        history_depth='partial'
    )
    
    if gate_a_lifesaving(ctx, obs, text):
        return TriageResult(level=1, gate="A", evidence=["Immediate lifesaving intervention required"])
        
    b_evidence = gate_b_high_risk(ctx, obs, text)
    if b_evidence:
        return TriageResult(level=2, gate="B", evidence=b_evidence)
        
    # Placeholder for Gate C (Resource prediction). We'll use a simple heuristic for now.
    # If text is very long, maybe they need more resources? Just mock it.
    text_len = len(text.split())
    if text_len > 15:
        level_c = 3
    elif text_len > 5:
        level_c = 4
    else:
        level_c = 5
        
    d_prompt = gate_d_vitals(ctx, obs)
    return TriageResult(level=level_c, gate="C", evidence=["Predicted based on resource heuristic"], pending_prompt=d_prompt)

