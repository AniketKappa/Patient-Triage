from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import os
import random
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
        esi=esi, ml_confidence=conf, status=status
    )
    db.add(enc)
    db.commit()
    
    if req.spo2 or req.hr or req.bp_sys or req.temp_c:
        v = models.Vitals(encounter_id=enc.id, spo2=req.spo2, hr=req.hr, bp_sys=req.bp_sys, temp_c=req.temp_c, rr=req.rr)
        db.add(v)
        db.commit()
        
    return {"status": "success", "encounter_id": enc.id}

class StatusUpdate(BaseModel):
    status: str

@app.post("/api/encounters/{patient_id}/status")
def update_status(patient_id: str, req: StatusUpdate, db: Session = Depends(get_db)):
    enc = db.query(models.Encounter).filter(models.Encounter.patient_id == patient_id).order_by(models.Encounter.id.desc()).first()
    if enc:
        enc.status = req.status
        db.commit()
        return {"status": "success"}
    return {"status": "not found"}

class VitalsUpdate(BaseModel):
    spo2: Optional[float] = None
    hr: Optional[float] = None
    bp_sys: Optional[float] = None
    temp_c: Optional[float] = None
    rr: Optional[float] = None
    critical_look: bool = False

@app.post("/api/encounters/{patient_id}/vitals")
def update_vitals(patient_id: str, req: VitalsUpdate, db: Session = Depends(get_db)):
    enc = db.query(models.Encounter).filter(models.Encounter.patient_id == patient_id, models.Encounter.status.in_(["queue", "ambulance"])).order_by(models.Encounter.id.desc()).first()
    if enc:
        v = models.Vitals(encounter_id=enc.id, spo2=req.spo2, hr=req.hr, bp_sys=req.bp_sys, temp_c=req.temp_c, rr=req.rr)
        db.add(v)
        
        esi, conf, expl = assign_esi_ml(enc.patient.age, req.spo2, req.hr, req.bp_sys, req.temp_c, req.rr, enc.family_statements, enc.symptoms)
        enc.esi = esi
        enc.ml_confidence = conf
        enc.explanation = expl
        db.commit()
        return {"status": "success"}
    return {"status": "not found"}

@app.get("/api/patients")
def get_patients(db: Session = Depends(get_db)):
    encounters = db.query(models.Encounter).filter(models.Encounter.status.in_(["queue", "ambulance"])).all()
    
    out = []
    reminders = []
    for enc in encounters:
        patient = enc.patient
        wait_time_min = (datetime.utcnow() - enc.arrival_time).total_seconds() / 60.0
        
        # Calculate deterioration
        deterioration_penalty = 0
        vitals_list = enc.vitals
        is_deteriorating = False
        if len(vitals_list) >= 2:
            old = vitals_list[-2]
            new = vitals_list[-1]
            if new.hr and old.hr and (new.hr - old.hr > 20):
                is_deteriorating = True
                deterioration_penalty += 15
            if new.spo2 and old.spo2 and (old.spo2 - new.spo2 > 2):
                is_deteriorating = True
                deterioration_penalty += 15
                
        # Reminder Logic
        if is_deteriorating:
            reminders.append({"patient_id": patient.patient_id, "message": f"DETERIORATION DETECTED! SpO2 or HR worsening. Re-evaluate immediately."})
        elif enc.esi in [1, 2] and wait_time_min > 5:
            reminders.append({"patient_id": patient.patient_id, "message": f"ESI {enc.esi} waiting {int(wait_time_min)}m! Needs urgent re-assessment."})
        elif enc.esi == 3 and wait_time_min > 15:
            reminders.append({"patient_id": patient.patient_id, "message": f"ESI 3 waiting >15m. Re-check vitals."})
        elif enc.esi >= 4 and wait_time_min > 45:
            reminders.append({"patient_id": patient.patient_id, "message": f"ESI {enc.esi} waiting >45m. Check if condition changed."})
        
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
            "priority": compute_priority(enc.esi, wait_time_min, enc.ml_confidence if enc.ml_confidence else 0, deterioration_penalty),
            "wait_time_min": int(wait_time_min),
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
