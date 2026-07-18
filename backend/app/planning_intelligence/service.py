from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ApprovalRequest,
    AuditRecord,
    GoalCreate,
    GoalRecord,
    MissionHandoffPreview,
    OptionEvaluation,
    PlanCreate,
    PlanRecord,
    PlanState,
    PlanningStatus,
    RiskLevel,
    SensitivityPoint,
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
        referenced = [payload.parent_goal_id, *payload.dependency_goal_ids]
        for goal_id in [item for item in referenced if item is not None]:
            goal = self.goals.get(goal_id)
            if goal is None or goal.workspace_id != payload.workspace_id:
                raise ValueError("referenced goal not found in workspace")
        if len(set(payload.dependency_goal_ids)) != len(payload.dependency_goal_ids):
            raise ValueError("dependency goals must be unique")
        record = GoalRecord(**payload.model_dump(exclude={"human_approved", "automatic_external_action"}))
        self.goals[record.id] = record
        self._audit(record.workspace_id, record.owner_id, "goal.created", "goal", record.id, {"key": record.key})
        return record

    def list_goals(self, workspace_id: str) -> list[GoalRecord]:
        return sorted(
            [item for item in self.goals.values() if item.workspace_id == workspace_id],
            key=lambda item: (-item.priority, item.deadline or datetime.max.replace(tzinfo=timezone.utc), item.key),
        )

    def goal_tree(self, workspace_id: str, root_goal_id: UUID) -> list[GoalRecord]:
        root = self.goals.get(root_goal_id)
        if root is None or root.workspace_id != workspace_id:
            raise ValueError("goal not found")
        result: list[GoalRecord] = []
        queue = [root.id]
        while queue:
            current = queue.pop(0)
            children = sorted(
                [item for item in self.goals.values() if item.workspace_id == workspace_id and item.parent_goal_id == current],
                key=lambda item: (-item.priority, item.key),
            )
            result.extend(children)
            queue.extend(item.id for item in children)
        return [root, *result]

    def create_plan(self, payload: PlanCreate) -> PlanRecord:
        goal = self.goals.get(payload.goal_id)
        if goal is None or goal.workspace_id != payload.workspace_id:
            raise ValueError("goal not found in workspace")
        if any(item.workspace_id == payload.workspace_id and item.key == payload.key for item in self.plans.values()):
            raise ValueError("plan key already exists in workspace")
        objective_keys = {item.key for item in goal.objectives}
        for option in payload.options:
            unknown = {item.objective_key for item in option.objective_contributions} - objective_keys
            if unknown:
                raise ValueError("option objective contributions must reference goal objectives")
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
        evaluations = self._evaluate(plan, payload)
        ranked = sorted(evaluations, key=lambda item: (-item.total_score, item.option_key))
        winner = next((item for item in ranked if item.feasible), None)
        confidence = self._confidence(ranked)
        record = SimulationRecord(
            plan_id=plan.id,
            scenario_name=payload.scenario_name,
            evaluations=ranked,
            recommended_option_key=winner.option_key if winner else None,
            confidence=confidence,
            sensitivity=self._sensitivity(plan, payload),
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

    def mission_handoff_preview(self, workspace_id: str, plan_id: UUID) -> MissionHandoffPreview:
        plan = self.get_plan(workspace_id, plan_id)
        if plan is None:
            raise ValueError("plan not found")
        if plan.state != PlanState.EXECUTION_READY or not plan.selected_option_key or not plan.approved_by:
            raise ValueError("plan must be independently approved and execution-ready")
        option = next(item for item in plan.options if item.key == plan.selected_option_key)
        return MissionHandoffPreview(
            plan_id=plan.id,
            mission_template_key=plan.mission_template_key,
            selected_option_key=option.key,
            required_capabilities=option.required_capabilities,
            tasks=option.steps,
            knowledge_entity_ids=plan.knowledge_entity_ids,
            affected_entity_ids=plan.affected_entity_ids,
            rollback_plan=option.rollback_plan,
        )

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

    def _evaluate(self, plan: PlanRecord, payload: SimulationRequest) -> list[OptionEvaluation]:
        goal = self.goals[plan.goal_id]
        max_cost = max((option.estimated_cost for option in plan.options), default=1.0) or 1.0
        max_duration = max((option.estimated_duration_minutes for option in plan.options), default=1) or 1
        total_objective_weight = sum(item.weight for item in goal.objectives) or 1.0
        evaluations: list[OptionEvaluation] = []
        for option in plan.options:
            reasons: list[str] = []
            feasible = True
            effective_cost_limit = min(value for value in [plan.max_cost, goal.budget] if value is not None) if any(value is not None for value in [plan.max_cost, goal.budget]) else None
            if effective_cost_limit is not None and option.estimated_cost > effective_cost_limit:
                feasible = False
                reasons.append("cost exceeds governed budget")
            if plan.max_duration_minutes is not None and option.estimated_duration_minutes > plan.max_duration_minutes:
                feasible = False
                reasons.append("duration exceeds plan limit")
            contributions = {item.objective_key: item.score for item in option.objective_contributions}
            if contributions:
                objective_score = sum(item.weight * contributions.get(item.key, 0.0) for item in goal.objectives) / total_objective_weight
            else:
                objective_score = min(1.0, 0.55 + (0.03 * len(goal.objectives)) + (0.02 * len(option.steps)))
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
            if feasible:
                reasons.append("satisfies configured hard constraints")
            evaluations.append(OptionEvaluation(
                option_key=option.key,
                objective_score=round(objective_score, 4),
                risk_score=round(risk_score, 4),
                cost_score=round(cost_score, 4),
                duration_score=round(duration_score, 4),
                total_score=round(total, 4),
                feasible=feasible,
                reasons=reasons,
            ))
        return evaluations

    def _sensitivity(self, plan: PlanRecord, payload: SimulationRequest) -> list[SensitivityPoint]:
        factors = ["risk_weight", "cost_weight", "duration_weight", "objective_weight"]
        points: list[SensitivityPoint] = []
        base = payload.model_dump()
        for factor in factors:
            for delta in (-payload.sensitivity_delta, payload.sensitivity_delta):
                weights = {name: base[name] for name in factors}
                weights[factor] = max(0.0, weights[factor] + delta)
                total = sum(weights.values()) or 1.0
                normalized = {name: value / total for name, value in weights.items()}
                scenario = SimulationRequest(
                    workspace_id=payload.workspace_id,
                    actor_id=payload.actor_id,
                    scenario_name=f"sensitivity:{factor}:{delta:+.2f}",
                    sensitivity_delta=payload.sensitivity_delta,
                    **normalized,
                )
                ranked = sorted(self._evaluate(plan, scenario), key=lambda item: (-item.total_score, item.option_key))
                winner = next((item for item in ranked if item.feasible), None)
                points.append(SensitivityPoint(
                    factor=factor,
                    delta=delta,
                    recommended_option_key=winner.option_key if winner else None,
                    confidence=self._confidence(ranked),
                ))
        return points

    @staticmethod
    def _confidence(ranked: list[OptionEvaluation]) -> float:
        feasible = [item for item in ranked if item.feasible]
        if not feasible:
            return 0.0
        if len(feasible) == 1:
            return round(feasible[0].total_score, 4)
        margin = max(0.0, feasible[0].total_score - feasible[1].total_score)
        return round(min(1.0, (feasible[0].total_score * 0.7) + (margin * 0.3)), 4)

    @staticmethod
    def _explain(simulation: SimulationRecord) -> list[str]:
        if not simulation.recommended_option_key:
            return ["No feasible option satisfied the configured constraints."]
        winner = next(item for item in simulation.evaluations if item.option_key == simulation.recommended_option_key)
        stable = sum(item.recommended_option_key == winner.option_key for item in simulation.sensitivity)
        return [
            f"Selected {winner.option_key} with MCDA score {winner.total_score:.4f}.",
            f"Objective {winner.objective_score:.4f}; risk {winner.risk_score:.4f}; cost {winner.cost_score:.4f}; duration {winner.duration_score:.4f}.",
            f"Recommendation remained stable in {stable}/{len(simulation.sensitivity)} sensitivity scenarios.",
            "Recommendation is advisory until an independent human reviewer approves it.",
        ]

    def _audit(self, workspace_id: str, actor_id: str, action: str, target_type: str, target_id: UUID, details: dict) -> None:
        self.audit_records.append(AuditRecord(
            workspace_id=workspace_id,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        ))


planning_intelligence_service = PlanningIntelligenceService()
