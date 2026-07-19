from datetime import datetime, timezone
from uuid import UUID

from .models import AuditRecord, EcosystemPortfolioCreate, EcosystemStatusResponse, ExecutiveEcosystemPortfolio, PartnershipUpdate


class ExecutiveEcosystemService:
    def __init__(self) -> None:
        self._items: dict[UUID, ExecutiveEcosystemPortfolio] = {}
        self._audit: list[AuditRecord] = []

    def create(self, payload: EcosystemPortfolioCreate) -> ExecutiveEcosystemPortfolio:
        if any(item.workspace_id == payload.workspace_id and item.name == payload.name for item in self._items.values()):
            raise ValueError("Executive ecosystem portfolio already exists")
        item = ExecutiveEcosystemPortfolio(**payload.model_dump())
        self._items[item.portfolio_id] = item
        self._record(item.workspace_id, payload.actor_id, "ecosystem_portfolio_created", item.portfolio_id)
        return item

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveEcosystemPortfolio | None:
        item = self._items.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveEcosystemPortfolio]:
        return [item for item in self._items.values() if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> EcosystemStatusResponse:
        items = self.list_portfolios(workspace_id)
        return EcosystemStatusResponse(workspace_id=workspace_id, portfolios=len(items), assessed_portfolios=sum(item.assessed_at is not None for item in items))

    def update_partner(self, portfolio_id: UUID, workspace_id: str, payload: PartnershipUpdate) -> ExecutiveEcosystemPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive ecosystem portfolio not found")
        partner = next((entry for entry in item.partners if entry.partner_id == payload.partner_id), None)
        if partner is None:
            raise KeyError("Partner not found")
        for field in ("performance_score", "trust_score", "joint_value_potential"):
            value = getattr(payload, field)
            if value is not None:
                setattr(partner, field, value)
        self._record(workspace_id, payload.actor_id, "ecosystem_partner_updated", portfolio_id)
        return item

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveEcosystemPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive ecosystem portfolio not found")
        count = len(item.partners)
        item.total_annual_value = round(sum(p.annual_value for p in item.partners), 2)
        item.total_joint_value_potential = round(sum(p.joint_value_potential for p in item.partners), 2)
        item.ecosystem_health_score = round(sum((p.performance_score + p.trust_score + p.strategic_alignment) / 3 for p in item.partners) / count, 2)
        dependency_weights = {"low": 20, "medium": 45, "high": 75, "critical": 100}
        item.dependency_risk_score = round(sum((dependency_weights[p.dependency_level.value] + p.substitution_difficulty + p.contract_criticality) / 3 for p in item.partners) / count, 2)
        item.partnership_value_score = round(sum((p.strategic_alignment + p.performance_score + min(p.joint_value_potential / max(p.annual_value, 1) * 100, 100)) / 3 for p in item.partners) / count, 2)
        item.concentration_risk_score = round(max(p.concentration_share for p in item.partners), 2)
        item.critical_partners = [p.partner_id for p in item.partners if p.dependency_level.value == "critical" or p.contract_criticality >= 80]
        item.growth_partners = [p.partner_id for p in item.partners if p.joint_value_potential > p.annual_value * 0.25 and p.strategic_alignment >= 70]
        recommendations = []
        if item.critical_partners:
            recommendations.append("Create contingency and substitution plans for critical partners")
        if item.concentration_risk_score >= 50:
            recommendations.append("Reduce ecosystem concentration and diversify strategic dependencies")
        if item.growth_partners:
            recommendations.append("Prioritize joint-value programs with high-potential growth partners")
        if item.ecosystem_health_score < 60:
            recommendations.append("Escalate partner performance and trust remediation")
        item.recommendations = recommendations or ["Maintain ecosystem governance and continue partnership monitoring"]
        item.assessed_at = datetime.now(timezone.utc)
        self._record(workspace_id, actor_id, "ecosystem_portfolio_assessed", portfolio_id)
        return item

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    def _record(self, workspace_id: str, actor_id: str, action: str, portfolio_id: UUID) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, portfolio_id=portfolio_id))


executive_ecosystem_service = ExecutiveEcosystemService()
