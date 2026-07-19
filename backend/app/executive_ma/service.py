from datetime import datetime, timezone
from uuid import UUID

from .models import AuditRecord, ExecutiveMAPortfolio, IntegrationRiskUpdate, MAAssessment, MAPortfolioCreate, MAStatusResponse, Severity


class ExecutiveMAService:
    def __init__(self) -> None:
        self._portfolios: dict[UUID, ExecutiveMAPortfolio] = {}
        self._audit: list[AuditRecord] = []

    def create(self, payload: MAPortfolioCreate) -> ExecutiveMAPortfolio:
        if any(item.workspace_id == payload.workspace_id and item.name.lower() == payload.name.lower() for item in self._portfolios.values()):
            raise ValueError("Executive M&A portfolio already exists")
        item = ExecutiveMAPortfolio(**payload.model_dump())
        self._portfolios[item.id] = item
        self._record(item.workspace_id, payload.executive_owner_id, "ma_portfolio_created", item.id)
        return item

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveMAPortfolio | None:
        item = self._portfolios.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveMAPortfolio]:
        return [item for item in self._portfolios.values() if item.workspace_id == workspace_id]

    def update_risk(self, portfolio_id: UUID, workspace_id: str, payload: IntegrationRiskUpdate) -> ExecutiveMAPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive M&A portfolio not found")
        risk = next((value for value in item.risks if value.risk_id == payload.risk_id), None)
        if risk is None:
            raise KeyError("Integration risk not found")
        risk.remediation_progress = payload.remediation_progress
        item.updated_at = datetime.now(timezone.utc)
        self._record(workspace_id, payload.actor_id, "ma_risk_updated", item.id, {"risk_id": payload.risk_id, "note": payload.note or ""})
        return item

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveMAPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive M&A portfolio not found")
        workstreams = item.workstreams
        progress = sum(value.progress for value in workstreams) / len(workstreams)
        day_1 = sum(value.day_1_readiness for value in workstreams) / len(workstreams)
        day_100 = sum(value.day_100_readiness for value in workstreams) / len(workstreams)
        dependency = sum((value.dependency_risk + value.tsa_dependency) / 2 for value in workstreams) / len(workstreams)
        target = sum(value.target_value for value in item.synergies)
        realized = sum(value.realized_value for value in item.synergies)
        synergy_score = 100.0 if target == 0 else min(100.0, realized / target * 100)
        confidence = 100.0 if not item.synergies else sum(value.confidence_score for value in item.synergies) / len(item.synergies)
        risk_exposure = 0.0
        if item.risks:
            risk_exposure = sum(value.probability * value.impact_score * (1 - value.remediation_progress / 100) for value in item.risks) / len(item.risks)
        people = (item.culture_alignment_score + item.talent_retention_score) / 2
        value_leakage = min(100.0, max(0.0, (100 - synergy_score) * 0.4 + (100 - confidence) * 0.2 + dependency * 0.2 + risk_exposure * 0.2))
        health = max(0.0, min(100.0, (progress + day_1 + day_100 + people + item.customer_continuity_score + item.strategic_fit_score + (100 - value_leakage)) / 7))
        priority_workstreams = [value.workstream_id for value in workstreams if value.progress < 60 or value.day_1_readiness < 70 or value.dependency_risk > 65 or value.tsa_dependency > 65]
        priority_risks = [value.risk_id for value in item.risks if value.severity in {Severity.high, Severity.critical} and value.probability * value.impact_score >= 35 and value.remediation_progress < 80]
        actions: list[str] = []
        if priority_workstreams:
            actions.append("Escalate delayed or dependency-heavy integration workstreams to the integration management office")
        if synergy_score < 70 or confidence < 70:
            actions.append("Revalidate synergy owners, timing assumptions and benefit-realization evidence")
        if people < 70:
            actions.append("Strengthen culture integration and retention plans for critical talent")
        if item.customer_continuity_score < 75:
            actions.append("Protect customer continuity with account-level migration and communication controls")
        if priority_risks:
            actions.append("Escalate priority integration risks and assign executive remediation owners")
        if not actions:
            actions.append("Maintain current integration cadence and continue monthly value-realization reviews")
        item.assessment = MAAssessment(
            integration_health_score=round(health, 2),
            synergy_realization_score=round(synergy_score, 2),
            value_leakage_exposure=round(value_leakage, 2),
            day_1_readiness_score=round(day_1, 2),
            day_100_readiness_score=round(day_100, 2),
            people_and_culture_score=round(people, 2),
            priority_workstreams=priority_workstreams,
            priority_risks=priority_risks,
            executive_actions=actions,
        )
        item.updated_at = datetime.now(timezone.utc)
        self._record(workspace_id, actor_id, "ma_portfolio_assessed", item.id)
        return item

    def status(self, workspace_id: str) -> MAStatusResponse:
        items = self.list_portfolios(workspace_id)
        risks = [risk for item in items for risk in item.risks if risk.remediation_progress < 100]
        return MAStatusResponse(
            workspace_id=workspace_id,
            portfolios=len(items),
            active_deals=sum(item.deal_stage.value != "stabilized" for item in items),
            open_risks=len(risks),
            critical_risks=sum(risk.severity == Severity.critical for risk in risks),
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _record(self, workspace_id: str, actor_id: str, action: str, resource_id: UUID, details: dict[str, object] | None = None) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, resource_id=resource_id, details=details or {}))


executive_ma_service = ExecutiveMAService()
