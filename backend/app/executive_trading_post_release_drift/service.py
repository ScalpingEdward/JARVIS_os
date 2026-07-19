from datetime import datetime, timezone
from threading import RLock
from uuid import UUID

from .models import (
    AuditRecord,
    DriftDimension,
    DriftSeverity,
    DriftSignal,
    MonitoringAssessment,
    MonitoringInput,
    MonitoringScores,
    MonitoringState,
    MonitoringStatusResponse,
)


class ExecutiveTradingPostReleaseDriftService:
    def __init__(self) -> None:
        self._items: dict[UUID, MonitoringAssessment] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(100.0, value)), 2)

    @staticmethod
    def _deviation(baseline: float, current: float, higher_is_better: bool) -> float:
        denominator = max(abs(baseline), 1e-9)
        raw = ((current - baseline) / denominator) * 100.0
        return raw if higher_is_better else -raw

    def assess(self, payload: MonitoringInput) -> MonitoringAssessment:
        with self._lock:
            if any(item.workspace_id == payload.workspace_id and item.source_key == payload.source_key for item in self._items.values()):
                raise ValueError("A post-release monitoring assessment with this source key already exists in the workspace")

            signals: list[DriftSignal] = []
            dimension_scores: dict[DriftDimension, list[float]] = {item: [] for item in DriftDimension}

            for metric in payload.metrics:
                signed = self._deviation(metric.baseline_value, metric.current_value, metric.higher_is_better)
                adverse = max(0.0, -signed)
                dimension_scores[metric.dimension].append(self._clamp(100 - adverse))
                severity = None
                blocking = False
                if adverse > max(35.0, metric.tolerance_percent * 3):
                    severity = DriftSeverity.critical
                    blocking = metric.dimension in {DriftDimension.risk, DriftDimension.data, DriftDimension.infrastructure}
                elif adverse > max(20.0, metric.tolerance_percent * 2):
                    severity = DriftSeverity.warning
                elif adverse > metric.tolerance_percent:
                    severity = DriftSeverity.info
                if severity:
                    signals.append(DriftSignal(
                        metric_name=metric.name,
                        dimension=metric.dimension,
                        severity=severity,
                        deviation_percent=round(adverse, 2),
                        message=f"{metric.name} deteriorated {adverse:.2f}% beyond the approved baseline",
                        blocking=blocking,
                        remediation=f"Review {metric.dimension.value} telemetry and restore the approved baseline before promotion",
                    ))

            if payload.open_critical_issues > 0:
                signals.append(DriftSignal(metric_name="open_critical_issues", dimension=DriftDimension.infrastructure, severity=DriftSeverity.critical, deviation_percent=100, message="Critical issues remain open after release", blocking=True, remediation="Resolve and verify every critical issue before live continuation"))
            if payload.incident_recurrence_count >= 2:
                signals.append(DriftSignal(metric_name="incident_recurrence", dimension=DriftDimension.infrastructure, severity=DriftSeverity.critical, deviation_percent=min(100, payload.incident_recurrence_count * 25), message="The released incident has recurred", blocking=True, remediation="Return to incident recovery and perform root-cause containment"))
            if payload.risk_state in {"blocked", "frozen"}:
                signals.append(DriftSignal(metric_name="risk_state", dimension=DriftDimension.risk, severity=DriftSeverity.critical, deviation_percent=100, message="Risk Brain no longer permits live operation", blocking=True, remediation="Regress to blocked state and obtain a new risk clearance"))
            if payload.readiness_state in {"blocked", "wait"}:
                signals.append(DriftSignal(metric_name="readiness_state", dimension=DriftDimension.infrastructure, severity=DriftSeverity.critical, deviation_percent=100, message="Trading readiness regressed after release", blocking=True, remediation="Return to readiness diagnostics before any live continuation"))

            def average(dimension: DriftDimension) -> float:
                values = dimension_scores[dimension]
                return self._clamp(sum(values) / len(values)) if values else 100.0

            performance = average(DriftDimension.performance)
            risk = average(DriftDimension.risk)
            execution = average(DriftDimension.execution)
            operational = self._clamp((average(DriftDimension.infrastructure) + average(DriftDimension.data) + average(DriftDimension.model)) / 3)
            fidelity = self._clamp((performance + risk + execution + operational) / 4)
            observation_progress = min(100.0, payload.observation_trades / payload.minimum_observation_trades * 100)
            time_progress = min(100.0, payload.stable_minutes / payload.minimum_stable_minutes * 100)
            promotion = self._clamp(fidelity * 0.55 + observation_progress * 0.25 + time_progress * 0.2)
            penalty = sum(45 if item.severity == DriftSeverity.critical else 18 if item.severity == DriftSeverity.warning else 5 for item in signals)
            overall = self._clamp(fidelity * 0.75 + promotion * 0.25 - penalty * 0.25)

            blocking = any(item.blocking for item in signals)
            critical = any(item.severity == DriftSeverity.critical for item in signals)
            warning = any(item.severity == DriftSeverity.warning for item in signals)
            if blocking:
                state = MonitoringState.blocked
                multiplier = 0.0
            elif critical:
                state = MonitoringState.shadow
                multiplier = 0.0
            elif warning or overall < 65:
                state = MonitoringState.reduce
                multiplier = min(payload.approved_risk_multiplier, 0.25)
            elif signals or overall < 82:
                state = MonitoringState.watch
                multiplier = min(payload.approved_risk_multiplier, 0.5)
            else:
                state = MonitoringState.stable
                multiplier = payload.approved_risk_multiplier

            promotion_allowed = state == MonitoringState.stable and promotion >= 85 and payload.observation_trades >= payload.minimum_observation_trades and payload.stable_minutes >= payload.minimum_stable_minutes
            reasons = [item.message for item in signals] or ["Post-release performance, risk, execution and operations remain within the approved baseline"]
            if not promotion_allowed:
                reasons.append("Promotion requires a stable state and completion of observation-trade and stability-time gates")

            record = MonitoringAssessment(
                workspace_id=payload.workspace_id,
                actor_id=payload.actor_id,
                source_key=payload.source_key,
                symbol=payload.symbol,
                account_profile=payload.account_profile,
                state=state,
                recommended_risk_multiplier=round(multiplier, 2),
                scores=MonitoringScores(
                    baseline_fidelity=fidelity,
                    performance_stability=performance,
                    risk_stability=risk,
                    execution_stability=execution,
                    operational_stability=operational,
                    promotion_readiness=promotion,
                    overall_health=overall,
                ),
                drift_signals=signals,
                reasons=reasons,
                promotion_allowed=promotion_allowed,
                regression_required=state in {MonitoringState.shadow, MonitoringState.blocked},
                assessed_at=self._now(),
            )
            self._items[record.id] = record
            self._audit.append(AuditRecord(workspace_id=payload.workspace_id, action="post-release-drift-assessed", actor_id=payload.actor_id, assessment_id=record.id, details={"state": state.value, "signals": len(signals), "promotion_allowed": promotion_allowed}, created_at=self._now()))
            return record

    def list_assessments(self, workspace_id: str) -> list[MonitoringAssessment]:
        with self._lock:
            return [item for item in self._items.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> MonitoringAssessment | None:
        with self._lock:
            item = self._items.get(assessment_id)
            return item if item and item.workspace_id == workspace_id else None

    def status(self, workspace_id: str) -> MonitoringStatusResponse:
        records = self.list_assessments(workspace_id)
        return MonitoringStatusResponse(
            assessments=len(records),
            stable=sum(item.state == MonitoringState.stable for item in records),
            watching=sum(item.state == MonitoringState.watch for item in records),
            reduced=sum(item.state == MonitoringState.reduce for item in records),
            shadow=sum(item.state == MonitoringState.shadow for item in records),
            blocked=sum(item.state == MonitoringState.blocked for item in records),
            critical_drifts=sum(signal.severity == DriftSeverity.critical for item in records for signal in item.drift_signals),
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        with self._lock:
            return [item for item in self._audit if item.workspace_id == workspace_id]


executive_trading_post_release_drift_service = ExecutiveTradingPostReleaseDriftService()
