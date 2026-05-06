from typing import Dict, List, Tuple

def _find_event(events: List[Dict], label: str):
    for event in events:
        if str(event.get("label", "")).lower() == label.lower():
            return event
    return None

def evaluate_case(case_data: Dict, response_data: Dict, default_threshold: float = 0.5) -> Tuple[bool, List[dict], dict]:
    errors = []
    expected = case_data.get("expected", {})

    raw_events = response_data.get("events", [])
    threshold = case_data.get("confidence_threshold", default_threshold)
    
    # Filter predictions
    filtered_events = [e for e in raw_events if e.get("confidence", 0.0) >= threshold]

    required_labels = expected.get("required_labels", [])
    required_directions = expected.get("required_directions", {})
    
    matched_labels = set()
    
    # Base ML Metrics
    tp = 0
    fn = 0
    fp = 0

    # --- STEP 1: False Negatives & Low Confidence Drops ---
    for label in required_labels:
        event = _find_event(filtered_events, label)
        if event is None:
            fn += 1 # We missed something we were supposed to find
            raw_match = _find_event(raw_events, label)
            if raw_match:
                errors.append({
                    "type": "Low Confidence Drop",
                    "label": label,
                    "confidence": raw_match.get('confidence'),
                    "reason": f"Found but filtered out (Confidence {raw_match.get('confidence')} < {threshold})"
                })
            else:
                errors.append({
                    "type": "False Negative",
                    "label": label,
                    "confidence": 0.0,
                    "reason": "Expected object completely undetected by model"
                })
        else:
            matched_labels.add(label)
            tp += 1 # We correctly found an expected object

    # --- STEP 2: Direction Errors ---
    for label, expected_direction in required_directions.items():
        event = _find_event(filtered_events, label)
        if event:
            actual_direction = event.get("direction")
            if actual_direction != expected_direction:
                errors.append({
                    "type": "Direction Error",
                    "label": label,
                    "reason": f"Expected '{expected_direction}', got '{actual_direction}'"
                })

    # --- STEP 3: False Positives ---
    for event in filtered_events:
        actual_label = event.get("label")
        if actual_label not in required_labels:
            fp += 1 # We found something that shouldn't be there
            errors.append({
                "type": "False Positive",
                "label": actual_label,
                "confidence": event.get('confidence'),
                "reason": f"Detected with confidence {event.get('confidence')}, but not in expected labels"
            })

    # --- STEP 4: System/Count Errors ---
    if "safe" in expected:
        actual_safe = response_data.get("safe")
        if actual_safe != expected["safe"]:
            errors.append({
                "type": "Logic Error",
                "label": "Safety Gate",
                "reason": f"Expected safe={expected['safe']}, got {actual_safe}"
            })

    if "min_event_count" in expected:
        if len(filtered_events) < expected["min_event_count"]:
            errors.append({
                "type": "Count Error",
                "label": "System",
                "reason": f"Expected at least {expected['min_event_count']} events, got {len(filtered_events)}"
            })

    stats = {
        "threshold": threshold,
        "raw_count": len(raw_events),
        "filtered_count": len(filtered_events),
        "TP": tp,
        "FP": fp,
        "FN": fn
    }

    passed = len(errors) == 0
    return passed, errors, stats