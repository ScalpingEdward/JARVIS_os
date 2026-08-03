from app.main import app
from app.api.routes import auron_demo1_telegram_continuous_conversation_supervisor_v21_323 as supervisor
from app.api.routes import auron_demo1_telegram_controlled_certificate_renewal_execution_v21_335 as renewal
from app.api.routes import auron_demo1_telegram_operational_go_live_acceptance_v21_322 as go_live
from app.api.routes import auron_demo1_telegram_post_renewal_continuity_governance_v21_336 as continuity
from app.api.routes import auron_demo1_telegram_service_certification_slo_v21_330 as certification


def setup_function() -> None:
    continuity.reset_telegram_post_renewal_continuity_governance_store()
    renewal.reset_telegram_controlled_certificate_renewal_execution_store()
    certification.reset_telegram_service_certification_slo_store()
    go_live.reset_telegram_operational_go_live_acceptance_store()
    supervisor.reset_telegram_continuous_conversation_supervisor_store()
    source = {
        'certificate_id': 'source-cert',
        'telegram_chat_id': '123',
        'certificate_state': 'superseded-after-governed-renewal',
        'integrity_hash': 'source-hash',
        'immutable': True,
        'runtime_reliability_score': 100.0,
    }
    successor = {
        'certificate_id': 'successor-cert',
        'supersedes_certificate_id': 'source-cert',
        'telegram_chat_id': '123',
        'certificate_state': 'certified',
        'integrity_hash': 'successor-hash',
        'immutable': True,
        'runtime_reliability_score': 100.0,
    }
    certification._certificate_store['source'] = source
    certification._certificate_store['successor'] = successor
    renewal._renewal_execution_store['source-cert'] = {
        'renewal_execution_id': 'execution-1',
        'source_certificate_id': 'source-cert',
        'successor_certificate_id': 'successor-cert',
        'telegram_chat_id': '123',
        'execution_state': 'completed-zero-downtime-handover',
    }
    renewal._handover_store['execution-1'] = {
        'handover_id': 'handover-1',
        'handover_state': 'committed-zero-downtime',
    }
    go_live._go_live_store['123'] = {
        'telegram_chat_id': '123',
        'continuous_mode_active': True,
        'go_live_state': 'renewed-certified-operational-service',
        'service_certificate_id': 'successor-cert',
    }
    supervisor._circuit_store['123'] = {'telegram_chat_id': '123', 'state': 'closed'}


def _start(required: int = 2) -> dict:
    return continuity.start_post_renewal_continuity(
        continuity.TelegramPostRenewalContinuityStartRequest(
            actor='operator',
            renewal_execution_id='execution-1',
            start_phrase='START AURON TELEGRAM POST RENEWAL CONTINUITY OBSERVATION',
            required_stable_observations=required,
            minimum_reliability_score=85.0,
            maximum_reliability_drop=5.0,
        )
    )


def test_starts_successor_stabilization_window() -> None:
    result = _start()
    assert result['state'] == 'telegram-post-renewal-continuity-started'
    assert result['continuity']['continuity_state'] == 'active-successor-stabilization-window'


def test_stable_observations_complete_successor(monkeypatch) -> None:
    monkeypatch.setattr(continuity, '_baseline_metrics', lambda _chat: {'runtime_reliability_score': 100.0})
    record = _start(required=2)['continuity']
    for _ in range(2):
        result = continuity.observe_post_renewal_continuity(
            continuity.TelegramPostRenewalContinuityObserveRequest(actor='operator', continuity_id=record['continuity_id'])
        )
        assert result['state'] == 'telegram-successor-stable-observation-recorded'
    completed = continuity.complete_successor_stabilization(
        continuity.TelegramSuccessorStabilizationCompleteRequest(
            actor='operator',
            continuity_id=record['continuity_id'],
            completion_phrase='COMPLETE AURON TELEGRAM SUCCESSOR STABILIZATION',
        )
    )
    assert completed['state'] == 'telegram-successor-stabilization-completed'
    assert completed['continuity']['stabilization_evidence_immutable'] is True
    assert len(completed['continuity']['stabilization_integrity_hash']) == 64


def test_degraded_successor_requires_rollback(monkeypatch) -> None:
    monkeypatch.setattr(continuity, '_baseline_metrics', lambda _chat: {'runtime_reliability_score': 60.0})
    record = _start(required=1)['continuity']
    result = continuity.observe_post_renewal_continuity(
        continuity.TelegramPostRenewalContinuityObserveRequest(actor='operator', continuity_id=record['continuity_id'])
    )
    assert result['state'] == 'telegram-successor-degraded-automatic-rollback-required'
    assert result['continuity']['continuity_state'] == 'automatic-rollback-required'


def test_governed_rollback_restores_source(monkeypatch) -> None:
    monkeypatch.setattr(continuity, '_baseline_metrics', lambda _chat: {'runtime_reliability_score': 50.0})
    record = _start(required=1)['continuity']
    continuity.observe_post_renewal_continuity(
        continuity.TelegramPostRenewalContinuityObserveRequest(actor='operator', continuity_id=record['continuity_id'])
    )
    result = continuity.rollback_certificate_handover(
        continuity.TelegramCertificateRollbackRequest(
            actor='operator',
            continuity_id=record['continuity_id'],
            rollback_phrase='ROLL BACK AURON TELEGRAM CERTIFICATE HANDOVER',
            reason='Successor reliability degraded during stabilization.',
        )
    )
    assert result['state'] == 'telegram-certificate-rollback-committed'
    assert certification._certificate_store['source']['certificate_state'] == 'certified'
    assert certification._certificate_store['successor']['certificate_state'] == 'rolled-back-after-continuity-degradation'
    assert go_live._go_live_store['123']['service_certificate_id'] == 'source-cert'


def test_start_requires_completed_handover() -> None:
    renewal._handover_store.clear()
    try:
        _start()
    except Exception as exc:
        assert getattr(exc, 'status_code', None) == 409
    else:
        raise AssertionError('Expected completed handover requirement')


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.336/start' in paths
    assert '/auron/demo1/v21.336/observe' in paths
    assert '/auron/demo1/v21.336/complete' in paths
    assert '/auron/demo1/v21.336/rollback' in paths
    assert '/auron/demo1/v21.336/status' in paths
    assert '/auron/demo1/v21.336/command-center' in paths
