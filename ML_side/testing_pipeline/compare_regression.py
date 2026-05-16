import argparse
import json
from pathlib import Path


def load_summary(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def pass_rate(summary):
    total = summary.get("total_cases", 0)

    if total == 0:
        return 0.0

    passed = summary.get("passed_cases", 0)
    return passed / total


def result_map(summary):
    results = summary.get("results", [])
    return {item["case_name"]: item for item in results}


def compare_summaries(previous, current):
    previous_rate = pass_rate(previous)
    current_rate = pass_rate(current)

    previous_results = result_map(previous)
    current_results = result_map(current)

    fixed_cases = []
    broken_cases = []
    still_failed_cases = []
    still_passed_cases = []
    new_cases = []
    removed_cases = []

    previous_names = set(previous_results.keys())
    current_names = set(current_results.keys())

    for case_name in sorted(current_names - previous_names):
        new_cases.append(case_name)

    for case_name in sorted(previous_names - current_names):
        removed_cases.append(case_name)

    for case_name in sorted(previous_names & current_names):
        previous_passed = previous_results[case_name].get("passed", False)
        current_passed = current_results[case_name].get("passed", False)

        if previous_passed is True and current_passed is True:
            still_passed_cases.append(case_name)

        if previous_passed is False and current_passed is False:
            still_failed_cases.append(case_name)

        if previous_passed is False and current_passed is True:
            fixed_cases.append(case_name)

        if previous_passed is True and current_passed is False:
            broken_cases.append(case_name)

    regression_detected = len(broken_cases) > 0 or current_rate < previous_rate

    return {
        "previous_pass_rate": round(previous_rate, 4),
        "current_pass_rate": round(current_rate, 4),
        "previous_passed_cases": previous.get("passed_cases", 0),
        "current_passed_cases": current.get("passed_cases", 0),
        "previous_failed_cases": previous.get("failed_cases", 0),
        "current_failed_cases": current.get("failed_cases", 0),
        "fixed_cases": fixed_cases,
        "broken_cases": broken_cases,
        "still_failed_cases": still_failed_cases,
        "still_passed_cases": still_passed_cases,
        "new_cases": new_cases,
        "removed_cases": removed_cases,
        "regression_detected": regression_detected
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--output", default="testing_pipeline/results/summaries/regression_report.json")
    args = parser.parse_args()

    previous = load_summary(args.previous)
    current = load_summary(args.current)

    report = compare_summaries(previous, current)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== Regression Test Report ===")
    print(f"Previous pass rate: {report['previous_pass_rate']}")
    print(f"Current pass rate: {report['current_pass_rate']}")
    print(f"Previous passed cases: {report['previous_passed_cases']}")
    print(f"Current passed cases: {report['current_passed_cases']}")
    print(f"Previous failed cases: {report['previous_failed_cases']}")
    print(f"Current failed cases: {report['current_failed_cases']}")
    print(f"Fixed cases: {len(report['fixed_cases'])}")
    print(f"Broken cases: {len(report['broken_cases'])}")
    print(f"Still failed cases: {len(report['still_failed_cases'])}")
    print(f"Still passed cases: {len(report['still_passed_cases'])}")
    print(f"New cases: {len(report['new_cases'])}")
    print(f"Removed cases: {len(report['removed_cases'])}")
    print(f"Regression detected: {report['regression_detected']}")
    print(f"Report saved to: {output_path}")

    if report["broken_cases"]:
        print()
        print("Broken cases:")
        for case_name in report["broken_cases"]:
            print(f"- {case_name}")

    if report["fixed_cases"]:
        print()
        print("Fixed cases:")
        for case_name in report["fixed_cases"]:
            print(f"- {case_name}")


if __name__ == "__main__":
    main()