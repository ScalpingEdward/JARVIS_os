from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AllocationUpdate,
    AuditRecord,
    CapitalAssessment,
    CapitalPortfolioCreate,
    CapitalStatusResponse,
    ExecutiveCapitalPortfolio,
    InvestmentAssessment,
)


_RISK_FACTOR = {"low": 0.95, "medium": 0.8, "high": 0.6, "critical": 0.35}


class ExecutiveCapitalService:
    def __init__(self) -> None:
        self._portfolios: dict[UUID, ExecutiveCapitalPortfolio] = {}
        self._audit: list[AuditRecord] = []

    def create(self, payload: CapitalPortfolioCreate) -> ExecutiveCapitalPortfolio:
        duplicate = any(
            item.workspace_id == payload.workspace_id
            and item.name.lower() == payload.name.lower()
            and item.fiscal_period.lower() == payload.fiscal_period.lower()
            for item in self._portfolios.values()
        )
        if duplicate:
            raise ValueError("Capital portfolio already exists for workspace and fiscal period")
        record = ExecutiveCapitalPortfolio(**payload.model_dump())
        self._portfolios[record.portfolio_id] = record
        self._log(record.workspace_id, "system", "capital_portfolio.created", record.portfolio_id)
        return record

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveCapitalPortfolio | None:
        record = self._portfolios.get(portfolio_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveCapitalPortfolio]:
        return [item for item in self._portfolios.values() if item.workspace_id == workspace_id]

    def update_allocation(self, portfolio_id: UUID, workspace_id: str, payload: AllocationUpdate) -> ExecutiveCapitalPortfolio:
        record = self.get(portfolio_id, workspace_id)
        if record is None:
            raise KeyError("Executive capital portfolio not found")
        investment = next((item for item in record.investments if item.investment_id == payload.investment_id), None)
        if investment is None:
            raise KeyError("Investment not found")
        if payload.committed_capital > investment.requested_capital:
            raise ValueError("Committed capital cannot exceed requested capital")
        investment.committed_capital = payload.committed_capital
        if payload.status is not None:
            investment.status = payload.status
        if payload.realized_value is not None:
            investment.realized_value = payload.realized_value
        record.assessment = None
        record.updated_at = datetime.now(timezone.utc)
        self._log(workspace_id, payload.actor_id, "capital_allocation.updated", portfolio_id, {"investment_id": str(payload.investment_id)})
        return record

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveCapitalPortfolio:
        record = self.get(portfolio_id, workspace_id)
        if record is None:
            raise KeyError("Executive capital portfolio not found")
        reserve = record.total_capital * record.reserve_ratio
        deployable = record.total_capital - reserve
        committed = sum(item.committed_capital for item in record.investments)
        realized = sum(item.realized_value for item in record.investments)
        assessments: list[InvestmentAssessment] = []
        for item in record.investments:
            risk_adjusted = item.expected_value * item.probability_of_success * _RISK_FACTOR[item.risk_level]
            value_multiple = risk_adjusted / item.requested_capital
            speed_score = max(0.0, 100 - (item.time_to_value_months / 60 * 100))
            priority = round(item.strategic_alignment * 0.45 + min(value_multiple * 25, 100) * 0.4 + speed_score * 0.15, 2)
            funding_gap = max(0.0, item.requested_capital - item.committed_capital)
            if item.risk_level == "critical" or value_multiple < 0.5:
                classification = "stop"
            elif priority >= 70 and value_multiple >= 1:
                classification = "fund"
            elif priority >= 50:
                classification = "conditional"
            else:
                classification = "defer"
            assessments.append(InvestmentAssessment(
                investment_id=item.investment_id,
                priority_score=priority,
                risk_adjusted_value=round(risk_adjusted, 2),
                value_multiple=round(value_multiple, 3),
                funding_gap=round(funding_gap, 2),
                classification=classification,
            ))
        ranked = sorted(assessments, key=lambda item: item.priority_score, reverse=True)
        expected_value = sum(item.risk_adjusted_value for item in assessments)
        capital_efficiency = realized / committed if committed else 0.0
        largest = max((item.committed_capital for item in record.investments), default=0.0)
        concentration = largest / committed if committed else 0.0
        value_at_risk = sum(
            item.expected_value * (1 - item.probability_of_success) * (1 - _RISK_FACTOR[item.risk_level])
            for item in record.investments
        )
        recommendations: list[str] = []
        if committed > deployable:
            recommendations.append("Committed capital exceeds deployable capital; pause new approvals.")
        if concentration > 0.4:
            recommendations.append("Reduce capital concentration in the largest investment.")
        if any(item.classification == "stop" for item in assessments):
            recommendations.append("Review stop-classified investments before further funding.")
        if not recommendations:
            recommendations.append("Maintain gated funding releases and validate realized value each review cycle.")
        record.assessment = CapitalAssessment(
            deployable_capital=round(deployable, 2),
            committed_capital=round(committed, 2),
            reserve_capital=round(reserve, 2),
            expected_portfolio_value=round(expected_value, 2),
            realized_value=round(realized, 2),
            capital_efficiency=round(capital_efficiency, 3),
            concentration_risk=round(concentration, 3),
            value_at_risk=round(value_at_risk, 2),
            investment_assessments=assessments,
            recommended_funding_order=[item.investment_id for item in ranked if item.classification != "stop"],
            executive_recommendations=recommendations,
        )
        record.updated_at = datetime.now(timezone.utc)
        self._log(workspace_id, actor_id, "capital_portfolio.assessed", portfolio_id)
        return record

    def status(self, workspace_id: str) -> CapitalStatusResponse:
        items = self.list_portfolios(workspace_id)
        investments = [investment for portfolio in items for investment in portfolio.investments]
        return CapitalStatusResponse(
            workspace_id=workspace_id,
            portfolios=len(items),
            total_capital=sum(item.total_capital for item in items),
            committed_capital=sum(item.committed_capital for item in investments),
            realized_value=sum(item.realized_value for item in investments),
            at_risk_investments=sum(item.risk_level in {"high", "critical"} for item in investments),
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, workspace_id: str, actor_id: str, action: str, entity_id: UUID, details: dict[str, object] | None = None) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, entity_id=entity_id, details=details or {}))


executive_capital_service = ExecutiveCapitalService()
