from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    Criticality,
    ExecutiveProcurementPortfolio,
    ProcurementAssessment,
    ProcurementPortfolioCreate,
    ProcurementStatusResponse,
    RiskLevel,
    ThirdPartyIssueUpdate,
)


class ExecutiveProcurementService:
    def __init__(self) -> None:
        self._portfolios: dict[UUID, ExecutiveProcurementPortfolio] = {}
        self._audit: list[AuditRecord] = []

    def create(self, payload: ProcurementPortfolioCreate) -> ExecutiveProcurementPortfolio:
        if any(item.workspace_id == payload.workspace_id and item.name == payload.name for item in self._portfolios.values()):
            raise ValueError("Executive procurement portfolio already exists")
        portfolio = ExecutiveProcurementPortfolio(**payload.model_dump())
        self._portfolios[portfolio.id] = portfolio
        self._record(payload.workspace_id, payload.executive_owner_id, "procurement_portfolio_created", portfolio.id)
        return portfolio

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveProcurementPortfolio | None:
        item = self._portfolios.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveProcurementPortfolio]:
        return [item for item in self._portfolios.values() if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> ProcurementStatusResponse:
        items = self.list_portfolios(workspace_id)
        suppliers = [supplier for item in items for supplier in item.suppliers]
        issues = [issue for item in items for issue in item.issues]
        return ProcurementStatusResponse(
            workspace_id=workspace_id,
            portfolios=len(items),
            suppliers=len(suppliers),
            critical_suppliers=sum(1 for item in suppliers if item.criticality == Criticality.critical),
            open_priority_issues=sum(1 for item in issues if item.risk_level in {RiskLevel.high, RiskLevel.severe} and item.remediation_progress < 1),
        )

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveProcurementPortfolio:
        portfolio = self.get(portfolio_id, workspace_id)
        if portfolio is None:
            raise KeyError("Executive procurement portfolio not found")
        suppliers = portfolio.suppliers
        total_spend = sum(item.annual_spend for item in suppliers)
        shares = [item.annual_spend / total_spend if total_spend else 0 for item in suppliers]
        concentration = max(shares, default=0) * 100
        supplier_health = sum((item.sla_performance + item.compliance_score + (1 - item.operational_risk)) / 3 for item in suppliers) / len(suppliers) * 100
        contract_governance = sum(item.contract_coverage for item in suppliers) / len(suppliers) * 100
        third_party_risk = sum((item.cyber_risk + item.operational_risk + item.financial_risk) / 3 for item in suppliers) / len(suppliers) * 100
        exit_readiness = sum((item.exit_readiness + item.substitutability) / 2 for item in suppliers) / len(suppliers) * 100
        critical = [item.supplier_id for item in suppliers if item.criticality == Criticality.critical]
        vulnerable = [item.supplier_id for item in suppliers if max(item.cyber_risk, item.operational_risk, item.financial_risk) >= 0.7 or item.exit_readiness < 0.4]
        priority = [item.issue_id for item in portfolio.issues if item.risk_level in {RiskLevel.high, RiskLevel.severe} and item.remediation_progress < 0.8]
        actions: list[str] = []
        if concentration >= 35:
            actions.append("Diversify high-spend supplier concentration and establish alternate sourcing capacity.")
        if third_party_risk >= 55:
            actions.append("Escalate cyber, operational and financial due diligence for vulnerable suppliers.")
        if contract_governance < 75:
            actions.append("Close contract, SLA and control-coverage gaps for material suppliers.")
        if exit_readiness < 60:
            actions.append("Build tested exit, transition and substitution plans for critical suppliers.")
        if priority:
            actions.append("Assign executive owners and deadlines to priority third-party issues.")
        portfolio.assessment = ProcurementAssessment(
            supplier_health_score=round(supplier_health, 2),
            contract_governance_score=round(contract_governance, 2),
            concentration_exposure_score=round(concentration, 2),
            third_party_risk_score=round(third_party_risk, 2),
            exit_readiness_score=round(exit_readiness, 2),
            critical_suppliers=critical,
            vulnerable_suppliers=vulnerable,
            priority_issues=priority,
            executive_actions=actions,
        )
        portfolio.updated_at = datetime.now(timezone.utc)
        self._record(workspace_id, actor_id, "procurement_portfolio_assessed", portfolio.id)
        return portfolio

    def update_issue(self, portfolio_id: UUID, workspace_id: str, payload: ThirdPartyIssueUpdate) -> ExecutiveProcurementPortfolio:
        portfolio = self.get(portfolio_id, workspace_id)
        if portfolio is None:
            raise KeyError("Executive procurement portfolio not found")
        issue = next((item for item in portfolio.issues if item.issue_id == payload.issue_id), None)
        if issue is None:
            raise KeyError("Third-party issue not found")
        issue.remediation_progress = payload.remediation_progress
        portfolio.updated_at = datetime.now(timezone.utc)
        self._record(workspace_id, payload.actor_id, "third_party_issue_updated", portfolio.id, {"issue_id": payload.issue_id, "note": payload.note})
        return portfolio

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _record(self, workspace_id: str, actor_id: str, action: str, resource_id: UUID, details: dict[str, object] | None = None) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, resource_id=resource_id, details=details or {}))


executive_procurement_service = ExecutiveProcurementService()
