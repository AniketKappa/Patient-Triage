from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import os
import random
import json
from sqlalchemy.orm import Session

from database import SessionLocal, engine, Base
import models
from triage_model import assign_esi_ml, compute_priority, get_diagnosis

app = FastAPI(title="PatientTriage.ai API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def reset_demo_times():
    db = SessionLocal()
    try:
        encounters = db.query(models.Encounter).all()
        now = datetime.utcnow()
        for enc in encounters:
            offset = random.randint(5, 60)
            enc.arrival_time = now - timedelta(minutes=offset)
        db.commit()
    finally:
        db.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def log_event(db: Session, encounter_id: int, event_type: str, actor: str, prev_esi: Optional[int] = None, new_esi: Optional[int] = None, reason: str = "", actor_id: str = ""):
    event = models.EventLog(
        encounter_id=encounter_id,
        event_type=event_type,
        actor=actor,
        actor_id=actor_id,
        prev_esi=prev_esi,
        new_esi=new_esi,
        reason=reason
    )
    db.add(event)

class IntakeRequest(BaseModel):
    patient_id: str
    age: int
    gender: str = "Unspecified"
    symptoms: str
    family_statements: str
    spo2: Optional[float] = None
    hr: Optional[float] = None
    bp_sys: Optional[float] = None
    temp_c: Optional[float] = None
    rr: Optional[float] = None
    critical_look: bool = False
    mode: str = "walkin"

@app.post("/api/intake")
def new_intake(req: IntakeRequest, db: Session = Depends(get_db)):
    patient = db.query(models.Patient).filter(models.Patient.patient_id == req.patient_id).first()
    if not patient:
        patient = models.Patient(patient_id=req.patient_id, age=req.age, gender=req.gender, chronic_conditions="")
        db.add(patient)
        db.commit()

    esi, conf, expl = assign_esi_ml(req.age, req.spo2, req.hr, req.bp_sys, req.temp_c, req.rr, req.family_statements, req.symptoms, req.critical_look)

    status = "queue" if req.mode in ["walkin", "intake"] else "ambulance"
    enc = models.Encounter(
        patient_id=req.patient_id, arrival_mode=req.mode,
        symptoms=req.symptoms, family_statements=req.family_statements,
        esi=esi, ml_confidence=conf, status=status, explanation=expl
    )
    db.add(enc)
    db.commit()
    
    # Event Log: Initial Triage
    log_event(db, enc.id, "INITIAL_TRIAGE", "AI", prev_esi=None, new_esi=esi, reason=expl)
    
    if req.spo2 or req.hr or req.bp_sys or req.temp_c or req.rr:
        v = models.Vitals(encounter_id=enc.id, spo2=req.spo2, hr=req.hr, bp_sys=req.bp_sys, temp_c=req.temp_c, rr=req.rr)
        db.add(v)
        
    db.commit()
    return {"status": "success", "encounter_id": enc.id}

class StatusUpdate(BaseModel):
    status: str
    clinician_id: str = "system"

@app.post("/api/encounters/{patient_id}/status")
def update_status(patient_id: str, req: StatusUpdate, db: Session = Depends(get_db)):
    enc = db.query(models.Encounter).filter(models.Encounter.patient_id == patient_id).order_by(models.Encounter.id.desc()).first()
    if enc:
        old_status = enc.status
        enc.status = req.status
        log_event(db, enc.id, "STATUS_CHANGE", "Clinician", actor_id=req.clinician_id, reason=f"Status changed from {old_status} to {req.status}")
        db.commit()
        return {"status": "success"}
    return {"status": "not found"}

class OverrideRequest(BaseModel):
    new_esi: int
    clinician_id: str
    reason: str

@app.post("/api/patients/{patient_id}/override")
def override_patient(patient_id: str, req: OverrideRequest, db: Session = Depends(get_db)):
    enc = db.query(models.Encounter).filter(models.Encounter.patient_id == patient_id, models.Encounter.status.in_(["queue", "ambulance"])).order_by(models.Encounter.id.desc()).first()
    if enc:
        old_esi = enc.esi
        enc.esi = req.new_esi
        enc.explanation = f"Overridden by {req.clinician_id}: {req.reason}"
        
        # Event Log: Human Override (Append-only)
        log_event(db, enc.id, "HUMAN_OVERRIDE", "Clinician", actor_id=req.clinician_id, prev_esi=old_esi, new_esi=req.new_esi, reason=req.reason)
        
        db.commit()
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Patient not found in active queue")

class VitalsUpdate(BaseModel):
    spo2: Optional[float] = None
    hr: Optional[float] = None
    bp_sys: Optional[float] = None
    temp_c: Optional[float] = None
    rr: Optional[float] = None
    critical_look: bool = False
    clinician_id: str = "nurse_station_1"

@app.post("/api/encounters/{patient_id}/vitals")
def update_vitals(patient_id: str, req: VitalsUpdate, db: Session = Depends(get_db)):
    enc = db.query(models.Encounter).filter(models.Encounter.patient_id == patient_id, models.Encounter.status.in_(["queue", "ambulance"])).order_by(models.Encounter.id.desc()).first()
    if enc:
        v = models.Vitals(encounter_id=enc.id, spo2=req.spo2, hr=req.hr, bp_sys=req.bp_sys, temp_c=req.temp_c, rr=req.rr)
        db.add(v)
        
        old_esi = enc.esi
        esi, conf, expl = assign_esi_ml(enc.patient.age, req.spo2, req.hr, req.bp_sys, req.temp_c, req.rr, enc.family_statements, enc.symptoms, req.critical_look)
        
        enc.esi = esi
        enc.ml_confidence = conf
        enc.explanation = expl
        
        # Event Log: Re-Triage
        log_event(db, enc.id, "RE_TRIAGE", "AI", prev_esi=old_esi, new_esi=esi, reason=expl)
        
        db.commit()
        return {"status": "success"}
    return {"status": "not found"}

def get_ctas_reassessment_interval(esi: int) -> int:
    intervals = {1: 0, 2: 15, 3: 30, 4: 60, 5: 120}
    return intervals.get(esi, 60)

@app.get("/api/patients")
def get_patients(db: Session = Depends(get_db)):
    encounters = db.query(models.Encounter).filter(models.Encounter.status.in_(["queue", "ambulance"])).all()
    
    out = []
    reminders = []
    for enc in encounters:
        patient = enc.patient
        wait_time_min = (datetime.utcnow() - enc.arrival_time).total_seconds() / 60.0
        
        # CTAS Reassessment Clocks (Step 3 implementation)
        target_interval = get_ctas_reassessment_interval(enc.esi)
        time_to_breach = target_interval - wait_time_min
        
        if time_to_breach < -target_interval:
            clock_state = "breach"
            reminders.append({"patient_id": patient.patient_id, "message": f"SAFETY BREACH! ESI {enc.esi} unassessed for >{int(wait_time_min)}m (Limit {target_interval}m)."})
        elif time_to_breach < 0:
            clock_state = "overdue"
            reminders.append({"patient_id": patient.patient_id, "message": f"ESI {enc.esi} is overdue for reassessment."})
        elif time_to_breach < 5:
            clock_state = "due"
        else:
            clock_state = "ok"

        # Vitals Deterioration (using baseline)
        deterioration_penalty = 0
        vitals_list = enc.vitals
        is_deteriorating = False
        if len(vitals_list) >= 2:
            old = vitals_list[-2]
            new = vitals_list[-1]
            # Replacing arbitrary noise with simple NEWS2-like proxy triggers
            if new.hr and old.hr and (new.hr - old.hr > 20):
                is_deteriorating = True
                deterioration_penalty += 15
            if new.spo2 and old.spo2 and (old.spo2 - new.spo2 > 2):
                is_deteriorating = True
                deterioration_penalty += 15
        
        diagnosis = get_diagnosis(enc.symptoms, enc.family_statements)

        out.append({
            "patient_id": patient.patient_id,
            "age": patient.age,
            "gender": patient.gender or "Unspecified",
            "age_band": "adult" if patient.age > 12 else "pediatric",
            "symptoms": enc.symptoms.split(",") if enc.symptoms else [],
            "diagnosis": diagnosis,
            "esi": enc.esi,
            "explanation": enc.explanation,
            "confidence": round(enc.ml_confidence, 1) if enc.ml_confidence else 0,
            
            # Queue ordering (Strictly by ESI first in lambda)
            # time_to_breach ensures overdue patients bubble up WITHIN their ESI bucket
            "priority": compute_priority(enc.esi, -time_to_breach, enc.ml_confidence if enc.ml_confidence else 0, deterioration_penalty),
            
            "wait_time_min": int(wait_time_min),
            "clock_state": clock_state,
            "target_interval": target_interval,
            "arrival_time": enc.arrival_time.isoformat() + "Z",
            "status": enc.status,
            "deteriorating": is_deteriorating
        })
    
    # Sort strictly by ESI first (1 is highest severity), then by priority within that ESI group
    out = sorted(out, key=lambda x: (x['esi'], -x['priority']))
    
    return {"queue": out, "reminders": reminders}

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_path, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# --- Step 7: Fairness and Calibration Monitoring ---
@app.get("/api/metrics/fairness")
def get_fairness_metrics(db: Session = Depends(get_db)):
    from sqlalchemy import func
    
    # Wait Time by Demographic (Gender)
    wait_times = db.query(
        models.Patient.gender, 
        func.avg(func.cast((func.julianday(func.current_timestamp()) - func.julianday(models.Encounter.arrival_time)) * 24 * 60, models.Integer))
    ).join(models.Encounter).filter(models.Encounter.status.in_(["queue", "ambulance"])).group_by(models.Patient.gender).all()
    
    wait_time_dict = {row[0]: round(row[1], 1) if row[1] else 0 for row in wait_times}
    
    # Override Rates by Demographic
    # Total encounters per gender
    total_enc = db.query(models.Patient.gender, func.count(models.Encounter.id)).join(models.Encounter).group_by(models.Patient.gender).all()
    total_dict = {row[0]: row[1] for row in total_enc}
    
    # Overrides per gender
    overrides = db.query(models.Patient.gender, func.count(models.EventLog.id)).join(
        models.Encounter, models.EventLog.encounter_id == models.Encounter.id
    ).join(models.Patient).filter(models.EventLog.event_type == "HUMAN_OVERRIDE").group_by(models.Patient.gender).all()
    
    override_dict = {row[0]: row[1] for row in overrides}
    
    override_rates = {}
    for gender, count in total_dict.items():
        o_count = override_dict.get(gender, 0)
        override_rates[gender] = round((o_count / count) * 100, 1) if count > 0 else 0
        
    return {
        "status": "success",
        "metrics": {
            "avg_wait_time_mins": wait_time_dict,
            "override_rate_pct": override_rates
        },
        "message": "Fairness and calibration monitoring infrastructure active."
    }
