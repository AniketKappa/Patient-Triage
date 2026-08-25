import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier

# Standard Gate C Resource Classes
RESOURCE_CLASSES = [
    "Labs", 
    "ECG", 
    "X-Ray", 
    "Advanced Imaging (CT/MRI/US)", 
    "IV Fluids", 
    "IV / IM Meds", 
    "Specialty Consult", 
    "Simple Procedure", 
    "Complex Procedure"
]

# Clinical seed data for mock training (Mapping text to the 9 classes above)
data = [
    ("sore throat, mild cough, congestion", [0,0,0,0,0,0,0,0,0]),
    ("sprained ankle, twisted, pain swelling", [0,0,1,0,0,0,0,0,0]),
    ("abdominal pain, severe nausea vomiting, stomach hurts", [1,0,0,1,1,1,0,0,0]),
    ("cut on arm, laceration, bleeding needs stitches", [0,0,0,0,0,0,0,1,0]),
    ("chest pain, shortness of breath, heavy chest", [1,1,1,0,0,1,0,0,0]),
    ("mild headache, clear vision, chronic", [0,0,0,0,0,0,0,0,0]),
    ("worst headache of life, thunderclap, sudden", [1,0,0,1,0,1,1,0,0]),
    ("burning urination, frequency, UTI symptoms", [1,0,0,0,0,0,0,0,0]),
    ("fall, deformed wrist, bone visible, fracture", [0,0,1,0,0,1,1,0,1]),
    ("allergic reaction, rash, itching hives", [0,0,0,0,0,1,0,0,0]),
    ("toothache, dental pain", [0,0,0,0,0,0,0,0,0]),
    ("ear pain, toddler earache", [0,0,0,0,0,0,0,0,0]),
    ("motor vehicle accident, neck pain whiplash", [0,0,1,1,0,0,0,0,0]),
    ("fever, chills, body aches flu", [1,0,0,0,0,0,0,0,0]),
    ("dizziness, weakness, older adult fainting syncope", [1,1,0,1,1,0,0,0,0]),
    ("asthma exacerbation, wheezing breathing heavy", [0,0,1,0,0,1,0,0,0]),
    ("suicidal ideation depressed", [0,0,0,0,0,0,1,0,0]),
    ("dislocated shoulder popped out", [0,0,1,0,0,1,0,1,0]),
    ("vomiting blood gi bleed", [1,1,0,1,1,1,1,0,0]),
    ("minor burn on finger hot pan", [0,0,0,0,0,0,0,0,0]),
    ("chest pressure arm pain", [1,1,1,0,0,1,1,0,0]),
    ("pregnant spotting cramping", [1,0,0,1,0,0,1,0,0]),
    ("abscess boil skin infection", [0,0,0,0,0,0,0,1,0])
]

X_text = []
y = []
# Upsample for stability
for _ in range(10):
    for text, labels in data:
        X_text.append(text)
        y.append(labels)

print("Training Gate C ML Resource Predictor (Multi-label RandomForest)...")
vectorizer = TfidfVectorizer(max_features=200, ngram_range=(1, 2))
X_features = vectorizer.fit_transform(X_text).toarray()
y = np.array(y)

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_features, y)

joblib.dump(vectorizer, 'resource_tfidf.pkl')
joblib.dump(model, 'resource_rf.pkl')
joblib.dump(RESOURCE_CLASSES, 'resource_classes.pkl')
print("Successfully saved ML assets for Gate C.")
