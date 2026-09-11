"""
Router-isolated unit tests for POST /retrain (predictive_path/retrain_router.py).

Validation-failure cases short-circuit before touching the model, so they
never need real training. The success-path test does call
retrain_from_dataframe for real, which writes predictive_path_model.pkl /
label_encoder.pkl -- the `preserve_model_files` fixture backs those up and
restores them afterward so the test doesn't clobber the committed model
artifacts with one trained on synthetic test data.

Run from the backend directory:
    pytest tests/test_retrain_router.py -v
"""

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from predictive_path import retrain_router, train_model


def _build_app():
    app = FastAPI()
    app.include_router(retrain_router.router)
    return app


@pytest.fixture
def preserve_model_files():
    """Back up and restore the real model/encoder files around a test that
    actually retrains, so the committed artifacts aren't left overwritten
    with a model trained on synthetic test data."""
    model_dir = os.path.dirname(train_model.__file__)
    paths = [
        os.path.join(model_dir, "predictive_path_model.pkl"),
        os.path.join(model_dir, "label_encoder.pkl"),
    ]
    originals = {}
    for path in paths:
        with open(path, "rb") as f:
            originals[path] = f.read()

    try:
        yield
    finally:
        for path, data in originals.items():
            with open(path, "wb") as f:
                f.write(data)


def _csv(rows):
    header = "speed,heading,gyro,risk_label"
    body = "\n".join(f"{s},{h},{g},{label}" for s, h, g, label in rows)
    return f"{header}\n{body}"


BALANCED_ROWS = (
    [(1.0 + 0.1 * i, 10.0 + i, 0.05, "safe") for i in range(4)]
    + [(1.5 + 0.1 * i, 40.0 + i, 0.2, "front") for i in range(4)]
    + [(1.2 + 0.1 * i, 70.0 + i, 0.15, "front_right") for i in range(4)]
)


def test_retrain_rejects_missing_columns():
    client = TestClient(_build_app())
    resp = client.post("/retrain", json={"csv_data": "speed,heading,gyro\n1,2,3"})

    assert resp.status_code == 400
    assert "Missing columns" in resp.json()["detail"]


def test_retrain_rejects_too_few_samples():
    client = TestClient(_build_app())
    csv = _csv(BALANCED_ROWS[:5])

    resp = client.post("/retrain", json={"csv_data": csv})

    assert resp.status_code == 400
    assert "at least 10 samples" in resp.json()["detail"].lower()


def test_retrain_rejects_unexpected_label_values():
    client = TestClient(_build_app())
    rows = BALANCED_ROWS[:-1] + [(1.0, 5.0, 0.05, "unknown")]
    csv = _csv(rows)

    resp = client.post("/retrain", json={"csv_data": csv})

    assert resp.status_code == 400
    assert "Unexpected risk_label values" in resp.json()["detail"]
    assert "unknown" in resp.json()["detail"]


def test_retrain_rejects_class_with_too_few_samples():
    client = TestClient(_build_app())
    # 10 rows, but only 1 "front_right" sample -- previously raised an
    # uncaught ValueError from train_test_split(..., stratify=...).
    rows = [(1.0 + 0.1 * i, 10.0 + i, 0.05, "safe" if i % 2 == 0 else "front") for i in range(9)]
    rows.append((2.0, 90.0, 0.3, "front_right"))
    csv = _csv(rows)

    resp = client.post("/retrain", json={"csv_data": csv})

    assert resp.status_code == 400
    assert "at least 2 samples" in resp.json()["detail"]
    assert "front_right" in resp.json()["detail"]


def test_retrain_rejects_too_few_samples_for_class_count():
    client = TestClient(_build_app())
    # 10 rows, every class has >= 2 samples, but a 0.2 test split of 10 rows
    # (2 rows) can't hold a representative of all 3 classes -- previously
    # raised an uncaught ValueError from train_test_split(..., stratify=...).
    rows = (
        [(1.0 + 0.1 * i, 10.0 + i, 0.05, "safe") for i in range(6)]
        + [(1.5, 40.0, 0.2, "front"), (1.6, 41.0, 0.2, "front")]
        + [(1.2, 70.0, 0.15, "front_right"), (1.3, 71.0, 0.15, "front_right")]
    )
    csv = _csv(rows)

    resp = client.post("/retrain", json={"csv_data": csv})

    assert resp.status_code == 400
    assert "Not enough samples" in resp.json()["detail"]


def test_retrain_succeeds_with_balanced_data(preserve_model_files):
    client = TestClient(_build_app())
    csv = _csv(BALANCED_ROWS)

    resp = client.post("/retrain", json={"csv_data": csv})

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert 0.0 <= body["accuracy"] <= 1.0
