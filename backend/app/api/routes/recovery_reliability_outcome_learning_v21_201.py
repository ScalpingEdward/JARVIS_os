from fastapi import APIRouter
from app.schemas.recovery_reliability_outcome_learning_v21_201 import RecoveryOutcomeLearningRequest, RecoveryOutcomeLearningDecision
from app.services.recovery_reliability_outcome_learning_v21_201 import evaluate_outcome_learning

router = APIRouter(prefix='/recovery-reliability/v21.201', tags=['recovery-reliability-v21.201'])

@router.post('/outcome-learning/evaluate', response_model=RecoveryOutcomeLearningDecision)
def outcome_learning(req: RecoveryOutcomeLearningRequest, human_approved: bool = False):
    return evaluate_outcome_learning(req, human_approved=human_approved)
