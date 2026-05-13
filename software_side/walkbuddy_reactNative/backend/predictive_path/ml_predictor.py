"""
ml_predictor.py
===============
Loads the trained model and predicts risk category from sensor input.
 
Input  : speed (m/s), heading (degrees 0-360), gyro (rad/s)
Output : predicted risk label + confidence scores
"""
 
import pickle
import numpy as np
import os
 
MODEL_FILE   = os.path.join(os.path.dirname(__file__), "predictive_path_model.pkl")
ENCODER_FILE = os.path.join(os.path.dirname(__file__), "label_encoder.pkl")
 
 
class MLPredictor:
    """Wraps the trained model for easy prediction."""
 
    def __init__(self):
        self.model   = None
        self.encoder = None
        self._load()
 
    def _load(self):
        if not os.path.exists(MODEL_FILE):
            raise FileNotFoundError(
                "Model not found. Run train_model.py first."
            )
        with open(MODEL_FILE, "rb") as f:
            self.model = pickle.load(f)
        with open(ENCODER_FILE, "rb") as f:
            self.encoder = pickle.load(f)
 
    def _build_features(self, speed: float, heading: float, gyro: float) -> np.ndarray:
        """Convert raw sensor inputs to the feature vector the model expects."""
        heading_sin = np.sin(np.radians(heading))
        heading_cos = np.cos(np.radians(heading))
        return np.array([[speed, heading_sin, heading_cos, gyro]])
 
    def predict(self, speed: float, heading: float, gyro: float) -> dict:
        """
        Predict risk for given sensor readings.
 
        Returns
        -------
        {
            'label'      : str   — 'safe' | 'front' | 'front_right'
            'confidence' : float — 0.0 to 1.0
            'all_scores' : dict  — probability per class
        }
        """
        features = self._build_features(speed, heading, gyro)
 
        pred_encoded  = self.model.predict(features)[0]
        pred_proba    = self.model.predict_proba(features)[0]
 
        label         = self.encoder.inverse_transform([pred_encoded])[0]
        class_names   = self.encoder.classes_
 
        all_scores = {cls: round(float(prob), 3)
                      for cls, prob in zip(class_names, pred_proba)}
        confidence = all_scores[label]
 
        return {
            "label"      : label,
            "confidence" : confidence,
            "all_scores" : all_scores,
        }
 
 
# ── Standalone demo ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    predictor = MLPredictor()
 
    test_cases = [
        # (speed, heading, gyro,  description)
        (1.5,   2.0,   0.08,  "Moving straight ahead slowly"),
        (2.0,  48.0,   0.35,  "Veering to the front-right"),
        (1.2, 180.0,   0.02,  "Moving south — clear path"),
        (1.8,   1.0,   0.10,  "Fast, heading north"),
        (0.9, 270.0,   0.01,  "Walking west — open space"),
    ]
 
    print("=" * 60)
    print("  ML PREDICTOR — Sensor Risk Classification")
    print("=" * 60)
 
    for speed, heading, gyro, desc in test_cases:
        result = predictor.predict(speed, heading, gyro)
        label  = result["label"]
        conf   = result["confidence"]
 
        # Visual indicator
        icon = {"safe": "✅", "front": "🚨", "front_right": "⚠️"}.get(label, "?")
 
        print(f"\n  Scenario : {desc}")
        print(f"  Input    : speed={speed}  heading={heading}°  gyro={gyro}")
        print(f"  Result   : {icon}  {label.upper()}  (confidence: {conf*100:.1f}%)")
        print(f"  Scores   : {result['all_scores']}")
 
    print("\n" + "=" * 60)