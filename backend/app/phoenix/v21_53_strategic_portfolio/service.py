from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    AllocationStatus,
    AuditEvent,
    PortfolioActionRequest,
    PortfolioState,
    RiskDecision,
    StrategicPortfolioCreate,
    StrategicPortfolioRecord,
)


class StrategicPortfolioError(RuntimeError):
    pass


class StrategicPortfolioService:
    def __init__(self) -> None:
        self._records: dict[str, StrategicPortfolioRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: StrategicPortfolioCreate) -> StrategicPortfolioRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise StrategicPortfolioError("duplicate source key")
        record = StrategicPortfolioRecord(**payload.model_dump())
        self._refresh(record)
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> StrategicPortfolioRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise StrategicPortfolioError("strategic portfolio record not found")
        return record

    def list(self, workspace_id: str) -> list[StrategicPortfolioRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: PortfolioActionRequest) -> StrategicPortfolioRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "prepare-evidence":
            self._require(record, PortfolioState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = PortfolioState.BLOCKED
            elif not record.portfolio_evidence_refs:
                raise StrategicPortfolioError("portfolio evidence is required")
            else:
                record.state = PortfolioState.EVIDENCE_READY
        elif action == "analyze":
            self._require(record, PortfolioState.EVIDENCE_READY)
            self._refresh(record)
            record.state = PortfolioState.ESCALATED if self._breached(record) else PortfolioState.ANALYZED
        elif action == "prepare-allocation":
            self._require(record, PortfolioState.ANALYZED)
            if any(item.confidence < record.minimum_sleeve_confidence for item in record.sleeves):
                raise StrategicPortfolioError("sleeve confidence below threshold")
            record.state = PortfolioState.ALLOCATION_READY
        elif action == "request-review":
            self._require(record, PortfolioState.ALLOCATION_READY)
            record.state = PortfolioState.REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, PortfolioState.REVIEW_REQUIRED)
            if not request.approval_token:
                raise StrategicPortfolioError("approval token is required")
            if request.approval_token in self._approval_tokens:
                raise StrategicPortfolioError("approval token replay detected")
            self._approval_tokens.add(request.approval_token)
            record.approval_actor = request.actor
            for sleeve in record.sleeves:
                sleeve.status = AllocationStatus.APPROVED
            record.state = PortfolioState.APPROVED
        elif action == "orchestrate":
            self._require(record, PortfolioState.APPROVED)
            if record.risk_decision == RiskDecision.BLOCK:
                raise StrategicPortfolioError("Risk Brain blocked orchestration")
            if not request.receipt_id:
                raise StrategicPortfolioError("orchestration receipt is required")
            if request.receipt_id in self._receipt_ids:
                raise StrategicPortfolioError("orchestration receipt replay detected")
            if not request.evidence_refs:
                raise StrategicPortfolioError("orchestration evidence is required")
            self._receipt_ids.add(request.receipt_id)
            record.orchestration_evidence_refs.extend(request.evidence_refs)
            for sleeve in record.sleeves:
                sleeve.status = AllocationStatus.ACTIVE
            record.state = PortfolioState.ORCHESTRATING
        elif action == "record-cycle":
            if record.state not in {PortfolioState.ORCHESTRATING, PortfolioState.MONITORING}:
                raise StrategicPortfolioError("record-cycle requires orchestrating or monitoring state")
            if request.cycle_healthy is None:
                raise StrategicPortfolioError("cycle_healthy is required")
            observed_breaches = request.observed_constraint_breaches or 0
            healthy = request.cycle_healthy and observed_breaches <= record.maximum_constraint_breaches
            if healthy:
                record.consecutive_healthy_cycles += 1
                record.state = PortfolioState.MONITORING
            else:
                record.consecutive_healthy_cycles = 0
                record.state = PortfolioState.ESCALATED
        elif action == "verify":
            self._require(record, PortfolioState.MONITORING)
            if record.consecutive_healthy_cycles < record.required_healthy_cycles:
                raise StrategicPortfolioError("insufficient healthy monitoring cycles")
            record.state = PortfolioState.VERIFIED
        elif action == "escalate":
            if record.state in {PortfolioState.REVOKED, PortfolioState.ARCHIVED}:
                raise StrategicPortfolioError("record cannot be escalated")
            record.state = PortfolioState.ESCALATED
        elif action == "suspend":
            if record.state not in {PortfolioState.APPROVED, PortfolioState.ORCHESTRATING, PortfolioState.MONITORING, PortfolioState.ESCALATED}:
                raise StrategicPortfolioError("record cannot be suspended")
            for sleeve in record.sleeves:
                if sleeve.status == AllocationStatus.ACTIVE:
                    sleeve.status = AllocationStatus.PAUSED
            record.state = PortfolioState.SUSPENDED
        elif action == "resume":
            self._require(record, PortfolioState.SUSPENDED)
            if record.risk_decision == RiskDecision.BLOCK:
                raise StrategicPortfolioError("Risk Brain blocked resume")
            record.state = PortfolioState.MONITORING if record.orchestration_evidence_refs else PortfolioState.APPROVED
        elif action == "revoke":
            if record.state == PortfolioState.ARCHIVED:
                raise StrategicPortfolioError("archived record cannot be revoked")
            for sleeve in record.sleeves:
                sleeve.status = AllocationStatus.RETIRED
            record.state = PortfolioState.REVOKED
        elif action == "archive":
            if record.state not in {PortfolioState.VERIFIED, PortfolioState.REVOKED}:
                raise StrategicPortfolioError("only verified or revoked records can be archived")
            record.state = PortfolioState.ARCHIVED
        else:
            raise StrategicPortfolioError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._emit(record, action, request.actor, before, record.state, request)
        return record

    @staticmethod
    def _require(record: StrategicPortfolioRecord, expected: PortfolioState) -> None:
        if record.state != expected:
            raise StrategicPortfolioError(f"action requires {expected.value} state")

    @staticmethod
    def _refresh(record: StrategicPortfolioRecord) -> None:
        record.concentration_breaches = sum(
            1 for item in record.sleeves if item.target_weight > record.maximum_single_sleeve_weight
        )
        record.correlation_breaches = sum(
            1 for item in record.correlations if abs(item.correlation) > record.maximum_pair_correlation
        )
        record.liquidity_breaches = sum(
            1 for item in record.sleeves if item.liquidity_score < record.minimum_liquidity_score
        )
        record.constraint_breaches = sum(
            1 for item in record.exposure_constraints
            if abs(item.current_exposure) > item.maximum_absolute_exposure
        )

    @staticmethod
    def _breached(record: StrategicPortfolioRecord) -> bool:
        return (
            record.concentration_breaches > 0
            or record.correlation_breaches > 0
            or record.liquidity_breaches > 0
            or record.constraint_breaches > record.maximum_constraint_breaches
        )

    def _emit(
        self,
        record: StrategicPortfolioRecord,
        action: str,
        actor: str,
        before: PortfolioState | None,
        after: PortfolioState,
        request: PortfolioActionRequest | None = None,
    ) -> None:
        details = {} if request is None else request.model_dump(exclude_none=True)
        self._audit.append(
            AuditEvent(
                record_id=record.record_id,
                workspace_id=record.workspace_id,
                action=action,
                actor=actor,
                from_state=before,
                to_state=after,
                details=details,
            )
        )


service = StrategicPortfolioService()
