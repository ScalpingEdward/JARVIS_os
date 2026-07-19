from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    ExecutiveTreasuryPortfolio,
    Severity,
    TreasuryAssessment,
    TreasuryPortfolioCreate,
    TreasuryRiskUpdate,
    TreasuryStatusResponse,
)


class ExecutiveTreasuryService:
    def __init__(self) -> None:
        self._portfolios: dict[UUID, ExecutiveTreasuryPortfolio] = {}
        self._audit: list[AuditRecord] = []

    def create(self, payload: TreasuryPortfolioCreate) -> ExecutiveTreasuryPortfolio:
        duplicate = any(
            item.workspace_id == payload.workspace_id and item.name.lower() == payload.name.lower()
            for item in self._portfolios.values()
        )
        if duplicate:
            raise ValueError("Executive treasury portfolio already exists")
        item = ExecutiveTreasuryPortfolio(**payload.model_dump())
        self._portfolios[item.id] = item
        self._record(item.workspace_id, payload.executive_owner_id, "treasury_portfolio_created", item.id)
        return item

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveTreasuryPortfolio | None:
        item = self._portfolios.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveTreasuryPortfolio]:
        return [item for item in self._portfolios.values() if item.workspace_id == workspace_id]

    def update_risk(self, portfolio_id: UUID, workspace_id: str, payload: TreasuryRiskUpdate) -> ExecutiveTreasuryPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive treasury portfolio not found")
        risk = next((value for value in item.risks if value.risk_id == payload.risk_id), None)
        if risk is None:
            raise KeyError("Treasury risk not found")
        risk.remediation_progress = payload.remediation_progress
        item.updated_at = datetime.now(timezone.utc)
        self._record(workspace_id, payload.actor_id, "treasury_risk_updated", item.id, {"risk_id": payload.risk_id, "note": payload.note or ""})
        return item

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveTreasuryPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive treasury portfolio not found")

        positions = item.cash_positions
        funding = item.funding_sources
        risks = item.risks
        scenarios = item.stress_scenarios

        total_cash = sum(value.available_cash for value in positions)
        restricted = sum(value.restricted_cash for value in positions)
        usable_ratio = 100.0 if total_cash <= 0 else max(0.0, 100.0 * (total_cash - restricted) / total_cash)
        forecast_quality = sum(value.forecast_accuracy_score for value in positions) / len(positions)
        cash_diversification = 100 - (sum(value.concentration_score for value in positions) / len(positions))
        liquidity_health = (usable_ratio + forecast_quality + cash_diversification) / 3

        funding_resilience = 100.0
        vulnerable_funding: list[str] = []
        if funding:
            scores = []
            for source in funding:
                undrawn_ratio = 100.0 if source.committed_amount <= 0 else 100 * (source.committed_amount - source.drawn_amount) / source.committed_amount
                maturity_score = min(100.0, source.maturity_months / 24 * 100)
                score = (undrawn_ratio + maturity_score + source.covenant_headroom_score) / 3
                scores.append(score)
                if source.covenant_headroom_score < 55 or source.maturity_months < 12:
                    vulnerable_funding.append(source.source_id)
            funding_resilience = sum(scores) / len(scores)

        market_coverage = (item.fx_hedge_coverage_score + item.interest_rate_hedge_coverage_score) / 2
        counterparty = item.counterparty_diversification_score
        stress_survival = 100.0
        if scenarios:
            stress_survival = sum(min(100.0, value.survival_months / 12 * 100) * 0.6 + value.response_readiness_score * 0.4 for value in scenarios) / len(scenarios)

        risk_exposure = 0.0
        if risks:
            risk_exposure = sum(value.probability * value.impact_score * (1 - value.remediation_progress / 100) for value in risks) / len(risks)
        priority = [value.risk_id for value in risks if value.severity in {Severity.high, Severity.critical} and value.probability * value.impact_score >= 35 and value.remediation_progress < 80]

        actions: list[str] = []
        if liquidity_health < 70:
            actions.append("Increase unrestricted liquidity buffers and improve cash-forecast accuracy")
        if vulnerable_funding:
            actions.append("Refinance vulnerable facilities and restore covenant headroom before maturity concentration increases")
        if market_coverage < 70:
            actions.append("Review FX and interest-rate hedge coverage against approved treasury risk appetite")
        if counterparty < 70:
            actions.append("Diversify bank and counterparty exposure and tighten concentration limits")
        if stress_survival < 70:
            actions.append("Strengthen liquidity contingency plans and pre-authorized crisis funding playbooks")
        if priority:
            actions.append("Escalate priority treasury risks to the executive risk and finance committee")
        if not actions:
            actions.append("Maintain current treasury controls and continue periodic liquidity stress testing")

        item.assessment = TreasuryAssessment(
            liquidity_health_score=round(max(0.0, min(100.0, liquidity_health)), 2),
            funding_resilience_score=round(max(0.0, min(100.0, funding_resilience)), 2),
            forecast_quality_score=round(forecast_quality, 2),
            market_risk_coverage_score=round(market_coverage, 2),
            counterparty_resilience_score=round(counterparty, 2),
            stress_survival_score=round(stress_survival, 2),
            risk_exposure_score=round(risk_exposure, 2),
            priority_risks=priority,
            vulnerable_funding_sources=vulnerable_funding,
            executive_actions=actions,
        )
        item.updated_at = datetime.now(timezone.utc)
        self._record(workspace_id, actor_id, "treasury_portfolio_assessed", item.id)
        return item

    def status(self, workspace_id: str) -> TreasuryStatusResponse:
        items = self.list_portfolios(workspace_id)
        open_risks = [risk for item in items for risk in item.risks if risk.remediation_progress < 100]
        return TreasuryStatusResponse(
            workspace_id=workspace_id,
            portfolios=len(items),
            total_available_cash=sum(position.available_cash for item in items for position in item.cash_positions),
            total_committed_funding=sum(source.committed_amount for item in items for source in item.funding_sources),
            open_risks=len(open_risks),
            critical_risks=sum(risk.severity == Severity.critical for risk in open_risks),
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _record(self, workspace_id: str, actor_id: str, action: str, resource_id: UUID, details: dict[str, object] | None = None) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, resource_id=resource_id, details=details or {}))


executive_treasury_service = ExecutiveTreasuryService()
