import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from ml_predictor import MLPredictor

df = pd.read_csv("sensor_data.csv")

y_true = df["risk_label"].astype(str).tolist()

ml = MLPredictor()

y_pred = []

for _, row in df.iterrows():
    result = ml.predict(row["speed"], row["heading"], row["gyro"])

    # Handle different possible return types from ml_predictor.py
    if isinstance(result, dict):
        pred = result.get("prediction") or result.get("label") or result.get("risk_label")
    elif isinstance(result, tuple) or isinstance(result, list):
        pred = result[0]
    else:
        pred = result

    y_pred.append(str(pred))

labels = ["front", "front_right", "safe"]

print("\nAccuracy:")
print(accuracy_score(y_true, y_pred))

print("\nConfusion Matrix:")
print(confusion_matrix(y_true, y_pred, labels=labels))

print("\nLabels order:")
print(labels)

print("\nClassification Report:")
print(classification_report(y_true, y_pred, labels=labels))