from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    CustomerPortfolioCreate,
    CustomerSignalUpdate,
    CustomerStatusResponse,
    ExecutiveCustomerPortfolio,
)


class ExecutiveCustomerService:
    def __init__(self) -> None:
        self._items: dict[UUID, ExecutiveCustomerPortfolio] = {}
        self._audit: list[AuditRecord] = []

    def create(self, payload: CustomerPortfolioCreate) -> ExecutiveCustomerPortfolio:
        if any(item.workspace_id == payload.workspace_id and item.name == payload.name for item in self._items.values()):
            raise ValueError("Executive customer portfolio already exists")
        item = ExecutiveCustomerPortfolio(**payload.model_dump())
        self._items[item.portfolio_id] = item
        self._record(item.workspace_id, payload.actor_id, "customer_portfolio_created", item.portfolio_id)
        return item

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveCustomerPortfolio | None:
        item = self._items.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveCustomerPortfolio]:
        return [item for item in self._items.values() if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> CustomerStatusResponse:
        items = self.list_portfolios(workspace_id)
        return CustomerStatusResponse(
            workspace_id=workspace_id,
            portfolios=len(items),
            assessed_portfolios=sum(item.assessed_at is not None for item in items),
        )

    def update_signal(self, portfolio_id: UUID, workspace_id: str, payload: CustomerSignalUpdate) -> ExecutiveCustomerPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive customer portfolio not found")
        signal = next((candidate for candidate in item.signals if candidate.signal_id == payload.signal_id), None)
        if signal is None:
            raise KeyError("Customer signal not found")
        for field in ("churn_probability", "revenue_at_risk", "satisfaction_score"):
            value = getattr(payload, field)
            if value is not None:
                setattr(signal, field, value)
        self._record(workspace_id, payload.actor_id, "customer_signal_updated", portfolio_id)
        return item

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveCustomerPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive customer portfolio not found")
        total_revenue = sum(segment.annual_revenue for segment in item.segments)
        revenue_denominator = total_revenue or 1
        item.total_revenue = round(total_revenue, 2)
        item.weighted_retention = round(
            sum(segment.annual_revenue * segment.retention_rate for segment in item.segments) / revenue_denominator,
            2,
        )
        item.weighted_expansion = round(
            sum(segment.annual_revenue * segment.expansion_rate for segment in item.segments) / revenue_denominator,
            2,
        )
        item.revenue_at_risk = round(sum(signal.revenue_at_risk for signal in item.signals), 2)
        value_scores = []
        for segment in item.segments:
            efficiency = min(segment.lifetime_value / max(segment.acquisition_cost, 1), 10) * 10
            value_scores.append((segment.gross_margin + segment.retention_rate + efficiency + segment.strategic_importance) / 4)
        item.customer_value_score = round(sum(value_scores) / len(value_scores), 2)
        item.growth_score = round(max(0, min(100, 50 + item.weighted_expansion + (item.weighted_retention - 80))), 2)
        high_risk_ids = {signal.segment_id for signal in item.signals if signal.churn_probability >= 60 or signal.satisfaction_score < 50}
        item.vulnerable_segments = sorted(high_risk_ids)
        item.expansion_segments = sorted(
            segment.segment_id
            for segment in item.segments
            if segment.expansion_rate >= 10 and segment.retention_rate >= 85 and segment.strategic_importance >= 60
        )
        recommendations = []
        if item.vulnerable_segments:
            recommendations.append("Prioritize executive retention plans for vulnerable customer segments")
        if item.expansion_segments:
            recommendations.append("Accelerate cross-sell and expansion programs in high-potential segments")
        if item.revenue_at_risk > total_revenue * 0.1:
            recommendations.append("Escalate revenue-at-risk mitigation to executive steering")
        if item.weighted_retention < 85:
            recommendations.append("Strengthen retention operating cadence and ownership")
        item.recommendations = recommendations or ["Maintain customer-value discipline and continue signal monitoring"]
        item.assessed_at = datetime.now(timezone.utc)
        self._record(workspace_id, actor_id, "customer_portfolio_assessed", portfolio_id)
        return item

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    def _record(self, workspace_id: str, actor_id: str, action: str, portfolio_id: UUID) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, portfolio_id=portfolio_id))


executive_customer_service = ExecutiveCustomerService()
