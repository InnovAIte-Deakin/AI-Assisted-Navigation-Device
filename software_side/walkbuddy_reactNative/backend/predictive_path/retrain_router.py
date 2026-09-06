from io import StringIO

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from predictive_path.train_model import retrain_from_dataframe


router = APIRouter()


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