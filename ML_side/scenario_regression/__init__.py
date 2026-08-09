"""Offline scenario-level regression evaluation for WalkBuddy detections."""

from .evaluator import (
    APPROVED_TAXONOMY,
    SCHEMA_VERSION,
    TOOL_NAME,
    TOOL_VERSION,
    ScenarioRegressionError,
    evaluate_suite,
    load_case_suite,
    load_prediction_fixture,
    run_fixture_evaluation,
)

__all__ = [
    "APPROVED_TAXONOMY",
    "SCHEMA_VERSION",
    "TOOL_NAME",
    "TOOL_VERSION",
    "ScenarioRegressionError",
    "evaluate_suite",
    "load_case_suite",
    "load_prediction_fixture",
    "run_fixture_evaluation",
]
