from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from .models import (
    AuditRecord,
    ExposureLine,
    LivePortfolioExposureAssessment,
    LivePortfolioExposureCreate,
    PortfolioScores,
    PortfolioState,
    PortfolioStatusResponse,
)


class ExecutiveLivePortfolioExposureService:
    def __init__(self) -> None:
        self._records: dict[UUID, LivePortfolioExposureAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: LivePortfolioExposureCreate) -> LivePortfolioExposureAssessment:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("Duplicate Live portfolio exposure source key")

        total = round(payload.total_live_owned_capital, 2)
        allocated = round(sum(item.allocated_capital for item in payload.positions), 2)
        total_risk = round(sum(item.risk_amount for item in payload.positions), 2)
        unallocated = round(total - allocated, 2)

        maps: dict[str, dict[str, float]] = {
            "broker": defaultdict(float),
            "symbol": defaultdict(float),
            "strategy": defaultdict(float),
            "currency": defaultdict(float),
            "correlation": defaultdict(float),
        }
        for item in payload.positions:
            maps["broker"][item.broker_id] += item.allocated_capital
            maps["symbol"][item.symbol.upper()] += item.allocated_capital
            maps["strategy"][item.strategy_id] += item.allocated_capital
            maps["currency"][item.currency.upper()] += item.allocated_capital
            maps["correlation"][item.correlation_group] += item.allocated_capital

        limits = {
            "broker": payload.policy.max_broker_share,
            "symbol": payload.policy.max_symbol_share,
            "strategy": payload.policy.max_strategy_share,
            "currency": payload.policy.max_currency_share,
            "correlation": payload.policy.max_correlation_group_share,
        }
        lines: list[ExposureLine] = []
        breaches: list[str] = []
        for dimension, values in maps.items():
            for exposure_key, amount in values.items():
                share = amount / total if total else 0.0
                breached = share > limits[dimension]
                if breached:
                    breaches.append(f"{dimension}:{exposure_key}")
                lines.append(
                    ExposureLine(
                        dimension=dimension,
                        key=exposure_key,
                        exposure_amount=round(amount, 2),
                        exposure_share=round(share, 4),
                        limit_share=limits[dimension],
                        breached=breached,
                        recommended_action="reduce" if breached else "hold",
                    )
                )

        risk_breach = total_risk / total > payload.policy.max_total_risk_share
        drawdown_breach = payload.current_drawdown / total > payload.policy.max_portfolio_drawdown_share
        reasons: list[str] = []

        if not payload.risk_brain_clear or risk_breach or drawdown_breach:
            state = PortfolioState.blocked
            if not payload.risk_brain_clear:
                reasons.append("Risk Brain is not clear")
            if risk_breach:
                reasons.append("Portfolio risk exceeds policy")
            if drawdown_breach:
                reasons.append("Portfolio drawdown exceeds policy")
        elif not payload.human_approved:
            state = PortfolioState.hold
            reasons.append("Human approval is required")
        elif breaches:
            state = PortfolioState.rebalance
            reasons.append("Concentration limits require rebalancing")
        elif unallocated > 0:
            state = PortfolioState.balanced
            reasons.append("Portfolio is within limits with unallocated capital")
        else:
            state = PortfolioState.fully_allocated
            reasons.append("Live portfolio is fully allocated within policy")

        unique_brokers = len(maps["broker"])
        unique_symbols = len(maps["symbol"])
        diversification = min(100, (unique_brokers + unique_symbols) * 20)
        max_corr = max((amount / total for amount in maps["correlation"].values()), default=0.0)
        max_symbol = max((amount / total for amount in maps["symbol"].values()), default=0.0)
        max_strategy = max((amount / total for amount in maps["strategy"].values()), default=0.0)
        correlation_safety = max(0, round(100 * (1 - max_corr)))
        symbol_safety = max(0, round(100 * (1 - max_symbol)))
        strategy_safety = max(0, round(100 * (1 - max_strategy)))
        drawdown_share = payload.current_drawdown / total if total else 0.0
        stability = max(0, round(100 * (1 - drawdown_share / payload.policy.max_portfolio_drawdown_share)))
        utilization = min(100, round(100 * allocated / total))
        confidence = round((diversification + correlation_safety + symbol_safety + strategy_safety + stability + utilization) / 6)

        record = LivePortfolioExposureAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            state=state,
            total_live_owned_capital=total,
            allocated_capital=allocated,
            unallocated_capital=unallocated,
            total_risk_amount=total_risk,
            exposure_lines=lines,
            scores=PortfolioScores(
                portfolio_diversification=diversification,
                correlation_safety=correlation_safety,
                symbol_concentration_safety=symbol_safety,
                strategy_concentration_safety=strategy_safety,
                portfolio_stability=stability,
                capital_utilization=utilization,
                exposure_confidence=confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._audit.append(AuditRecord(workspace_id=record.workspace_id, assessment_id=record.id, actor_id=record.actor_id, action="live-portfolio-exposure-assessed"))
        return record

    def list_assessments(self, workspace_id: str) -> list[LivePortfolioExposureAssessment]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> LivePortfolioExposureAssessment | None:
        item = self._records.get(assessment_id)
        return item if item and item.workspace_id == workspace_id else None

    def status(self, workspace_id: str) -> PortfolioStatusResponse:
        items = self.list_assessments(workspace_id)
        return PortfolioStatusResponse(workspace_id=workspace_id, assessments=len(items), latest_state=items[-1].state if items else None)

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_live_portfolio_exposure_service = ExecutiveLivePortfolioExposureService()
