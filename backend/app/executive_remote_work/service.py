from datetime import datetime, timezone
from statistics import mean
from uuid import UUID

from .models import AuditRecord, ExecutiveRemoteWorkPortfolio, RemoteWorkPortfolioCreate, RemoteWorkRiskUpdate, RemoteWorkStatusResponse


class ExecutiveRemoteWorkService:
    def __init__(self) -> None:
        self._items: dict[UUID, ExecutiveRemoteWorkPortfolio] = {}
        self._audit: list[AuditRecord] = []

    def status(self, workspace_id: str) -> RemoteWorkStatusResponse:
        return RemoteWorkStatusResponse(workspace_id=workspace_id, portfolios=len(self.list_portfolios(workspace_id)))

    def create(self, payload: RemoteWorkPortfolioCreate) -> ExecutiveRemoteWorkPortfolio:
        if any(item.workspace_id == payload.workspace_id and item.name.lower() == payload.name.lower() for item in self._items.values()):
            raise ValueError("Executive remote-work portfolio already exists")
        item = ExecutiveRemoteWorkPortfolio(**payload.model_dump())
        self._items[item.portfolio_id] = item
        self._audit.append(AuditRecord(workspace_id=item.workspace_id, portfolio_id=item.portfolio_id, action="portfolio_created", actor_id="system"))
        return item

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveRemoteWorkPortfolio]:
        return [item for item in self._items.values() if item.workspace_id == workspace_id]

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveRemoteWorkPortfolio | None:
        item = self._items.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def update_risk(self, portfolio_id: UUID, workspace_id: str, payload: RemoteWorkRiskUpdate) -> ExecutiveRemoteWorkPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive remote-work portfolio not found")
        for risk in item.risks:
            if risk.risk_id == payload.risk_id:
                risk.remediation_progress = payload.remediation_progress
                return item
        raise KeyError("Remote-work risk not found")

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveRemoteWorkPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive remote-work portfolio not found")

        opportunities = item.opportunities
        engagements = item.engagements
        risks = item.risks
        item.opportunity_quality_score = round(mean([(o.skill_fit + o.delivery_confidence + o.client_quality + o.contract_clarity) / 4 for o in opportunities]), 2) if opportunities else 0
        item.profitability_score = round(mean([min(100, max(0, o.effective_hourly_rate * 2)) for o in opportunities]), 2) if opportunities else 0
        item.ethical_readiness_score = round(mean([100 if o.ai_use_permitted or o.delivery_mode.value == "human_led" else 40 for o in opportunities]), 2) if opportunities else 0
        item.delivery_capacity_score = round(mean([max(0, 100 - (e.committed_hours / e.capacity_limit_hours * 100)) * 0.4 + e.quality_score * 0.3 + e.deadline_readiness * 0.3 for e in engagements]), 2) if engagements else 100
        item.risk_exposure_score = round(mean([(r.severity + r.probability + r.impact) / 3 * (1 - r.remediation_progress / 100) for r in risks]), 2) if risks else 0
        item.priority_opportunity_ids = [o.opportunity_id for o in opportunities if o.skill_fit >= 70 and o.delivery_confidence >= 70 and o.effective_hourly_rate >= 25 and (o.ai_use_permitted or o.delivery_mode.value == "human_led")]
        item.priority_risk_ids = [r.risk_id for r in risks if (r.severity + r.probability + r.impact) / 3 >= 65 and r.remediation_progress < 70]
        recommendations: list[str] = []
        if item.opportunity_quality_score < 65:
            recommendations.append("Prioritize opportunities with stronger skill fit, contract clarity and client quality.")
        if item.delivery_capacity_score < 60:
            recommendations.append("Reduce concurrent commitments or add governed delivery capacity before accepting new work.")
        if item.ethical_readiness_score < 70:
            recommendations.append("Disclose AI-assisted delivery and exclude roles that prohibit automation or require personal performance.")
        if item.risk_exposure_score >= 55:
            recommendations.append("Resolve payment, scope, platform and compliance risks before execution.")
        item.recommendations = recommendations or ["Maintain selective sourcing, transparent AI use and quality-controlled delivery."]
        item.assessed_at = datetime.now(timezone.utc)
        self._audit.append(AuditRecord(workspace_id=workspace_id, portfolio_id=portfolio_id, action="portfolio_assessed", actor_id=actor_id))
        return item

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]


executive_remote_work_service = ExecutiveRemoteWorkService()
