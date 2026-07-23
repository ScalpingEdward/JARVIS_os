from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set
from uuid import uuid4

from app.schemas.exchange_infrastructure_health import (
    InfrastructureHealthAction,
    InfrastructureHealthCreate,
    InfrastructureHealthRecord,
    InfrastructureHealthScores,
    InfrastructureHealthState,
    InfrastructureVenueAssessment,
)


@dataclass
class AuditEvent:
    event_id: str
    workspace_id: str
    record_id: str
    action: str
    actor: str
    operation_id: str
    state: str
    reason: str | None = None


class ExchangeInfrastructureHealthService:
    def __init__(self) -> None:
        self._records: Dict[str, InfrastructureHealthRecord] = {}
        self._source_keys: Set[tuple[str, str]] = set()
        self._operations: Set[tuple[str, str]] = set()
        self._audit: List[AuditEvent] = []
        self._risk_brain_blocked_workspaces: Set[str] = set()

    def status(self) -> dict:
        return {
            "module": "PHOENIX v21.76 Exchange Infrastructure Health Governance",
            "advisory_only": True,
            "infrastructure_mutation_enabled": False,
            "routing_mutation_enabled": False,
            "failover_execution_enabled": False,
            "execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def set_risk_brain_block(self, workspace_id: str, blocked: bool) -> None:
        if blocked:
            self._risk_brain_blocked_workspaces.add(workspace_id)
        else:
            self._risk_brain_blocked_workspaces.discard(workspace_id)

    def create(self, payload: InfrastructureHealthCreate) -> InfrastructureHealthRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key in workspace")

        assessments: List[InfrastructureVenueAssessment] = []
        risk_flags: List[str] = []
        weighted_confidence = 0.0

        for item in payload.observations:
            latency_score = self._clamp(
                1 - ((item.gateway_latency_ms + item.market_data_latency_ms + item.order_ack_latency_ms) / 3) /
                max(payload.max_gateway_latency_ms, 1)
            )
            connectivity_score = self._clamp(
                1 - (item.packet_loss_rate * 35 + item.disconnect_rate * 25 + item.error_rate * 20)
            )
            data_integrity_score = self._clamp(
                1 - (item.stale_quote_rate * 30 + min(item.time_sync_drift_ms / 100, 1) * 0.35)
            )
            capacity_score = self._clamp(
                1 - max(item.cpu_utilization, item.memory_utilization, item.queue_utilization)
            )
            failover_score = self._clamp(item.failover_readiness * item.uptime_rate)
            confidence = item.confidence * item.freshness
            weighted_confidence += confidence

            health_score = self._clamp(
                (latency_score * 0.22 + connectivity_score * 0.22 + data_integrity_score * 0.20 +
                 capacity_score * 0.16 + failover_score * 0.20) * confidence
            )

            signal = "stable"
            if item.uptime_rate < payload.min_uptime_rate or item.disconnect_rate > 0.02:
                signal = "connectivity-alert"
                risk_flags.append(f"{item.venue_id}:connectivity-alert")
            if item.gateway_latency_ms > payload.max_gateway_latency_ms:
                signal = "latency-alert"
                risk_flags.append(f"{item.venue_id}:latency-alert")
            if item.packet_loss_rate > payload.max_packet_loss_rate or item.stale_quote_rate > 0.02:
                signal = "data-degradation"
                risk_flags.append(f"{item.venue_id}:data-degradation")
            if item.queue_utilization > payload.max_queue_utilization:
                signal = "capacity-alert"
                risk_flags.append(f"{item.venue_id}:capacity-alert")
            if health_score < 0.35 or item.failover_readiness < 0.4:
                signal = "failover-required"
                risk_flags.append(f"{item.venue_id}:failover-required")

            assessments.append(
                InfrastructureVenueAssessment(
                    venue_id=item.venue_id,
                    connectivity_score=round(connectivity_score, 6),
                    data_integrity_score=round(data_integrity_score, 6),
                    latency_score=round(latency_score, 6),
                    capacity_score=round(capacity_score, 6),
                    failover_score=round(failover_score, 6),
                    health_score=round(health_score, 6),
                    operational_signal=signal,
                )
            )

        count = len(assessments)
        avg = lambda name: sum(getattr(x, name) for x in assessments) / count
        clock_integrity = self._clamp(
            1 - sum(min(x.time_sync_drift_ms / 100, 1) for x in payload.observations) / count
        )
        scores = InfrastructureHealthScores(
            aggregate_health=round(avg("health_score"), 6),
            connectivity_resilience=round(avg("connectivity_score"), 6),
            market_data_integrity=round(avg("data_integrity_score"), 6),
            execution_path_health=round(avg("latency_score"), 6),
            capacity_headroom=round(avg("capacity_score"), 6),
            failover_readiness=round(avg("failover_score"), 6),
            clock_integrity=round(clock_integrity, 6),
            confidence=round(weighted_confidence / count, 6),
        )

        state = InfrastructureHealthState.EVIDENCE_READY
        if any(flag.endswith("failover-required") for flag in risk_flags):
            state = InfrastructureHealthState.FAILOVER_REQUIRED
        elif any(flag.endswith("capacity-alert") for flag in risk_flags):
            state = InfrastructureHealthState.CAPACITY_ALERT
        elif any(flag.endswith("data-degradation") for flag in risk_flags):
            state = InfrastructureHealthState.DATA_DEGRADATION
        elif any(flag.endswith("latency-alert") for flag in risk_flags):
            state = InfrastructureHealthState.LATENCY_ALERT
        elif any(flag.endswith("connectivity-alert") for flag in risk_flags):
            state = InfrastructureHealthState.CONNECTIVITY_ALERT

        record = InfrastructureHealthRecord(
            record_id=str(uuid4()),
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            scores=scores,
            assessments=assessments,
            risk_flags=sorted(set(risk_flags)),
        )
        self._records[record.record_id] = record
        self._source_keys.add(source_identity)
        self._write_audit(record, "create", payload.requested_by, f"create:{payload.source_key}")
        return record

    def list(self, workspace_id: str) -> List[InfrastructureHealthRecord]:
        return [r for r in self._records.values() if r.workspace_id == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> InfrastructureHealthRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise KeyError("record not found")
        return record

    def act(self, workspace_id: str, record_id: str, action: InfrastructureHealthAction) -> InfrastructureHealthRecord:
        record = self.get(workspace_id, record_id)
        operation_identity = (workspace_id, action.operation_id)
        if operation_identity in self._operations:
            raise ValueError("operation replay detected")
        if action.action in {"approve", "activate", "monitor"} and workspace_id in self._risk_brain_blocked_workspaces:
            raise PermissionError("Risk Brain hard block is active")
        if action.action == "activate" and not record.approved_by:
            raise PermissionError("human approval required")

        transitions = {
            "score": InfrastructureHealthState.SCORED,
            "submit-review": InfrastructureHealthState.REVIEW_REQUIRED,
            "approve": InfrastructureHealthState.APPROVED,
            "activate": InfrastructureHealthState.ACTIVE,
            "monitor": InfrastructureHealthState.MONITORING,
            "suspend": InfrastructureHealthState.SUSPENDED,
            "revoke": InfrastructureHealthState.REVOKED,
            "archive": InfrastructureHealthState.ARCHIVED,
        }
        updated = record.model_copy(update={
            "state": transitions[action.action],
            "approved_by": action.actor if action.action == "approve" else record.approved_by,
            "version": record.version + 1,
        })
        self._records[record_id] = updated
        self._operations.add(operation_identity)
        self._write_audit(updated, action.action, action.actor, action.operation_id, action.reason)
        return updated

    def audit(self, workspace_id: str) -> List[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def _write_audit(self, record: InfrastructureHealthRecord, action: str, actor: str, operation_id: str, reason: str | None = None) -> None:
        self._audit.append(AuditEvent(
            event_id=str(uuid4()), workspace_id=record.workspace_id, record_id=record.record_id,
            action=action, actor=actor, operation_id=operation_id, state=record.state.value, reason=reason,
        ))

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))
