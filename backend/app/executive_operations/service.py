from collections import defaultdict
from datetime import datetime, timezone
from threading import RLock
from uuid import UUID

from .models import (
    AuditRecord,
    DependencyEdge,
    ExecutiveAlert,
    HealthState,
    ModuleSummary,
    OperationsAnalysis,
    OperationsSnapshot,
    OperationsSnapshotCreate,
    OperationsStatus,
    RiskCell,
    Severity,
)


class ExecutiveOperationsService:
    def __init__(self) -> None:
        self._snapshots: dict[UUID, OperationsSnapshot] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _write_audit(self, workspace_id: str, action: str, actor_id: str, snapshot_id: UUID | None = None, details: dict | None = None) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, action=action, actor_id=actor_id, snapshot_id=snapshot_id, details=details or {}, created_at=self._now()))

    def create(self, payload: OperationsSnapshotCreate) -> OperationsSnapshot:
        now = self._now()
        record = OperationsSnapshot(**payload.model_dump(), created_at=now, updated_at=now)
        with self._lock:
            if any(item.workspace_id == payload.workspace_id and item.title == payload.title for item in self._snapshots.values()):
                raise ValueError("An operations snapshot with this title already exists in the workspace")
            self._snapshots[record.id] = record
            self._write_audit(payload.workspace_id, "operations-snapshot-created", payload.owner_id, record.id, {"modules": len(payload.signals)})
        return record

    def list_snapshots(self, workspace_id: str) -> list[OperationsSnapshot]:
        with self._lock:
            return [item for item in self._snapshots.values() if item.workspace_id == workspace_id]

    def get(self, snapshot_id: UUID, workspace_id: str) -> OperationsSnapshot | None:
        with self._lock:
            record = self._snapshots.get(snapshot_id)
            return record if record is not None and record.workspace_id == workspace_id else None

    @staticmethod
    def _severity(score: float, blocked: int = 0) -> Severity:
        if score >= 75 or blocked >= 5:
            return Severity.critical
        if score >= 45 or blocked > 0:
            return Severity.warning
        return Severity.info

    def analyze(self, snapshot_id: UUID, workspace_id: str, actor_id: str) -> OperationsSnapshot:
        with self._lock:
            record = self._snapshots.get(snapshot_id)
            if record is None or record.workspace_id != workspace_id:
                raise KeyError("Operations snapshot not found")

            summaries = [ModuleSummary(module=item.module, health=item.health, readiness_score=item.readiness_score, open_items=item.open_items, blocked_items=item.blocked_items, pending_approvals=item.pending_approvals, utilization_percent=item.utilization_percent, risk_score=item.risk_score) for item in record.signals]
            kpi_values: dict[str, list[float]] = defaultdict(list)
            alerts: list[ExecutiveAlert] = []
            heatmap: list[RiskCell] = []
            dependencies: list[DependencyEdge] = []

            for signal in record.signals:
                for name, value in signal.kpis.items():
                    kpi_values[name].append(value)
                severity = self._severity(signal.risk_score, signal.blocked_items)
                heatmap.append(RiskCell(module=signal.module, risk_score=signal.risk_score, blocked_items=signal.blocked_items, pending_approvals=signal.pending_approvals, severity=severity))
                if signal.health == HealthState.critical or severity == Severity.critical:
                    alerts.append(ExecutiveAlert(module=signal.module, severity=Severity.critical, code="MODULE_CRITICAL", message=f"{signal.module} requires executive attention", recommended_action="Review blockers, risk and release gates immediately"))
                elif signal.health == HealthState.degraded or signal.blocked_items or signal.pending_approvals:
                    alerts.append(ExecutiveAlert(module=signal.module, severity=Severity.warning, code="MODULE_DEGRADED", message=f"{signal.module} has unresolved operational constraints", recommended_action="Resolve blocked work and pending approvals"))
                if signal.utilization_percent >= 90:
                    alerts.append(ExecutiveAlert(module=signal.module, severity=Severity.warning, code="CAPACITY_HIGH", message=f"{signal.module} utilization is {signal.utilization_percent:.1f}%", recommended_action="Rebalance capacity or defer lower-priority work"))
                for target in signal.dependency_modules:
                    target_signal = next((candidate for candidate in record.signals if candidate.module == target), None)
                    blocked = target_signal is None or target_signal.health == HealthState.critical
                    dependencies.append(DependencyEdge(source_module=signal.module, target_module=target, blocked=blocked, explanation="Dependency is unavailable or critical" if blocked else "Dependency is available"))

            aggregated = {name: round(sum(values) / len(values), 2) for name, values in kpi_values.items()}
            readiness = sum(item.readiness_score for item in record.signals) / len(record.signals)
            risk = sum(item.risk_score for item in record.signals) / len(record.signals)
            utilization = sum(item.utilization_percent for item in record.signals) / len(record.signals)
            total_approvals = sum(item.pending_approvals for item in record.signals)
            total_blocked = sum(item.blocked_items for item in record.signals)
            governance = max(0.0, 100.0 - total_approvals * 4.0 - total_blocked * 6.0)
            executive_score = max(0.0, min(100.0, readiness * 0.45 + governance * 0.3 + (100.0 - risk) * 0.25))

            if any(item.health == HealthState.critical for item in record.signals) or any(edge.blocked for edge in dependencies):
                overall = HealthState.critical
            elif any(item.health == HealthState.degraded for item in record.signals) or alerts:
                overall = HealthState.degraded
            else:
                overall = HealthState.healthy

            recommendations: list[str] = []
            if total_blocked:
                recommendations.append("Resolve cross-module blockers before expanding the active portfolio")
            if total_approvals:
                recommendations.append("Prioritize pending governance approvals by strategic impact and risk")
            if utilization >= 85:
                recommendations.append("Rebalance capacity and defer non-critical operational work")
            if any(edge.blocked for edge in dependencies):
                recommendations.append("Repair blocked module dependencies before execution handoff")
            if not recommendations:
                recommendations.append("Operations are stable; continue governed monitoring and human review")

            analysis = OperationsAnalysis(analyzed_at=self._now(), overall_health=overall, executive_score=round(executive_score, 2), module_summaries=summaries, aggregated_kpis=aggregated, alerts=alerts, risk_heatmap=heatmap, dependency_graph=dependencies, governance_compliance_percent=round(governance, 2), capacity_utilization_percent=round(utilization, 2), executive_recommendations=recommendations)
            updated = record.model_copy(update={"analysis": analysis, "updated_at": self._now()})
            self._snapshots[snapshot_id] = updated
            self._write_audit(workspace_id, "operations-snapshot-analyzed", actor_id, snapshot_id, {"alerts": len(alerts), "executive_score": analysis.executive_score})
            return updated

    def status(self, workspace_id: str) -> OperationsStatus:
        records = self.list_snapshots(workspace_id)
        analyses = [item.analysis for item in records if item.analysis is not None]
        summaries = [summary for analysis in analyses for summary in analysis.module_summaries]
        return OperationsStatus(snapshots=len(records), healthy_modules=sum(item.health == HealthState.healthy for item in summaries), degraded_modules=sum(item.health == HealthState.degraded for item in summaries), critical_modules=sum(item.health == HealthState.critical for item in summaries), active_alerts=sum(len(analysis.alerts) for analysis in analyses))

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        with self._lock:
            return [item for item in self._audit if item.workspace_id == workspace_id]


executive_operations_service = ExecutiveOperationsService()
