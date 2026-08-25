# 🏥 PatientTriage.ai

**An Enterprise-Grade Clinical Decision Support System (CDSS) for Emergency Departments.**

Developed for the **Accenture Innovation Challenge**, PatientTriage.ai is a full-stack, AI-augmented triage engine designed to combat ED overcrowding, reduce algorithmic undertriage, and optimize hospital resource allocation. 

Rather than relying on a "black-box" LLM, this platform utilizes a hybrid architecture: it anchors life-safety decisions on deterministic clinical standards (ESI v5, PALS, CTAS) and strategically applies Machine Learning (Multi-Output Random Forests, Conformal Prediction) exclusively for resource planning and ambiguity resolution.

---

## ✨ Core Functionalities

### 1. Hybrid Triage Engine (ESI v5)
* **Gate A (Immediate Life-Saving):** Deterministic evaluation using age-banded Pediatric Advanced Life Support (PALS) thresholds.
* **Gate B (High-Risk Conditions):** Evaluates chief complaints against a version-controlled clinical YAML rulebook with NLP negation-handling.
* **Gate C (Resource Prediction ML):** A TF-IDF & Random Forest pipeline that predicts precise ED resource utilization (Labs, ECG, Imaging) to stratify ESI 3, 4, and 5 patients.
* **Gate D (Danger Vitals):** A dynamic safety net that flags abnormal vitals and forces a blocking UI prompt for clinicians to accept an uptriage or provide a structured dismissal reason.

### 2. CDSS Safety & Governance
* **Conformal Prediction Sets:** The ML model quantifies its own uncertainty. If a patient's probability distribution straddles an acuity boundary (e.g., ESI 2 vs. 3), the system automatically escalates to the safer, higher-acuity level to mathematically prevent undertriage.
* **Event-Sourced Audit Trail:** Replaces standard mutable databases with an append-only `EventLog`. Every AI prediction, vital sign update, and human override is immutably stamped with the actor, reason, and model version.
* **DPDP 2023 Compliance:** Built to align with India’s Digital Personal Data Protection Act, enforcing strict data-minimization, emergency-processing consent waivers, and algorithmic fairness monitoring.

### 3. High-Performance Clinical Frontend
* **CTAS Reassessment Worklist:** Implements the Canadian Triage and Acuity Scale (CTAS) countdown timers (e.g., ESI 2 = 15m). If a patient sits unassessed, the UI escalates from "Due" to "OVERDUE", eventually throwing a bright red "SAFETY BREACH" alert.
* **Ambulance Pre-Arrival Lane:** Allows EMS to dispatch provisional data. Patients render with a distinct `PROVISIONAL (EN-ROUTE)` UI state until a nurse physically clicks "Arrived".
* **Explanation Layer & Needs Planner:** Replaces black-box scores with total transparency. Every card displays the **WHY** (clinical rule cited) and the **CONFIDENCE**. ESI 3+ patients generate a "Needs Planner" card predicting the exact medical equipment required.
* **Mass-Casualty Surge Simulator:** A dedicated UI trigger (`/api/admin/surge`) that injects 15 synthetic, highly-complex patients into the database simultaneously to stress-test the engine's sorting logic and timer degradation during extreme ED volume.

---

## 🛠️ Technology Stack

**Backend Architecture**
* **Framework:** FastAPI (Python 3.11)
* **Database:** SQLite with SQLAlchemy ORM (Event-Sourced schema)
* **Machine Learning:** Scikit-Learn (Multi-Output Random Forest Classifier, TF-IDF Vectorization)
* **Server:** Uvicorn

**Frontend Application**
* **Core:** HTML5, Alpine.js (Lightweight Reactive SPA)
* **Styling:** Tailwind CSS
* **Architecture:** Zero-build-step architecture for maximum reliability and rapid iterative deployment.

**Deployment & DevOps**
* **Containerization:** Docker
* **Hosting:** Render (Auto-deployments)

---

## 🚀 Running Locally

### Option 1: Docker (Recommended)
```bash
# Clone the repository
git clone https://github.com/AniketKappa/Patient-Triage.git
cd Patient-Triage

# Build and run the container
docker build -t patient-triage .
docker run -p 8000:8000 patient-triage
```
Access the application at `http://localhost:8000`

### Option 2: Standard Python Environment
```bash
cd Patient-Triage/backend

# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload
```

---

## 📂 Project Structure
* `backend/main.py`: FastAPI server, routing, and timeline metrics.
* `backend/esi_rules.py`: Deterministic ESI v5 and CTAS clinical logic core.
* `backend/triage_model.py`: Adapter connecting the FastAPI data shapes to the ML pipeline.
* `backend/models.py`: SQLAlchemy schemas (Patients, Encounters, Vitals, EventLog).
* `backend/train_resource_model.py`: Training script for the synthetic Gate C and Outcome-Risk models.
* `frontend/index.html`: The complete Alpine.js/Tailwind SPA dashboard.
* `docs/`: Comprehensive architecture documentation (`COMPLIANCE.md`, `ADOPTION.md`, `LIMITATIONS.md`).

---

## ⚠️ Disclaimer
**This software is a prototype developed for a hackathon (Accenture Innovation Challenge).** It is not a registered Software as a Medical Device (SaMD). The machine learning weights provided in this repository are trained on synthetic data and must be retrospectively calibrated against localized hospital EHR data prior to any real-world clinical deployment. See `docs/LIMITATIONS.md` for a full breakdown of architectural constraints.
