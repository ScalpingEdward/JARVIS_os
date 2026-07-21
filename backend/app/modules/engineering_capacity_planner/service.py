from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from .models import (
    CapacityAllocation,
    CapacityPlanningAudit,
    CapacityPlanningCreate,
    CapacityPlanningExecuteRequest,
    CapacityPlanningRecord,
    CapacityPlanningState,
    CapacityPlanningStatus,
)


class EngineeringCapacityPlannerService:
    def __init__(self) -> None:
        self._records: dict[UUID, CapacityPlanningRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._receipts: set[tuple[str, str]] = set()
        self._audit: list[CapacityPlanningAudit] = []

    def create(self, payload: CapacityPlanningCreate) -> CapacityPlanningRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")

        state, detail, allocations, available, required, utilization, cost, unallocated = self._evaluate(payload)
        record = CapacityPlanningRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            allocations=allocations,
            total_available_points=available,
            total_required_points=required,
            utilization_percent=utilization,
            estimated_total_cost=cost,
            unallocated_candidate_ids=unallocated,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, payload: CapacityPlanningCreate):
        if payload.upstream_risk_brain_blocked:
            return CapacityPlanningState.BLOCKED, "upstream Risk Brain hard block", [], 0, 0, 0, 0, []
        if not payload.v21_02_priority_approved:
            return CapacityPlanningState.EVIDENCE_REQUIRED, "approved v21.02 priority evidence required", [], 0, 0, 0, 0, []
        if not payload.work_items or not payload.resources:
            return CapacityPlanningState.EVIDENCE_REQUIRED, "work items and capacity resources are required", [], 0, 0, 0, 0, []

        resources = [resource for resource in payload.resources if resource.available and resource.available_points > 0]
        if not resources:
            return CapacityPlanningState.CAPACITY_CONSTRAINED, "no executable capacity available", [], 0, sum(i.effort_points for i in payload.work_items), 0, 0, [i.candidate_id for i in payload.work_items]

        remaining = {resource.resource_id: resource.available_points for resource in resources}
        active_count = {resource.resource_id: 0 for resource in resources}
        allocations: list[CapacityAllocation] = []
        unallocated: list[str] = []
        total_cost = 0.0
        required = sum(item.effort_points for item in payload.work_items)
        available = sum(resource.available_points for resource in resources)

        for item in sorted(payload.work_items, key=lambda value: (value.rank, -value.priority_score, value.candidate_id)):
            if not item.dependency_ready:
                allocations.append(CapacityAllocation(candidate_id=item.candidate_id, allocated_points=0, estimated_cost=0, status="dependency-blocked", reason="dependency readiness required"))
                unallocated.append(item.candidate_id)
                continue

            matching = []
            for resource in resources:
                role_ok = not item.required_roles or resource.role in item.required_roles
                skill_ok = not item.required_skills or set(item.required_skills).issubset(set(resource.skills))
                parallel_ok = active_count[resource.resource_id] < resource.max_parallel_items
                if role_ok and skill_ok and parallel_ok and remaining[resource.resource_id] > 0:
                    matching.append(resource)
            matching.sort(key=lambda resource: (-remaining[resource.resource_id], resource.hourly_cost, resource.resource_id))

            needed = item.effort_points
            assigned: list[str] = []
            item_cost = 0.0
            for resource in matching:
                if needed <= 0:
                    break
                granted = min(needed, remaining[resource.resource_id])
                if granted <= 0:
                    continue
                remaining[resource.resource_id] -= granted
                active_count[resource.resource_id] += 1
                needed -= granted
                assigned.append(resource.resource_id)
                item_cost += granted * resource.hourly_cost

            allocated = item.effort_points - needed
            if needed > 0:
                status = "partially-allocated" if allocated else "unallocated"
                reason = "insufficient matching capacity"
                unallocated.append(item.candidate_id)
            else:
                status = "allocated"
                reason = "capacity and skill requirements satisfied"
            total_cost += item_cost
            allocations.append(CapacityAllocation(
                candidate_id=item.candidate_id,
                assigned_resource_ids=assigned,
                allocated_points=allocated,
                estimated_cost=round(item_cost, 2),
                status=status,
                reason=reason,
            ))

        consumed = available - sum(remaining.values())
        utilization = round((consumed / available) * 100, 2) if available else 0
        if payload.max_total_cost is not None and total_cost > payload.max_total_cost:
            state = CapacityPlanningState.HUMAN_REVIEW_REQUIRED
            detail = "capacity plan exceeds declared cost ceiling"
        elif unallocated:
            state = CapacityPlanningState.CAPACITY_CONSTRAINED
            detail = "capacity plan contains unallocated or blocked work"
        else:
            state = CapacityPlanningState.PLAN_READY
            detail = "capacity plan satisfies ranked workload"
        return state, detail, allocations, available, required, utilization, round(total_cost, 2), unallocated

    def execute(self, record_id: UUID, workspace_id: str, request: CapacityPlanningExecuteRequest) -> CapacityPlanningRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("capacity planning record not found")

        if request.action == "approve":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state not in {CapacityPlanningState.PLAN_READY, CapacityPlanningState.CAPACITY_CONSTRAINED, CapacityPlanningState.HUMAN_REVIEW_REQUIRED}:
                raise ValueError("capacity approval unavailable")
            if record.unallocated_candidate_ids:
                raise ValueError("unallocated work must be resolved before approval")
            raw = f"{record.workspace_id}:{record.id}:{record.source_key}:{record.estimated_total_cost}"
            record.approval_token = sha256(raw.encode("utf-8")).hexdigest()
            record.state = CapacityPlanningState.APPROVED
            record.detail = "engineering capacity plan approved"
        elif request.action == "issue-to-budget-planning":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state != CapacityPlanningState.APPROVED or not record.approval_token:
                raise ValueError("approved capacity plan required")
            if not request.budget_planning_receipt_id:
                raise ValueError("budget planning receipt id required")
            receipt_key = (workspace_id, request.budget_planning_receipt_id)
            if receipt_key in self._receipts:
                raise ValueError("budget planning receipt already consumed")
            self._receipts.add(receipt_key)
            record.state = CapacityPlanningState.ISSUED_TO_BUDGET_PLANNING
            record.detail = "approved capacity plan issued to v21.04 budget planning"
        elif request.action == "reject":
            record.state = CapacityPlanningState.REJECTED
            record.detail = "capacity plan rejected"
        elif request.action == "archive":
            record.state = CapacityPlanningState.ARCHIVED
            record.detail = "capacity planning record archived"
        else:
            raise ValueError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> CapacityPlanningRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[CapacityPlanningRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def audit_records(self, workspace_id: str) -> list[CapacityPlanningAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> CapacityPlanningStatus:
        records = self.list_records(workspace_id)
        blocked = {CapacityPlanningState.BLOCKED, CapacityPlanningState.EVIDENCE_REQUIRED, CapacityPlanningState.REJECTED, CapacityPlanningState.FAILED}
        return CapacityPlanningStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            ready_records=sum(record.state == CapacityPlanningState.PLAN_READY for record in records),
            constrained_records=sum(record.state in {CapacityPlanningState.CAPACITY_CONSTRAINED, CapacityPlanningState.HUMAN_REVIEW_REQUIRED} for record in records),
            approved_records=sum(record.state == CapacityPlanningState.APPROVED for record in records),
            issued_records=sum(record.state == CapacityPlanningState.ISSUED_TO_BUDGET_PLANNING for record in records),
            blocked_records=sum(record.state in blocked for record in records),
        )

    def _log(self, record: CapacityPlanningRecord, actor_id: str, action: str) -> None:
        self._audit.append(CapacityPlanningAudit(
            record_id=record.id,
            workspace_id=record.workspace_id,
            actor_id=actor_id,
            action=action,
            state=record.state,
            detail=record.detail,
        ))


engineering_capacity_planner_service = EngineeringCapacityPlannerService()
