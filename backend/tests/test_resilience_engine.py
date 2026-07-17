from datetime import datetime, timedelta, timezone

import pytest

from app.resilience_engine.models import (
    AdmissionRequest, CircuitState, Decision, Mutation, Outcome, OutcomeRequest,
    PolicyCreate, PolicyState,
)
from app.resilience_engine.service import ResilienceService


def _policy(workspace: str = "alpha", owner: str = "owner", **overrides) -> PolicyCreate:
    data = dict(
        workspace_id=workspace,
        owner_id=owner,
        policy_key=f"api-{workspace}",
        target_service="event-bus",
        target_operation="publish",
        requests_per_window=2,
        window_seconds=60,
        failure_threshold=2,
        failure_window_seconds=60,
        open_seconds=30,
        bulkhead_max_concurrency=10,
        retry_budget=1,
        retry_window_seconds=60,
    )
    data.update(overrides)
    return PolicyCreate(**data)


def _admission(service: ResilienceService, policy_id, subject: str = "user", **overrides):
    data = dict(
        workspace_id="alpha",
        requester_id="owner",
        policy_id=policy_id,
        subject_key=subject,
        correlation_id=f"corr-{subject}-{len(service.admissions)}",
    )
    data.update(overrides)
    return service.evaluate(AdmissionRequest(**data))


def test_policy_lifecycle_rate_limit_and_workspace_isolation() -> None:
    service = ResilienceService()
    policy = service.create_policy(_policy())
    assert policy.state == PolicyState.DRAFT
    service.set_policy_state(policy.id, "alpha", Mutation(requester_id="owner"), PolicyState.ACTIVE)

    first = _admission(service, policy.id)
    second = _admission(service, policy.id)
    third = _admission(service, policy.id)
    assert first.decision == Decision.ALLOW
    assert second.decision == Decision.ALLOW
    assert third.decision == Decision.RATE_LIMITED
    assert third.retry_after_seconds >= 1
    assert service.get_policy(policy.id, "beta") is None
    assert service.metrics("alpha").rate_limited == 1


def test_bulkhead_release_and_retry_budget() -> None:
    service = ResilienceService()
    policy = service.create_policy(_policy(requests_per_window=20, bulkhead_max_concurrency=1))
    service.set_policy_state(policy.id, "alpha", Mutation(requester_id="owner"), PolicyState.ACTIVE)

    first = _admission(service, policy.id)
    blocked = _admission(service, policy.id, subject="other")
    assert blocked.decision == Decision.BULKHEAD_FULL

    service.record_outcome(OutcomeRequest(
        workspace_id="alpha", requester_id="owner", admission_id=first.id,
        outcome=Outcome.SUCCESS, latency_ms=12,
    ))
    allowed = _admission(service, policy.id, subject="other")
    assert allowed.decision == Decision.ALLOW
    service.record_outcome(OutcomeRequest(
        workspace_id="alpha", requester_id="owner", admission_id=allowed.id,
        outcome=Outcome.SUCCESS,
    ))

    retry_one = _admission(service, policy.id, subject="retry-a", is_retry=True)
    service.record_outcome(OutcomeRequest(
        workspace_id="alpha", requester_id="owner", admission_id=retry_one.id,
        outcome=Outcome.SUCCESS,
    ))
    retry_two = _admission(service, policy.id, subject="retry-b", is_retry=True)
    assert retry_two.decision == Decision.RETRY_BUDGET_EXHAUSTED


def test_circuit_open_half_open_recovery_and_manual_reset() -> None:
    service = ResilienceService()
    policy = service.create_policy(_policy(requests_per_window=100, bulkhead_max_concurrency=10))
    service.set_policy_state(policy.id, "alpha", Mutation(requester_id="owner"), PolicyState.ACTIVE)

    for index in range(2):
        admission = _admission(service, policy.id, subject=f"failure-{index}")
        service.record_outcome(OutcomeRequest(
            workspace_id="alpha", requester_id="owner", admission_id=admission.id,
            outcome=Outcome.FAILURE, reason="dependency error",
        ))
    assert policy.circuit_state == CircuitState.OPEN
    rejected = _admission(service, policy.id, subject="blocked")
    assert rejected.decision == Decision.CIRCUIT_OPEN

    probe_time = datetime.now(timezone.utc) + timedelta(seconds=31)
    probe = _admission(service, policy.id, subject="probe", evaluation_time=probe_time)
    assert probe.decision == Decision.ALLOW
    assert policy.circuit_state == CircuitState.HALF_OPEN
    service.record_outcome(OutcomeRequest(
        workspace_id="alpha", requester_id="owner", admission_id=probe.id,
        outcome=Outcome.SUCCESS,
    ))
    assert policy.circuit_state == CircuitState.CLOSED

    service.reset_circuit(policy.id, "alpha", Mutation(requester_id="owner", reason="approved reset"))
    assert policy.circuit_state == CircuitState.CLOSED


def test_duplicate_outcome_and_safety_guards() -> None:
    service = ResilienceService()
    policy = service.create_policy(_policy())
    service.set_policy_state(policy.id, "alpha", Mutation(requester_id="owner"), PolicyState.ACTIVE)
    admission = _admission(service, policy.id)
    outcome = OutcomeRequest(
        workspace_id="alpha", requester_id="owner", admission_id=admission.id,
        outcome=Outcome.SUCCESS,
    )
    service.record_outcome(outcome)
    with pytest.raises(ValueError, match="already recorded"):
        service.record_outcome(outcome)
    with pytest.raises(ValueError, match="automatic resilience-policy activation"):
        PolicyCreate(**{**_policy().model_dump(), "automatic_activation": True})
    with pytest.raises(ValueError, match="never execute target requests"):
        AdmissionRequest(
            workspace_id="alpha", requester_id="owner", policy_id=policy.id,
            subject_key="user", correlation_id="unsafe", execute_request=True,
        )
    with pytest.raises(ValueError, match="external resilience providers"):
        PolicyCreate(**{**_policy().model_dump(), "external_provider": True})
