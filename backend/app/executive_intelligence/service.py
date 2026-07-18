from collections import defaultdict
from datetime import datetime, timezone
from threading import RLock
from uuid import UUID

from .models import (
    AnomalyInsight,
    AuditRecord,
    BriefingAnalysis,
    BriefingCreate,
    Correlation,
    DecisionImpact,
    EventSeverity,
    ExecutiveBriefing,
    IntelligenceStatus,
    PredictiveAlert,
    TrendDirection,
    TrendInsight,
)


class ExecutiveIntelligenceService:
    def __init__(self) -> None:
        self._briefings: dict[UUID, ExecutiveBriefing] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _write_audit(self, workspace_id: str, action: str, actor_id: str, briefing_id: UUID | None = None, details: dict | None = None) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, action=action, actor_id=actor_id, briefing_id=briefing_id, details=details or {}, created_at=self._now()))

    def create(self, payload: BriefingCreate) -> ExecutiveBriefing:
        now = self._now()
        record = ExecutiveBriefing(**payload.model_dump(), created_at=now, updated_at=now)
        with self._lock:
            if any(item.workspace_id == payload.workspace_id and item.title == payload.title for item in self._briefings.values()):
                raise ValueError("An executive briefing with this title already exists in the workspace")
            self._briefings[record.id] = record
            self._write_audit(payload.workspace_id, "executive-briefing-created", payload.owner_id, record.id, {"events": len(payload.events)})
        return record

    def list_briefings(self, workspace_id: str) -> list[ExecutiveBriefing]:
        with self._lock:
            return [item for item in self._briefings.values() if item.workspace_id == workspace_id]

    def get(self, briefing_id: UUID, workspace_id: str) -> ExecutiveBriefing | None:
        with self._lock:
            item = self._briefings.get(briefing_id)
            return item if item is not None and item.workspace_id == workspace_id else None

    def analyze(self, briefing_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveBriefing:
        with self._lock:
            record = self._briefings.get(briefing_id)
            if record is None or record.workspace_id != workspace_id:
                raise KeyError("Executive briefing not found")

            events_by_key = {event.event_key: event for event in record.events}
            correlations: list[Correlation] = []
            trends: list[TrendInsight] = []
            anomalies: list[AnomalyInsight] = []
            alerts: list[PredictiveAlert] = []
            module_events: dict[str, list] = defaultdict(list)

            for event in record.events:
                module_events[event.module].append(event)
                for related_key in event.related_event_keys:
                    related = events_by_key[related_key]
                    confidence = 90.0 if related.module != event.module else 75.0
                    correlations.append(Correlation(source_event_key=event.event_key, target_event_key=related_key, confidence=confidence, explanation=f"{event.module} event is explicitly related to {related.module}"))

                if event.metric_value is not None and event.baseline_value not in (None, 0):
                    change = ((event.metric_value - event.baseline_value) / abs(event.baseline_value)) * 100
                    direction = TrendDirection.improving if change > 5 else TrendDirection.deteriorating if change < -5 else TrendDirection.stable
                    trends.append(TrendInsight(module=event.module, metric_name=event.metric_name or "metric", direction=direction, change_percent=round(change, 2), confidence=min(100.0, 65.0 + abs(change) / 2)))
                    if abs(change) >= 25:
                        anomalies.append(AnomalyInsight(event_key=event.event_key, module=event.module, severity=event.severity if event.severity != EventSeverity.info else EventSeverity.warning, deviation_percent=round(abs(change), 2), explanation="Metric deviates materially from its baseline"))

                if event.severity == EventSeverity.critical:
                    alerts.append(PredictiveAlert(module=event.module, severity=EventSeverity.critical, horizon="immediate", message=f"Critical pattern detected: {event.description}", recommended_action="Escalate for executive review and validate dependent governance gates"))

            impacts: list[DecisionImpact] = []
            for module, module_items in module_events.items():
                critical = sum(item.severity == EventSeverity.critical for item in module_items)
                warning = sum(item.severity == EventSeverity.warning for item in module_items)
                score = min(100.0, critical * 35.0 + warning * 15.0 + len(module_items) * 5.0)
                impacts.append(DecisionImpact(module=module, event_count=len(module_items), critical_events=critical, impact_score=round(score, 2)))
                deteriorating = [trend for trend in trends if trend.module == module and trend.direction == TrendDirection.deteriorating]
                if len(deteriorating) >= 2 and not any(alert.module == module for alert in alerts):
                    alerts.append(PredictiveAlert(module=module, severity=EventSeverity.warning, horizon="near-term", message="Multiple deteriorating KPI trends may create an operational constraint", recommended_action="Review capacity, dependencies and pending approvals"))

            root_causes = []
            related_counts = {key: 0 for key in events_by_key}
            for correlation in correlations:
                related_counts[correlation.target_event_key] += 1
            for key, count in sorted(related_counts.items(), key=lambda item: item[1], reverse=True):
                if count > 0:
                    root_causes.append(f"{key}: referenced by {count} correlated event(s)")
            if not root_causes and record.events:
                root_causes.append(f"{record.events[0].event_key}: earliest available causal candidate")

            critical_count = sum(event.severity == EventSeverity.critical for event in record.events)
            warning_count = sum(event.severity == EventSeverity.warning for event in record.events)
            confidence = min(100.0, 55.0 + len(correlations) * 5.0 + len(trends) * 3.0)
            summary = f"Analyzed {len(record.events)} events across {len(module_events)} modules; found {len(correlations)} correlations, {len(anomalies)} anomalies and {len(alerts)} predictive alerts."
            recommendations: list[str] = []
            if critical_count:
                recommendations.append("Prioritize critical correlated events for independent human review")
            if anomalies:
                recommendations.append("Validate anomalous KPI movements against source systems and recent decisions")
            if correlations:
                recommendations.append("Inspect the highest-connected root-cause candidates before approving downstream actions")
            if warning_count and not critical_count:
                recommendations.append("Monitor warning patterns and prepare mitigation before they become execution blockers")
            if not recommendations:
                recommendations.append("Situation is stable; continue governed monitoring and periodic executive briefings")

            analysis = BriefingAnalysis(analyzed_at=self._now(), situation_summary=summary, executive_confidence=round(confidence, 2), correlations=correlations, trends=trends, anomalies=anomalies, predictive_alerts=alerts, decision_impacts=sorted(impacts, key=lambda item: item.impact_score, reverse=True), root_cause_candidates=root_causes, executive_recommendations=recommendations)
            updated = record.model_copy(update={"analysis": analysis, "updated_at": self._now()})
            self._briefings[briefing_id] = updated
            self._write_audit(workspace_id, "executive-briefing-analyzed", actor_id, briefing_id, {"alerts": len(alerts), "confidence": analysis.executive_confidence})
            return updated

    def status(self, workspace_id: str) -> IntelligenceStatus:
        records = self.list_briefings(workspace_id)
        analyses = [item.analysis for item in records if item.analysis is not None]
        return IntelligenceStatus(briefings=len(records), analyzed_briefings=len(analyses), active_predictive_alerts=sum(len(item.predictive_alerts) for item in analyses), critical_anomalies=sum(anomaly.severity == EventSeverity.critical for item in analyses for anomaly in item.anomalies))

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        with self._lock:
            return [item for item in self._audit if item.workspace_id == workspace_id]


executive_intelligence_service = ExecutiveIntelligenceService()
