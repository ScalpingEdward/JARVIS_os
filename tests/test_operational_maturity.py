import pytest
from pydantic import ValidationError

from backend.app.phoenix.v21_51_operational_maturity.models import (
    ImprovementInitiative,
    InitiativeStatus,
    MaturityActionRequest,
    MaturityCreate,
    MaturityDomain,
    MaturityState,
    RiskDecision,
)
from backend.app.phoenix.v21_51_operational_maturity.service import (
    MaturityGovernanceError,
    MaturityGovernanceService,
)


def payload(workspace_id: str = "ws-1", source_key: str = "source-1") -> MaturityCreate:
    return MaturityCreate(
        workspace_id=workspace_id,
        source_key=source_key,
        resilience_record_id="resilience-1",
        program_name="Operational Excellence",
        domains=[
            MaturityDomain(
                domain_id="operations",
                domain="Operations",
                owner="ops",
                current_score=4,
                target_score=4.5,
                minimum_acceptable_score=3,
                evidence_refs=["evidence://operations"],
            )
        ],
        initiatives=[
            ImprovementInitiative(
                initiative_id="initiative-1",
                domain_id="operations",
                title="Reduce recovery variance",
                owner="ops",
                priority=1,
                expected_score_gain=0.5,
                confidence=0.95,
                status=InitiativeStatus.PROPOSED,
                evidence_refs=["evidence://initiative"],
            )
        ],
        minimum_average_maturity=3,
        maturity_evidence_refs=["evidence://maturity"],
    )


def act(service, record, action, **kwargs):
    return service.act(
        record.record_id,
        record.workspace_id,
        MaturityActionRequest(action=action, actor="tester", **kwargs),
    )


def test_complete_maturity_lifecycle():
    service = MaturityGovernanceService()
    record = service.create(payload())
    act(service, record, "prepare-evidence")
    act(service, record, "assess")
    act(service, record, "prepare-improvement-plan")
    act(service, record, "request-review")
    act(service, record, "approve", approval_token="approval-1")
    act(service, record, "implement", receipt_id="implementation-1", evidence_refs=["evidence://implementation"])
    for index in range(3):
        act(
            service,
            record,
            "record-cycle",
            receipt_id=f"cycle-{index}",
            cycle_healthy=True,
            observed_average_maturity=4,
            observed_below_minimum_domains=0,
            observed_failed_initiatives=0,
        )
    act(service, record, "verify")
    assert record.state == MaturityState.VERIFIED
    assert len(service.audit("ws-1")) == 10


def test_low_maturity_escalates():
    service = MaturityGovernanceService()
    data = payload()
    data.domains[0].current_score = 2
    record = service.create(data)
    act(service, record, "prepare-evidence")
    act(service, record, "assess")
    assert record.state == MaturityState.ESCALATED


def test_risk_block_is_authoritative():
    service = MaturityGovernanceService()
    data = payload()
    data.risk_decision = RiskDecision.BLOCK
    record = service.create(data)
    act(service, record, "prepare-evidence")
    assert record.state == MaturityState.BLOCKED


def test_approval_and_receipt_replay_protection():
    service = MaturityGovernanceService()
    first = service.create(payload())
    for action in ("prepare-evidence", "assess", "prepare-improvement-plan", "request-review"):
        act(service, first, action)
    act(service, first, "approve", approval_token="shared-token")

    second = service.create(payload(source_key="source-2"))
    for action in ("prepare-evidence", "assess", "prepare-improvement-plan", "request-review"):
        act(service, second, action)
    with pytest.raises(MaturityGovernanceError, match="replay"):
        act(service, second, "approve", approval_token="shared-token")


def test_workspace_isolation_and_duplicate_source_key():
    service = MaturityGovernanceService()
    record = service.create(payload())
    with pytest.raises(MaturityGovernanceError):
        service.get(record.record_id, "other-workspace")
    with pytest.raises(MaturityGovernanceError, match="duplicate"):
        service.create(payload())


def test_initiative_must_reference_known_domain():
    with pytest.raises(ValidationError):
        MaturityCreate(
            workspace_id="ws",
            source_key="source",
            resilience_record_id="resilience",
            program_name="program",
            domains=[
                MaturityDomain(
                    domain_id="known",
                    domain="Known",
                    owner="owner",
                    current_score=4,
                    target_score=5,
                    minimum_acceptable_score=3,
                    evidence_refs=["evidence"],
                )
            ],
            initiatives=[
                ImprovementInitiative(
                    initiative_id="initiative",
                    domain_id="unknown",
                    title="title",
                    owner="owner",
                    priority=1,
                    expected_score_gain=1,
                    confidence=0.9,
                    evidence_refs=["evidence"],
                )
            ],
            maturity_evidence_refs=["evidence"],
        )
