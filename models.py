from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
import datetime

class Patient(Base):
    __tablename__ = "patients"
    patient_id = Column(String, primary_key=True, index=True)
    age = Column(Integer)
    chronic_conditions = Column(String)  # comma separated
    encounters = relationship("Encounter", back_populates="patient")

class Encounter(Base):
    __tablename__ = "encounters"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, ForeignKey("patients.patient_id"))
    arrival_mode = Column(String)
    symptoms = Column(String) # comma separated
    family_statements = Column(String, nullable=True)
    unconscious = Column(Boolean, default=False)
    severe_bleeding = Column(Boolean, default=False)
    history_available = Column(Boolean, default=True)
    
    # ML Outputs
    esi = Column(Integer, nullable=True)
    risk_score = Column(Float, nullable=True)
    ml_confidence = Column(Float, nullable=True)
    
    # Status
    status = Column(String, default="queue") # queue, ambulance, treated
    arrival_time = Column(DateTime, default=datetime.datetime.utcnow)
    
    patient = relationship("Patient", back_populates="encounters")
    vitals = relationship("Vitals", back_populates="encounter")

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
