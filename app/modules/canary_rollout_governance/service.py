from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from threading import RLock

from .models import AuditEvent, RolloutAction, RolloutCreate, RolloutRecord, RolloutState


class CanaryRolloutError(ValueError):
    pass


class CanaryRolloutService:
    def __init__(self) -> None:
        self._records: dict[str, RolloutRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipts: set[str] = set()
        self._audit: list[AuditEvent] = []
        self._lock = RLock()

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def create(self, payload: RolloutCreate) -> RolloutRecord:
        with self._lock:
            source = (payload.workspace_id, payload.source_key)
            if source in self._source_keys:
                raise CanaryRolloutError("duplicate source key")

            if payload.risk_brain_blocked:
                state = RolloutState.BLOCKED
            elif not payload.upstream_evidence_verified:
                state = RolloutState.EVIDENCE_REQUIRED
            else:
                state = RolloutState.HUMAN_REVIEW_REQUIRED

            record = RolloutRecord(
                workspace_id=payload.workspace_id,
                source_key=payload.source_key,
                reliability_record_id=payload.reliability_record_id,
                proposal_ids=payload.proposal_ids,
                target_runtime_ids=payload.target_runtime_ids,
                config_version=payload.config_version,
                rollback_version=payload.rollback_version,
                stages=[item.model_copy(deep=True) for item in payload.stages],
                metrics=[item.model_copy(deep=True) for item in payload.metrics],
                state=state,
                risk_brain_blocked=payload.risk_brain_blocked,
                upstream_evidence_verified=payload.upstream_evidence_verified,
            )
            self._records[record.record_id] = record
            self._source_keys.add(source)
            self._log(record, "create", "system", None)
            return record

    def list(self, workspace_id: str) -> list[RolloutRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> RolloutRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise CanaryRolloutError("rollout not found")
        return record

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, action: RolloutAction) -> RolloutRecord:
        with self._lock:
            record = self.get(record_id, workspace_id)
            now = datetime.now(timezone.utc)

            if action.action == "approve":
                self._require_state(record, RolloutState.HUMAN_REVIEW_REQUIRED)
                if not action.approval_token:
                    raise CanaryRolloutError("approval token required")
                token_hash = self._hash(action.approval_token)
                if token_hash in self._approval_tokens:
                    raise CanaryRolloutError("approval token replay detected")
                self._approval_tokens.add(token_hash)
                record.approval_token_hash = token_hash
                record.state = RolloutState.APPROVED

            elif action.action == "start-canary":
                self._require_state(record, RolloutState.APPROVED)
                self._consume_receipt(action.receipt_id)
                self._enforce_governance(record)
                record.current_stage_index = 0
                record.observation_count = 0
                record.state = RolloutState.CANARY_RUNNING

            elif action.action == "observe":
                self._require_state(record, RolloutState.CANARY_RUNNING)
                self._consume_receipt(action.receipt_id)
                if not action.observations:
                    raise CanaryRolloutError("metric observations required")
                known = {item.metric_id: item for item in record.metrics}
                if set(action.observations) != set(known):
                    raise CanaryRolloutError("observations must cover every canary metric")
                for metric_id, value in action.observations.items():
                    known[metric_id].observed_value = value
                record.observation_count += action.observation_count or 1
                if self._threshold_breached(record):
                    record.state = RolloutState.PAUSED

            elif action.action == "advance-stage":
                self._require_state(record, RolloutState.CANARY_RUNNING)
                self._consume_receipt(action.receipt_id)
                stage = record.stages[record.current_stage_index]
                if record.observation_count < stage.minimum_observations:
                    raise CanaryRolloutError("minimum observations not reached")
                if self._threshold_breached(record):
                    raise CanaryRolloutError("canary threshold breached")
                stage.completed = True
                if record.current_stage_index == len(record.stages) - 1:
                    record.state = RolloutState.PROMOTION_READY
                else:
                    record.current_stage_index += 1
                    record.observation_count = 0

            elif action.action == "pause":
                self._require_state(record, RolloutState.CANARY_RUNNING)
                self._consume_receipt(action.receipt_id)
                record.state = RolloutState.PAUSED

            elif action.action == "resume":
                self._require_state(record, RolloutState.PAUSED)
                self._consume_receipt(action.receipt_id)
                self._enforce_governance(record)
                if self._threshold_breached(record):
                    raise CanaryRolloutError("canary threshold still breached")
                record.state = RolloutState.CANARY_RUNNING

            elif action.action == "promote":
                self._require_state(record, RolloutState.PROMOTION_READY)
                self._consume_receipt(action.receipt_id)
                self._enforce_governance(record)
                if not all(stage.completed for stage in record.stages):
                    raise CanaryRolloutError("all rollout stages must be completed")
                record.state = RolloutState.PROMOTED

            elif action.action == "rollback":
                self._require_state(
                    record,
                    RolloutState.CANARY_RUNNING,
                    RolloutState.PAUSED,
                    RolloutState.PROMOTION_READY,
                    RolloutState.PROMOTED,
                    RolloutState.FAILED,
                )
                self._consume_receipt(action.receipt_id)
                record.state = RolloutState.ROLLED_BACK

            elif action.action == "fail":
                self._require_state(record, RolloutState.CANARY_RUNNING, RolloutState.PAUSED)
                record.state = RolloutState.FAILED

            elif action.action == "archive":
                self._require_state(record, RolloutState.PROMOTED, RolloutState.ROLLED_BACK, RolloutState.FAILED)
                record.state = RolloutState.ARCHIVED

            record.last_receipt_id = action.receipt_id or record.last_receipt_id
            record.updated_at = now
            self._log(record, action.action, action.actor_id, action.reason)
            return record

    @staticmethod
    def _threshold_breached(record: RolloutRecord) -> bool:
        for metric in record.metrics:
            if metric.observed_value is None:
                continue
            if metric.direction == "max" and metric.observed_value > metric.failure_threshold:
                return True
            if metric.direction == "min" and metric.observed_value < metric.failure_threshold:
                return True
        return False

    @staticmethod
    def _enforce_governance(record: RolloutRecord) -> None:
        if record.risk_brain_blocked:
            raise CanaryRolloutError("Risk Brain hard block")
        if not record.upstream_evidence_verified:
            raise CanaryRolloutError("upstream evidence required")
        if not record.approval_token_hash:
            raise CanaryRolloutError("human approval required")

    def _consume_receipt(self, receipt_id: str | None) -> None:
        if not receipt_id:
            raise CanaryRolloutError("receipt id required")
        if receipt_id in self._receipts:
            raise CanaryRolloutError("receipt replay detected")
        self._receipts.add(receipt_id)

    @staticmethod
    def _require_state(record: RolloutRecord, *states: RolloutState) -> None:
        if record.state not in states:
            expected = ", ".join(state.value for state in states)
            raise CanaryRolloutError(f"invalid state transition from {record.state.value}; expected {expected}")

    def _log(self, record: RolloutRecord, action: str, actor_id: str, reason: str | None) -> None:
        self._audit.append(
            AuditEvent(
                record_id=record.record_id,
                workspace_id=record.workspace_id,
                action=action,
                actor_id=actor_id,
                state=record.state,
                reason=reason,
            )
        )


service = CanaryRolloutService()
