from fastapi import APIRouter
from app.schemas.recovery_reliability_baseline_rollout_v21_214 import BaselineRolloutRequest, BaselineRolloutDecision
from app.services.recovery_reliability_baseline_rollout_v21_214 import evaluate_rollout

router = APIRouter(prefix='/recovery-reliability/v21.214', tags=['recovery-reliability-v21.214'])

@router.post('/baseline-rollout/evaluate', response_model=BaselineRolloutDecision)
def baseline_rollout(req: BaselineRolloutRequest, human_approved: bool = False):
    return evaluate_rollout(req, human_approved=human_approved)
