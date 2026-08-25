from database import engine, Base, SessionLocal
import models
from demo_data import PATIENTS
from triage_model import assign_esi_ml

print("Creating database tables...")
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

db = SessionLocal()

print("Seeding demo data into SQLite...")
for i, p in enumerate(PATIENTS):
    import random
    # Create patient
    db_patient = models.Patient(
        patient_id=p.patient_id,
        age=p.age,
        gender=random.choice(["Male", "Female"]),
        chronic_conditions=",".join(p.chronic_conditions)
    )
    db.add(db_patient)
    db.commit()
    
    # ML predict
    v = p.latest_vitals
    spo2 = v.spo2 if v else 98
    hr = v.hr if v else 80
    bp_sys = v.bp_sys if v else 120
    temp_c = v.temp_c if v else 37
    statements = "Patient complaining of " + ", ".join(p.symptoms)
    
    esi, confidence, expl = assign_esi_ml(p.age, spo2, hr, bp_sys, temp_c, v.rr if v else 20, statements, ",".join(p.symptoms))
    
    # Create encounter
    db_enc = models.Encounter(
        patient_id=p.patient_id,
        arrival_mode=p.arrival_mode,
        symptoms=",".join(p.symptoms),
        family_statements=statements,
        esi=esi,
        ml_confidence=confidence,
        explanation=expl,
        status="queue"
    )
    db.add(db_enc)
    db.commit()
    db_event = models.EventLog(encounter_id=db_enc.id, event_type="INITIAL_TRIAGE", actor="AI", new_esi=esi, reason=expl)
    db.add(db_event)
    db.commit()
    
    if v:
        db_vit = models.Vitals(
            encounter_id=db_enc.id,
            spo2=v.spo2, hr=v.hr, bp_sys=v.bp_sys, temp_c=v.temp_c
        )
        db.add(db_vit)
        db.commit()

print("Seeding complete.")
