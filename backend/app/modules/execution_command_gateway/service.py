from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from threading import RLock
from typing import Dict, List, Protocol

from .models import (
    AuditEvent,
    BrokerKind,
    CommandAction,
    CommandState,
    CommandType,
    CommandValidation,
    ExecutionCommandCreate,
    ExecutionCommandRecord,
    GatewayCommand,
)


class GatewayError(ValueError):
    pass


class BrokerAdapter(Protocol):
    kind: BrokerKind

    def validate(self, payload: ExecutionCommandCreate) -> List[str]: ...


class GenericBrokerAdapter:
    def __init__(self, kind: BrokerKind) -> None:
        self.kind = kind

    def validate(self, payload: ExecutionCommandCreate) -> List[str]:
        violations: List[str] = []
        if payload.order_type != "market" and payload.price is None:
            violations.append("pending-order-price-required")
        if payload.command_type in {
            CommandType.MODIFY_ORDER,
            CommandType.CANCEL_ORDER,
            CommandType.CLOSE_POSITION,
            CommandType.PARTIAL_CLOSE,
        } and not (payload.position_id or payload.client_order_id):
            violations.append("target-order-or-position-required")
        if payload.stop_loss is not None and payload.take_profit is not None:
            if payload.side == "buy" and payload.stop_loss >= payload.take_profit:
                violations.append("invalid-buy-protection-shape")
            if payload.side == "sell" and payload.stop_loss <= payload.take_profit:
                violations.append("invalid-sell-protection-shape")
        return violations


