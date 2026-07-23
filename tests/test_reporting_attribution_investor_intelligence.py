import pytest
from pydantic import ValidationError

from backend.app.modules.reporting_attribution_investor_intelligence.models import (
    AttributionComponent,
    AudienceType,
    ReportSection,
    ReportingActionRequest,
    ReportingCreate,
    ReportingState,
    RiskDecision,
)
from backend.app.modules.reporting_attribution_investor_intelligence.service import (
    ReportingGovernanceError,
    ReportingGovernanceService,
)


def payload(workspace: str = "ws") -> ReportingCreate:
    return ReportingCreate(
        workspace_id=workspace,
        source_key="report-1",
        financial_close_record_id="close-1",
        report_name="monthly-investor-report",
        reporting_period="2026-07",
        audience=AudienceType.INVESTOR,
        total_return=0.08,
        benchmark_return=0.05,
        attribution_components=[
            AttributionComponent(
                component_id="c1",
                strategy_id="s1",
                account_id="a1",
                contribution=0.081,
                fees=0.001,
                risk_contribution=0.3,
                evidence_refs=["attr-1"],
            )
        ],
        sections=[
            ReportSection(
                section_id="summary",
                title="Executive summary",
                content_summary="Verified portfolio performance and risk summary.",
                evidence_refs=["section-1"],
                confidence=0.95,
            )
        ],
        maximum_attribution_variance=0.001,
        required_healthy_cycles=2,
        reporting_evidence_refs=["report-evidence"],
    )


def act(service, record, action, **kwargs):
    return service.act(record.record_id, record.workspace_id, ReportingActionRequest(action=action, actor="tester", **kwargs))


def test_full_reporting_lifecycle():
    service = ReportingGovernanceService()
    record = service.create(payload())
    act(service, record, "prepare-evidence")
    act(service, record, "calculate-attribution")
    assert record.attributed_return == pytest.approx(0.08)
    act(service, record, "generate-report")
    act(service, record, "request-review")
    act(service, record, "approve", approval_token="a1")
    act(service, record, "publish", receipt_id="r1", evidence_refs=["publication"])
    for index in range(2):
        act(service, record, "record-cycle", receipt_id=f"m{index}", cycle_healthy=True, observed_total_return=0.08)
    act(service, record, "verify", receipt_id="verified")
    assert record.state == ReportingState.VERIFIED


def test_attribution_variance_escalates():
    service = ReportingGovernanceService()
    data = payload().model_copy(update={"total_return": 0.2})
    record = service.create(data)
    act(service, record, "prepare-evidence")
    act(service, record, "calculate-attribution")
    assert record.state == ReportingState.ESCALATED


def test_risk_block_and_replay_controls():
    service = ReportingGovernanceService()
    blocked = service.create(payload("blocked").model_copy(update={"source_key": "blocked", "risk_decision": RiskDecision.BLOCK}))
    act(service, blocked, "prepare-evidence")
    assert blocked.state == ReportingState.BLOCKED

    record = service.create(payload().model_copy(update={"source_key": "second"}))
    for action in ["prepare-evidence", "calculate-attribution", "generate-report", "request-review"]:
        act(service, record, action)
    act(service, record, "approve", approval_token="token")
    act(service, record, "publish", receipt_id="receipt")
    with pytest.raises(ReportingGovernanceError):
        act(service, record, "record-cycle", receipt_id="receipt", cycle_healthy=True)


def test_duplicate_component_ids_rejected():
    component = payload().attribution_components[0]
    with pytest.raises(ValidationError):
        ReportingCreate(**payload().model_dump() | {"attribution_components": [component.model_dump(), component.model_dump()]})


def test_workspace_isolation():
    service = ReportingGovernanceService()
    record = service.create(payload())
    with pytest.raises(ReportingGovernanceError):
        service.get(record.record_id, "other")
