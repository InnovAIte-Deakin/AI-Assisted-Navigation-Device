import math
from io import StringIO

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from predictive_path.predictive_path import SAFE_LABEL, RISKY_LABELS
from predictive_path.train_model import retrain_from_dataframe


router = APIRouter()

ALLOWED_LABELS = {SAFE_LABEL, *RISKY_LABELS}

# Must match the test_size used by retrain_from_dataframe's train_test_split.
TEST_SIZE = 0.2

# train_test_split(..., stratify=...) requires at least 2 samples per class.
MIN_SAMPLES_PER_LABEL = 2


class RetrainRequest(BaseModel):
    csv_data: str


@router.post("/retrain")
def retrain_model(body: RetrainRequest):
    try:
        df = pd.read_csv(StringIO(body.csv_data))

        required_columns = [
            "speed",
            "heading",
            "gyro",
            "risk_label"
        ]

        missing_columns = [
            column for column in required_columns
            if column not in df.columns
        ]

        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Missing columns: {missing_columns}"
            )

        if len(df) < 10:
            raise HTTPException(
                status_code=400,
                detail="At least 10 samples are required for retraining"
            )

        bad_labels = sorted(set(df["risk_label"]) - ALLOWED_LABELS)
        if bad_labels:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unexpected risk_label values: {bad_labels}. "
                    f"Allowed: {sorted(ALLOWED_LABELS)}"
                )
            )

        label_counts = df["risk_label"].value_counts()
        sparse_labels = label_counts[label_counts < MIN_SAMPLES_PER_LABEL]
        if not sparse_labels.empty:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Each risk_label needs at least {MIN_SAMPLES_PER_LABEL} samples; "
                    f"too few: {sparse_labels.to_dict()}"
                )
            )

        # The stratified split needs a test partition large enough to hold at
        # least one sample of every class, or train_test_split raises.
        n_classes_present = len(label_counts)
        n_test = math.ceil(TEST_SIZE * len(df))
        if n_test < n_classes_present:
            min_required = math.ceil(n_classes_present / TEST_SIZE)
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Not enough samples for {n_classes_present} distinct risk_label "
                    f"values; at least {min_required} total samples are required"
                )
            )

        accuracy = retrain_from_dataframe(df)

        return {
            "success": True,
            "accuracy": accuracy
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Retraining failed: {str(e)}"
        )
