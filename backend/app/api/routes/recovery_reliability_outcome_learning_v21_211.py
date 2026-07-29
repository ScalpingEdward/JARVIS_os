from fastapi import APIRouter
from app.schemas.recovery_reliability_outcome_learning_v21_211 import OutcomeLearningRequest, OutcomeLearningDecision
from app.services.recovery_reliability_outcome_learning_v21_211 import evaluate_outcome_learning

router = APIRouter(prefix='/recovery-reliability/v21.211', tags=['recovery-reliability-v21.211'])

@router.post('/outcome-learning/evaluate', response_model=OutcomeLearningDecision)
def outcome_learning(req: OutcomeLearningRequest, human_approved: bool = False):
    return evaluate_outcome_learning(req, human_approved=human_approved)
