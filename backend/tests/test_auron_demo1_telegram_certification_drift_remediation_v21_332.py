from app.main import app
from app.api.routes import auron_demo1_telegram_certification_drift_remediation_v21_332 as remediation
from app.api.routes import auron_demo1_telegram_continuous_conversation_supervisor_v21_323 as supervisor
from app.api.routes import auron_demo1_telegram_operational_go_live_acceptance_v21_322 as go_live
from app.api.routes import auron_demo1_telegram_service_certification_slo_v21_330 as certification
from app.api.routes import auron_demo1_telegram_slo_monitoring_drift_v21_331 as drift


def setup_function() -> None:
    remediation.reset_telegram_certification_drift_remediation_store()
    supervisor.reset_telegram_continuous_conversation_supervisor_store()
    go_live.reset_telegram_operational_go_live_acceptance_store()
    certification.reset_telegram_service_certification_slo_store()
    drift.reset_telegram_slo_monitoring_drift_store()
    go_live._go_live_store['123'] = {
        'go_live_acceptance_id': 'go-live-1',
        'telegram_chat_id': '123',
        'continuous_mode_active': False,
        'go_live_state': 'suspended-by-certification-drift',
    }
    certification._certificate_store['probation-1'] = {
        'certificate_id': 'certificate-1',
        'telegram_chat_id': '123',
        'certificate_state': 'suspended-by-drift',
        'slo_baseline': {
            'delivery_success_rate': 1.0,
            'lifecycle_completion_rate': 1.0,
            'queue_completion_rate': 1.0,
            'dead_letter_rate': 0.0,
        },
        'runtime_reliability_score': 100.0,
    }
    drift._drift_store['drift-1'] = {
        'drift_id': 'drift-1',
        'observation_id': 'observation-1',
        'certificate_id': 'certificate-1',
        'telegram_chat_id': '123',
        'severity': 'critical',
        'blockers': ['reliability_within_tolerance'],
        'deltas': {'runtime_reliability_score': -10.0},
        'detected_at': '2026-08-03T10:00:00+00:00',
        'automatic_suspension_applied': True,
    }
    supervisor._circuit_store['123'] = {
        'telegram_chat_id': '123',
        'state': 'open',
        'consecutive_failures': 0,
    }


def _acknowledge() -> dict:
    return remediation.acknowledge_certification_drift(
        remediation.TelegramCertificationDriftAcknowledgeRequest(
            actor='operator',
            drift_id='drift-1',
            acknowledgement_phrase='ACKNOWLEDGE AURON TELEGRAM CERTIFICATION DRIFT',
            remediation_plan='Repair reliability regression and verify the SLO evidence chain.',
        )
    )


def _evidence() -> dict:
    return remediation.submit_remediation_evidence(
        remediation.TelegramCertificationDriftEvidenceRequest(
            actor='operator',
            drift_id='drift-1',
            evidence_id='evidence-1',
            evidence_summary='All runtime metrics recovered to the certified baseline.',
        )
    )


def test_acknowledges_certification_drift() -> None:
    result = _acknowledge()
    assert result['state'] == 'telegram-certification-drift-acknowledged'
    assert result['remediation']['remediation_state'] == 'acknowledged-awaiting-evidence'
    assert drift._drift_store['drift-1']['acknowledged'] is True


def test_records_immutable_remediation_evidence() -> None:
    _acknowledge()
    result = _evidence()
    assert result['state'] == 'telegram-certification-drift-evidence-recorded'
    assert result['remediation']['evidence_immutable'] is True
    assert len(result['remediation']['evidence_integrity_hash']) == 64


def test_controlled_recertification_restores_service() -> None:
    _acknowledge()
    _evidence()
    result = remediation.recertify_telegram_service(
        remediation.TelegramServiceRecertificationRequest(
            actor='operator',
            drift_id='drift-1',
            recertification_phrase='RECERTIFY AURON TELEGRAM SERVICE',
            minimum_reliability_score=85.0,
        )
    )
    assert result['state'] == 'telegram-service-recertified'
    assert result['certificate']['certificate_state'] == 'certified'
    assert go_live._go_live_store['123']['continuous_mode_active'] is True
    assert supervisor._circuit_store['123']['state'] == 'closed'
    assert certification._certificate_store['probation-1']['certificate_state'] == 'superseded-after-drift-remediation'


def test_recertification_requires_verified_evidence() -> None:
    _acknowledge()
    try:
        remediation.recertify_telegram_service(
            remediation.TelegramServiceRecertificationRequest(
                actor='operator',
                drift_id='drift-1',
                recertification_phrase='RECERTIFY AURON TELEGRAM SERVICE',
            )
        )
    except Exception as exc:
        assert getattr(exc, 'status_code', None) == 409
    else:
        raise AssertionError('Expected re-certification to be blocked without evidence')


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.332/acknowledge' in paths
    assert '/auron/demo1/v21.332/evidence' in paths
    assert '/auron/demo1/v21.332/recertify' in paths
    assert '/auron/demo1/v21.332/status' in paths
    assert '/auron/demo1/v21.332/command-center' in paths
