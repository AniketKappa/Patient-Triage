from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
import datetime

class Patient(Base):
    __tablename__ = "patients"
    patient_id = Column(String, primary_key=True, index=True)
    age = Column(Integer)
    gender = Column(String, nullable=True)
    chronic_conditions = Column(String)  # comma separated
    encounters = relationship("Encounter", back_populates="patient")

class Encounter(Base):
    __tablename__ = "encounters"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, ForeignKey("patients.patient_id"))
    arrival_mode = Column(String)
    symptoms = Column(String) # comma separated
    family_statements = Column(String, nullable=True)
    history_available = Column(Boolean, default=True)
    
    # ML Outputs (Maintained as materialized current state for fast queries)
    esi = Column(Integer, nullable=True)
    risk_score = Column(Float, nullable=True)
    ml_confidence = Column(Float, nullable=True)
    explanation = Column(String, nullable=True)
    
    # Status
    status = Column(String, default="queue") # queue, ambulance, treated, discharged, admitted
    arrival_time = Column(DateTime, default=datetime.datetime.utcnow)
    
    patient = relationship("Patient", back_populates="encounters")
    vitals = relationship("Vitals", back_populates="encounter")
    events = relationship("EventLog", back_populates="encounter", cascade="all, delete")

class Vitals(Base):
    __tablename__ = "vitals"
    id = Column(Integer, primary_key=True, index=True)
    encounter_id = Column(Integer, ForeignKey("encounters.id"))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    spo2 = Column(Float, nullable=True)
    hr = Column(Float, nullable=True)
    bp_sys = Column(Float, nullable=True)
    bp_dia = Column(Float, nullable=True)
    rr = Column(Float, nullable=True)
    temp_c = Column(Float, nullable=True)
    
    encounter = relationship("Encounter", back_populates="vitals")

class EventLog(Base):
    __tablename__ = "event_log"
    id = Column(Integer, primary_key=True, index=True)
    encounter_id = Column(Integer, ForeignKey("encounters.id"))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    event_type = Column(String)  # 'INITIAL_TRIAGE', 'RE_TRIAGE', 'HUMAN_OVERRIDE', 'STATUS_CHANGE'
    actor = Column(String)       # 'AI', 'System', 'Clinician'
    actor_id = Column(String, nullable=True) 
    prev_esi = Column(Integer, nullable=True)
    new_esi = Column(Integer, nullable=True)
    reason = Column(String, nullable=True)
    payload = Column(String, nullable=True) # Extra JSON context if needed
    
    encounter = relationship("Encounter", back_populates="events")

