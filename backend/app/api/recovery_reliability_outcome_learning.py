"""API contract for PHOENIX v21.181 recovery reliability outcome learning governance."""
from fastapi import APIRouter

router = APIRouter(prefix="/v1/recovery-reliability-outcome-learning", tags=["recovery-reliability-outcome-learning"])


@router.get("/status")
def status() -> dict:
    return {
        "module": "v21.181",
        "name": "Recovery Reliability Outcome Learning & Baseline Feedback Governance",
        "runtime_mutation": False,
        "baseline_mutation": False,
        "human_approval_required": True,
        "risk_brain_authoritative": True,
        "max_feedback_adjustment": 0.05,
    }
