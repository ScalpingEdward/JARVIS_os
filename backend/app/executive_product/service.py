from datetime import datetime, timezone
from uuid import UUID

from .models import AuditRecord, ExecutiveProductPortfolio, InitiativeUpdate, ProductPortfolioCreate, ProductStatusResponse


class ExecutiveProductService:
    def __init__(self) -> None:
        self._items: dict[UUID, ExecutiveProductPortfolio] = {}
        self._audit: list[AuditRecord] = []

    def create(self, payload: ProductPortfolioCreate) -> ExecutiveProductPortfolio:
        if any(item.workspace_id == payload.workspace_id and item.name == payload.name for item in self._items.values()):
            raise ValueError("Executive product portfolio already exists")
        item = ExecutiveProductPortfolio(**payload.model_dump())
        self._items[item.portfolio_id] = item
        self._record(item.workspace_id, payload.actor_id, "product_portfolio_created", item.portfolio_id)
        return item

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveProductPortfolio | None:
        item = self._items.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveProductPortfolio]:
        return [item for item in self._items.values() if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> ProductStatusResponse:
        items = self.list_portfolios(workspace_id)
        return ProductStatusResponse(workspace_id=workspace_id, portfolios=len(items), assessed_portfolios=sum(i.assessed_at is not None for i in items))

    def update_initiative(self, portfolio_id: UUID, workspace_id: str, payload: InitiativeUpdate) -> ExecutiveProductPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive product portfolio not found")
        initiative = next((entry for entry in item.initiatives if entry.initiative_id == payload.initiative_id), None)
        if initiative is None:
            raise KeyError("Innovation initiative not found")
        for field in ("investment_required", "expected_annual_value", "feasibility", "execution_risk"):
            value = getattr(payload, field)
            if value is not None:
                setattr(initiative, field, value)
        self._record(workspace_id, payload.actor_id, "innovation_initiative_updated", portfolio_id)
        return item

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveProductPortfolio:
        item = self.get(portfolio_id, workspace_id)
        if item is None:
            raise KeyError("Executive product portfolio not found")
        product_count = len(item.products)
        item.portfolio_health_score = round(sum((p.market_fit + p.strategic_alignment + p.technical_health) / 3 for p in item.products) / product_count, 2)
        item.growth_exposure_score = round(sum(p.growth_potential for p in item.products) / product_count, 2)
        item.technical_debt_exposure = round(sum(100 - p.technical_health for p in item.products) / product_count, 2)
        item.total_innovation_investment = round(sum(i.investment_required for i in item.initiatives), 2)
        item.expected_innovation_value = round(sum(i.expected_annual_value for i in item.initiatives), 2)
        if item.initiatives:
            readiness = [((i.feasibility + i.customer_desirability + i.strategic_alignment) / 3) - i.execution_risk * 0.35 for i in item.initiatives]
            item.innovation_readiness_score = round(max(0, sum(readiness) / len(readiness)), 2)
            item.priority_initiatives = [i.initiative_id for i in item.initiatives if i.feasibility >= 65 and i.customer_desirability >= 70 and i.strategic_alignment >= 70 and i.execution_risk <= 45]
        item.review_products = [p.product_id for p in item.products if p.stage.value in {"mature", "sunset"} and (p.growth_potential < 40 or p.technical_health < 50)]
        recommendations: list[str] = []
        if item.priority_initiatives:
            recommendations.append("Prioritize high-readiness innovation initiatives for executive funding review")
        if item.review_products:
            recommendations.append("Review mature or declining products for modernization, repositioning or retirement")
        if item.technical_debt_exposure >= 40:
            recommendations.append("Allocate product capacity to reduce material technical-debt exposure")
        if item.innovation_readiness_score < 50 and item.initiatives:
            recommendations.append("Strengthen validation and feasibility evidence before scaling innovation investment")
        item.recommendations = recommendations or ["Maintain portfolio trajectory and continue product evidence monitoring"]
        item.assessed_at = datetime.now(timezone.utc)
        self._record(workspace_id, actor_id, "product_portfolio_assessed", portfolio_id)
        return item

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    def _record(self, workspace_id: str, actor_id: str, action: str, portfolio_id: UUID) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, portfolio_id=portfolio_id))


executive_product_service = ExecutiveProductService()
