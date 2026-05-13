"""
train_model.py
==============
Trains a Random Forest classifier on sensor_data.csv to predict
movement risk direction: safe | front | front_right

Uses scikit-learn (same ML concepts as TensorFlow, portable everywhere).
Saves the trained model to predictive_path_model.pkl
"""

import pandas as pd
import numpy as np
import pickle
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, accuracy_score

# ── 1. Load Data ──────────────────────────────────────────────────────────────
print("=" * 55)
print("  PREDICTIVE PATH INTELLIGENCE — Model Training")
print("=" * 55)

DATA_FILE = os.path.join(os.path.dirname(__file__), "sensor_data.csv")

df = pd.read_csv(DATA_FILE)
print(f"\n[✔] Loaded dataset: {len(df)} samples")
print(f"    Columns : {list(df.columns)}")
print(f"    Classes : {df['risk_label'].unique().tolist()}")
print(f"\n    Class distribution:")
for label, count in df['risk_label'].value_counts().items():
    print(f"      {label:<15} → {count} samples")

# ── 2. Feature Engineering ────────────────────────────────────────────────────
# Convert heading to sine/cosine so 0° and 360° are treated as the same
df['heading_sin'] = np.sin(np.radians(df['heading']))
df['heading_cos'] = np.cos(np.radians(df['heading']))

FEATURES = ['speed', 'heading_sin', 'heading_cos', 'gyro']
LABEL    = 'risk_label'

X = df[FEATURES].values
y = df[LABEL].values

# Encode labels to integers
encoder = LabelEncoder()
y_encoded = encoder.fit_transform(y)
class_names = encoder.classes_.tolist()

print(f"\n[✔] Features used : {FEATURES}")
print(f"[✔] Label encoding : {dict(zip(class_names, encoder.transform(class_names)))}")

# ── 3. Train / Test Split ─────────────────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
)
print(f"\n[✔] Train samples : {len(X_train)}")
print(f"[✔] Test  samples : {len(X_test)}")

# ── 4. Train Model ────────────────────────────────────────────────────────────
print("\n[⏳] Training Random Forest model ...")
model = RandomForestClassifier(
    n_estimators=100,
    max_depth=8,
    random_state=42
)
model.fit(X_train, y_train)
print("[✔] Training complete!")

# ── 5. Evaluate ───────────────────────────────────────────────────────────────
y_pred = model.predict(X_test)
acc = accuracy_score(y_test, y_pred)

print(f"\n{'─'*55}")
print(f"  Model Accuracy : {acc*100:.1f}%")
print(f"{'─'*55}")
print("\n  Classification Report:")
print(classification_report(y_test, y_pred, target_names=class_names))

# Feature importance
print("  Feature Importances:")
for feat, imp in sorted(zip(FEATURES, model.feature_importances_), key=lambda x: -x[1]):
    bar = "█" * int(imp * 40)
    print(f"    {feat:<18} {imp:.3f}  {bar}")

# ── 6. Save Model ─────────────────────────────────────────────────────────────
MODEL_FILE   = os.path.join(os.path.dirname(__file__), "predictive_path_model.pkl")
ENCODER_FILE = os.path.join(os.path.dirname(__file__), "label_encoder.pkl")

with open(MODEL_FILE, "wb") as f:
    pickle.dump(model, f)

with open(ENCODER_FILE, "wb") as f:
    pickle.dump(encoder, f)

print(f"\n[✔] Model saved   → {MODEL_FILE}")
print(f"[✔] Encoder saved → {ENCODER_FILE}")
print("\n  Run ml_predictor.py to test predictions.")
print("  Run test_predictive_path.py for the full system demo.\n")
