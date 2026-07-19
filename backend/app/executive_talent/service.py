from datetime import datetime, timezone
from threading import RLock
from uuid import UUID

from .models import AuditRecord, ExecutiveTalentPortfolio, RiskLevel, TalentPortfolioCreate, TalentStatusResponse, TalentUpdate


class ExecutiveTalentService:
    def __init__(self) -> None:
        self._items: dict[UUID, ExecutiveTalentPortfolio] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    def create(self, payload: TalentPortfolioCreate) -> ExecutiveTalentPortfolio:
        with self._lock:
            if any(item.workspace_id == payload.workspace_id and item.name.lower() == payload.name.lower() for item in self._items.values()):
                raise ValueError("Executive talent portfolio already exists")
            item = ExecutiveTalentPortfolio(**payload.model_dump())
            self._items[item.portfolio_id] = item
            self._record(item, "created", payload.executive_owner_id)
            return item

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveTalentPortfolio | None:
        item = self._items.get(portfolio_id)
        return item if item and item.workspace_id == workspace_id else None

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveTalentPortfolio]:
        return [item for item in self._items.values() if item.workspace_id == workspace_id]

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveTalentPortfolio:
        with self._lock:
            item = self.get(portfolio_id, workspace_id)
            if item is None:
                raise KeyError("Executive talent portfolio not found")
            total_required = sum(role.required_capacity for role in item.roles)
            total_available = sum(min(role.available_capacity, role.required_capacity) for role in item.roles)
            item.capacity_coverage_score = round(100 * total_available / total_required, 2) if total_required else 100
            skill_scores = []
            for role in item.roles:
                required = set(role.required_skills)
                covered = set(role.covered_skills)
                skill_scores.append(100 * len(required & covered) / len(required) if required else 100)
            item.skill_coverage_score = round(sum(skill_scores) / len(skill_scores), 2)
            critical_roles = [role for role in item.roles if role.criticality.value == "critical"]
            ready_roles = 0
            gaps = []
            for role in critical_roles:
                candidates = [c for c in item.successors if c.role_id == role.role_id and c.readiness_score >= 70]
                if candidates:
                    ready_roles += 1
                else:
                    gaps.append(role.role_id)
            item.succession_readiness_score = round(100 * ready_roles / len(critical_roles), 2) if critical_roles else 100
            weights = {RiskLevel.low: 5, RiskLevel.medium: 30, RiskLevel.high: 70, RiskLevel.critical: 100}
            item.retention_exposure_score = round(sum(weights[role.retention_risk] for role in item.roles) / len(item.roles), 2)
            scenario_exposure = sum(s.probability * s.capacity_impact * (1 - s.mitigation_strength / 100) for s in item.scenarios)
            item.workforce_resilience_score = round(max(0, min(100, (item.capacity_coverage_score + item.skill_coverage_score + item.succession_readiness_score + (100 - item.retention_exposure_score) + max(0, 100 - scenario_exposure)) / 5)), 2)
            item.critical_role_gaps = gaps
            actions = []
            if gaps:
                actions.append("Accelerate succession plans for uncovered critical roles")
            if item.capacity_coverage_score < 85:
                actions.append("Rebalance capacity or recruit against constrained roles")
            if item.skill_coverage_score < 80:
                actions.append("Fund targeted capability development for material skill gaps")
            if item.retention_exposure_score >= 50:
                actions.append("Launch retention interventions for high-risk role holders")
            item.executive_actions = actions
            item.assessed_at = item.updated_at = datetime.now(timezone.utc)
            self._record(item, "assessed", actor_id)
            return item

    def update(self, portfolio_id: UUID, workspace_id: str, payload: TalentUpdate) -> ExecutiveTalentPortfolio:
        with self._lock:
            item = self.get(portfolio_id, workspace_id)
            if item is None:
                raise KeyError("Executive talent portfolio not found")
            role = next((r for r in item.roles if r.role_id == payload.role_id), None)
            if role is None:
                raise KeyError("Talent role not found")
            if payload.available_capacity is not None:
                role.available_capacity = payload.available_capacity
            if payload.retention_risk is not None:
                role.retention_risk = payload.retention_risk
            if payload.candidate_id is not None:
                candidate = next((c for c in item.successors if c.candidate_id == payload.candidate_id and c.role_id == role.role_id), None)
                if candidate is None:
                    raise KeyError("Successor candidate not found")
                if payload.readiness is not None:
                    candidate.readiness = payload.readiness
                if payload.readiness_score is not None:
                    candidate.readiness_score = payload.readiness_score
            item.updated_at = datetime.now(timezone.utc)
            self._record(item, "updated", payload.actor_id)
            return item

    def status(self, workspace_id: str) -> TalentStatusResponse:
        items = self.list_portfolios(workspace_id)
        critical = [r for item in items for r in item.roles if r.criticality.value == "critical"]
        gaps = sum(len(item.critical_role_gaps) for item in items)
        average = round(sum(item.workforce_resilience_score for item in items) / len(items), 2) if items else 0
        return TalentStatusResponse(workspace_id=workspace_id, portfolios=len(items), critical_roles=len(critical), uncovered_critical_roles=gaps, average_resilience_score=average)

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    def _record(self, item: ExecutiveTalentPortfolio, action: str, actor_id: str) -> None:
        self._audit.append(AuditRecord(workspace_id=item.workspace_id, portfolio_id=item.portfolio_id, action=action, actor_id=actor_id))


executive_talent_service = ExecutiveTalentService()
