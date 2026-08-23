from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os

from triage_model import (
    assign_esi, compute_priority, apply_override,
    should_recommend_diversion, diversion_candidates, patient_to_dict
)
from demo_data import PATIENTS

app = FastAPI(title="PatientTriage.ai API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for p in PATIENTS:
    assign_esi(p)

class OverrideRequest(BaseModel):
    new_esi: int
    clinician_id: str
    reason: str

@app.get("/api/patients")
def get_patients():
    queue = sorted(PATIENTS, key=lambda p: (-compute_priority(p)))
    return [patient_to_dict(p) for p in queue]

@app.post("/api/patients/{patient_id}/override")
def override_patient(patient_id: str, req: OverrideRequest):
    for p in PATIENTS:
        if p.patient_id == patient_id:
            apply_override(p, req.new_esi, req.clinician_id, req.reason, datetime.now())
            return {"status": "success", "patient": patient_to_dict(p)}
    raise HTTPException(status_code=404, detail="Patient not found")

@app.get("/api/surge-status")
def get_surge_status():
    baseline_capacity = 7
    surge_triggered = should_recommend_diversion(PATIENTS, baseline_capacity)
    divert = diversion_candidates(PATIENTS) if surge_triggered else []
    return {
        "baseline_capacity": baseline_capacity,
        "current_queue_depth": len(PATIENTS),
        "surge_ratio": round(len(PATIENTS) / baseline_capacity, 2),
        "diversion_recommended": surge_triggered,
        "diversion_candidates": [p.patient_id for p in divert],
    }

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_path, "index.html"))
