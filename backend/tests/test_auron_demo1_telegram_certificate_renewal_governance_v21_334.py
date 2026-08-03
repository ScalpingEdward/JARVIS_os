from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.main import app
from app.api.routes import auron_demo1_telegram_certificate_renewal_governance_v21_334 as renewal
from app.api.routes import auron_demo1_telegram_continuous_conversation_supervisor_v21_323 as supervisor
from app.api.routes import auron_demo1_telegram_operational_go_live_acceptance_v21_322 as go_live
from app.api.routes import auron_demo1_telegram_post_recertification_governance_v21_333 as governance
from app.api.routes import auron_demo1_telegram_service_certification_slo_v21_330 as certification


def setup_function() -> None:
    renewal.reset_telegram_certificate_renewal_governance_store()
    governance.reset_telegram_post_recertification_governance_store()
    certification.reset_telegram_service_certification_slo_store()
    go_live.reset_telegram_operational_go_live_acceptance_store()
    supervisor.reset_telegram_continuous_conversation_supervisor_store()

    certified_at = datetime.now(timezone.utc) - timedelta(days=80)
    certificate = {
        'certificate_id': 'certificate-2',
        'supersedes_certificate_id': 'certificate-1',
        'telegram_chat_id': '123',
        'certificate_state': 'certified',
        'integrity_hash': 'hash-2',
        'immutable': True,
        'certified_at': certified_at.isoformat(),
        'slo_baseline': {
            'delivery_success_rate': 1.0,
            'lifecycle_completion_rate': 1.0,
            'queue_completion_rate': 1.0,
            'dead_letter_rate': 0.0,
        },
        'runtime_reliability_score': 100.0,
    }
    parent = {
        'certificate_id': 'certificate-1',
        'telegram_chat_id': '123',
        'certificate_state': 'superseded-after-drift-remediation',
        'integrity_hash': 'hash-1',
        'immutable': True,
        'certified_at': (certified_at - timedelta(days=90)).isoformat(),
        'slo_baseline': certificate['slo_baseline'],
        'runtime_reliability_score': 100.0,
    }
    certification._certificate_store['parent'] = parent
    certification._certificate_store['replacement'] = certificate
    go_live._go_live_store['123'] = {
        'telegram_chat_id': '123',
        'continuous_mode_active': True,
        'go_live_state': 'recertified-operational-service',
    }
    supervisor._circuit_store['123'] = {'telegram_chat_id': '123', 'state': 'closed'}
    governance._observation_store['certificate-2'] = {
        'governance_id': 'governance-1',
        'certificate_id': 'certificate-2',
        'telegram_chat_id': '123',
        'governance_state': 'completed-long-horizon-governance',
        'lineage_audit_id': 'audit-1',
    }
    governance._lineage_audit_store['governance-1'] = {
        'lineage_audit_id': 'audit-1',
        'certificate_id': 'certificate-2',
        'immutable': True,
        'integrity_hash': 'audit-hash',
    }


def _policy() -> dict:
    return renewal.establish_certificate_renewal_policy(
        renewal.TelegramCertificateRenewalPolicyRequest(
            actor='operator',
            certificate_id='certificate-2',
            policy_phrase='ESTABLISH AURON TELEGRAM CERTIFICATE RENEWAL POLICY',
            certificate_lifetime_days=90,
            renewal_lead_days=14,
            minimum_reliability_score=85.0,
            maximum_lineage_depth=10,
        )
    )


def test_establishes_immutable_renewal_policy() -> None:
    result = _policy()
    assert result['state'] == 'telegram-certificate-renewal-policy-established'
    assert result['policy']['immutable'] is True
    assert result['policy']['integrity_hash']


def test_evaluation_marks_certificate_renewal_due() -> None:
    _policy()
    result = renewal.evaluate_certificate_renewal(
        renewal.TelegramCertificateRenewalEvaluateRequest(
            actor='operator',
            certificate_id='certificate-2',
            evaluated_at=datetime.now(timezone.utc),
        )
    )
    assert result['evaluation']['renewal_state'] == 'renewal-due'
    assert result['evaluation']['blockers'] == []


def test_governed_renewal_schedule_is_idempotent() -> None:
    _policy()
    renewal.evaluate_certificate_renewal(
        renewal.TelegramCertificateRenewalEvaluateRequest(
            actor='operator',
            certificate_id='certificate-2',
            evaluated_at=datetime.now(timezone.utc),
        )
    )
    payload = renewal.TelegramCertificateRenewalScheduleRequest(
        actor='operator',
        certificate_id='certificate-2',
        schedule_phrase='SCHEDULE AURON TELEGRAM CERTIFICATE RENEWAL',
        reason='Certificate entered governed renewal window',
    )
    first = renewal.schedule_certificate_renewal(payload)
    second = renewal.schedule_certificate_renewal(payload)
    assert first['state'] == 'telegram-certificate-renewal-scheduled'
    assert second['idempotent_replay'] is True
    assert first['schedule']['integrity_hash']


def test_policy_blocked_without_completed_governance() -> None:
    governance._observation_store.clear()
    try:
        _policy()
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError('Expected renewal policy to be blocked')


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.334/policy' in paths
    assert '/auron/demo1/v21.334/evaluate' in paths
    assert '/auron/demo1/v21.334/schedule' in paths
    assert '/auron/demo1/v21.334/status' in paths
    assert '/auron/demo1/v21.334/command-center' in paths
