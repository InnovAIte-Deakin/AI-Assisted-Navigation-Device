import argparse
import json
from pathlib import Path

import requests

from evaluate_case import evaluate_case
from save_failure_log import save_failure_log


def load_case(case_path: Path):
    return json.loads(case_path.read_text(encoding="utf-8"))


def call_api(base_url: str, case_data: dict):
    endpoint = case_data["endpoint"]
    image_path = Path(case_data["image"])

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    url = f"{base_url}/{endpoint}"

    with image_path.open("rb") as f:
        files = {"file": (image_path.name, f, "image/png")}

        if endpoint == "two_brain":
            question = case_data.get("question", "What is in front of me?")
            response = requests.post(
                url,
                files=files,
                data={"question": question},
                timeout=120,
            )
        else:
            response = requests.post(
                url,
                files=files,
                timeout=120,
            )

    response.raise_for_status()
    return response.json()


def save_raw_json(case_name: str, response_data: dict, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{case_name}.json"
    path.write_text(json.dumps(response_data, indent=2), encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--cases-dir", default="testing_pipeline/cases")
    parser.add_argument("--results-dir", default="testing_pipeline/results")
    args = parser.parse_args()

    cases_dir = Path(args.cases_dir)
    results_dir = Path(args.results_dir)

    raw_json_dir = results_dir / "raw_json"
    failure_logs_dir = results_dir / "failure_logs"
    summaries_dir = results_dir / "summaries"

    case_files = sorted(cases_dir.glob("*.json"))
    if not case_files:
        raise RuntimeError(f"No case files found in {cases_dir}")

    summary = {
        "total_cases": 0,
        "passed_cases": 0,
        "failed_cases": 0,
        "results": [],
    }

    for case_path in case_files:
        case_data = load_case(case_path)
        case_name = case_data["name"]

        print(f"Running case: {case_name}")

        try:
            response_data = call_api(args.base_url, case_data)
            save_raw_json(case_name, response_data, raw_json_dir)

            passed, failures = evaluate_case(case_data, response_data)

            result = {
                "case_name": case_name,
                "passed": passed,
                "failures": failures,
            }

            if not passed:
                failure_log_path = save_failure_log(
                    case_name=case_name,
                    case_data=case_data,
                    response_data=response_data,
                    failures=failures,
                    output_dir=failure_logs_dir,
                )
                result["failure_log"] = str(failure_log_path)

            summary["results"].append(result)
            summary["total_cases"] += 1

            if passed:
                summary["passed_cases"] += 1
                print("PASS")
            else:
                summary["failed_cases"] += 1
                print("FAIL")
                for failure in failures:
                    print(f"  - {failure}")

        except Exception as e:
            summary["total_cases"] += 1
            summary["failed_cases"] += 1

            result = {
                "case_name": case_name,
                "passed": False,
                "failures": [f"Runtime error: {str(e)}"],
            }
            summary["results"].append(result)

            print("FAIL")
            print(f"  - Runtime error: {e}")

    summaries_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summaries_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print()
    print(f"Finished. Summary saved to: {summary_path}")
    print(f"Passed: {summary['passed_cases']}")
    print(f"Failed: {summary['failed_cases']}")


if __name__ == "__main__":
    main()