from dataclasses import replace
import pytest

from app.content.auron_instagram_canary_e2e_certification_v21_594 import (
    InstagramCanaryE2ECertificationError,
    InstagramCanaryE2ECertificationHarness,
    InstagramCanaryE2ERequest,
)
from app.core.auron_integration_readiness_v21_594 import get_integration_readiness
from app.core.auron_production_readiness_canary_gate_v21_583 import CanaryReadinessDecision


def ready():
    return CanaryReadinessDecision(
        'd-instagram', 'instagram-content', 'instagram-local-draft-preview', True, (), 1, True, False,
        '2026-08-19T09:20:00+00:00', 'evidence-instagram'
    )


def request(**overrides):
    values = dict(
        readiness_decision=ready(), operator_id='operator-1', scope='draft-preview-only',
        action_key='render-draft-preview',
        payload={'draft_id': 'draft-1', 'caption': 'hello world', 'media_refs': ['local://image-1']},
    )
    values.update(overrides)
    return InstagramCanaryE2ERequest(**values)


def test_full_instagram_canary_chain_certifies_without_publish_or_transport(tmp_path):
    result = InstagramCanaryE2ECertificationHarness(tmp_path).run(request())
    assert result.execution_state == 'provider-submitted'
    assert result.reconciliation_state == 'reconciled'
    assert result.certification_outcome == 'promote' and result.certified is True
    assert result.provider_write_enabled is False
    assert result.public_publish_enabled is False
    assert result.network_transport_enabled is False
    assert result.production_transport_enabled is False


def test_same_request_is_idempotent_across_execution_and_reconciliation(tmp_path):
    harness = InstagramCanaryE2ECertificationHarness(tmp_path)
    a = harness.run(request())
    b = harness.run(request())
    assert a.activation_id == b.activation_id
    assert a.execution_id == b.execution_id
    assert a.reconciliation_id == b.reconciliation_id
    assert a.certification_id == b.certification_id


def test_wrong_provider_fails_before_execution(tmp_path):
    bad = replace(ready(), provider_id='instagram-api')
    with pytest.raises(InstagramCanaryE2ECertificationError):
        InstagramCanaryE2ECertificationHarness(tmp_path).run(request(readiness_decision=bad))


def test_publish_action_fails_before_execution(tmp_path):
    with pytest.raises(InstagramCanaryE2ECertificationError):
        InstagramCanaryE2ECertificationHarness(tmp_path).run(request(action_key='publish-post'))


def test_health_drift_yields_hold_and_no_publish_enablement(tmp_path):
    result = InstagramCanaryE2ECertificationHarness(tmp_path).run(request(provider_health_green=False))
    assert result.certification_outcome == 'hold' and result.certified is False
    assert result.public_publish_enabled is False and result.production_transport_enabled is False


def test_missing_promotion_approval_yields_hold(tmp_path):
    result = InstagramCanaryE2ECertificationHarness(tmp_path).run(request(operator_promotion_approved=False))
    assert result.certification_outcome == 'hold' and result.certified is False


def test_g7_readiness_advances_to_g8():
    r = get_integration_readiness()
    assert r['roadmap_version'] == 'v21.594'
    assert r['next_item'] == 'G8-instagram-health-drift-command-centre-certification'
    assert r['live_transports_enabled'] is False
