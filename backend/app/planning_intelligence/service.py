from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ApprovalRequest,
    AuditRecord,
    GoalCreate,
    GoalRecord,
    OptionEvaluation,
    PlanCreate,
    PlanRecord,
    PlanState,
    PlanningStatus,
    RiskLevel,
    SimulationRecord,
    SimulationRequest,
)


_RISK_SCORES = {
    RiskLevel.LOW: 1.0,
    RiskLevel.MEDIUM: 0.7,
    RiskLevel.HIGH: 0.35,
    RiskLevel.CRITICAL: 0.0,
}


class PlanningIntelligenceService:
    def __init__(self) -> None:
        self.goals: dict[UUID, GoalRecord] = {}
        self.plans: dict[UUID, PlanRecord] = {}
        self.simulations: dict[UUID, SimulationRecord] = {}
        self.audit_records: list[AuditRecord] = []

    def reset(self) -> None:
        self.goals.clear()
        self.plans.clear()
        self.simulations.clear()
        self.audit_records.clear()

    def create_goal(self, payload: GoalCreate) -> GoalRecord:
        if any(item.workspace_id == payload.workspace_id and item.key == payload.key for item in self.goals.values()):
            raise ValueError("goal key already exists in workspace")
        record = GoalRecord(**payload.model_dump(exclude={"human_approved", "automatic_external_action"}))
        self.goals[record.id] = record
        self._audit(record.workspace_id, record.owner_id, "goal.created", "goal", record.id, {"key": record.key})
        return record

    def list_goals(self, workspace_id: str) -> list[GoalRecord]:
        return sorted(
            [item for item in self.goals.values() if item.workspace_id == workspace_id],
            key=lambda item: (-item.priority, item.key),
        )

    def create_plan(self, payload: PlanCreate) -> PlanRecord:
        goal = self.goals.get(payload.goal_id)
        if goal is None or goal.workspace_id != payload.workspace_id:
            raise ValueError("goal not found in workspace")
        if any(item.workspace_id == payload.workspace_id and item.key == payload.key for item in self.plans.values()):
            raise ValueError("plan key already exists in workspace")
        record = PlanRecord(**payload.model_dump(exclude={"human_approved", "automatic_external_action"}))
        record.state = PlanState.ANALYZED
        self.plans[record.id] = record
        self._audit(record.workspace_id, record.owner_id, "plan.created", "plan", record.id, {"key": record.key})
        return record

    def list_plans(self, workspace_id: str) -> list[PlanRecord]:
        return sorted(
            [item for item in self.plans.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
            reverse=True,
        )

    def get_plan(self, workspace_id: str, plan_id: UUID) -> PlanRecord | None:
        plan = self.plans.get(plan_id)
        return plan if plan and plan.workspace_id == workspace_id else None

    def simulate(self, plan_id: UUID, payload: SimulationRequest) -> SimulationRecord:
        plan = self.get_plan(payload.workspace_id, plan_id)
        if plan is None:
            raise ValueError("plan not found")
        goal = self.goals[plan.goal_id]
        max_cost = max((option.estimated_cost for option in plan.options), default=1.0) or 1.0
        max_duration = max((option.estimated_duration_minutes for option in plan.options), default=1) or 1
        evaluations: list[OptionEvaluation] = []
        for option in plan.options:
            reasons: list[str] = []
            feasible = True
            if plan.max_cost is not None and option.estimated_cost > plan.max_cost:
                feasible = False
                reasons.append("cost exceeds plan limit")
            if plan.max_duration_minutes is not None and option.estimated_duration_minutes > plan.max_duration_minutes:
                feasible = False
                reasons.append("duration exceeds plan limit")
            objective_score = min(1.0, 0.6 + (0.04 * len(goal.objectives)) + (0.02 * len(option.steps)))
            risk_score = _RISK_SCORES[option.risk_level]
            cost_score = max(0.0, 1.0 - (option.estimated_cost / max_cost))
            duration_score = max(0.0, 1.0 - (option.estimated_duration_minutes / max_duration))
            total = (
                objective_score * payload.objective_weight
                + risk_score * payload.risk_weight
                + cost_score * payload.cost_weight
                + duration_score * payload.duration_weight
            )
            if not feasible:
                total = 0.0
            if feasible and not reasons:
                reasons.append("satisfies configured cost and duration constraints")
            evaluations.append(
                OptionEvaluation(
                    option_key=option.key,
                    objective_score=round(objective_score, 4),
                    risk_score=round(risk_score, 4),
                    cost_score=round(cost_score, 4),
                    duration_score=round(duration_score, 4),
                    total_score=round(total, 4),
                    feasible=feasible,
                    reasons=reasons,
                )
            )
        ranked = sorted(evaluations, key=lambda item: (-item.total_score, item.option_key))
        winner = next((item for item in ranked if item.feasible), None)
        confidence = winner.total_score if winner else 0.0
        record = SimulationRecord(
            plan_id=plan.id,
            scenario_name=payload.scenario_name,
            evaluations=ranked,
            recommended_option_key=winner.option_key if winner else None,
            confidence=round(confidence, 4),
        )
        self.simulations[record.id] = record
        plan.state = PlanState.SIMULATED
        plan.selected_option_key = record.recommended_option_key
        plan.decision_explanation = self._explain(record)
        plan.updated_at = datetime.now(timezone.utc)
        self._audit(plan.workspace_id, payload.actor_id, "plan.simulated", "plan", plan.id, {"scenario": payload.scenario_name})
        return record

    def approve(self, plan_id: UUID, payload: ApprovalRequest) -> PlanRecord:
        plan = self.get_plan(payload.workspace_id, plan_id)
        if plan is None:
            raise ValueError("plan not found")
        if plan.owner_id == payload.reviewer_id:
            raise ValueError("plan owner cannot self-approve")
        if plan.state != PlanState.SIMULATED:
            raise ValueError("plan must be simulated before approval")
        if payload.selected_option_key not in {item.key for item in plan.options}:
            raise ValueError("selected option not found")
        latest = self.latest_simulation(plan.id)
        evaluation = next((item for item in latest.evaluations if item.option_key == payload.selected_option_key), None) if latest else None
        if evaluation is None or not evaluation.feasible:
            raise ValueError("selected option is not feasible")
        plan.selected_option_key = payload.selected_option_key
        plan.approved_by = payload.reviewer_id
        plan.state = PlanState.EXECUTION_READY
        plan.version += 1
        plan.updated_at = datetime.now(timezone.utc)
        self._audit(plan.workspace_id, payload.reviewer_id, "plan.approved", "plan", plan.id, {"option": payload.selected_option_key})
        return plan

    def archive(self, workspace_id: str, plan_id: UUID, actor_id: str) -> PlanRecord:
        plan = self.get_plan(workspace_id, plan_id)
        if plan is None:
            raise ValueError("plan not found")
        plan.state = PlanState.ARCHIVED
        plan.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, actor_id, "plan.archived", "plan", plan.id, {})
        return plan

    def latest_simulation(self, plan_id: UUID) -> SimulationRecord | None:
        items = [item for item in self.simulations.values() if item.plan_id == plan_id]
        return max(items, key=lambda item: item.created_at) if items else None

    def status(self, workspace_id: str) -> PlanningStatus:
        goals = [item for item in self.goals.values() if item.workspace_id == workspace_id]
        plans = [item for item in self.plans.values() if item.workspace_id == workspace_id]
        plan_ids = {item.id for item in plans}
        simulations = [item for item in self.simulations.values() if item.plan_id in plan_ids]
        return PlanningStatus(
            goals=len(goals),
            plans=len(plans),
            simulations=len(simulations),
            execution_ready_plans=sum(item.state == PlanState.EXECUTION_READY for item in plans),
        )

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self.audit_records if item.workspace_id == workspace_id]

    @staticmethod
    def _explain(simulation: SimulationRecord) -> list[str]:
        if not simulation.recommended_option_key:
            return ["No feasible option satisfied the configured constraints."]
        winner = next(item for item in simulation.evaluations if item.option_key == simulation.recommended_option_key)
        return [
            f"Selected {winner.option_key} with total score {winner.total_score:.4f}.",
            f"Risk score {winner.risk_score:.4f}; cost score {winner.cost_score:.4f}; duration score {winner.duration_score:.4f}.",
            "Recommendation is advisory until an independent human reviewer approves it.",
        ]

    def _audit(self, workspace_id: str, actor_id: str, action: str, target_type: str, target_id: UUID, details: dict) -> None:
        self.audit_records.append(
            AuditRecord(
                workspace_id=workspace_id,
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details,
            )
        )


planning_intelligence_service = PlanningIntelligenceService()
