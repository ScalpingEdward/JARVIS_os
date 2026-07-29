"""API contract for PHOENIX v21.171 recovery outcome reliability learning governance."""
from fastapi import APIRouter

router = APIRouter(prefix="/v1/recovery-outcome-reliability-learning", tags=["recovery-outcome-reliability-learning"])


@router.get("/status")
def status() -> dict:
    return {
        "module": "v21.171",
        "name": "Recovery Outcome Reliability Learning & Baseline Feedback Governance",
        "baseline_mutation": False,
        "human_approval_required": True,
        "risk_brain_authoritative": True,
        "max_reliability_adjustment": 0.05,
    }
