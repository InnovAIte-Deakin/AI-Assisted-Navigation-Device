import argparse
import json
from pathlib import Path
from collections import defaultdict
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
            response = requests.post(url, files=files, data={"question": question}, timeout=120)
        else:
            response = requests.post(url, files=files, timeout=120)

    response.raise_for_status()
    return response.json()

def save_raw_json(case_name: str, response_data: dict, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{case_name}.json"
    path.write_text(json.dumps(response_data, indent=2), encoding="utf-8")
    return path

def main():
    current_dir = Path(__file__).parent

    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--cases-dir", type=Path, default=current_dir / "cases")
    parser.add_argument("--results-dir", type=Path, default=current_dir / "results")
    parser.add_argument("--confidence", type=float, default=0.5, help="Minimum confidence threshold")
    args = parser.parse_args()

    print(f"Checking API connection at {args.base_url}...")
    try:
        requests.get(f"{args.base_url}/docs", timeout=5) 
        print(f"API is online. Starting tests with Confidence Threshold: {args.confidence}...\n")
    except requests.exceptions.ConnectionError:
        print(f"CRITICAL ERROR: Cannot connect to API.")
        return

    cases_dir = args.cases_dir
    results_dir = args.results_dir

    raw_json_dir = results_dir / "raw_json"
    failure_logs_dir = results_dir / "failure_logs"
    summaries_dir = results_dir / "summaries"

    case_files = sorted(cases_dir.glob("*.json"))
    if not case_files:
        raise RuntimeError(f"No case files found in {cases_dir}")

    global_errors = defaultdict(list)
    
    # Global Metrics Tracking
    total_tp = 0
    total_fp = 0
    total_fn = 0

    summary = {
        "global_threshold_used": args.confidence,
        "total_cases": 0,
        "passed_cases": 0,
        "failed_cases": 0,
        "metrics": {},
        "error_breakdown": {},
        "results": [],
    }

    for case_path in case_files:
        case_data = load_case(case_path)
        case_name = case_data["name"]

        print(f"Running case: {case_name}")

        try:
            response_data = call_api(args.base_url, case_data)
            save_raw_json(case_name, response_data, raw_json_dir)

            passed, errors, stats = evaluate_case(case_data, response_data, args.confidence)

            # Accumulate global true/false positives and negatives
            total_tp += stats["TP"]
            total_fp += stats["FP"]
            total_fn += stats["FN"]

            result = {
                "case_name": case_name,
                "passed": passed,
                "stats": stats,
                "errors": errors,
            }

            print(f"  > Detected {stats['raw_count']} objects → {stats['filtered_count']} after filtering")

            if not passed:
                failure_log_path = save_failure_log(
                    case_name=case_name,
                    case_data=case_data,
                    response_data=response_data,
                    failures=errors, 
                    stats=stats,
                    output_dir=failure_logs_dir,
                )
                result["failure_log"] = str(failure_log_path)

            summary["results"].append(result)
            summary["total_cases"] += 1

            if passed:
                summary["passed_cases"] += 1
                print("  > PASS\n")
            else:
                summary["failed_cases"] += 1
                print("  > FAIL")
                for err in errors:
                    print(f"    - [{err['type']}] {err['label']}: {err['reason']}")
                    global_errors[err['type']].append(err)
                print()

        except Exception as e:
            summary["total_cases"] += 1
            summary["failed_cases"] += 1
            print("  > FAIL")
            print(f"    - Runtime error: {e}\n")

    # --- Calculate Core ML Metrics ---
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    summary["metrics"] = {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1_score": round(f1_score, 3)
    }

    # Finalize Summary JSON
    summary["error_breakdown"] = {k: len(v) for k, v in global_errors.items()}
    summaries_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summaries_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # --- THE UPGRADED INTELLIGENCE REPORT ---
    print(f"=== TEST SUITE COMPLETE ===")
    print(f"Passed: {summary['passed_cases']} | Failed: {summary['failed_cases']}\n")
    
    print("--- Global ML Metrics ---")
    print(f"Precision: {precision:.3f} (When the model detected something, it was right {precision*100:.1f}% of the time)")
    print(f"Recall:    {recall:.3f} (The model found {recall*100:.1f}% of all the expected objects)")
    print(f"F1 Score:  {f1_score:.3f}\n")
    
    if global_errors:
        print("--- Error Intelligence Report ---")
        
        # Detail Low Confidence Drops
        if "Low Confidence Drop" in global_errors:
            print("Low Confidence Drops:")
            for e in global_errors["Low Confidence Drop"]:
                conf = e.get("confidence", 0)
                severity = "very low" if conf < 0.4 else "moderate"
                print(f"- {e['label']} ({conf:.3f}) → {severity} confidence")
            print()
            
        # Detail False Positives
        if "False Positive" in global_errors:
            print("False Positives (Hallucinations/Background):")
            for e in global_errors["False Positive"]:
                conf = e.get("confidence", 0)
                print(f"- {e['label']} ({conf:.3f})")
            print()

        # Print counts for the rest
        for err_type, err_list in global_errors.items():
            if err_type not in ["Low Confidence Drop", "False Positive"]:
                print(f"{err_type}: {len(err_list)}")
        
        print("\nDiagnostic:")
        top_error_type = max(global_errors, key=lambda k: len(global_errors[k]))
        
        if top_error_type == "Low Confidence Drop":
            labels = list(set([e['label'] for e in global_errors["Low Confidence Drop"]]))
            worst_label = labels[0] if labels else "objects"
            print(f"Primary failure is due to low-confidence detections, especially for '{worst_label}'.")
            print(f"\nAction:\nConsider lowering the threshold to recover moderate-confidence detections, or improve model training for consistently low-confidence objects like '{worst_label}'.")
        
        elif top_error_type == "False Positive":
            print("Primary failure is false positives, indicating the model is hallucinating or detecting excessive background noise.")
            print("\nAction:\nConsider raising the confidence threshold to filter out these untargeted detections.")
        
        else:
            print(f"Primary failure mode is '{top_error_type}'. Review logs for architectural or logic mismatches.")

if __name__ == "__main__":
    main()