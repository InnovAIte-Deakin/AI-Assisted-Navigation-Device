import json
from pathlib import Path
from datetime import datetime


def save_failure_log(case_name: str, case_data: dict, response_data: dict, failures: list, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"{case_name}_{timestamp}.json"

    payload = {
        "case_name": case_name,
        "timestamp": timestamp,
        "case_data": case_data,
        "response_data": response_data,
        "failures": failures,
    }

    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path