from datetime import datetime, timezone
from threading import RLock
from uuid import UUID

from .models import (
    AuditRecord,
    KPIResult,
    MeasurementUpdate,
    PerformanceAlert,
    PerformanceAnalysis,
    PerformanceStatus,
    PerformanceStatusResponse,
    Scorecard,
    ScorecardCreate,
    TrendDirection,
)


class ExecutivePerformanceService:
    def __init__(self) -> None:
        self._scorecards: dict[UUID, Scorecard] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _write_audit(self, workspace_id: str, action: str, actor_id: str, scorecard_id: UUID | None = None, details: dict | None = None) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, action=action, actor_id=actor_id, scorecard_id=scorecard_id, details=details or {}, created_at=self._now()))

    def create(self, payload: ScorecardCreate) -> Scorecard:
        now = self._now()
        record = Scorecard(**payload.model_dump(), created_at=now, updated_at=now)
        with self._lock:
            if any(item.workspace_id == payload.workspace_id and item.title == payload.title for item in self._scorecards.values()):
                raise ValueError("A performance scorecard with this title already exists in the workspace")
            self._scorecards[record.id] = record
            self._write_audit(payload.workspace_id, "performance-scorecard-created", payload.owner_id, record.id, {"kpis": len(payload.kpis), "risks": len(payload.risks)})
        return record

    def list_scorecards(self, workspace_id: str) -> list[Scorecard]:
        with self._lock:
            return [item for item in self._scorecards.values() if item.workspace_id == workspace_id]

    def get(self, scorecard_id: UUID, workspace_id: str) -> Scorecard | None:
        with self._lock:
            record = self._scorecards.get(scorecard_id)
            return record if record is not None and record.workspace_id == workspace_id else None

    def update_measurements(self, scorecard_id: UUID, workspace_id: str, payload: MeasurementUpdate) -> Scorecard:
        with self._lock:
            record = self._scorecards.get(scorecard_id)
            if record is None or record.workspace_id != workspace_id:
                raise KeyError("Performance scorecard not found")
            known = {item.key for item in record.kpis}
            unknown = set(payload.values) - known
            if unknown:
                raise ValueError(f"Unknown KPI keys: {sorted(unknown)}")
            updated_kpis = [item.model_copy(update={"current": payload.values[item.key]}) if item.key in payload.values else item for item in record.kpis]
            updated = record.model_copy(update={"kpis": updated_kpis, "analysis": None, "status": PerformanceStatus.draft, "version": record.version + 1, "updated_at": self._now()})
            self._scorecards[scorecard_id] = updated
            self._write_audit(workspace_id, "performance-measurements-updated", payload.actor_id, scorecard_id, {"updated_kpis": sorted(payload.values)})
            return updated

    def analyze(self, scorecard_id: UUID, workspace_id: str, actor_id: str) -> Scorecard:
        with self._lock:
            record = self._scorecards.get(scorecard_id)
            if record is None or record.workspace_id != workspace_id:
                raise KeyError("Performance scorecard not found")
            results: list[KPIResult] = []
            alerts: list[PerformanceAlert] = []
            recommendations: list[str] = []
            overall = 0.0
            aligned = 0
            for kpi in record.kpis:
                if kpi.target == kpi.baseline:
                    attainment = 100.0 if kpi.current == kpi.target else 0.0
                elif kpi.higher_is_better:
                    attainment = (kpi.current - kpi.baseline) / (kpi.target - kpi.baseline) * 100
                else:
                    attainment = (kpi.baseline - kpi.current) / (kpi.baseline - kpi.target) * 100
                attainment = max(0.0, min(200.0, attainment))
                variance = kpi.current - kpi.target
                if kpi.current == kpi.baseline:
                    trend = TrendDirection.stable
                elif (kpi.current > kpi.baseline) == kpi.higher_is_better:
                    trend = TrendDirection.improving
                else:
                    trend = TrendDirection.declining
                status = PerformanceStatus.on_track if attainment >= 90 else PerformanceStatus.at_risk if attainment >= 70 else PerformanceStatus.off_track
                weighted = attainment * kpi.weight / 100.0
                overall += weighted
                aligned += int(kpi.objective_key is not None)
                results.append(KPIResult(key=kpi.key, attainment=round(attainment, 2), weighted_score=round(weighted, 2), variance=round(variance, 2), trend=trend, status=status))
                if status != PerformanceStatus.on_track:
                    severity = "critical" if status == PerformanceStatus.off_track else "warning"
                    alerts.append(PerformanceAlert(severity=severity, source_key=kpi.key, message=f"{kpi.name} is {status.value} at {attainment:.1f}% attainment"))
                    recommendations.append(f"Review corrective actions and ownership for KPI {kpi.key}")
            risk_exposure = sum(item.probability * item.impact / 100.0 for item in record.risks)
            for risk in record.risks:
                exposure = risk.probability * risk.impact / 100.0
                if exposure >= 40:
                    alerts.append(PerformanceAlert(severity="critical" if exposure >= 60 else "warning", source_key=risk.key, message=f"Strategic risk exposure is {exposure:.1f}"))
                    recommendations.append(f"Activate or strengthen mitigation for risk {risk.key}")
            forecast = max(0.0, min(200.0, overall - risk_exposure * 0.2))
            status = PerformanceStatus.on_track if forecast >= 90 else PerformanceStatus.at_risk if forecast >= 70 else PerformanceStatus.off_track
            alignment_score = aligned / len(record.kpis) * 100
            analysis = PerformanceAnalysis(
                analyzed_at=self._now(), overall_score=round(overall, 2), alignment_score=round(alignment_score, 2), forecast_score=round(forecast, 2), status=status,
                kpi_results=results, risk_exposure=round(risk_exposure, 2), alerts=alerts,
                executive_summary=f"Performance is {status.value} with an overall score of {overall:.2f} and risk-adjusted forecast of {forecast:.2f}. Human review remains mandatory.",
                recommendations=sorted(set(recommendations)),
            )
            updated = record.model_copy(update={"analysis": analysis, "status": status, "version": record.version + 1, "updated_at": self._now()})
            self._scorecards[scorecard_id] = updated
            self._write_audit(workspace_id, "performance-scorecard-analyzed", actor_id, scorecard_id, {"status": status.value, "overall_score": analysis.overall_score, "alerts": len(alerts)})
            return updated

    def status(self, workspace_id: str) -> PerformanceStatusResponse:
        records = self.list_scorecards(workspace_id)
        return PerformanceStatusResponse(scorecards=len(records), analyzed_scorecards=sum(item.analysis is not None for item in records), at_risk_scorecards=sum(item.status == PerformanceStatus.at_risk for item in records), off_track_scorecards=sum(item.status == PerformanceStatus.off_track for item in records))

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        with self._lock:
            return [item for item in self._audit if item.workspace_id == workspace_id]


executive_performance_service = ExecutivePerformanceService()
