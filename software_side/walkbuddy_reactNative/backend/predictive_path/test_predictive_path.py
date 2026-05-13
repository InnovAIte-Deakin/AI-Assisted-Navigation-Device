"""
test_predictive_path.py
=======================
Full system integration test for the Predictive Path Intelligence project.
 
Tests
-----
1. Data file exists and is valid
2. ML model is trained and loadable
3. MLPredictor returns correct output format
4. PathPredictor generates the right number of steps
5. Risk labels are valid
6. Alert messages fire when expected
7. End-to-end system run for multiple scenarios
"""
 
import os
import sys
import math
import traceback
 
# Make sure imports resolve to the project folder
sys.path.insert(0, os.path.dirname(__file__))
 
PASS = "  [PASS]"
FAIL = "  [FAIL]"
SEP  = "─" * 55
 
 
def section(title: str) -> None:
    print(f"\n{SEP}\n  {title}\n{SEP}")
 
 
def check(condition: bool, msg: str) -> bool:
    status = PASS if condition else FAIL
    print(f"{status}  {msg}")
    return condition
 
 
# ── Test 1: Data File ─────────────────────────────────────────────────────────
def test_data_file() -> int:
    section("TEST 1 — Data File")
    errors = 0
 
    path = os.path.join(os.path.dirname(__file__), "sensor_data.csv")
    exists = os.path.exists(path)
    errors += 0 if check(exists, "sensor_data.csv exists") else 1
    if not exists:
        return errors
 
    import pandas as pd
    df = pd.read_csv(path)
 
    errors += 0 if check(len(df) > 0, f"Dataset has {len(df)} rows") else 1
    for col in ["speed", "heading", "gyro", "risk_label"]:
        errors += 0 if check(col in df.columns, f"Column '{col}' present") else 1
 
    labels = set(df["risk_label"].unique())
    expected = {"safe", "front", "front_right"}
    errors += 0 if check(labels == expected, f"Labels correct: {labels}") else 1
 
    return errors
 
 
# ── Test 2: Model Exists ──────────────────────────────────────────────────────
def test_model_exists() -> int:
    section("TEST 2 — Trained Model Files")
    errors = 0
    base = os.path.dirname(__file__)
 
    for fname in ["predictive_path_model.pkl", "label_encoder.pkl"]:
        path = os.path.join(base, fname)
        errors += 0 if check(os.path.exists(path), f"{fname} exists") else 1
 
    return errors
 
 
# ── Test 3: MLPredictor ───────────────────────────────────────────────────────
def test_ml_predictor() -> int:
    section("TEST 3 — MLPredictor Output Format")
    errors = 0
 
    try:
        from ml_predictor import MLPredictor
        predictor = MLPredictor()
        errors += 0 if check(True, "MLPredictor loaded successfully") else 1
 
        result = predictor.predict(speed=1.5, heading=2.0, gyro=0.08)
 
        errors += 0 if check("label" in result,      "'label' key in result") else 1
        errors += 0 if check("confidence" in result,  "'confidence' key in result") else 1
        errors += 0 if check("all_scores" in result,  "'all_scores' key in result") else 1
 
        label = result["label"]
        errors += 0 if check(
            label in {"safe", "front", "front_right"},
            f"Label is valid: '{label}'"
        ) else 1
 
        conf = result["confidence"]
        errors += 0 if check(
            0.0 <= conf <= 1.0,
            f"Confidence in range [0,1]: {conf:.2f}"
        ) else 1
 
        scores = result["all_scores"]
        errors += 0 if check(
            abs(sum(scores.values()) - 1.0) < 0.01,
            f"Scores sum to 1.0: {sum(scores.values()):.4f}"
        ) else 1
 
    except Exception as e:
        check(False, f"MLPredictor raised exception: {e}")
        traceback.print_exc()
        errors += 1
 
    return errors
 
 
# ── Test 4: PathPredictor ─────────────────────────────────────────────────────
def test_path_predictor() -> int:
    section("TEST 4 — PathPredictor")
    errors = 0
 
    try:
        from predictive_path import PathPredictor
        pp = PathPredictor(dt=0.5, steps=5)
        path = pp.predict_path(speed=1.2, heading=90.0, gyro=0.02)
 
        errors += 0 if check(len(path) == 5, f"Generated 5 path steps (got {len(path)})") else 1
 
        for key in ["step", "x", "y", "distance", "heading", "speed", "gyro"]:
            errors += 0 if check(key in path[0], f"Step has '{key}' key") else 1
 
        # Moving east (heading=90) → x should increase, y near 0
        last = path[-1]
        errors += 0 if check(last["x"] > 0, f"x is positive when heading east: {last['x']}") else 1
        errors += 0 if check(last["distance"] > 0, f"Distance > 0: {last['distance']}") else 1
 
        # Steps are numbered 1..5
        steps = [s["step"] for s in path]
        errors += 0 if check(steps == list(range(1, 6)), f"Steps numbered 1-5: {steps}") else 1
 
    except Exception as e:
        check(False, f"PathPredictor raised exception: {e}")
        traceback.print_exc()
        errors += 1
 
    return errors
 
 
