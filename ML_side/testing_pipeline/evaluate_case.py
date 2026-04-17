from typing import Dict, List, Tuple


def _find_event(events: List[Dict], label: str):
    for event in events:
        if str(event.get("label", "")).lower() == label.lower():
            return event
    return None


def evaluate_case(case_data: Dict, response_data: Dict) -> Tuple[bool, List[str]]:
    failures = []

    expected = case_data.get("expected", {})
    events = response_data.get("events", [])

    required_labels = expected.get("required_labels", [])
    for label in required_labels:
        event = _find_event(events, label)
        if event is None:
            failures.append(f"Missing required label: {label}")

    required_directions = expected.get("required_directions", {})
    for label, expected_direction in required_directions.items():
        event = _find_event(events, label)
        if event is None:
            failures.append(f"Direction check failed because label was missing: {label}")
            continue

        actual_direction = event.get("direction")
        if actual_direction != expected_direction:
            failures.append(
                f"Wrong direction for {label}: expected '{expected_direction}', got '{actual_direction}'"
            )

    if "safe" in expected:
        actual_safe = response_data.get("safe")
        if actual_safe != expected["safe"]:
            failures.append(
                f"Wrong safe value: expected '{expected['safe']}', got '{actual_safe}'"
            )

    if "source" in expected:
        actual_source = response_data.get("source")
        if actual_source != expected["source"]:
            failures.append(
                f"Wrong source value: expected '{expected['source']}', got '{actual_source}'"
            )

    if "min_event_count" in expected:
        actual_count = len(events)
        if actual_count < expected["min_event_count"]:
            failures.append(
                f"Too few events: expected at least {expected['min_event_count']}, got {actual_count}"
            )

    passed = len(failures) == 0
    return passed, failures