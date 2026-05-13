"""
predict_with_model.py
=====================
Standalone demo: load the trained model and run single predictions.
Equivalent role to predict_with_tflite.py in a TensorFlow project.
 
Usage
-----
    python predict_with_model.py
    python predict_with_model.py --speed 1.5 --heading 2.0 --gyro 0.08
"""
 
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
 
from ml_predictor import MLPredictor
 
 
def predict_single(speed: float, heading: float, gyro: float) -> None:
    """Run a prediction and print a formatted result."""
    predictor = MLPredictor()
    result    = predictor.predict(speed=speed, heading=heading, gyro=gyro)
 
    label = result["label"]
    conf  = result["confidence"]
    icon  = {"safe": "✅", "front": "🚨", "front_right": "⚠️"}.get(label, "?")
 
    bar_len  = 30
    filled   = int(conf * bar_len)
    conf_bar = "█" * filled + "░" * (bar_len - filled)
 
    print("\n┌─────────────────────────────────────────┐")
    print("│     PREDICTIVE PATH MODEL PREDICTION    │")
    print("├─────────────────────────────────────────┤")
    print(f"│  Speed   : {speed} m/s")
    print(f"│  Heading : {heading}°")
    print(f"│  Gyro    : {gyro} rad/s")
    print("├─────────────────────────────────────────┤")
    print(f"│  Result  : {icon}  {label.upper()}")
    print(f"│  Conf    : [{conf_bar}] {conf*100:.1f}%")
    print("├─────────────────────────────────────────┤")
    print("│  All class probabilities:")
    for cls, prob in sorted(result["all_scores"].items(), key=lambda x: -x[1]):
        bar = "█" * int(prob * 20) + "░" * (20 - int(prob * 20))
        print(f"│    {cls:<14} [{bar}] {prob*100:.1f}%")
    print("└─────────────────────────────────────────┘\n")
 
 
def main():
    # Parse optional CLI args
    args = sys.argv[1:]
    if "--speed" in args:
        speed   = float(args[args.index("--speed")   + 1])
        heading = float(args[args.index("--heading") + 1])
        gyro    = float(args[args.index("--gyro")    + 1])
        predict_single(speed, heading, gyro)
    else:
        # Run the built-in demo
        print("=" * 55)
        print("  MODEL DEMO — Running sample predictions")
        print("=" * 55)
 
        samples = [
            (1.5,   2.0,  0.08),
            (1.2,  48.0,  0.35),
            (1.0, 180.0,  0.02),
            (2.0,   0.5,  0.10),
            (0.8, 270.0,  0.01),
        ]
 
        for speed, heading, gyro in samples:
            predict_single(speed, heading, gyro)
 
 
if __name__ == "__main__":
    main()