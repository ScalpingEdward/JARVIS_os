from fastapi import APIRouter
from app.schemas.recovery_reliability_baseline_rollout_v21_204 import BaselineRolloutRequest, BaselineRolloutDecision
from app.services.recovery_reliability_baseline_rollout_v21_204 import evaluate_rollout

router = APIRouter(prefix='/recovery-reliability/v21.204', tags=['recovery-reliability-v21.204'])

@router.post('/baseline-rollout/evaluate', response_model=BaselineRolloutDecision)
def baseline_rollout(req: BaselineRolloutRequest, eligibility_approved: bool = False, approved_stage_indices: list[int] | None = None):
    return evaluate_rollout(req, eligibility_approved=eligibility_approved, approved_stage_indices=approved_stage_indices)
