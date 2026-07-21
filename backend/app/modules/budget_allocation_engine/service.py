from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from .models import (
    BudgetAllocationAudit,
    BudgetAllocationCreate,
    BudgetAllocationExecuteRequest,
    BudgetAllocationPlan,
    BudgetAllocationRecord,
    BudgetAllocationState,
    BudgetAllocationStatus,
    BudgetLine,
)


class BudgetAllocationService:
    def __init__(self) -> None:
        self._records: dict[UUID, BudgetAllocationRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._capacity_tokens: set[tuple[str, str]] = set()
        self._roadmap_receipts: set[tuple[str, str]] = set()
        self._audit: list[BudgetAllocationAudit] = []

    def create(self, payload: BudgetAllocationCreate) -> BudgetAllocationRecord:
        source_key = (payload.workspace_id, payload.source_key)
        capacity_key = (payload.workspace_id, payload.evidence.approval_token)
        if source_key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        if capacity_key in self._capacity_tokens:
            raise ValueError("capacity approval token already consumed")

        state, detail, plan = self._evaluate(payload)
        record = BudgetAllocationRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            plan=plan,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._capacity_tokens.add(capacity_key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, payload: BudgetAllocationCreate):
        if payload.upstream_risk_brain_blocked:
            return BudgetAllocationState.BLOCKED, "upstream Risk Brain hard block", None
        if not payload.v21_03_capacity_approved:
            return BudgetAllocationState.EVIDENCE_REQUIRED, "approved v21.03 capacity evidence required", None

        evidence = payload.evidence
        envelope = payload.envelope
        if evidence.capacity_state not in {"approved", "issued-to-budget-planning"}:
            return BudgetAllocationState.EVIDENCE_REQUIRED, "capacity plan must be approved", None
        if not evidence.human_approved:
            return BudgetAllocationState.EVIDENCE_REQUIRED, "human-approved capacity evidence required", None
        if evidence.allocated_effort_points <= 0 or not evidence.workstream_ids:
            return BudgetAllocationState.BLOCKED, "no executable capacity available for budgeting", None
        if evidence.dependency_blocked_workstreams:
            return BudgetAllocationState.BLOCKED, "dependency-blocked workstreams cannot receive executable budget", None

        requested = {
            "labor": round(evidence.estimated_labor_cost, 2),
            "ai": round(evidence.estimated_ai_cost, 2),
            "cloud": round(evidence.estimated_cloud_cost, 2),
        }
        category_limits = {
            "labor": envelope.labor_budget,
            "ai": envelope.ai_budget,
            "cloud": envelope.cloud_budget,
        }
        lines: list[BudgetLine] = []
        total_allocated = 0.0
        constrained = False
        for category in ("labor", "ai", "cloud"):
            amount = requested[category]
            limit = category_limits[category]
            allocated = min(amount, limit)
            if allocated + 0.01 < amount:
                constrained = True
            total_allocated += allocated
            lines.append(
                BudgetLine(
                    category=category,
                    requested_amount=amount,
                    allocated_amount=round(allocated, 2),
                    variance_amount=round(allocated - amount, 2),
                    utilization_ratio=round(allocated / limit, 4) if limit else (1.0 if amount == 0 else 0.0),
                    rationale=f"bounded by the approved {category} envelope",
                )
            )

        total_requested = round(sum(requested.values()), 2)
        reserve_required = round(envelope.total_budget * envelope.reserve_ratio, 2)
        contingency_reserved = min(envelope.contingency_budget, reserve_required)
        spend_with_reserve = round(total_allocated + contingency_reserved, 2)
        hard_ceiling = envelope.hard_cost_ceiling or envelope.total_budget
        if spend_with_reserve > hard_ceiling or spend_with_reserve > envelope.total_budget:
            constrained = True

        available_for_execution = max(0.0, envelope.total_budget - contingency_reserved)
        if total_allocated > available_for_execution:
            scale = available_for_execution / total_allocated if total_allocated else 0
            total_allocated = 0.0
            for line in lines:
                line.allocated_amount = round(line.allocated_amount * scale, 2)
                line.variance_amount = round(line.allocated_amount - line.requested_amount, 2)
                total_allocated += line.allocated_amount
            constrained = True

        unallocated = round(envelope.total_budget - contingency_reserved - total_allocated, 2)
        coverage = total_allocated / total_requested if total_requested else 1.0
        affordability = max(0.0, min(100.0, coverage * 70 + payload.strategic_priority_score * 0.30))
        projected_roi = None
        if total_allocated > 0 and payload.expected_business_value > 0:
            projected_roi = round((payload.expected_business_value - total_allocated) / total_allocated, 4)

        plan = BudgetAllocationPlan(
            currency=envelope.currency.upper(),
            target_period=payload.target_period,
            total_requested=total_requested,
            total_allocated=round(total_allocated, 2),
            contingency_reserved=round(contingency_reserved, 2),
            unallocated_budget=unallocated,
            projected_roi=projected_roi,
            affordability_score=round(affordability, 2),
            lines=lines,
            blocked_workstreams=list(evidence.dependency_blocked_workstreams),
        )

        if total_allocated <= 0:
            return BudgetAllocationState.BLOCKED, "budget envelope cannot fund executable capacity", plan
        if constrained or coverage < 1:
            return BudgetAllocationState.HUMAN_REVIEW_REQUIRED, "budget constraints require explicit executive review", plan
        return BudgetAllocationState.PLAN_READY, "budget allocation plan prepared within approved envelope", plan

    def execute(
        self,
        record_id: UUID,
        workspace_id: str,
        request: BudgetAllocationExecuteRequest,
    ) -> BudgetAllocationRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("budget allocation record not found")

        if request.action == "approve":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state not in {BudgetAllocationState.PLAN_READY, BudgetAllocationState.HUMAN_REVIEW_REQUIRED}:
                raise ValueError("budget approval unavailable")
            if record.plan is None or record.plan.total_allocated <= 0:
                raise ValueError("executable budget plan required")
            material = f"{workspace_id}:{record.id}:{record.request.evidence.approval_token}:{record.plan.total_allocated}"
            record.approval_token = sha256(material.encode("utf-8")).hexdigest()
            record.state = BudgetAllocationState.APPROVED
            record.detail = "executive budget allocation approved"
        elif request.action == "issue-to-roadmap":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state != BudgetAllocationState.APPROVED or not record.approval_token:
                raise ValueError("approved budget plan required")
            if not request.roadmap_receipt_id:
                raise ValueError("roadmap receipt id required")
            receipt_key = (workspace_id, request.roadmap_receipt_id)
            if receipt_key in self._roadmap_receipts:
                raise ValueError("roadmap receipt already consumed")
            self._roadmap_receipts.add(receipt_key)
            record.roadmap_receipt_id = request.roadmap_receipt_id
            record.state = BudgetAllocationState.ISSUED_TO_ROADMAP
            record.detail = "approved budget issued to v21.05 roadmap generation"
        elif request.action == "reject":
            record.state = BudgetAllocationState.REJECTED
            record.detail = request.resolution_note or "budget allocation rejected"
        elif request.action == "archive":
            record.state = BudgetAllocationState.ARCHIVED
            record.detail = "budget allocation record archived"
        else:
            raise ValueError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> BudgetAllocationRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[BudgetAllocationRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> BudgetAllocationStatus:
        records = self.list_records(workspace_id)
        blocked = {
            BudgetAllocationState.BLOCKED,
            BudgetAllocationState.EVIDENCE_REQUIRED,
            BudgetAllocationState.REJECTED,
            BudgetAllocationState.FAILED,
        }
        return BudgetAllocationStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            ready_records=sum(record.state == BudgetAllocationState.PLAN_READY for record in records),
            constrained_records=sum(record.state in {BudgetAllocationState.BUDGET_CONSTRAINED, BudgetAllocationState.HUMAN_REVIEW_REQUIRED} for record in records),
            approved_records=sum(record.state == BudgetAllocationState.APPROVED for record in records),
            issued_records=sum(record.state == BudgetAllocationState.ISSUED_TO_ROADMAP for record in records),
            blocked_records=sum(record.state in blocked for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[BudgetAllocationAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: BudgetAllocationRecord, actor_id: str, action: str) -> None:
        self._audit.append(
            BudgetAllocationAudit(
                record_id=record.id,
                workspace_id=record.workspace_id,
                actor_id=actor_id,
                action=action,
                state=record.state,
                detail=record.detail,
            )
        )


budget_allocation_service = BudgetAllocationService()