class ExecutionCommandGatewayService:
    def __init__(self) -> None:
        self._records: Dict[str, ExecutionCommandRecord] = {}
        self._audit: List[AuditEvent] = []
        self._source_keys: Dict[str, set[str]] = defaultdict(set)
        self._idempotency_keys: Dict[str, set[str]] = defaultdict(set)
        self._approval_tokens: set[str] = set()
        self._queue_receipts: set[str] = set()
        self._dispatch_receipts: set[str] = set()
        self._broker_receipts: set[str] = set()
        self._adapters = {kind: GenericBrokerAdapter(kind) for kind in BrokerKind}
        self._lock = RLock()

    def create(self, payload: ExecutionCommandCreate, actor: str = "system") -> ExecutionCommandRecord:
        with self._lock:
            if payload.source_key in self._source_keys[payload.workspace_id]:
                raise GatewayError("duplicate source_key in workspace")
            if payload.idempotency_key in self._idempotency_keys[payload.workspace_id]:
                raise GatewayError("idempotency key replay detected")

            validation = self._validate(payload)
            if payload.risk_brain_blocked:
                state = CommandState.BLOCKED
            elif not payload.upstream_evidence_verified or not payload.active_policy_verified or not payload.workflow_dispatch_verified:
                state = CommandState.EVIDENCE_REQUIRED
            elif not validation.valid:
                state = CommandState.VALIDATION_FAILED
            else:
                state = CommandState.HUMAN_REVIEW_REQUIRED

            record = ExecutionCommandRecord(
                **payload.model_dump(exclude={
                    "upstream_evidence_verified",
                    "active_policy_verified",
                    "workflow_dispatch_verified",
                    "risk_brain_blocked",
                }),
                state=state,
                validation=validation,
            )
            self._records[record.id] = record
            self._source_keys[payload.workspace_id].add(payload.source_key)
            self._idempotency_keys[payload.workspace_id].add(payload.idempotency_key)
            self._append_audit(record, "created", actor, None, state)
            return record.model_copy(deep=True)

    def get(self, workspace_id: str, record_id: str) -> ExecutionCommandRecord:
        with self._lock:
            record = self._records.get(record_id)
            if record is None or record.workspace_id != workspace_id:
                raise GatewayError("record not found")
            return record.model_copy(deep=True)

    def list(self, workspace_id: str) -> List[ExecutionCommandRecord]:
        with self._lock:
            return [r.model_copy(deep=True) for r in self._records.values() if r.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> List[AuditEvent]:
        with self._lock:
            return [event.model_copy(deep=True) for event in self._audit if event.workspace_id == workspace_id]

    def act(self, workspace_id: str, record_id: str, action: CommandAction) -> ExecutionCommandRecord:
        with self._lock:
            record = self._records.get(record_id)
            if record is None or record.workspace_id != workspace_id:
                raise GatewayError("record not found")
            previous = record.state

            if action.command == GatewayCommand.APPROVE:
                if previous != CommandState.HUMAN_REVIEW_REQUIRED:
                    raise GatewayError("command is not approvable")
                self._consume(action.approval_token, self._approval_tokens, "approval token")
                record.approval_token = action.approval_token
                record.state = CommandState.APPROVED
            elif action.command == GatewayCommand.QUEUE:
                if previous != CommandState.APPROVED:
                    raise GatewayError("command must be approved before queue")
                self._consume(action.queue_receipt, self._queue_receipts, "queue receipt")
                record.queue_receipt = action.queue_receipt
                record.state = CommandState.QUEUED
            elif action.command == GatewayCommand.DISPATCH:
                if previous != CommandState.QUEUED:
                    raise GatewayError("command must be queued before dispatch")
                self._consume(action.dispatch_receipt, self._dispatch_receipts, "dispatch receipt")
                record.dispatch_receipt = action.dispatch_receipt
                record.state = CommandState.DISPATCHED
            elif action.command == GatewayCommand.ACKNOWLEDGE:
                if previous != CommandState.DISPATCHED:
                    raise GatewayError("command must be dispatched before acknowledgement")
                self._consume(action.broker_receipt, self._broker_receipts, "broker receipt")
                record.broker_receipt = action.broker_receipt
                record.state = CommandState.ACKNOWLEDGED
            elif action.command == GatewayCommand.FAIL:
                if previous not in {CommandState.QUEUED, CommandState.DISPATCHED}:
                    raise GatewayError("only queued or dispatched commands can fail")
                record.state = CommandState.FAILED
            elif action.command == GatewayCommand.CANCEL:
                if previous in {CommandState.ACKNOWLEDGED, CommandState.ARCHIVED}:
                    raise GatewayError("terminal command cannot be cancelled")
                record.state = CommandState.CANCELLED
            elif action.command == GatewayCommand.ARCHIVE:
                if previous not in {CommandState.ACKNOWLEDGED, CommandState.FAILED, CommandState.CANCELLED}:
                    raise GatewayError("only terminal commands can be archived")
                record.state = CommandState.ARCHIVED
            else:
                raise GatewayError("unsupported command")

            record.updated_at = datetime.now(timezone.utc)
            self._append_audit(record, action.command.value, action.actor, previous, record.state, {"reason": action.reason} if action.reason else {})
            return record.model_copy(deep=True)

    def _validate(self, payload: ExecutionCommandCreate) -> CommandValidation:
        violations = self._adapters[payload.broker].validate(payload)
        warnings: List[str] = []
        if payload.stop_loss is None:
            warnings.append("stop-loss-not-specified")
        backoff = [min(2 ** attempt, 30) for attempt in range(payload.max_retries)]
        return CommandValidation(
            valid=not violations,
            violations=violations,
            warnings=warnings,
            adapter=payload.broker,
            retry_backoff_seconds=backoff,
        )

    @staticmethod
    def _consume(value: str | None, registry: set[str], label: str) -> None:
        if not value:
            raise GatewayError(f"{label} required")
        if value in registry:
            raise GatewayError(f"{label} replay detected")
        registry.add(value)

    def _append_audit(
        self,
        record: ExecutionCommandRecord,
        action: str,
        actor: str,
        from_state: CommandState | None,
        to_state: CommandState,
        details: Dict[str, object] | None = None,
    ) -> None:
        self._audit.append(AuditEvent(
            workspace_id=record.workspace_id,
            record_id=record.id,
            action=action,
            actor=actor,
            from_state=from_state,
            to_state=to_state,
            details=details or {},
        ))
