from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    ExecutiveWorkforcePortfolio,
    TalentRiskUpdate,
    WorkforceAssessment,
    WorkforcePortfolioCreate,
    WorkforceStatusResponse,
)


class ExecutiveWorkforceService:
    def __init__(self) -> None:
        self._portfolios: dict[UUID, ExecutiveWorkforcePortfolio] = {}
        self._audit: list[AuditRecord] = []

    def create(self, payload: WorkforcePortfolioCreate) -> ExecutiveWorkforcePortfolio:
        duplicate = any(
            item.workspace_id == payload.workspace_id and item.name.lower() == payload.name.lower()
            for item in self._portfolios.values()
        )
        if duplicate:
            raise ValueError("Executive workforce portfolio already exists")
        portfolio = ExecutiveWorkforcePortfolio(**payload.model_dump())
        self._portfolios[portfolio.id] = portfolio
        self._audit.append(AuditRecord(
            workspace_id=portfolio.workspace_id,
            actor_id=portfolio.executive_owner_id,
            action="workforce_portfolio_created",
            resource_id=portfolio.id,
            details={"name": portfolio.name},
        ))
        return portfolio

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveWorkforcePortfolio | None:
        item = self._portfolios.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveWorkforcePortfolio]:
        return [item for item in self._portfolios.values() if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> WorkforceStatusResponse:
        items = self.list_portfolios(workspace_id)
        segments = [segment for item in items for segment in item.segments]
        return WorkforceStatusResponse(
            workspace_id=workspace_id,
            portfolios=len(items),
            total_headcount=sum(item.headcount for item in segments),
            critical_segments=sum(item.criticality.value == "critical" for item in segments),
            high_retention_risk_segments=sum(item.retention_risk >= 0.6 for item in segments),
        )

    def update_risk(self, portfolio_id: UUID, workspace_id: str, payload: TalentRiskUpdate) -> ExecutiveWorkforcePortfolio:
        portfolio = self.get(portfolio_id, workspace_id)
        if portfolio is None:
            raise KeyError("Executive workforce portfolio not found")
        risk = next((item for item in portfolio.risks if item.risk_id == payload.risk_id), None)
        if risk is None:
            raise KeyError("Talent risk not found")
        risk.remediation_progress = payload.remediation_progress
        portfolio.updated_at = datetime.now(timezone.utc)
        self._audit.append(AuditRecord(
            workspace_id=workspace_id,
            actor_id=payload.actor_id,
            action="talent_risk_updated",
            resource_id=portfolio.id,
            details={"risk_id": payload.risk_id, "remediation_progress": payload.remediation_progress},
        ))
        return portfolio

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveWorkforcePortfolio:
        portfolio = self.get(portfolio_id, workspace_id)
        if portfolio is None:
            raise KeyError("Executive workforce portfolio not found")
        total = max(sum(item.headcount for item in portfolio.segments), 1)
        weighted = lambda field: sum(getattr(item, field) * item.headcount for item in portfolio.segments) / total
        capacity = max(0.0, 100 - abs(weighted("capacity_utilization") - 0.85) * 200)
        skills = weighted("skill_coverage") * 100
        succession = weighted("succession_coverage") * 100
        retention = weighted("retention_risk") * 100
        engagement = weighted("engagement_score")
        health = max(0.0, min(100.0, engagement * 0.3 + skills * 0.25 + succession * 0.2 + capacity * 0.15 + (100 - retention) * 0.1))
        critical_segments = [item.segment_id for item in portfolio.segments if item.criticality.value == "critical" and (item.skill_coverage < 0.7 or item.retention_risk >= 0.5)]
        vulnerable_roles = [item.role_id for item in portfolio.critical_roles if item.incumbents < item.required_incumbents or item.ready_successors == 0 or item.attrition_risk >= 0.5]
        priority_risks = [item.risk_id for item in portfolio.risks if item.severity * item.probability * (1 - item.remediation_progress) >= 0.35]
        actions: list[str] = []
        if critical_segments:
            actions.append("Fund targeted capability and retention plans for critical workforce segments")
        if vulnerable_roles:
            actions.append("Create succession and accelerated hiring plans for vulnerable critical roles")
        if capacity < 65:
            actions.append("Rebalance workload and capacity before approving additional strategic commitments")
        if priority_risks:
            actions.append("Escalate priority talent risks with named owners and dated remediation milestones")
        portfolio.assessment = WorkforceAssessment(
            workforce_health_score=round(health, 2),
            capacity_resilience_score=round(capacity, 2),
            skill_readiness_score=round(skills, 2),
            succession_readiness_score=round(succession, 2),
            retention_exposure_score=round(retention, 2),
            critical_segments=critical_segments,
            vulnerable_roles=vulnerable_roles,
            priority_risks=priority_risks,
            executive_actions=actions,
        )
        portfolio.updated_at = datetime.now(timezone.utc)
        self._audit.append(AuditRecord(
            workspace_id=workspace_id,
            actor_id=actor_id,
            action="workforce_portfolio_assessed",
            resource_id=portfolio.id,
            details={"workforce_health_score": portfolio.assessment.workforce_health_score},
        ))
        return portfolio

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_workforce_service = ExecutiveWorkforceService()
