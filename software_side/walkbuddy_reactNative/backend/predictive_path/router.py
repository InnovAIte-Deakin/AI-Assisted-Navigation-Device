from fastapi import APIRouter
from pydantic import BaseModel
from internal import state

router = APIRouter(prefix="/predict-path")

class SensorInput(BaseModel):
    speed: float
    heading: float
    gyro: float

@router.post("")
def predict(body: SensorInput):
    from predictive_path.predictive_path import PredictivePathSystem
    system = PredictivePathSystem(dt=0.5, steps=5)
    report = system.run(body.speed, body.heading, body.gyro)
    if report["overall_risk"] == "risky" and report["path"]:
        first = next((s for s in report["path"] if s["alert"]), None)
        if first:
            state.memory.add_event(
                label=first["risk_label"],
                direction="ahead" if first["risk_label"] == "front" else "right",
                distance_m=first["distance"],
                confidence=first["confidence"],
            )
    return {
        "overall_risk": report["overall_risk"],
        "first_alert": report["first_alert"],
        "alerts": report["alerts"]
    }
