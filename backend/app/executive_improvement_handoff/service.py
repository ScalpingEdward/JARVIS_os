from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from .models import (
    ImprovementHandoffAudit,
    ImprovementHandoffCreate,
    ImprovementHandoffExecuteRequest,
    ImprovementHandoffRecord,
    ImprovementHandoffState,
    ImprovementHandoffStatus,
    PlanningIntakePackage,
)


class ImprovementHandoffService:
    def __init__(self) -> None:
        self._records: dict[UUID, ImprovementHandoffRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._digests: set[tuple[str, str]] = set()
        self._audit: list[ImprovementHandoffAudit] = []

    def create(self, payload: ImprovementHandoffCreate) -> ImprovementHandoffRecord:
        source_key = (payload.workspace_id, payload.source_key)
        digest_key = (payload.workspace_id, payload.evidence_digest.lower())
        if source_key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        if digest_key in self._digests:
            raise ValueError("evidence digest already consumed in workspace")

        state, detail, package = self._evaluate(payload)
        record = ImprovementHandoffRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            intake_package=package,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._digests.add(digest_key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, payload: ImprovementHandoffCreate):
        if payload.upstream_risk_brain_blocked:
            return ImprovementHandoffState.BLOCKED, "upstream Risk Brain hard block", None
        if not payload.v20_09_ready:
            return ImprovementHandoffState.EVIDENCE_REQUIRED, "v20.09 ready-for-v20.01 evidence required", None

        evidence = payload.evidence
        if evidence.backlog_state != "ready-for-v20.01":
            return ImprovementHandoffState.EVIDENCE_REQUIRED, "backlog item is not ready for v20.01", None
        if not evidence.human_approved:
            return ImprovementHandoffState.HUMAN_REVIEW_REQUIRED, "v20.09 human approval evidence required", None
        if not evidence.defensive_only:
            return ImprovementHandoffState.BLOCKED, "non-defensive improvement cannot enter automated handoff", None

        package = PlanningIntakePackage(
            objective=evidence.title,
            scope=[evidence.description],
            acceptance_criteria=[
                "implementation remains workspace isolated",
                "tests cover success and fail-closed paths",
                "Risk Brain authority remains unchanged",
                "human review is required before merge and deployment",
            ],
            constraints=[
                "no autonomous live-trading activation",
                "no autonomous risk increase or limit relaxation",
                "no direct main-branch write",
                "no deployment from this module",
            ],
            dependencies=evidence.dependencies,
            priority_score=evidence.priority_score,
            confidence_score=evidence.confidence_score,
            effort_points=evidence.effort_points,
            evidence_digest=payload.evidence_digest.lower(),
        )
        return ImprovementHandoffState.READY, "immutable planning intake package prepared", package

    def execute(self, record_id: UUID, workspace_id: str, request: ImprovementHandoffExecuteRequest) -> ImprovementHandoffRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("improvement handoff record not found")

        if request.action == "handoff":
            if record.state != ImprovementHandoffState.READY:
                raise ValueError("handoff unavailable")
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.intake_package is None:
                raise ValueError("planning intake package missing")
            token_material = f"{record.workspace_id}:{record.id}:{record.request.evidence_digest}:v20.01"
            record.handoff_token = sha256(token_material.encode("utf-8")).hexdigest()
            record.state = ImprovementHandoffState.HANDED_OFF
            record.detail = "planning intake package handed off to v20.01 boundary"
        elif request.action == "accept":
            if record.state != ImprovementHandoffState.HANDED_OFF:
                raise ValueError("acceptance unavailable")
            if not request.v20_01_receipt_id:
                raise ValueError("v20.01 receipt id required")
            record.state = ImprovementHandoffState.ACCEPTED_BY_V20_01
            record.detail = f"accepted by v20.01 receipt {request.v20_01_receipt_id}"
        elif request.action == "reject":
            record.state = ImprovementHandoffState.REJECTED
            record.detail = "planning intake handoff rejected"
        elif request.action == "expire":
            if record.state not in {ImprovementHandoffState.READY, ImprovementHandoffState.HANDED_OFF}:
                raise ValueError("expiration unavailable")
            record.state = ImprovementHandoffState.EXPIRED
            record.detail = "planning intake authorization expired"
        elif request.action == "archive":
            record.state = ImprovementHandoffState.ARCHIVED
            record.detail = "improvement handoff record archived"
        else:
            raise ValueError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> ImprovementHandoffRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[ImprovementHandoffRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> ImprovementHandoffStatus:
        records = self.list_records(workspace_id)
        blocked = {
            ImprovementHandoffState.BLOCKED,
            ImprovementHandoffState.EVIDENCE_REQUIRED,
            ImprovementHandoffState.HUMAN_REVIEW_REQUIRED,
            ImprovementHandoffState.REJECTED,
            ImprovementHandoffState.EXPIRED,
            ImprovementHandoffState.FAILED,
        }
        return ImprovementHandoffStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            ready_records=sum(record.state == ImprovementHandoffState.READY for record in records),
            handed_off_records=sum(record.state == ImprovementHandoffState.HANDED_OFF for record in records),
            accepted_records=sum(record.state == ImprovementHandoffState.ACCEPTED_BY_V20_01 for record in records),
            blocked_records=sum(record.state in blocked for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[ImprovementHandoffAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: ImprovementHandoffRecord, actor_id: str, action: str) -> None:
        self._audit.append(ImprovementHandoffAudit(
            record_id=record.id,
            workspace_id=record.workspace_id,
            actor_id=actor_id,
            action=action,
            state=record.state,
            detail=record.detail,
        ))


improvement_handoff_service = ImprovementHandoffService()
