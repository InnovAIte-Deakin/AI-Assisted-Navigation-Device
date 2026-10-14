"""Ensure interview claims fail on inconsistent provenance and missing evidence."""
import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_interview_evidence as evidence


@pytest.fixture
def recorded():
    # All values are synthetic, deliberately unrelated to WalkBuddy's measurements.
    registry = {"artifact": {"sha256": "a" * 64}, "taxonomy": {"classes": ["person"]}}
    metrics = {"precision": 0.75, "recall": 0.5, "mAP50": 0.6, "mAP50_95": 0.3,
               "validation_image_count": 2, "per_class_results": {
                   "0": {"class_name": "person", "precision": 0.75, "recall": 0.5, "mAP50": 0.6, "mAP50_95": 0.3}}}
    summary = {"mode": "labelled_validation", "dataset_split": "test", "model": {
        "sha256": "a" * 64, "ordered_class_names": ["person"]}, "validation_metrics": metrics,
        "results": {"validation_metrics": copy.deepcopy(metrics)}}
    return registry, summary


def test_f1_is_derived_per_class_and_aggregate_is_unavailable(recorded):
    report = evidence.summarize_evaluation(*recorded)
    assert report["per_class"][0]["derived_f1_from_recorded_pr"] == pytest.approx(0.6)
    assert report["derived_macro_f1_from_recorded_class_pr"] == pytest.approx(0.6)
    assert report["aggregate_f1"] is None
    assert report["evidence_kind"] == "historical_recorded_labelled_evaluation_not_rerun"
    assert "not measured at the runtime" in report["f1_semantics"]


def test_evaluation_for_different_weights_is_rejected(recorded):
    recorded[1]["model"]["sha256"] = "b" * 64
    with pytest.raises(evidence.EvidenceError, match="SHA-256 differ"):
        evidence.summarize_evaluation(*recorded)


def test_metric_copies_cannot_silently_disagree(recorded):
    recorded[1]["results"]["validation_metrics"]["precision"] = 0.99
    with pytest.raises(evidence.EvidenceError, match="copies disagree"):
        evidence.summarize_evaluation(*recorded)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.1, 1.1, True, "0.9"])
def test_invalid_metric_values_are_rejected(recorded, value):
    for key in ("validation_metrics",):
        recorded[1][key]["precision"] = value
    recorded[1]["results"]["validation_metrics"] = recorded[1]["validation_metrics"]
    with pytest.raises(evidence.EvidenceError, match="finite fraction"):
        evidence.summarize_evaluation(*recorded)


def test_class_identity_mismatch_is_rejected(recorded):
    recorded[1]["validation_metrics"]["per_class_results"]["0"]["class_name"] = "stairs"
    recorded[1]["results"]["validation_metrics"] = recorded[1]["validation_metrics"]
    with pytest.raises(evidence.EvidenceError, match="class metric identity"):
        evidence.summarize_evaluation(*recorded)


def test_zero_f1_denominator_is_explicitly_unavailable(recorded):
    row = recorded[1]["validation_metrics"]["per_class_results"]["0"]
    row.update(precision=0, recall=0)
    recorded[1]["results"]["validation_metrics"] = recorded[1]["validation_metrics"]
    report = evidence.summarize_evaluation(*recorded)
    assert report["per_class"][0]["derived_f1_from_recorded_pr"] is None
    assert report["derived_macro_f1_from_recorded_class_pr"] is None


def test_local_weights_are_hashed_without_loading_and_missing_is_not_checked(tmp_path):
    model = tmp_path / "synthetic.pt"
    model.write_bytes(b"not a model, only a checksum fixture")
    expected = hashlib.sha256(model.read_bytes()).hexdigest()
    assert evidence.verify_local_artifact(expected, model)["status"] == "MATCH"
    assert evidence.verify_local_artifact("0" * 64, model)["status"] == "MISMATCH"
    assert evidence.verify_local_artifact(expected, tmp_path / "absent.pt")["status"] == "NOT_CHECKED"
    assert evidence.verify_local_artifact(expected, None)["status"] == "NOT_CHECKED"


def test_source_fingerprints_are_portable_but_model_hashes_retain_exact_bytes(tmp_path):
    lf = tmp_path / "lf.txt"
    crlf = tmp_path / "crlf.txt"
    lf.write_bytes(b"first\nsecond\n")
    crlf.write_bytes(b"first\r\nsecond\r\n")
    assert evidence.source_sha256(lf) == evidence.source_sha256(crlf)
    assert evidence.sha256(lf) != evidence.sha256(crlf)


def test_offline_report_does_not_claim_current_measurements_or_real_data_audit(tmp_path):
    report = evidence.build_report(evidence.ROOT, None)
    assert report["model_inference_performed"] is False
    assert report["dataset_integrity"]["status"] == "NOT_CHECKED"
    assert report["live_mobile_or_backend_test"] == "NOT_CHECKED"
    assert len(report["safety_gate_probes"]) == 14
    assert all(row["matches_current_gate"] for row in report["safety_gate_probes"])
    assert all(row["evidence_kind"] == "synthetic_contract_probe" for row in report["safety_gate_probes"])
    evidence.write_outputs(report, tmp_path / "one", False)
    evidence.write_outputs(report, tmp_path / "two", False)
    assert (tmp_path / "one/interview_evidence.json").read_bytes() == (tmp_path / "two/interview_evidence.json").read_bytes()
    saved = json.loads((tmp_path / "one/interview_evidence.json").read_text())
    assert saved["local_artifact"]["status"] == "NOT_CHECKED"


def test_missing_repository_evidence_has_no_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(evidence, "ROOT", tmp_path)
    assert evidence.main(["--output-dir", str(tmp_path / "reports")]) == 1
    assert "Repository evidence is unavailable" in capsys.readouterr().err
