from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ApprovalRequest,
    AuditRecord,
    CandidateScore,
    ConflictSeverity,
    PortfolioAnalysisRecord,
    PortfolioAnalysisRequest,
    PortfolioCreate,
    PortfolioRecord,
    PortfolioState,
    PortfolioStatus,
    ReplanningAction,
    ResourceConflict,
)


class PlanningPortfolioService:
    def __init__(self) -> None:
        self.portfolios: dict[UUID, PortfolioRecord] = {}
        self.analyses: dict[UUID, PortfolioAnalysisRecord] = {}
        self.audit_records: list[AuditRecord] = []

    def reset(self) -> None:
        self.portfolios.clear()
        self.analyses.clear()
        self.audit_records.clear()

    def create(self, payload: PortfolioCreate) -> PortfolioRecord:
        if any(item.workspace_id == payload.workspace_id and item.key == payload.key for item in self.portfolios.values()):
            raise ValueError("portfolio key already exists in workspace")
        record = PortfolioRecord(**payload.model_dump(exclude={"human_approved", "automatic_external_action"}))
        self.portfolios[record.id] = record
        self._audit(record.workspace_id, record.owner_id, "portfolio.created", record.id, {"key": record.key})
        return record

    def list(self, workspace_id: str) -> list[PortfolioRecord]:
        return sorted(
            [item for item in self.portfolios.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
            reverse=True,
        )

    def get(self, workspace_id: str, portfolio_id: UUID) -> PortfolioRecord | None:
        record = self.portfolios.get(portfolio_id)
        return record if record and record.workspace_id == workspace_id else None

    def analyze(self, portfolio_id: UUID, payload: PortfolioAnalysisRequest) -> PortfolioAnalysisRecord:
        portfolio = self.get(payload.workspace_id, portfolio_id)
        if portfolio is None:
            raise ValueError("portfolio not found")

        max_cost = max((item.estimated_cost for item in portfolio.candidates), default=1.0) or 1.0
        raw_scores: dict[UUID, float] = {}
        for candidate in portfolio.candidates:
            efficiency = max(0.0, 1.0 - candidate.estimated_cost / max_cost)
            raw_scores[candidate.plan_id] = (
                candidate.strategic_value * payload.strategic_weight
                + candidate.urgency * payload.urgency_weight
                + candidate.confidence * payload.confidence_weight
                + efficiency * payload.efficiency_weight
            )

        ordered = sorted(portfolio.candidates, key=lambda item: (-raw_scores[item.plan_id], str(item.plan_id)))
        selected: list[UUID] = []
        deferred: list[UUID] = []
        total_cost = 0.0
        capacity_used: dict[str, float] = {}
        available = {item.capability: item.available_units for item in portfolio.capacity_profiles}
        score_records: list[CandidateScore] = []

        for candidate in ordered:
            blocked = [dep for dep in candidate.dependencies if dep not in selected]
            cost_fit = portfolio.max_total_cost is None or total_cost + candidate.estimated_cost <= portfolio.max_total_cost
            capacity_fit = all(
                capacity_used.get(capability, 0.0) + units <= available.get(capability, 0.0)
                for capability, units in candidate.required_capacity.items()
            )
            within_parallel_limit = len(selected) < portfolio.max_parallel_plans
            reasons: list[str] = []
            if blocked:
                reasons.append("dependencies are not selected yet")
            if not cost_fit:
                reasons.append("portfolio cost limit would be exceeded")
            if not capacity_fit:
                reasons.append("required capability capacity is unavailable")
            if not within_parallel_limit:
                reasons.append("parallel plan limit reached")

            if not blocked and cost_fit and capacity_fit and within_parallel_limit:
                selected.append(candidate.plan_id)
                total_cost += candidate.estimated_cost
                for capability, units in candidate.required_capacity.items():
                    capacity_used[capability] = capacity_used.get(capability, 0.0) + units
                reasons.append("selected by portfolio priority and constraints")
            else:
                deferred.append(candidate.plan_id)

            score_records.append(
                CandidateScore(
                    plan_id=candidate.plan_id,
                    score=round(raw_scores[candidate.plan_id], 4),
                    rank=len(score_records) + 1,
                    blocked_by=blocked,
                    capacity_fit=capacity_fit,
                    cost_fit=cost_fit,
                    reasons=reasons,
                )
            )

        conflicts = self._conflicts(portfolio, selected)
        actions = self._replanning_actions(portfolio, deferred, conflicts)
        record = PortfolioAnalysisRecord(
            portfolio_id=portfolio.id,
            scores=score_records,
            recommended_sequence=selected,
            deferred_plan_ids=deferred,
            conflicts=conflicts,
            replanning_actions=actions,
            total_selected_cost=round(total_cost, 2),
            stable=not conflicts and not deferred,
        )
        self.analyses[record.id] = record
        portfolio.state = PortfolioState.ANALYZED
        portfolio.updated_at = datetime.now(timezone.utc)
        self._audit(portfolio.workspace_id, payload.actor_id, "portfolio.analyzed", portfolio.id, {"analysis_id": str(record.id)})
        return record

    def approve(self, portfolio_id: UUID, payload: ApprovalRequest) -> PortfolioRecord:
        portfolio = self.get(payload.workspace_id, portfolio_id)
        if portfolio is None:
            raise ValueError("portfolio not found")
        if portfolio.owner_id == payload.reviewer_id:
            raise ValueError("portfolio owner cannot self-approve")
        if portfolio.state != PortfolioState.ANALYZED:
            raise ValueError("portfolio must be analyzed before approval")
        portfolio.state = PortfolioState.APPROVED
        portfolio.approved_by = payload.reviewer_id
        portfolio.updated_at = datetime.now(timezone.utc)
        self._audit(portfolio.workspace_id, payload.reviewer_id, "portfolio.approved", portfolio.id, {})
        return portfolio

    def latest_analysis(self, portfolio_id: UUID) -> PortfolioAnalysisRecord | None:
        items = [item for item in self.analyses.values() if item.portfolio_id == portfolio_id]
        return max(items, key=lambda item: item.created_at) if items else None

    def status(self, workspace_id: str) -> PortfolioStatus:
        portfolios = [item for item in self.portfolios.values() if item.workspace_id == workspace_id]
        portfolio_ids = {item.id for item in portfolios}
        analyses = [item for item in self.analyses.values() if item.portfolio_id in portfolio_ids]
        latest = [self.latest_analysis(item.id) for item in portfolios]
        return PortfolioStatus(
            portfolios=len(portfolios),
            analyses=len(analyses),
            approved_portfolios=sum(item.state == PortfolioState.APPROVED for item in portfolios),
            open_conflicts=sum(len(item.conflicts) for item in latest if item is not None),
        )

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self.audit_records if item.workspace_id == workspace_id]

    @staticmethod
    def _conflicts(portfolio: PortfolioRecord, selected: list[UUID]) -> list[ResourceConflict]:
        selected_set = set(selected)
        available = {item.capability: item.available_units for item in portfolio.capacity_profiles}
        usage: dict[str, tuple[float, list[UUID]]] = {}
        for candidate in portfolio.candidates:
            if candidate.plan_id not in selected_set:
                continue
            for capability, units in candidate.required_capacity.items():
                current, plan_ids = usage.get(capability, (0.0, []))
                usage[capability] = (current + units, [*plan_ids, candidate.plan_id])
        conflicts: list[ResourceConflict] = []
        for capability, (required, plan_ids) in usage.items():
            capacity = available.get(capability, 0.0)
            if required <= capacity:
                continue
            deficit = required - capacity
            severity = ConflictSeverity.CRITICAL if capacity == 0 or deficit > capacity else ConflictSeverity.WARNING
            conflicts.append(
                ResourceConflict(
                    capability=capability,
                    required_units=required,
                    available_units=capacity,
                    deficit_units=deficit,
                    plan_ids=plan_ids,
                    severity=severity,
                )
            )
        return sorted(conflicts, key=lambda item: (item.severity.value, item.capability))

    @staticmethod
    def _replanning_actions(
        portfolio: PortfolioRecord,
        deferred: list[UUID],
        conflicts: list[ResourceConflict],
    ) -> list[ReplanningAction]:
        actions = [
            ReplanningAction(
                action="defer-plan",
                plan_id=plan_id,
                reason="Plan does not currently fit portfolio constraints.",
            )
            for plan_id in deferred
        ]
        for conflict in conflicts:
            actions.append(
                ReplanningAction(
                    action="increase-capacity-or-sequence",
                    reason=f"Resolve {conflict.capability} deficit before execution.",
                    metadata={"deficit_units": conflict.deficit_units, "plan_ids": [str(item) for item in conflict.plan_ids]},
                )
            )
        if portfolio.max_total_cost is not None and deferred:
            actions.append(
                ReplanningAction(
                    action="review-budget",
                    reason="Review portfolio budget or reduce candidate scope.",
                    metadata={"max_total_cost": portfolio.max_total_cost},
                )
            )
        return actions

    def _audit(self, workspace_id: str, actor_id: str, action: str, target_id: UUID, details: dict) -> None:
        self.audit_records.append(
            AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, target_id=target_id, details=details)
        )


planning_portfolio_service = PlanningPortfolioService()
