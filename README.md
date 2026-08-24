# 🏥 PatientTriage.ai

**Live Demo:** [https://patient-triage.onrender.com](https://patient-triage.onrender.com)

PatientTriage.ai is a real-time, hybrid AI triage framework designed to achieve dynamic patient prioritization and explicit severity categorization (ESI 1-5) across parallel clinical queues in overcrowded emergency rooms. It was recently implemented as a Proof of Concept (POC) in a local hospital setting.

## 🚀 Key Features

* **Hybrid Clinical Decision Support System (CDSS):** Uses a Random Forest classifier and TF-IDF NLP pipeline to parse unstructured symptom descriptions (60% weight) combined with vitals deviation (40% weight).
* **Clinical Safety-Net Overrides:** Hard-coded algorithmic bypasses ensure patients with critical vitals (e.g., SpO2 < 90, Sys BP < 80) are instantly categorized as ESI 1/2, preventing catastrophic ML under-triage.
* **Dynamic Priority Scaling:** Patient queues aren't static. Priority scores continuously increase based on wait time, ensuring stable patients are not left stranded while critical patients are handled.
* **Real-time Deterioration Alerts:** Re-assessing vitals cross-references historical data. Sudden drops in SpO2 or spikes in Heart Rate trigger an immediate priority penalty and can dynamically shift a patient from the Standard Queue into the Critical Queue.
* **Split Queue Dashboard:** Visually separates Resuscitation/Emergent (ESI 1 & 2) from Standard Triage (ESI 3, 4, 5).

## 🛠️ Tech Stack

* **Frontend:** HTML5, Tailwind CSS, Alpine.js (Reactive polling)
* **Backend:** Python, FastAPI, SQLite, SQLAlchemy (ORM)
* **Machine Learning:** Scikit-Learn (Random Forest, TF-IDF), NumPy, Pandas
* **Deployment:** Render (PaaS)

## 💻 Local Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/AniketKappa/Patient-Triage.git
   cd Patient-Triage/backend
   ```

2. **Set up the virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Generate the Database & Synthetic Data:**
   ```bash
   python seed.py
   ```

5. **Run the FastAPI Server:**
   ```bash
   uvicorn main:app --reload
   ```

6. Open your browser and navigate to `http://localhost:8000` to view the dashboard.
