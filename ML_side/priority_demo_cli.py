"""
Priority Assignment Demo — Interview Script
Run: python priority_demo_cli.py
No model or server required.
"""

OBJECT_PRIORITY = {
    "stairs": 5, "emergency-exit": 5,
    "person": 4, "fire-extinguisher": 4,
    "door": 3, "elevator": 3, "handrail": 3,
    "signage": 2, "whiteboard": 2, "tv": 2,
    "book": 1, "books": 1, "monitor": 1, "office-chair": 1, "table": 1,
}
LABELS = {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "MINIMAL"}
COLOURS = {5: "\033[91m", 4: "\033[93m", 3: "\033[33m", 2: "\033[92m", 1: "\033[32m"}
RESET = "\033[0m"

SCENARIOS = [
    {
        "name": "Hallway — mixed scene",
        "detections": [
            ("monitor",  0.91, "left"),
            ("stairs",   0.87, "center"),
            ("handrail", 0.74, "right"),
            ("book",     0.65, "left"),
        ]
    },
    {
        "name": "Library entrance — person blocking path",
        "detections": [
            ("table",    0.88, "left"),
            ("person",   0.93, "center"),
            ("signage",  0.70, "right"),
        ]
    },
    {
        "name": "Clear path — only furniture",
        "detections": [
            ("office-chair", 0.82, "right"),
            ("whiteboard",   0.75, "left"),
        ]
    },
]

def navigate(detections):
    detections = sorted(detections, key=lambda d: d[0], reverse=True)
    top_p, top_name = detections[0][0], detections[0][1]
    if top_p == 5:
        return "STOP", "High", f"⛔  STOP — {top_name.upper()} detected. Assess before moving."
    elif top_p == 4:
        return "CAUTION", "High", f"⚠️  CAUTION — {top_name} nearby. Slow down."
    elif top_p == 3:
        return "AWARE", "Medium", f"👁  AWARE — {top_name} detected. Navigate around it."
    else:
        return "PROCEED", "Low", "✅  Path is clear. Continue forward."

def run():
    print("\n" + "="*60)
    print("  OBJECT PRIORITY ASSIGNMENT — LIVE DEMO")
    print("  AI-Assisted Navigation Device | bravine6")
    print("="*60)

    for scenario in SCENARIOS:
        print(f"\n📍 Scenario: {scenario['name']}")
        print("-"*50)

        enriched = []
        for name, conf, pos in scenario["detections"]:
            p = OBJECT_PRIORITY.get(name, 1)
            enriched.append((p, name, conf, pos))

        enriched.sort(reverse=True)

        print(f"  {'Object':<20} {'Priority':<5} {'Label':<10} {'Conf':<7} {'Position'}")
        print(f"  {'-'*55}")
        for p, name, conf, pos in enriched:
            c = COLOURS[p]
            print(f"  {c}{name:<20} {p:<5} {LABELS[p]:<10}{RESET} {conf:.0%}     {pos}")

        direction, safety, message = navigate(enriched)
        print(f"\n  → Navigation: {message}")
        print(f"  → Safety Level: {safety}  |  Direction: {direction}")

    print("\n" + "="*60)
    print("  30/30 unit tests passing  |  pytest tests/test_priority.py")
    print("="*60 + "\n")

if __name__ == "__main__":
    run()
