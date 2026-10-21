"""Summarize saved evidence without inference, training, downloads, or model loading.

Run from the repository root: python -m ML_side.tools.build_interview_evidence
JSON/CSV work without plotting libraries. --chart uses an existing matplotlib.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = "ML_side/model_registry/records/navigation_candidate.json"
METRICS = ("precision", "recall", "mAP50", "mAP50_95")


class EvidenceError(ValueError):
    """Saved evidence is missing, malformed, or inconsistent."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_sha256(path: Path) -> str:
    """Fingerprint text consistently across Git's CRLF/LF checkout conversion.

    Model artifacts use sha256() instead, retaining exact binary byte identity.
    """
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def metric(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise EvidenceError(f"Metric must be a finite fraction in [0, 1]: {value!r}")
    return float(value)


def summarize_evaluation(registry: dict, summary: dict) -> dict:
    """Validate identity before interpreting saved metrics; never invent aggregate F1."""
    expected = registry["artifact"]["sha256"]
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise EvidenceError("Registry requires a lowercase artifact SHA-256.")
    if summary["model"]["sha256"] != expected:
        raise EvidenceError("Recorded evaluation and registry artifact SHA-256 differ.")
    names = registry["taxonomy"]["classes"]
    if (not isinstance(names, list) or not names
            or not all(isinstance(name, str) and name for name in names)
            or len(set(names)) != len(names) or summary["model"]["ordered_class_names"] != names):
        raise EvidenceError("Recorded evaluation and registry ordered taxonomies differ.")
    values = summary["validation_metrics"]
    if summary.get("results", {}).get("validation_metrics") != values:
        raise EvidenceError("Evaluation metric copies disagree.")
    if summary.get("mode") != "labelled_validation" or summary.get("dataset_split") != "test":
        raise EvidenceError("Expected the registry-linked labelled held-out test evidence.")
    count = values["validation_image_count"]
    if type(count) is not int or count < 1:
        raise EvidenceError("Recorded held-out image count must be a positive integer.")
    per_class = values["per_class_results"]
    if set(per_class) != {str(index) for index in range(len(names))}:
        raise EvidenceError("Recorded per-class metric coverage is incomplete.")
    rows = []
    for index, name in enumerate(names):
        row = per_class[str(index)]
        if row["class_name"] != name:
            raise EvidenceError("Per-class metric identity disagrees with ordered taxonomy.")
        measured = {key: metric(row[key]) for key in METRICS}
        p, r = measured["precision"], measured["recall"]
        rows.append({"class_id": index, "class_name": name, **measured,
                     "derived_f1_from_recorded_pr": 2 * p * r / (p + r) if p + r else None})
    return {
        "evidence_kind": "historical_recorded_labelled_evaluation_not_rerun",
        "created_at_utc": summary.get("created_at_utc"),
        "model_sha256": expected,
        "split": summary["dataset_split"],
        "image_count": count,
        "aggregate_recorded_metrics": {key: metric(values[key]) for key in METRICS},
        "aggregate_f1": None,
        "aggregate_f1_reason": "No aggregate F1 was recorded. Micro F1 requires TP/FP/FN; support-weighted F1 requires class support. Neither is available.",
        "derived_macro_f1_from_recorded_class_pr": (
            sum(row["derived_f1_from_recorded_pr"] for row in rows) / len(rows)
            if all(row["derived_f1_from_recorded_pr"] is not None for row in rows) else None
        ),
        "derived_macro_f1_semantics": "Unweighted mean of the supplied per-class derived F1 values; not a recorded aggregate measurement or runtime warning score.",
        "per_class": rows,
        "settings_as_recorded": summary.get("evaluation_settings"),
        "provenance_not_recorded": ["dataset content digest", "dataset release ID in the evaluator summary",
                                    "per-class instance support", "TP/FP/FN", "evaluation seed",
                                    "evaluation environment versions", "runtime warning operating-point accuracy"],
        "f1_semantics": "Algebraic per-class 2PR/(P+R) from saved evaluator P/R (null if denominator zero); not measured at the runtime 0.5 warning threshold.",
    }


def verify_local_artifact(expected: str, path: Path | None) -> dict:
    if path is None:
        return {"status": "NOT_CHECKED", "reason": "No local model supplied; metadata evidence only."}
    if not path.is_file():
        return {"status": "NOT_CHECKED", "reason": "Requested local model is unavailable; no download attempted."}
    actual = sha256(path)
    return {"status": "MATCH" if actual == expected else "MISMATCH", "filename": path.name,
            "sha256": actual, "size_bytes": path.stat().st_size,
            "scope": "Bytes only; no model loaded, backend launch or live deployment identity checked."}


def repository_file(root: Path, reference: str) -> Path:
    path = (root / reference).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise EvidenceError(f"Repository evidence is unavailable or outside root: {reference}")
    return path


def safety_probes(root: Path) -> list[dict]:
    """Exercise the real pure gate with explicitly synthetic events, without slow_lane startup."""
    backend = root / "software_side/walkbuddy_reactNative/backend"
    added = str(backend) not in sys.path
    if added:
        sys.path.insert(0, str(backend))
    try:
        from ml_contract.navigation_semantics import NAVIGATION_CLASSES
        spec = importlib.util.spec_from_file_location("interview_safety_gate", backend / "slow_lane/safetygate.py")
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        cases = [(f"canonical-{item.name}", {"label": item.name, "direction": "ahead", "confidence": 0.9}, True)
                 for item in NAVIGATION_CLASSES]
        cases += [
            ("stairs-below-warning-threshold", {"label": "stairs", "direction": "ahead", "confidence": 0.499}, False),
            ("stairs-at-warning-threshold", {"label": "stairs", "direction": "ahead", "confidence": 0.5}, True),
            ("stairs-to-left", {"label": "stairs", "direction": "left", "confidence": 0.9}, False),
            ("chair-alias", {"label": "office-chair", "direction": "ahead", "confidence": 0.9}, True),
            ("unsupported-stationary-pothole", {"label": "pothole", "direction": "ahead", "confidence": 0.99}, False),
            ("unknown-approaching", {"label": "unknown", "direction": "ahead", "confidence": 0.9, "approaching": True}, True),
        ]
        return [{"case_id": name, "evidence_kind": "synthetic_contract_probe", "input": event,
                 "expected_stop_under_current_gate": expected,
                 "observed_stop": bool(response := gate.safe_or_stop_recommendation([event])),
                 "response": response, "matches_current_gate": bool(response) == expected}
                for name, event, expected in cases]
    finally:
        if added:
            sys.path.remove(str(backend))


def build_report(root: Path, model_path: Path | None) -> dict:
    registry_path = repository_file(root, REGISTRY)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    evaluation_path = repository_file(root, registry["evaluation"]["evidence_reference"])
    summary = json.loads(evaluation_path.read_text(encoding="utf-8"))
    evaluation = summarize_evaluation(registry, summary)
    sources = {REGISTRY: source_sha256(registry_path), registry["evaluation"]["evidence_reference"]: source_sha256(evaluation_path)}
    training_reference = registry["training"]["configuration_reference"]
    training_path = repository_file(root, training_reference)
    sources[training_reference] = source_sha256(training_path)
    try:
        import yaml
        training = yaml.safe_load(training_path.read_text(encoding="utf-8"))
        training_config = {"evidence_kind": "committed_configuration_not_training_rerun",
                           "settings": training["training"], "initial_weights_reference": training["model"]["initial_weights_path"]}
    except ImportError:
        training_config = {"status": "NOT_CHECKED", "reason": "PyYAML not installed; original configuration still fingerprinted."}
    historical = []
    for path in sorted((root / "ML_side/experiments/cohort-1").glob("*/results.csv")):
        with path.open(encoding="utf-8-sig", newline="") as source:
            rows = list(csv.DictReader(source))
        if not rows:
            raise EvidenceError(f"Empty historical log: {path.name}")
        final = rows[-1]
        historical.append({"run": path.parent.name, "logged_epochs": len(rows), "final_epoch": int(final["epoch"]),
                           **{key: metric(float(final[f"metrics/{'mAP50-95' if key == 'mAP50_95' else key}(B)"])) for key in METRICS},
                           "model_sha256": None, "evidence_kind": "historical_final_epoch_csv_not_current_weights"})
        sources[path.relative_to(root).as_posix()] = source_sha256(path)
        args = repository_file(root, path.parent.relative_to(root).as_posix() + "/args.yaml")
        sources[args.relative_to(root).as_posix()] = source_sha256(args)
    for reference in ("software_side/walkbuddy_reactNative/backend/slow_lane/safetygate.py",
                      "software_side/walkbuddy_reactNative/backend/routers/ai_service.py",
                      "software_side/walkbuddy_reactNative/backend/adapters/vision_adapter.py",
                      "software_side/walkbuddy_reactNative/backend/ml_contract/navigation_semantics.py",
                      "ML_side/tools/inspect_candidate_dataset.py",
                      "ML_side/tools/build_interview_evidence.py"):
        sources[reference] = source_sha256(repository_file(root, reference))
    return {"schema_version": "1.0.0", "tool": "build_interview_evidence", "network_access": False,
            "model_inference_performed": False, "source_sha256": sources,
            "source_hash_semantics": "SHA-256 of text bytes with CRLF normalized to LF; model artifact hashes use exact bytes.",
            "registry_model_id": registry["model_id"], "registry_lifecycle": registry["lifecycle"]["status"],
            "registry_dataset_release_claim": registry["dataset"]["release_id"],
            "dataset_integrity": {"status": "NOT_CHECKED", "reason": "No controlled dataset supplied to this evidence summarizer; no real duplicate/coverage counts claimed."},
            "local_artifact": verify_local_artifact(evaluation["model_sha256"], model_path),
            "recorded_evaluation": evaluation, "training_configuration": training_config,
            "historical_experiment_final_rows": historical, "safety_gate_probes": safety_probes(root),
            "live_mobile_or_backend_test": "NOT_CHECKED"}


def write_outputs(report: dict, output: Path, chart: bool) -> None:
    output.mkdir(parents=True, exist_ok=True)
    rows = report["recorded_evaluation"]["per_class"]
    with (output / "recorded_per_class_metrics.csv").open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report["chart"] = {"status": "NOT_REQUESTED"}
    if chart:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            report["chart"] = {"status": "NOT_CHECKED", "reason": "matplotlib unavailable; no installation attempted."}
        else:
            fig, ax = plt.subplots(figsize=(10, 5.4))
            positions = list(range(len(rows)))
            for offset, key, label, color in [(-0.24, "precision", "Precision", "#244b72"),
                                               (0, "recall", "Recall", "#568a70"),
                                               (0.24, "mAP50_95", "AP@50:95", "#c68135")]:
                ax.bar([x + offset for x in positions], [row[key] for row in rows], width=0.24, label=label, color=color)
            ax.set_xticks(positions, [row["class_name"] for row in rows])
            ax.set_ylim(0, 1)
            ax.set_ylabel("Recorded fraction")
            evaluation = report["recorded_evaluation"]
            recorded_date = str(evaluation["created_at_utc"] or "date not recorded")[:10]
            ax.set_title(f"Saved held-out evaluation: {recorded_date} · {evaluation['image_count']:,} images")
            ax.legend(loc="upper right")
            ax.grid(axis="y", alpha=0.2)
            ax.set_axisbelow(True)
            fig.text(0.5, 0.01, f"{report['registry_model_id']} · Historical metrics, no inference rerun · Runtime warning accuracy not measured", ha="center", fontsize=9)
            fig.tight_layout(rect=(0, 0.04, 1, 1))
            fig.savefig(output / "recorded_per_class_metrics.png", dpi=160)
            plt.close(fig)
            report["chart"] = {"status": "GENERATED", "source": "recorded_evaluation.per_class", "filename": "recorded_per_class_metrics.png"}
    (output / "interview_evidence.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("docs/interview/evidence"))
    parser.add_argument("--model", type=Path, help="Optional local weights: hash bytes only, never load the model.")
    parser.add_argument("--chart", action="store_true", help="Create PNG with an already-installed matplotlib.")
    args = parser.parse_args(argv)
    try:
        report = build_report(ROOT, args.model)
        write_outputs(report, args.output_dir, args.chart)
    except (EvidenceError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Interview evidence failed: {exc}", file=sys.stderr)
        return 1
    print(f"Recorded evidence summarized; local artifact: {report['local_artifact']['status']}; "
          f"synthetic gate probes: {len(report['safety_gate_probes'])}.")
    return 1 if report["local_artifact"]["status"] == "MISMATCH" or any(not row["matches_current_gate"] for row in report["safety_gate_probes"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
