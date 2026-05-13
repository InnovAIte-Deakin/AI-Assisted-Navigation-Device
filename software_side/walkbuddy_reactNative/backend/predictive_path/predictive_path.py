"""
predictive_path.py
==================
Core engine: takes live sensor readings, predicts the user's future
position over multiple time steps, asks the ML model for risk at each
step, and returns alerts when danger is detected.
 
Components
----------
- PathPredictor  : calculates future (x, y) positions
- RiskEvaluator  : wraps MLPredictor, decides if a step is risky
- PredictivePathSystem : orchestrates everything, produces alerts
"""
 
import math
from ml_predictor import MLPredictor
 
 
# ── PathPredictor ─────────────────────────────────────────────────────────────
 
class PathPredictor:
    """
    Given current speed and heading, projects future positions.
 
    Uses simple dead-reckoning physics:
        x_new = x + speed * sin(heading) * dt
        y_new = y + speed * cos(heading) * dt
    """
 
    def __init__(self, dt: float = 0.5, steps: int = 5):
        """
        Parameters
        ----------
        dt    : time step in seconds between predictions
        steps : how many steps ahead to predict
        """
        self.dt    = dt
        self.steps = steps
 
    def predict_path(
        self,
        speed:   float,
        heading: float,
        gyro:    float,
        x0:      float = 0.0,
        y0:      float = 0.0,
    ) -> list[dict]:
        """
        Project the path `self.steps` steps into the future.
 
        Returns list of dicts:
            [{ 'step', 'x', 'y', 'distance', 'heading', 'speed', 'gyro' }, ...]
        """
        heading_rad = math.radians(heading)
        # Gyro gently adjusts heading each step (simulates turning)
        heading_change_per_step = math.degrees(gyro) * self.dt
 
        path   = []
        x, y   = x0, y0
        h      = heading
 
        for step in range(1, self.steps + 1):
            h += heading_change_per_step          # apply gyro-induced turn
            h  = h % 360                          # keep 0–360
 
            h_rad = math.radians(h)
            x += speed * math.sin(h_rad) * self.dt
            y += speed * math.cos(h_rad) * self.dt
 
            distance = math.sqrt(x**2 + y**2)    # distance from start
 
            path.append({
                "step"    : step,
                "x"       : round(x, 3),
                "y"       : round(y, 3),
                "distance": round(distance, 3),
                "heading" : round(h, 2),
                "speed"   : speed,
                "gyro"    : gyro,
            })
 
        return path
 
 
# ── RiskEvaluator ─────────────────────────────────────────────────────────────
 
SAFE_LABEL        = "safe"
RISKY_LABELS      = {"front", "front_right"}
ALERT_MESSAGES    = {
    "front"      : "🚨 WARNING: Obstacle AHEAD!",
    "front_right": "⚠️  WARNING: Obstacle on RIGHT!",
}
CONFIDENCE_THRESH = 0.50   # only alert if model is ≥50% confident
 
 
class RiskEvaluator:
    """Uses the ML model to evaluate risk at each predicted path step."""
 
    def __init__(self):
        self.predictor = MLPredictor()
 
    def evaluate(self, step: dict) -> dict:
        """
        Runs ML prediction for one path step.
 
        Returns the step dict enriched with:
            'risk_label', 'confidence', 'alert', 'alert_message'
        """
        result = self.predictor.predict(
            speed   = step["speed"],
            heading = step["heading"],
            gyro    = step["gyro"],
        )
 
        label  = result["label"]
        conf   = result["confidence"]
        risky  = (label in RISKY_LABELS) and (conf >= CONFIDENCE_THRESH)
 
        return {
            **step,
            "risk_label"    : label,
            "confidence"    : conf,
            "all_scores"    : result["all_scores"],
            "alert"         : risky,
            "alert_message" : ALERT_MESSAGES.get(label, "") if risky else "",
        }
 
 
# ── PredictivePathSystem ───────────────────────────────────────────────────────
 