# ── Test 5: Risk Evaluator ────────────────────────────────────────────────────
def test_risk_evaluator() -> int:
    section("TEST 5 — RiskEvaluator")
    errors = 0
 
    try:
        from predictive_path import PathPredictor, RiskEvaluator
 
        pp = PathPredictor(dt=0.5, steps=1)
        re = RiskEvaluator()
 
        step = pp.predict_path(speed=1.5, heading=2.0, gyro=0.08)[0]
        evaluated = re.evaluate(step)
 
        for key in ["risk_label", "confidence", "alert", "alert_message"]:
            errors += 0 if check(key in evaluated, f"Evaluated step has '{key}'") else 1
 
        errors += 0 if check(
            evaluated["risk_label"] in {"safe", "front", "front_right"},
            f"risk_label is valid: '{evaluated['risk_label']}'"
        ) else 1
 
        errors += 0 if check(
            isinstance(evaluated["alert"], bool),
            f"'alert' is bool: {evaluated['alert']}"
        ) else 1
 
    except Exception as e:
        check(False, f"RiskEvaluator raised exception: {e}")
        traceback.print_exc()
        errors += 1
 
    return errors
 
 
# ── Test 6: Alert Logic ───────────────────────────────────────────────────────
def test_alert_logic() -> int:
    section("TEST 6 — Alert Logic (End-to-End)")
    errors = 0
 
    try:
        from predictive_path import PredictivePathSystem
 
        system = PredictivePathSystem(dt=0.5, steps=5)
 
        # Heading 0° (north) with gyro = risky
        report_risky = system.run(speed=1.5, heading=2.0, gyro=0.08)
        errors += 0 if check(
            report_risky["overall_risk"] == "risky",
            "North-heading scenario classified as risky"
        ) else 1
        errors += 0 if check(
            len(report_risky["alerts"]) > 0,
            f"Alerts generated: {len(report_risky['alerts'])}"
        ) else 1
 
        # Heading 180° (south) — safe direction
        report_safe = system.run(speed=1.2, heading=180.0, gyro=0.02)
        errors += 0 if check(
            report_safe["overall_risk"] == "safe",
            "South-heading scenario classified as safe"
        ) else 1
        errors += 0 if check(
            len(report_safe["alerts"]) == 0,
            "No alerts for safe scenario"
        ) else 1
 
        # Report structure
        for key in ["input", "path", "alerts", "first_alert", "overall_risk"]:
            errors += 0 if check(key in report_risky, f"Report has '{key}' key") else 1
 
    except Exception as e:
        check(False, f"Alert logic test raised exception: {e}")
        traceback.print_exc()
        errors += 1
 
    return errors
 
 
# ── Test 7: Full Scenarios Demo ───────────────────────────────────────────────
def test_full_scenarios() -> int:
    section("TEST 7 — Full Scenario Walkthrough")
 
    from predictive_path import PredictivePathSystem
    system = PredictivePathSystem(dt=0.5, steps=5)
 
    scenarios = [
        (1.5,   2.0,  0.08, "Moving north — obstacle ahead"),
        (1.2,  48.0,  0.35, "Veering front-right"),
        (1.0, 180.0,  0.02, "Moving south — clear"),
        (1.8, 270.0,  0.01, "Moving west — clear"),
        (2.0,   1.0,  0.10, "Fast north — obstacle ahead"),
    ]
 
    errors = 0
    for speed, heading, gyro, desc in scenarios:
        report = system.run(speed=speed, heading=heading, gyro=gyro)
        risk   = report["overall_risk"]
        nalert = len(report["alerts"])
        icon   = "🔴" if risk == "risky" else "🟢"
 
        print(f"\n  {icon} {desc}")
        print(f"     Input   : speed={speed}  heading={heading}°  gyro={gyro}")
        print(f"     Risk    : {risk.upper()}")
        if report["alerts"]:
            for a in report["alerts"]:
                print(f"     Alert   : {a}")
        else:
            print(f"     Alert   : none — path is clear")
 
        errors += 0 if check(
            risk in {"safe", "risky"},
            f"overall_risk is valid: '{risk}'"
        ) else 1
 
    return errors
 
 
# ── Runner ─────────────────────────────────────────────────────────────────────
def main() -> None:
    print("\n" + "═" * 55)
    print("  PREDICTIVE PATH INTELLIGENCE — SYSTEM TEST SUITE")
    print("═" * 55)
 
    total_errors = 0
 
    total_errors += test_data_file()
    total_errors += test_model_exists()
    total_errors += test_ml_predictor()
    total_errors += test_path_predictor()
    total_errors += test_risk_evaluator()
    total_errors += test_alert_logic()
    total_errors += test_full_scenarios()
 
    print("\n" + "═" * 55)
    if total_errors == 0:
        print("  ✅ ALL TESTS PASSED — System working correctly!")
    else:
        print(f"  ❌ {total_errors} test(s) FAILED — check output above.")
    print("═" * 55 + "\n")
    sys.exit(0 if total_errors == 0 else 1)
 
 
if __name__ == "__main__":
    main()