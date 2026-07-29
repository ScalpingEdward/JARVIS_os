from fastapi import APIRouter
from app.schemas.recovery_reliability_stability_observation_v21_210 import StabilityObservationRequest, StabilityObservationDecision
from app.services.recovery_reliability_stability_observation_v21_210 import evaluate_stability

router = APIRouter(prefix='/recovery-reliability/v21.210', tags=['recovery-reliability-v21.210'])

@router.post('/stability/observe', response_model=StabilityObservationDecision)
def stability_observation(req: StabilityObservationRequest, human_approved: bool = False):
    return evaluate_stability(req, human_approved=human_approved)
