"""Strategy evaluation service — evaluates market snapshots against all strategies."""

from __future__ import annotations

from .ict_silver_bullet.strategy import evaluate as evaluate_ict_silver_bullet
from .models import MarketSnapshot, StrategyResult
from .scalping_3tp.strategy import evaluate as evaluate_scalping_3tp

# Registry of all available strategies
STRATEGIES = {
    "scalping_3tp": {
        "id": "scalping_3tp",
        "name": "Scalping 3TP (FVG + Order Block)",
        "description": "FVG + Order Block mitigation with 3 TPs at 30%/50%/100% RR, min 1:2 RR",
        "evaluate": evaluate_scalping_3tp,
    },
    "ict_silver_bullet": {
        "id": "ict_silver_bullet",
        "name": "ICT Silver Bullet (Session FVG + Structure)",
        "description": (
            "London/NY session-gated FVG entry, structure-based SL and nearest "
            "structure-liquidity target with 2 TPs, min 1:2 RR"
        ),
        "evaluate": evaluate_ict_silver_bullet,
    },
    # Future strategies will be added here:
    # "smc": {...},
    # "open_range": {...},
}


class StrategyServiceError(ValueError):
    """Strategy service errors."""

    pass


class StrategyService:
    """Evaluates market snapshots against registered trading strategies."""

    def list_strategies(self) -> list[dict]:
        """List all available strategies with metadata."""
        return [
            {"id": s["id"], "name": s["name"], "description": s["description"]}
            for s in STRATEGIES.values()
        ]

    def evaluate_strategy(self, strategy_id: str, snapshot: MarketSnapshot) -> StrategyResult:
        """Evaluate a single strategy against a market snapshot."""
        strategy = STRATEGIES.get(strategy_id)
        if not strategy:
            raise StrategyServiceError(f"Unknown strategy: {strategy_id}")
        return strategy["evaluate"](snapshot)

    def evaluate_all(self, snapshot: MarketSnapshot) -> list[StrategyResult]:
        """Evaluate all registered strategies against a market snapshot."""
        return [strategy["evaluate"](snapshot) for strategy in STRATEGIES.values()]

    def find_setups(self, snapshot: MarketSnapshot) -> list[StrategyResult]:
        """Evaluate all strategies and return only those with valid setups."""
        results = self.evaluate_all(snapshot)
        return [r for r in results if r.setup is not None]


strategy_service = StrategyService()
