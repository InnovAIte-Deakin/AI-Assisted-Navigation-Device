"""CLI entry point for offline WalkBuddy scenario-regression fixture replay."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence


ML_SIDE_DIR = Path(__file__).resolve().parents[1]
if str(ML_SIDE_DIR) not in sys.path:
    sys.path.insert(0, str(ML_SIDE_DIR))

from scenario_regression.evaluator import ScenarioRegressionError, run_fixture_evaluation


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay normalized local detections against WalkBuddy navigation scenarios without a server or model loading."
    )
    parser.add_argument("--cases", required=True, help="Versioned scenario-suite JSON file.")
    parser.add_argument("--predictions", required=True, help="Versioned normalized-prediction fixture JSON file.")
    parser.add_argument("--output", required=True, help="External directory for scenario_evaluation JSON and Markdown reports.")
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.0,
        help="Optional detector operating threshold from 0 to 1; it is not a navigation-risk policy.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Allow replacement of reports in a non-empty output directory.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run_fixture_evaluation(
            case_suite_path=args.cases,
            prediction_fixture_path=args.predictions,
            output_path=args.output,
            confidence_threshold=args.confidence_threshold,
            overwrite=args.overwrite,
        )
    except ScenarioRegressionError as exc:
        print(f"Scenario evaluation failed: {exc}", file=sys.stderr)
        return 1
    aggregate = report["aggregate"]
    assert isinstance(aggregate, dict)
    print(
        "Scenario evaluation complete: "
        f"{aggregate['scenarios_passed']}/{aggregate['scenario_count']} scenarios passed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
