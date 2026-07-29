"""API contract for PHOENIX v21.191 recovery reliability outcome learning governance."""
from fastapi import APIRouter

router = APIRouter(
    prefix="/v1/recovery-reliability-outcome-learning",
    tags=["recovery-reliability-outcome-learning"],
)


@router.get("/status")
def status() -> dict:
    return {
        "module": "v21.191",
        "name": "Recovery Reliability Outcome Learning & Baseline Feedback Governance",
        "source_state_required": "closed",
        "human_approval_required": True,
        "max_feedback_adjustment": 0.05,
        "baseline_mutation_enabled": False,
        "runtime_mutation_enabled": False,
        "execution_enabled": False,
        "device_actuation_enabled": False,
        "risk_brain_authoritative": True,
    }
