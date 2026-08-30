"""Strategy evaluation API — evaluate market snapshots against trading strategies."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from .models import MarketSnapshot, StrategyResult
from .service import StrategyServiceError, strategy_service

router = APIRouter(prefix="/v1/strategies", tags=["strategies"])


@router.get("/", response_model=list[dict])
def list_strategies() -> list[dict]:
    """List all available trading strategies.

    Returns metadata for each strategy: id, name, description.
    """
    return strategy_service.list_strategies()


@router.post("/evaluate/{strategy_id}", response_model=StrategyResult)
def evaluate_strategy(
    strategy_id: str = Path(min_length=1, max_length=50),
    snapshot: MarketSnapshot = ...,
) -> StrategyResult:
    """Evaluate a single strategy against a market snapshot.

    Returns either a TradingSetup (if conditions are met) or a reason why
    no setup was generated.
    """
    try:
        return strategy_service.evaluate_strategy(strategy_id, snapshot)
    except StrategyServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evaluate-all", response_model=list[StrategyResult])
def evaluate_all_strategies(snapshot: MarketSnapshot) -> list[StrategyResult]:
    """Evaluate all registered strategies against a market snapshot.

    Returns a result for each strategy, including those without a setup.
    Use /find-setups to get only strategies with valid setups.
    """
    return strategy_service.evaluate_all(snapshot)


@router.post("/find-setups", response_model=list[StrategyResult])
def find_setups(snapshot: MarketSnapshot) -> list[StrategyResult]:
    """Find all valid trading setups for a market snapshot.

    Evaluates all strategies and returns only those with valid TradingSetups.
    """
    return strategy_service.find_setups(snapshot)
