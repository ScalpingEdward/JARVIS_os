from datetime import datetime, timezone
from uuid import UUID

from .models import AuditRecord, DataAIPortfolioCreate, DataAIStatusResponse, ExecutiveDataAIPortfolio, GovernanceUpdate


class ExecutiveDataAIService:
    def __init__(self) -> None:
        self._items: dict[UUID, ExecutiveDataAIPortfolio] = {}
        self._audit: list[AuditRecord] = []

    def create(self, payload: DataAIPortfolioCreate) -> ExecutiveDataAIPortfolio:
        if any(item.workspace_id == payload.workspace_id and item.name == payload.name for item in self._items.values()):
            raise ValueError("Executive data AI portfolio already exists")
        item = ExecutiveDataAIPortfolio(**payload.model_dump())
        self._items[item.portfolio_id] = item
        self._record(item.workspace_id, payload.actor_id, "data_ai_portfolio_created", item.portfolio_id)
        return item

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveDataAIPortfolio | None:
        item = self._items.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveDataAIPortfolio]:
        return [item for item in self._items.values() if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> DataAIStatusResponse:
        items = self.list_portfolios(workspace_id)
        return DataAIStatusResponse(
            workspace_id=workspace_id,
            portfolios=len(items),
            assessed_portfolios=sum(item.assessed_at is not None for item in items),
        )

    def update_issue(self, portfolio_id: UUID, workspace_id: str, payload: GovernanceUpdate) -> ExecutiveDataAIPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive data AI portfolio not found")
        issue = next((value for value in item.issues if value.issue_id == payload.issue_id), None)
        if issue is None:
            raise KeyError("Governance issue not found")
        issue.remediation_progress = payload.remediation_progress
        self._record(workspace_id, payload.actor_id, "governance_issue_updated", portfolio_id)
        return item

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveDataAIPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive data AI portfolio not found")

        products = item.data_products
        systems = item.ai_systems
        issues = item.issues
        if products:
            item.data_governance_score = round(sum(
                (p.quality_score + p.lineage_coverage + p.access_control_score + (100 - p.privacy_risk)) / 4
                for p in products
            ) / len(products), 2)
        if systems:
            item.ai_governance_score = round(sum(
                (s.model_performance + s.explainability + s.human_oversight + s.compliance_readiness + (100 - s.bias_risk) + (100 - s.drift_risk)) / 6
                for s in systems
            ) / len(systems), 2)
            item.model_risk_exposure = round(sum((s.bias_risk + s.drift_risk + (100 - s.human_oversight)) / 3 for s in systems) / len(systems), 2)
        open_issue_exposure = sum(issue.severity * (100 - issue.remediation_progress) / 100 for issue in issues)
        item.compliance_exposure = round(open_issue_exposure / max(len(issues), 1), 2)
        item.critical_data_products = [p.data_product_id for p in products if p.business_criticality >= 70 and (p.quality_score < 70 or p.privacy_risk >= 60)]
        item.high_risk_ai_systems = [s.ai_system_id for s in systems if s.risk_level.value in {"high", "critical"} and (s.human_oversight < 70 or s.compliance_readiness < 70)]

        recs: list[str] = []
        if item.critical_data_products:
            recs.append("Prioritize remediation of critical data products with quality or privacy exposure")
        if item.high_risk_ai_systems:
            recs.append("Escalate high-risk AI systems for executive governance review")
        if item.model_risk_exposure >= 40:
            recs.append("Strengthen model monitoring, bias controls and human oversight")
        if item.compliance_exposure >= 30:
            recs.append("Accelerate remediation of material governance and compliance issues")
        item.recommendations = recs or ["Maintain current controls and continue periodic governance assessment"]
        item.assessed_at = datetime.now(timezone.utc)
        self._record(workspace_id, actor_id, "data_ai_portfolio_assessed", portfolio_id)
        return item

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    def _record(self, workspace_id: str, actor_id: str, action: str, portfolio_id: UUID) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, portfolio_id=portfolio_id))


executive_data_ai_service = ExecutiveDataAIService()
