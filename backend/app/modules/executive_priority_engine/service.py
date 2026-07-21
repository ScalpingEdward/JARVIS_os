from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from .models import (
    PriorityAudit,
    PriorityCreate,
    PriorityExecuteRequest,
    PriorityRecord,
    PriorityState,
    PriorityStatus,
    RankedCandidate,
)


class ExecutivePriorityService:
    def __init__(self) -> None:
        self._records: dict[UUID, PriorityRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._objective_tokens: set[tuple[str, str]] = set()
        self._capacity_receipts: set[tuple[str, str]] = set()
        self._audit: list[PriorityAudit] = []

    def create(self, payload: PriorityCreate) -> PriorityRecord:
        source_key = (payload.workspace_id, payload.source_key)
        objective_key = (payload.workspace_id, payload.evidence.approval_token)
        if source_key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        if objective_key in self._objective_tokens:
            raise ValueError("strategic objective approval token already consumed")

        state, detail, ranking, portfolio_score = self._evaluate(payload)
        record = PriorityRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            ranking=ranking,
            portfolio_score=portfolio_score,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._objective_tokens.add(objective_key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, payload: PriorityCreate):
        evidence = payload.evidence
        if payload.upstream_risk_brain_blocked:
            return PriorityState.BLOCKED, "upstream Risk Brain hard block", [], 0
        if not payload.v21_01_approved:
            return PriorityState.EVIDENCE_REQUIRED, "approved v21.01 objective evidence required", [], 0
        if evidence.objective_state not in {"approved", "issued-to-executive-planning"}:
            return PriorityState.EVIDENCE_REQUIRED, "v21.01 objective must be approved or issued", [], 0
        if not evidence.human_approved:
            return PriorityState.EVIDENCE_REQUIRED, "human-approved strategic objective evidence required", [], 0
        if not evidence.success_metrics or not evidence.constraints:
            return PriorityState.EVIDENCE_REQUIRED, "success metrics and constraints are mandatory", [], 0

        ranked: list[RankedCandidate] = []
        seen: set[str] = set()
        for candidate in payload.candidates:
            if candidate.candidate_key in seen:
                raise ValueError("duplicate candidate_key in request")
            seen.add(candidate.candidate_key)

            unresolved = [
                dependency
                for dependency in candidate.dependencies
                if not payload.dependency_status.get(dependency, False)
            ]
            blocked = candidate.blocked or bool(unresolved)
            cost_of_delay = (
                candidate.impact_score * 0.30
                + candidate.customer_value * 0.20
                + candidate.urgency * 0.20
                + candidate.risk_reduction * 0.15
                + evidence.time_criticality * 0.10
                + evidence.opportunity_enablement * 0.05
            )
            wsjf = cost_of_delay / max(candidate.effort_points, 1)
            risk_adjusted_value = (
                candidate.impact_score * 0.30
                + candidate.customer_value * 0.20
                + candidate.strategic_alignment * 0.20
                + candidate.urgency * 0.10
                + candidate.risk_reduction * 0.10
                + evidence.business_value * 0.10
            ) * (candidate.confidence / 100)
            cost_penalty = min(20.0, candidate.estimated_cost / 5000)
            effort_penalty = min(15.0, candidate.effort_points * 0.75)
            dependency_penalty = 35.0 if blocked else 0.0
            priority_score = max(
                0.0,
                min(
                    100.0,
                    risk_adjusted_value * 0.65
                    + min(wsjf * 8, 35)
                    + evidence.confidence * 0.10
                    - cost_penalty
                    - effort_penalty
                    - dependency_penalty,
                ),
            )
            rationale = [
                f"cost-of-delay={cost_of_delay:.2f}",
                f"wsjf={wsjf:.2f}",
                f"risk-adjusted-value={risk_adjusted_value:.2f}",
            ]
            if blocked:
                rationale.append("blocked candidates cannot be issued for capacity planning")
            ranked.append(
                RankedCandidate(
                    candidate_key=candidate.candidate_key,
                    title=candidate.title,
                    rank=1,
                    priority_score=round(priority_score, 2),
                    cost_of_delay=round(cost_of_delay, 2),
                    wsjf_score=round(wsjf, 2),
                    risk_adjusted_value=round(risk_adjusted_value, 2),
                    blocked=blocked,
                    blocking_dependencies=unresolved,
                    rationale=rationale,
                )
            )

        ranked.sort(key=lambda item: (item.blocked, -item.priority_score, -item.wsjf_score, item.candidate_key))
        for index, item in enumerate(ranked, start=1):
            item.rank = index

        available = [item.priority_score for item in ranked if not item.blocked]
        portfolio_score = round(sum(available) / len(available), 2) if available else 0
        if not available:
            return PriorityState.BLOCKED, "all candidates are dependency-blocked", ranked, portfolio_score

        sensitive = (
            evidence.risk_exposure >= 70
            or evidence.estimated_cost >= 50000
            or any(item.priority_score >= 90 for item in ranked)
        )
        detail = "executive ranking prepared; explicit human approval required"
        state = PriorityState.HUMAN_REVIEW_REQUIRED if sensitive else PriorityState.PRIORITIZED
        return state, detail, ranked, portfolio_score

    def execute(self, record_id: UUID, workspace_id: str, request: PriorityExecuteRequest) -> PriorityRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("executive priority record not found")

        if request.action == "approve":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state not in {PriorityState.PRIORITIZED, PriorityState.HUMAN_REVIEW_REQUIRED}:
                raise ValueError("priority approval unavailable")
            if not any(not item.blocked for item in record.ranking):
                raise ValueError("no executable candidate available")
            raw = f"{workspace_id}:{record.id}:{record.request.evidence.approval_token}:{record.portfolio_score}"
            record.approval_token = sha256(raw.encode("utf-8")).hexdigest()
            record.state = PriorityState.APPROVED
            record.detail = "executive priority order approved"
        elif request.action == "issue-to-capacity-planning":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state != PriorityState.APPROVED or not record.approval_token:
                raise ValueError("approved priority order required")
            if not request.capacity_planning_receipt_id:
                raise ValueError("capacity planning receipt required")
            receipt_key = (workspace_id, request.capacity_planning_receipt_id)
            if receipt_key in self._capacity_receipts:
                raise ValueError("capacity planning receipt already consumed")
            self._capacity_receipts.add(receipt_key)
            record.state = PriorityState.ISSUED_TO_CAPACITY_PLANNING
            record.detail = "approved executive priority order issued to v21.03 boundary"
        elif request.action == "reject":
            record.state = PriorityState.REJECTED
            record.detail = request.resolution_note or "executive priority order rejected"
        elif request.action == "archive":
            record.state = PriorityState.ARCHIVED
            record.detail = "executive priority record archived"
        else:
            raise ValueError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> PriorityRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[PriorityRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> PriorityStatus:
        records = self.list_records(workspace_id)
        blocked = {
            PriorityState.BLOCKED,
            PriorityState.EVIDENCE_REQUIRED,
            PriorityState.REJECTED,
            PriorityState.FAILED,
        }
        return PriorityStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            review_records=sum(record.state == PriorityState.HUMAN_REVIEW_REQUIRED for record in records),
            prioritized_records=sum(record.state == PriorityState.PRIORITIZED for record in records),
            approved_records=sum(record.state == PriorityState.APPROVED for record in records),
            issued_records=sum(record.state == PriorityState.ISSUED_TO_CAPACITY_PLANNING for record in records),
            blocked_records=sum(record.state in blocked for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[PriorityAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: PriorityRecord, actor_id: str, action: str) -> None:
        self._audit.append(
            PriorityAudit(
                record_id=record.id,
                workspace_id=record.workspace_id,
                actor_id=actor_id,
                action=action,
                state=record.state,
                detail=record.detail,
            )
        )


executive_priority_service = ExecutivePriorityService()
