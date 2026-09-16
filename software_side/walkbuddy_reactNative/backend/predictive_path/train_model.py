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


DATA_FILE = os.path.join(
    os.path.dirname(__file__),
    "sensor_data.csv"
)


def retrain_from_dataframe(df):

    # Feature engineering
    df["heading_sin"] = np.sin(np.radians(df["heading"]))
    df["heading_cos"] = np.cos(np.radians(df["heading"]))

    features = [
        "speed",
        "heading_sin",
        "heading_cos",
        "gyro"
    ]

    X = df[features]
    y = df["risk_label"]

    # Encode labels
    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y_encoded,
        test_size=0.2,
        random_state=42,
        stratify=y_encoded
    )

    # Random Forest
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        random_state=42
    )

    model.fit(X_train, y_train)

    # Predictions
    predictions = model.predict(X_test)

    accuracy = accuracy_score(y_test, predictions)

    print("Accuracy:", accuracy)
    print(classification_report(
        y_test,
        predictions,
        target_names=label_encoder.classes_
    ))

    # Save model
    model_path = os.path.join(
        os.path.dirname(__file__),
        "predictive_path_model.pkl"
    )

    encoder_path = os.path.join(
        os.path.dirname(__file__),
        "label_encoder.pkl"
    )

    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    with open(encoder_path, "wb") as f:
        pickle.dump(label_encoder, f)

    return accuracy


if __name__ == "__main__":

    df = pd.read_csv(DATA_FILE)

    retrain_from_dataframe(df)
