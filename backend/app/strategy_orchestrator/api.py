"""Strategy orchestrator API endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from ..strategies.models import MarketSnapshot
from .models import OrchestrationResult
from .service import strategy_orchestrator

router = APIRouter(prefix="/v1/strategy-orchestrator", tags=["strategy-orchestrator"])


@router.post("/evaluate", response_model=OrchestrationResult)
def evaluate_all_accounts(snapshot: MarketSnapshot) -> OrchestrationResult:
    """Evaluate assigned strategies for all active accounts with compliance filtering.

    For each active account:
    - Evaluates only the strategies assigned to that account
    - Checks account compliance (not breached, active status)
    - Returns only setups that are safe to execute

    This is the orchestration layer that sits between strategy evaluation and
    order execution — it ensures that only compliant setups reach the executor.
    """
    return strategy_orchestrator.evaluate_all_accounts(snapshot)
