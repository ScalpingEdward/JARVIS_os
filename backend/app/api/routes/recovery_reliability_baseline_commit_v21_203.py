from fastapi import APIRouter
from app.schemas.recovery_reliability_baseline_commit_v21_203 import BaselineCommitRequest, BaselineCommitDecision
from app.services.recovery_reliability_baseline_commit_v21_203 import evaluate_baseline_commit

router = APIRouter(prefix='/recovery-reliability/v21.203', tags=['recovery-reliability-v21.203'])

@router.post('/baseline/commit', response_model=BaselineCommitDecision)
def controlled_baseline_commit(req: BaselineCommitRequest, human_approved: bool = False):
    return evaluate_baseline_commit(req, human_approved=human_approved)
