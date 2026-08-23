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
from triage_model import assign_esi_ml, compute_priority

app = FastAPI(title="PatientTriage.ai API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def reset_demo_times():
    db = SessionLocal()
    try:
        encounters = db.query(models.Encounter).all()
        now = datetime.utcnow()
        for enc in encounters:
            # Stagger their arrival times randomly between 5 and 60 minutes ago
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
    symptoms: str
    family_statements: str
    spo2: Optional[float] = None
    hr: Optional[float] = None
    bp_sys: Optional[float] = None
    temp_c: Optional[float] = None
    mode: str = "walkin"

@app.post("/api/intake")
def new_intake(req: IntakeRequest, db: Session = Depends(get_db)):
    # Create or update patient
    patient = db.query(models.Patient).filter(models.Patient.patient_id == req.patient_id).first()
    if not patient:
        patient = models.Patient(patient_id=req.patient_id, age=req.age, chronic_conditions="")
        db.add(patient)
        db.commit()

    # ML predict
    esi, conf = assign_esi_ml(req.age, req.spo2, req.hr, req.bp_sys, req.temp_c, req.family_statements)

    # Create encounter
    status = "queue" if req.mode in ["walkin", "intake"] else "ambulance"
    enc = models.Encounter(
        patient_id=req.patient_id, arrival_mode=req.mode,
        symptoms=req.symptoms, family_statements=req.family_statements,
        esi=esi, ml_confidence=conf, status=status
    )
    db.add(enc)
    db.commit()
    
    # Add vitals
    if req.spo2 or req.hr or req.bp_sys or req.temp_c:
        v = models.Vitals(encounter_id=enc.id, spo2=req.spo2, hr=req.hr, bp_sys=req.bp_sys, temp_c=req.temp_c)
        db.add(v)
        db.commit()
        
    return {"status": "success", "encounter_id": enc.id}

@app.get("/api/patients")
def get_patients(db: Session = Depends(get_db)):
    encounters = db.query(models.Encounter).filter(models.Encounter.status.in_(["queue", "ambulance"])).all()
    
    out = []
    reminders = []
    for enc in encounters:
        patient = enc.patient
        vitals = enc.vitals[-1] if enc.vitals else None
        
        # Calculate wait time
        wait_time_min = (datetime.utcnow() - enc.arrival_time).total_seconds() / 60.0
        
        # Reminders Logic: ESI 1/2 need frequent checks
        if enc.esi in [1, 2] and wait_time_min > 10:
            reminders.append({"patient_id": patient.patient_id, "message": f"ESI {enc.esi} waiting {int(wait_time_min)}m! Needs re-assessment."})
        elif enc.esi == 3 and wait_time_min > 30:
            reminders.append({"patient_id": patient.patient_id, "message": f"ESI 3 waiting >30m. Re-check vitals."})
        
        out.append({
            "patient_id": patient.patient_id,
            "age": patient.age,
            "age_band": "adult" if patient.age > 12 else "pediatric",
            "symptoms": enc.symptoms.split(",") if enc.symptoms else [],
            "esi": enc.esi,
            "confidence": round(enc.ml_confidence, 1) if enc.ml_confidence else 0,
            "priority": compute_priority(enc.esi, wait_time_min, enc.ml_confidence),
            "wait_time_min": int(wait_time_min),
            "arrival_time": enc.arrival_time.isoformat() + "Z",
            "status": enc.status,
            "discordant": False,
            "inconclusive": False,
            "override_log": [],
            "contributing_factors": [f"ML Model assessed {enc.family_statements}"] if enc.family_statements else []
        })
    
    out = sorted(out, key=lambda x: -x['priority'])
    
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
