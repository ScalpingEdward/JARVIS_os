from datetime import datetime, timezone
from threading import RLock
from uuid import UUID

from .models import (
    AuditRecord,
    ExecutiveStrategyCreate,
    ExecutiveStrategyPlan,
    InitiativeAnalysis,
    Milestone,
    StrategicRoadmapItem,
    StrategyAnalysis,
    StrategyStatus,
    StrategyStatusResponse,
    WhatIfRequest,
)


class ExecutiveStrategyService:
    def __init__(self) -> None:
        self._plans: dict[UUID, ExecutiveStrategyPlan] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _write_audit(self, workspace_id: str, action: str, actor_id: str, plan_id: UUID | None = None, details: dict | None = None) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, action=action, actor_id=actor_id, plan_id=plan_id, details=details or {}, created_at=self._now()))

    def create(self, payload: ExecutiveStrategyCreate) -> ExecutiveStrategyPlan:
        now = self._now()
        record = ExecutiveStrategyPlan(**payload.model_dump(), created_at=now, updated_at=now)
        with self._lock:
            if any(item.workspace_id == payload.workspace_id and item.title == payload.title for item in self._plans.values()):
                raise ValueError("An executive strategy plan with this title already exists in the workspace")
            self._plans[record.id] = record
            self._write_audit(payload.workspace_id, "executive-strategy-created", payload.owner_id, record.id, {"objectives": len(payload.objectives), "initiatives": len(payload.initiatives)})
        return record

    def list_plans(self, workspace_id: str) -> list[ExecutiveStrategyPlan]:
        with self._lock:
            return [item for item in self._plans.values() if item.workspace_id == workspace_id]

    def get(self, plan_id: UUID, workspace_id: str) -> ExecutiveStrategyPlan | None:
        with self._lock:
            record = self._plans.get(plan_id)
            return record if record is not None and record.workspace_id == workspace_id else None

    @staticmethod
    def _topological_order(initiatives) -> list[str]:
        graph = {item.initiative_key: list(item.dependencies) for item in initiatives}
        remaining = set(graph)
        order: list[str] = []
        while remaining:
            ready = sorted(key for key in remaining if all(dep in order for dep in graph[key]))
            if not ready:
                raise ValueError("Strategic dependency graph contains a cycle")
            order.extend(ready)
            remaining.difference_update(ready)
        return order

    def _analyze(self, record: ExecutiveStrategyPlan, scenario: WhatIfRequest | None = None) -> StrategyAnalysis:
        scenario = scenario or WhatIfRequest()
        objectives = [item.model_copy() for item in record.objectives]
        for objective in objectives:
            if objective.objective_key in scenario.objective_weight_overrides:
                objective.weight = scenario.objective_weight_overrides[objective.objective_key]
        if abs(sum(item.weight for item in objectives) - 100.0) > 0.01:
            raise ValueError("Scenario objective weights must total 100")

        capacities = {item.resource_key: item.capacity for item in record.resources}
        capacities.update(scenario.resource_capacity_overrides)
        used = {key: 0.0 for key in capacities}
        objective_map = {item.objective_key: item for item in objectives}
        order = self._topological_order(record.initiatives)
        initiative_map = {item.initiative_key: item for item in record.initiatives}
        analyses: list[InitiativeAnalysis] = []
        allocation: dict[str, dict[str, float]] = {}
        roadmap: list[StrategicRoadmapItem] = []
        milestones: list[Milestone] = []
        end_by_key: dict[str, int] = {}

        for sequence, key in enumerate(order, start=1):
            initiative = initiative_map[key]
            risk = scenario.initiative_risk_overrides.get(key, initiative.risk_score)
            alignment = sum(objective_map[obj].weight for obj in initiative.objective_keys)
            priority = initiative.strategic_value * 0.5 + initiative.confidence * 0.3 + alignment * 0.2
            adjusted = max(0.0, min(100.0, priority - risk * 0.25))
            blockers: list[str] = []
            allocated: dict[str, float] = {}
            for resource_key, demand in initiative.resource_demand.items():
                capacity = capacities.get(resource_key, 0.0)
                if used.get(resource_key, 0.0) + demand > capacity:
                    blockers.append(f"Insufficient {resource_key} capacity")
                else:
                    used[resource_key] = used.get(resource_key, 0.0) + demand
                    allocated[resource_key] = demand
            feasible = not blockers
            if not feasible:
                for resource_key, demand in allocated.items():
                    used[resource_key] -= demand
                allocated = {}
            allocation[key] = allocated
            analyses.append(InitiativeAnalysis(
                initiative_key=key,
                priority_score=round(priority, 2),
                alignment_score=round(alignment, 2),
                risk_adjusted_score=round(adjusted if feasible else 0.0, 2),
                feasible=feasible,
                blocking_reasons=blockers,
                allocated_resources=allocated,
            ))
            start_day = max((end_by_key[dep] for dep in initiative.dependencies), default=0)
            end_day = start_day + initiative.duration_days
            end_by_key[key] = end_day
            roadmap.append(StrategicRoadmapItem(initiative_key=key, sequence=sequence, start_day=start_day, end_day=end_day, dependencies=initiative.dependencies))
            if initiative.milestone_titles:
                step = max(1, initiative.duration_days // len(initiative.milestone_titles))
                for index, title in enumerate(initiative.milestone_titles, start=1):
                    milestones.append(Milestone(initiative_key=key, title=title, target_day=min(end_day, start_day + step * index)))

        objective_progress = {item.objective_key: round(min(100.0, item.current_value / item.target_value * 100.0), 2) for item in objectives}
        weighted_progress = sum(objective_progress[item.objective_key] * item.weight / 100.0 for item in objectives)
        feasible_ratio = sum(item.feasible for item in analyses) / len(analyses) * 100.0
        alignment_score = round(weighted_progress * 0.55 + feasible_ratio * 0.45, 2)
        risk_register = [
            {
                "risk_key": risk.risk_key,
                "title": risk.title,
                "exposure": round(risk.probability * risk.impact / 100.0, 2),
                "severity": "critical" if risk.probability * risk.impact >= 6000 else "warning" if risk.probability * risk.impact >= 3000 else "normal",
                "mitigation": risk.mitigation,
                "initiative_keys": risk.initiative_keys,
            }
            for risk in record.risks
        ]
        blocked = [item.initiative_key for item in analyses if not item.feasible]
        scenario_summary = f"Scenario evaluated with {len(scenario.resource_capacity_overrides)} capacity, {len(scenario.initiative_risk_overrides)} risk and {len(scenario.objective_weight_overrides)} objective-weight overrides."
        executive_summary = f"Strategy alignment is {alignment_score:.2f}. {len(analyses) - len(blocked)} of {len(analyses)} initiatives are resource-feasible. Human governance remains mandatory."
        return StrategyAnalysis(
            analyzed_at=self._now(),
            alignment_score=alignment_score,
            objective_progress=objective_progress,
            initiatives=analyses,
            dependency_graph={item.initiative_key: item.dependencies for item in record.initiatives},
            resource_allocation=allocation,
            risk_register=risk_register,
            roadmap=roadmap,
            milestones=milestones,
            scenario_summary=scenario_summary,
            executive_summary=executive_summary,
        )

    def analyze(self, plan_id: UUID, workspace_id: str, actor_id: str, scenario: WhatIfRequest | None = None) -> ExecutiveStrategyPlan:
        with self._lock:
            record = self._plans.get(plan_id)
            if record is None or record.workspace_id != workspace_id:
                raise KeyError("Executive strategy plan not found")
            analysis = self._analyze(record, scenario)
            updated = record.model_copy(update={"analysis": analysis, "status": StrategyStatus.analyzed, "version": record.version + 1, "updated_at": self._now()})
            self._plans[plan_id] = updated
            self._write_audit(workspace_id, "executive-strategy-analyzed", actor_id, plan_id, {"alignment_score": analysis.alignment_score})
            return updated

    def roadmap(self, plan_id: UUID, workspace_id: str, actor_id: str, scenario: WhatIfRequest | None = None) -> StrategyAnalysis:
        updated = self.analyze(plan_id, workspace_id, actor_id, scenario)
        self._write_audit(workspace_id, "executive-strategy-roadmap-generated", actor_id, plan_id, {"roadmap_items": len(updated.analysis.roadmap) if updated.analysis else 0})
        return updated.analysis

    def status(self, workspace_id: str) -> StrategyStatusResponse:
        records = self.list_plans(workspace_id)
        analyzed = [item for item in records if item.analysis is not None]
        average = sum(item.analysis.alignment_score for item in analyzed) / len(analyzed) if analyzed else 0.0
        return StrategyStatusResponse(plans=len(records), analyzed_plans=len(analyzed), average_alignment_score=round(average, 2))

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        with self._lock:
            return [item for item in self._audit if item.workspace_id == workspace_id]


executive_strategy_service = ExecutiveStrategyService()
