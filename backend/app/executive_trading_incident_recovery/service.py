from datetime import datetime, timezone
from threading import RLock
from uuid import UUID

from .models import (
    AuditRecord,
    IncidentRecoveryAssessment,
    IncidentSeverity,
    IncidentStatus,
    RecoveryAction,
    RecoveryInput,
    RecoveryPlan,
    RecoveryScores,
    RecoveryStatusResponse,
)


class ExecutiveTradingIncidentRecoveryService:
    def __init__(self) -> None:
        self._items: dict[UUID, IncidentRecoveryAssessment] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(100.0, value)), 2)

    @staticmethod
    def _severity_weight(severity: IncidentSeverity) -> float:
        return {
            IncidentSeverity.low: 10.0,
            IncidentSeverity.medium: 30.0,
            IncidentSeverity.high: 65.0,
            IncidentSeverity.critical: 100.0,
        }[severity]

    def assess(self, payload: RecoveryInput) -> IncidentRecoveryAssessment:
        with self._lock:
            if any(item.workspace_id == payload.workspace_id and item.source_key == payload.source_key for item in self._items.values()):
                raise ValueError("An incident recovery assessment with this source key already exists in the workspace")

            ranked = sorted(
                payload.incidents,
                key=lambda item: (self._severity_weight(item.severity), item.blocking, item.recurrence_count, item.age_minutes),
                reverse=True,
            )
            dominant = ranked[0]
            pressure = self._clamp(
                sum(self._severity_weight(item.severity) * min(1.5, 1 + (item.recurrence_count - 1) * 0.1) for item in payload.incidents)
                / max(len(payload.incidents), 1)
            )
            containment = self._clamp(
                (100 if payload.readiness_state == "blocked" else 65 if payload.readiness_state in {"wait", "conditional"} else 30)
                + (10 if payload.trading_decision in {"freeze", "reject"} else 0)
            )
            recovery = self._clamp(
                payload.recovery_confidence * 0.45
                + payload.data_integrity_score * 0.25
                + (100 if payload.rollback_available else 0) * 0.12
                + (100 if payload.failover_available else 0) * 0.1
                + (100 if payload.restart_safe else 0) * 0.08
            )
            resilience = self._clamp(recovery * 0.55 + containment * 0.3 + (100 - pressure) * 0.15)
            restart_safety = self._clamp(
                payload.data_integrity_score * 0.45
                + payload.recovery_confidence * 0.35
                + (100 if payload.restart_safe else 0) * 0.2
            )

            critical = any(item.severity == IncidentSeverity.critical or item.blocking for item in payload.incidents)
            reasons = [
                f"Dominant incident {dominant.code} affects {dominant.component}",
                f"Incident pressure is {pressure:.2f}",
                f"Recovery readiness is {recovery:.2f}",
            ]

            if payload.data_integrity_score < 60:
                primary = RecoveryAction.remain_blocked
                fallback = RecoveryAction.manual_intervention
                status = IncidentStatus.blocked
                steps = ["Preserve current state", "Block all trading paths", "Validate data integrity", "Escalate for manual recovery"]
                reasons.append("Data integrity is below the safe recovery threshold")
            elif dominant.component in {"feed", "broker", "network", "vps"} and payload.failover_available:
                primary = RecoveryAction.failover
                fallback = RecoveryAction.isolate
                status = IncidentStatus.recovering
                steps = [f"Isolate unhealthy {dominant.component}", "Activate verified failover", "Validate fresh data and connectivity", "Keep trading blocked during observation"]
            elif payload.rollback_available and dominant.recurrence_count >= 2:
                primary = RecoveryAction.rollback
                fallback = RecoveryAction.manual_intervention
                status = IncidentStatus.recovering
                steps = ["Freeze affected workflow", "Restore last known-good version", "Run integrity and regression checks", "Observe before release"]
            elif payload.restart_safe and dominant.component in {"parser", "worker", "service", "feed"} and not critical:
                primary = RecoveryAction.restart
                fallback = RecoveryAction.isolate
                status = IncidentStatus.recovering
                steps = [f"Gracefully restart {dominant.component}", "Confirm heartbeat and timestamp progression", "Run smoke checks", "Maintain reduced or blocked mode during observation"]
            elif critical:
                primary = RecoveryAction.isolate
                fallback = RecoveryAction.manual_intervention
                status = IncidentStatus.contained
                steps = [f"Isolate {dominant.component}", "Preserve logs and evidence", "Prevent automatic retries", "Require human-approved remediation"]
            else:
                primary = RecoveryAction.observe
                fallback = RecoveryAction.isolate
                status = IncidentStatus.detected
                steps = ["Continue diagnostic observation", "Collect recurrence and latency evidence", "Escalate if severity increases"]

            plan = RecoveryPlan(
                primary_action=primary,
                fallback_action=fallback,
                ordered_steps=steps,
                verification_checks=[
                    "No critical incident remains open",
                    "Market data timestamps progress normally",
                    "Broker, feed and VPS health are stable",
                    "Risk Brain and Readiness are reassessed",
                    "Human release approval is recorded",
                ],
                rollback_required=primary == RecoveryAction.rollback,
            )
            record = IncidentRecoveryAssessment(
                workspace_id=payload.workspace_id,
                actor_id=payload.actor_id,
                source_key=payload.source_key,
                symbol=payload.symbol,
                account_profile=payload.account_profile,
                status=status,
                dominant_incident_code=dominant.code,
                scores=RecoveryScores(
                    incident_pressure=pressure,
                    containment_readiness=containment,
                    recovery_readiness=recovery,
                    resilience_score=resilience,
                    restart_safety=restart_safety,
                ),
                plan=plan,
                reasons=reasons,
                trading_blocked=status != IncidentStatus.resolved,
                created_at=self._now(),
            )
            self._items[record.id] = record
            self._audit.append(AuditRecord(
                workspace_id=payload.workspace_id,
                action="trading-incident-recovery-assessed",
                actor_id=payload.actor_id,
                assessment_id=record.id,
                details={"status": status.value, "dominant": dominant.code, "primary_action": primary.value},
                created_at=self._now(),
            ))
            return record

    def list_assessments(self, workspace_id: str) -> list[IncidentRecoveryAssessment]:
        with self._lock:
            return [item for item in self._items.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> IncidentRecoveryAssessment | None:
        with self._lock:
            item = self._items.get(assessment_id)
            return item if item and item.workspace_id == workspace_id else None

    def status(self, workspace_id: str) -> RecoveryStatusResponse:
        records = self.list_assessments(workspace_id)
        return RecoveryStatusResponse(
            assessments=len(records),
            active_incidents=sum(item.status != IncidentStatus.resolved for item in records),
            critical_incidents=sum(item.scores.incident_pressure >= 80 for item in records),
            recovery_ready=sum(item.scores.recovery_readiness >= 70 for item in records),
            resolved=sum(item.status == IncidentStatus.resolved for item in records),
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        with self._lock:
            return [item for item in self._audit if item.workspace_id == workspace_id]


executive_trading_incident_recovery_service = ExecutiveTradingIncidentRecoveryService()
