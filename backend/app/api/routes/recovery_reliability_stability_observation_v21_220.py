from fastapi import APIRouter

from app.schemas.recovery_reliability_stability_observation_v21_220 import (
    StabilityObservationDecision,
    StabilityObservationRequest,
)
from app.services.recovery_reliability_stability_observation_v21_220 import (
    evaluate_episode_stability,
)

router = APIRouter(
    prefix='/recovery-reliability/v21.220',
    tags=['recovery-reliability-v21.220'],
)


@router.post('/stability/observe', response_model=StabilityObservationDecision)
def stability_observation(
    req: StabilityObservationRequest,
    human_approved: bool = False,
):
    return evaluate_episode_stability(req, human_approved=human_approved)
