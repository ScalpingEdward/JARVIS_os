from fastapi import APIRouter
from app.schemas.recovery_reliability_cross_consumer_adoption_consistency_v21_216 import CrossConsumerAdoptionConsistencyRequest, CrossConsumerAdoptionConsistencyDecision
from app.services.recovery_reliability_cross_consumer_adoption_consistency_v21_216 import evaluate_adoption_consistency

router = APIRouter(prefix='/recovery-reliability/v21.216', tags=['recovery-reliability-v21.216'])

@router.post('/adoption-consistency/observe', response_model=CrossConsumerAdoptionConsistencyDecision)
def observe_adoption_consistency(req: CrossConsumerAdoptionConsistencyRequest, human_approved: bool = False):
    return evaluate_adoption_consistency(req, human_approved=human_approved)