class PredictivePathSystem:
    """
    Main system class.  Feed it sensor data, get path + alerts back.
 
    Usage
    -----
        system = PredictivePathSystem()
        report = system.run(speed=1.5, heading=2.0, gyro=0.08)
        system.print_report(report)
    """
 
    def __init__(self, dt: float = 0.5, steps: int = 5):
        self.path_predictor = PathPredictor(dt=dt, steps=steps)
        self.risk_evaluator = RiskEvaluator()
 
    def run(
        self,
        speed:   float,
        heading: float,
        gyro:    float,
        x0:      float = 0.0,
        y0:      float = 0.0,
    ) -> dict:
        """
        Full pipeline: predict path → evaluate risk → collect alerts.
 
        Returns
        -------
        {
            'input'       : { speed, heading, gyro },
            'path'        : [ enriched step dicts ],
            'alerts'      : [ alert strings ],
            'first_alert' : str | None,
            'overall_risk': 'safe' | 'risky',
        }
        """
        # Step 1: predict future positions
        path_steps = self.path_predictor.predict_path(
            speed, heading, gyro, x0, y0
        )
 
        # Step 2: evaluate risk at each step
        evaluated  = [self.risk_evaluator.evaluate(s) for s in path_steps]
 
        # Step 3: collect alerts
        alerts = [
            f"Step {s['step']} ({s['distance']}m): {s['alert_message']}"
            for s in evaluated if s["alert"]
        ]
 
        first_alert = alerts[0] if alerts else None
        overall_risk = "risky" if alerts else "safe"
 
        return {
            "input"        : {"speed": speed, "heading": heading, "gyro": gyro},
            "path"         : evaluated,
            "alerts"       : alerts,
            "first_alert"  : first_alert,
            "overall_risk" : overall_risk,
        }
 
    @staticmethod
    def print_report(report: dict) -> None:
        """Pretty-print a full system report to the terminal."""
        inp = report["input"]
        print("\n" + "═" * 60)
        print("  PREDICTIVE PATH INTELLIGENCE REPORT")
        print("═" * 60)
        print(f"  Input  →  speed={inp['speed']} m/s  |  "
              f"heading={inp['heading']}°  |  gyro={inp['gyro']} rad/s")
        print(f"  Overall risk: {'🔴 RISKY' if report['overall_risk']=='risky' else '🟢 SAFE'}")
        print()
 
        # Path table
        print(f"  {'Step':<5} {'X':>7} {'Y':>7} {'Dist(m)':>8}  "
              f"{'Heading':>8}  {'Risk':<12} {'Conf':>6}  Alert")
        print("  " + "─" * 72)
        for s in report["path"]:
            flag = "◀ ALERT" if s["alert"] else ""
            print(
                f"  {s['step']:<5} {s['x']:>7.2f} {s['y']:>7.2f} "
                f"{s['distance']:>8.2f}  {s['heading']:>8.2f}°  "
                f"{s['risk_label']:<12} {s['confidence']:>5.0%}  {flag}"
            )
 
        # Alerts
        print()
        if report["alerts"]:
            print("  ⚡ ALERTS GENERATED:")
            for a in report["alerts"]:
                print(f"    → {a}")
        else:
            print("  ✅ No alerts — path is clear.")
        print("═" * 60 + "\n")
 
 
# ── Quick demo when run directly ──────────────────────────────────────────────
if __name__ == "__main__":
    system = PredictivePathSystem(dt=0.5, steps=6)
 
    scenarios = [
        (1.5,   2.0,  0.08, "Heading straight north (risky)"),
        (1.2,  48.0,  0.35, "Veering front-right (risky)"),
        (1.0, 180.0,  0.02, "Moving south (safe)"),
    ]
 
    for speed, heading, gyro, desc in scenarios:
        print(f"\n  Scenario: {desc}")
        report = system.run(speed=speed, heading=heading, gyro=gyro)
        system.print_report(report)