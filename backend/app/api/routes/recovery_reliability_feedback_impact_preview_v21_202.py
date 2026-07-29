from fastapi import APIRouter
from app.schemas.recovery_reliability_feedback_impact_preview_v21_202 import FeedbackImpactPreviewRequest, FeedbackImpactPreviewDecision
from app.services.recovery_reliability_feedback_impact_preview_v21_202 import simulate_feedback_impact

router = APIRouter(prefix='/recovery-reliability/v21.202', tags=['recovery-reliability-v21.202'])

@router.post('/feedback-impact/preview', response_model=FeedbackImpactPreviewDecision)
def feedback_impact_preview(req: FeedbackImpactPreviewRequest, human_approved: bool = False):
    return simulate_feedback_impact(req, human_approved=human_approved)
