from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from threading import RLock
from typing import Dict, List

from .models import (
    AuditEvent,
    GovernanceAction,
    GovernanceCommand,
    GovernanceState,
    PolicyAssessment,
    StrategyPolicyCreate,
    StrategyPolicyRecord,
)


class GovernanceError(ValueError):
    pass


class StrategyGovernanceService:
    def __init__(self) -> None:
        self._records: Dict[str, StrategyPolicyRecord] = {}
        self._audit: List[AuditEvent] = []
        self._source_keys: Dict[str, set[str]] = defaultdict(set)
        self._versions: Dict[tuple[str, str], set[int]] = defaultdict(set)
        self._active_versions: Dict[tuple[str, str], int] = {}
        self._approval_tokens: set[str] = set()
        self._activation_receipts: set[str] = set()
        self._lock = RLock()

    def create(self, payload: StrategyPolicyCreate, actor: str = "system") -> StrategyPolicyRecord:
        with self._lock:
            if payload.source_key in self._source_keys[payload.workspace_id]:
                raise GovernanceError("duplicate source_key in workspace")
            version_key = (payload.workspace_id, payload.strategy_id)
            if payload.policy_version in self._versions[version_key]:
                raise GovernanceError("policy version already exists")

            assessment = self._assess(payload)
            if payload.risk_brain_blocked:
                state = GovernanceState.BLOCKED
            elif not payload.upstream_evidence_verified:
                state = GovernanceState.EVIDENCE_REQUIRED
            elif assessment.violations or assessment.warnings:
                state = GovernanceState.POLICY_REVIEW_REQUIRED
            else:
                state = GovernanceState.POLICY_READY

            record = StrategyPolicyRecord(
                workspace_id=payload.workspace_id,
                source_key=payload.source_key,
                optimizer_record_id=payload.optimizer_record_id,
                strategy_id=payload.strategy_id,
                policy_version=payload.policy_version,
                state=state,
                policy=payload,
                assessment=assessment,
                previous_active_version=self._active_versions.get(version_key),
            )
            self._records[record.id] = record
            self._source_keys[payload.workspace_id].add(payload.source_key)
            self._versions[version_key].add(payload.policy_version)
            self._append_audit(record, "created", actor, None, state)
            return record.model_copy(deep=True)

    def get(self, workspace_id: str, record_id: str) -> StrategyPolicyRecord:
        with self._lock:
            record = self._records.get(record_id)
            if record is None or record.workspace_id != workspace_id:
                raise GovernanceError("record not found")
            return record.model_copy(deep=True)

    def list(self, workspace_id: str) -> List[StrategyPolicyRecord]:
        with self._lock:
            return [r.model_copy(deep=True) for r in self._records.values() if r.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> List[AuditEvent]:
        with self._lock:
            return [event.model_copy(deep=True) for event in self._audit if event.workspace_id == workspace_id]

    def act(self, workspace_id: str, record_id: str, action: GovernanceAction) -> StrategyPolicyRecord:
        with self._lock:
            record = self._records.get(record_id)
            if record is None or record.workspace_id != workspace_id:
                raise GovernanceError("record not found")
            previous = record.state
            key = (record.workspace_id, record.strategy_id)

            if action.command == GovernanceCommand.APPROVE:
                if previous not in {GovernanceState.POLICY_READY, GovernanceState.POLICY_REVIEW_REQUIRED}:
                    raise GovernanceError("policy is not approvable")
                if record.assessment and record.assessment.violations:
                    raise GovernanceError("policy violations must be resolved before approval")
                if not action.approval_token:
                    raise GovernanceError("approval token required")
                if action.approval_token in self._approval_tokens:
                    raise GovernanceError("approval token replay detected")
                self._approval_tokens.add(action.approval_token)
                record.approval_token = action.approval_token
                record.state = GovernanceState.APPROVED

            elif action.command == GovernanceCommand.ACTIVATE:
                if previous != GovernanceState.APPROVED:
                    raise GovernanceError("policy must be approved before activation")
                if not action.activation_receipt:
                    raise GovernanceError("activation receipt required")
                if action.activation_receipt in self._activation_receipts:
                    raise GovernanceError("activation receipt replay detected")
                self._activation_receipts.add(action.activation_receipt)
                record.previous_active_version = self._active_versions.get(key)
                self._active_versions[key] = record.policy_version
                record.activation_receipt = action.activation_receipt
                record.state = GovernanceState.ACTIVATED

            elif action.command == GovernanceCommand.ROLLBACK:
                if previous != GovernanceState.ACTIVATED:
                    raise GovernanceError("only an active policy can be rolled back")
                target = action.rollback_target_version or record.previous_active_version
                if target is None or target not in self._versions[key]:
                    raise GovernanceError("valid rollback target version required")
                self._active_versions[key] = target
                record.state = GovernanceState.ROLLED_BACK

            elif action.command == GovernanceCommand.REJECT:
                record.state = GovernanceState.REJECTED
            elif action.command == GovernanceCommand.INVALIDATE:
                record.state = GovernanceState.INVALIDATED
            elif action.command == GovernanceCommand.ARCHIVE:
                if previous not in {
                    GovernanceState.REJECTED,
                    GovernanceState.ROLLED_BACK,
                    GovernanceState.INVALIDATED,
                }:
                    raise GovernanceError("only terminal policies can be archived")
                record.state = GovernanceState.ARCHIVED
            else:
                raise GovernanceError("unsupported command")

            record.updated_at = datetime.now(timezone.utc)
            details = {}
            if action.reason:
                details["reason"] = action.reason
            if action.rollback_target_version:
                details["rollback_target_version"] = action.rollback_target_version
            self._append_audit(record, action.command.value, action.actor, previous, record.state, details)
            return record.model_copy(deep=True)

    def active_policy(self, workspace_id: str, strategy_id: str) -> StrategyPolicyRecord:
        with self._lock:
            version = self._active_versions.get((workspace_id, strategy_id))
            if version is None:
                raise GovernanceError("no active policy")
            for record in self._records.values():
                if (
                    record.workspace_id == workspace_id
                    and record.strategy_id == strategy_id
                    and record.policy_version == version
                ):
                    return record.model_copy(deep=True)
            raise GovernanceError("active policy record not found")

    @staticmethod
    def _assess(payload: StrategyPolicyCreate) -> PolicyAssessment:
        violations: List[str] = []
        warnings: List[str] = []
        overlap = sorted(set(payload.symbols_allowed) & set(payload.symbols_blocked))
        if overlap:
            violations.append("symbols present in both allow and block lists: " + ",".join(overlap))
        if payload.max_daily_risk_percent < payload.max_risk_per_trade_percent:
            violations.append("daily risk cap cannot be below per-trade risk cap")
        if payload.observed_sample_size < payload.minimum_sample_size:
            warnings.append("minimum optimizer sample size not reached")
        if not payload.trading_windows:
            warnings.append("no explicit trading windows configured")
        effective_cap = min(payload.max_risk_per_trade_percent, payload.max_daily_risk_percent)
        return PolicyAssessment(
            compliant=not violations,
            violations=violations,
            warnings=warnings,
            effective_risk_cap_percent=effective_cap,
            requires_human_review=True,
        )

    def _append_audit(
        self,
        record: StrategyPolicyRecord,
        action: str,
        actor: str,
        previous: GovernanceState | None,
        target: GovernanceState,
        details: Dict[str, object] | None = None,
    ) -> None:
        self._audit.append(
            AuditEvent(
                workspace_id=record.workspace_id,
                record_id=record.id,
                action=action,
                actor=actor,
                from_state=previous,
                to_state=target,
                details=details or {},
            )
        )
