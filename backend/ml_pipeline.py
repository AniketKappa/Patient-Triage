import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
import joblib
import random

print("Generating synthetic patient data...")

# Generate synthetic dataset
n_samples = 5000
data = {
    'age': np.random.randint(1, 95, n_samples),
    'spo2': np.random.normal(96, 4, n_samples).clip(70, 100),
    'hr': np.random.normal(85, 20, n_samples).clip(40, 180),
    'bp_sys': np.random.normal(120, 20, n_samples).clip(70, 200),
    'temp_c': np.random.normal(37, 1, n_samples).clip(35, 41),
    'family_statements': []
}

esi_labels = []
symptom_pool = ['chest pain', 'fever', 'headache', 'dizzy', 'unresponsive', 'bleeding', 'weakness', 'cough', 'vomiting', 'pain']

for i in range(n_samples):
    symptom = random.choice(symptom_pool)
    statement = f"Patient is complaining of {symptom}. "
    
    risk = 5
    if data['spo2'][i] < 90 or 'unresponsive' in symptom or data['bp_sys'][i] < 80:
        risk = 1
        statement += "They look very bad, dropping in and out of consciousness."
    elif 'chest pain' in symptom or data['hr'][i] > 130 or data['temp_c'][i] > 39:
        risk = 2
        statement += "It started suddenly."
    elif data['temp_c'][i] > 38 or 'bleeding' in symptom:
        risk = 3
    elif data['hr'][i] > 100:
        risk = 4
        statement += "Just feeling unwell."
        
    data['family_statements'].append(statement)
    esi_labels.append(risk)

df = pd.DataFrame(data)
y = np.array(esi_labels)

print("Training NLP TF-IDF...")
vectorizer = TfidfVectorizer(max_features=10)
text_features = vectorizer.fit_transform(df['family_statements']).toarray()

num_features = df[['age', 'spo2', 'hr', 'bp_sys', 'temp_c']].values
X = np.hstack((num_features, text_features))

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print("Training RandomForest Classifier (Replacing XGBoost due to env)...")
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

print("Saving models to .pkl...")
joblib.dump(model, 'rf_triage.pkl')
joblib.dump(vectorizer, 'tfidf.pkl')

print("ML Pipeline Complete.")
