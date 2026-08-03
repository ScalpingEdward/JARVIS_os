from fastapi import HTTPException

from app.main import app
from app.api.routes import auron_demo1_telegram_service_certification_slo_v21_330 as certification
from app.api.routes import auron_demo1_telegram_restoration_probation_v21_329 as probation
from app.api.routes import auron_demo1_telegram_operational_go_live_acceptance_v21_322 as go_live
from app.api.routes import auron_demo1_telegram_continuous_conversation_supervisor_v21_323 as supervisor
from app.api.routes import auron_demo1_telegram_lifecycle_progression_worker_v21_325 as progression


def setup_function() -> None:
    certification.reset_telegram_service_certification_slo_store()
    probation.reset_telegram_restoration_probation_store()
    go_live.reset_telegram_operational_go_live_acceptance_store()
    supervisor.reset_telegram_continuous_conversation_supervisor_store()
    progression.reset_telegram_lifecycle_progression_worker_store()
    go_live._go_live_store['123'] = {
        'go_live_acceptance_id': 'go-live-1',
        'telegram_chat_id': '123',
        'continuous_mode_active': True,
        'go_live_state': 'operational-after-successful-restoration-probation',
    }
    probation._probation_store['anomaly-1'] = {
        'probation_id': 'probation-1',
        'anomaly_id': 'anomaly-1',
        'telegram_chat_id': '123',
        'probation_state': 'completed-stable',
        'completed_at': '2026-08-03T10:00:00+00:00',
    }


def _certify(**overrides) -> dict:
    values = {
        'actor': 'operator',
        'probation_id': 'probation-1',
        'certification_phrase': 'CERTIFY AURON TELEGRAM SERVICE',
        'minimum_reliability_score': 85.0,
    }
    values.update(overrides)
    return certification.certify_telegram_service(certification.TelegramServiceCertificationRequest(**values))


def test_certifies_completed_stable_probation() -> None:
    result = _certify()
    assert result['state'] == 'telegram-service-certified'
    assert result['certificate']['certificate_state'] == 'certified'
    assert result['certificate']['immutable'] is True
    assert len(result['certificate']['integrity_hash']) == 64
    assert go_live._go_live_store['123']['go_live_state'] == 'certified-operational-service'


def test_certification_is_idempotent() -> None:
    first = _certify()
    second = _certify()
    assert second['idempotent_replay'] is True
    assert second['certificate']['certificate_id'] == first['certificate']['certificate_id']


def test_blocks_unfinished_probation() -> None:
    probation._probation_store['anomaly-1']['probation_state'] = 'active-observation-window'
    try:
        _certify()
    except HTTPException as exc:
        assert exc.status_code == 409
        assert 'probation_completed_stable' in exc.detail['blockers']
    else:
        raise AssertionError('unfinished probation should block certification')


def test_blocks_open_safety_circuit() -> None:
    supervisor._circuit_store['123'] = {'telegram_chat_id': '123', 'state': 'open'}
    try:
        _certify()
    except HTTPException as exc:
        assert exc.status_code == 409
        assert 'safety_circuit_closed' in exc.detail['blockers']
    else:
        raise AssertionError('open circuit should block certification')


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.330/certify' in paths
    assert '/auron/demo1/v21.330/status' in paths
    assert '/auron/demo1/v21.330/certificates' in paths
    assert '/auron/demo1/v21.330/command-center' in paths
