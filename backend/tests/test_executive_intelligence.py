from datetime import datetime, timezone

import pytest

from app.executive_intelligence.models import BriefingCreate, EventSeverity, IntelligenceEvent
from app.executive_intelligence.service import ExecutiveIntelligenceService


def event(key: str, module: str, severity: EventSeverity = EventSeverity.info, value: float | None = None, baseline: float | None = None, related: list[str] | None = None) -> IntelligenceEvent:
    return IntelligenceEvent(event_key=key, module=module, category="operations", severity=severity, occurred_at=datetime.now(timezone.utc), metric_name="readiness", metric_value=value, baseline_value=baseline, related_event_keys=related or [], description=f"{module} event")


def test_analysis_builds_correlations_trends_anomalies_and_alerts() -> None:
    service = ExecutiveIntelligenceService()
    record = service.create(BriefingCreate(workspace_id="ws-a", owner_id="owner", title="Morning briefing", events=[event("root", "jarvis-core", EventSeverity.critical, 40, 90), event("dependent", "mission-control", EventSeverity.warning, 55, 80, ["root"])]))
    analyzed = service.analyze(record.id, "ws-a", "analyst")
    assert analyzed.analysis is not None
    assert analyzed.analysis.autonomous_actions_enabled is False
    assert analyzed.analysis.correlations[0].target_event_key == "root"
    assert len(analyzed.analysis.anomalies) == 2
    assert analyzed.analysis.predictive_alerts
    assert analyzed.analysis.root_cause_candidates[0].startswith("root:")


def test_workspace_isolation_and_duplicate_title() -> None:
    service = ExecutiveIntelligenceService()
    payload = BriefingCreate(workspace_id="ws-a", owner_id="owner", title="Daily", events=[event("one", "core")])
    record = service.create(payload)
    assert service.get(record.id, "ws-b") is None
    assert service.list_briefings("ws-b") == []
    with pytest.raises(ValueError):
        service.create(payload)


def test_unknown_related_event_is_rejected() -> None:
    with pytest.raises(ValueError):
        BriefingCreate(workspace_id="ws-a", owner_id="owner", title="Invalid", events=[event("one", "core", related=["missing"])])


def test_status_and_audit_are_workspace_scoped() -> None:
    service = ExecutiveIntelligenceService()
    record = service.create(BriefingCreate(workspace_id="ws-a", owner_id="owner", title="Status", events=[event("critical", "core", EventSeverity.critical, 10, 100)]))
    service.analyze(record.id, "ws-a", "analyst")
    status = service.status("ws-a")
    assert status.version == "18.1"
    assert status.briefings == 1
    assert status.analyzed_briefings == 1
    assert status.autonomous_actions_enabled is False
    assert len(service.audit_records("ws-a")) == 2
    assert service.audit_records("ws-b") == []
