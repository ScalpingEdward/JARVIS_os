from app.main import app
from app.api.routes import auron_demo1_telegram_slo_monitoring_drift_v21_331 as drift
from app.api.routes import auron_demo1_telegram_service_certification_slo_v21_330 as certification
from app.api.routes import auron_demo1_telegram_operational_go_live_acceptance_v21_322 as go_live
from app.api.routes import auron_demo1_telegram_continuous_conversation_supervisor_v21_323 as supervisor


def setup_function() -> None:
    drift.reset_telegram_slo_monitoring_drift_store()
    certification.reset_telegram_service_certification_slo_store()
    go_live.reset_telegram_operational_go_live_acceptance_store()
    supervisor.reset_telegram_continuous_conversation_supervisor_store()
    certification._certificate_store['probation-1'] = {
        'certificate_id': 'certificate-1',
        'probation_id': 'probation-1',
        'telegram_chat_id': '123',
        'certificate_state': 'certified',
        'slo_baseline': {
            'delivery_success_rate': 1.0,
            'lifecycle_completion_rate': 1.0,
            'queue_completion_rate': 1.0,
            'dead_letter_rate': 0.0,
        },
        'runtime_reliability_score': 100.0,
    }
    go_live._go_live_store['123'] = {
        'go_live_acceptance_id': 'go-live-1',
        'telegram_chat_id': '123',
        'continuous_mode_active': True,
        'go_live_state': 'certified-operational-service',
    }


def _observe(**overrides) -> dict:
    values = {
        'actor': 'operator',
        'certificate_id': 'certificate-1',
        'max_delivery_drop': 0.05,
        'max_lifecycle_drop': 0.05,
        'max_queue_drop': 0.10,
        'max_dead_letter_increase': 0.02,
        'max_reliability_drop': 5.0,
        'auto_suspend_on_critical_drift': True,
    }
    values.update(overrides)
    return drift.observe_certified_slo(drift.TelegramSLOObservationRequest(**values))


def test_stable_certified_slo_observation() -> None:
    result = _observe()
    assert result['state'] == 'telegram-certified-slo-stable'
    assert result['observation']['trend_state'] == 'stable'
    assert result['drift'] is None
    assert go_live._go_live_store['123']['continuous_mode_active'] is True


def test_critical_reliability_drift_suspends_service(monkeypatch) -> None:
    monkeypatch.setattr(drift, '_baseline_metrics', lambda chat_id: {
        'delivery_success_rate': 0.5,
        'lifecycle_completion_rate': 0.5,
        'queue_completion_rate': 0.8,
        'dead_letter_rate': 0.2,
        'runtime_reliability_score': 55.0,
    })
    result = _observe()
    assert result['state'] == 'telegram-certified-slo-critical-drift'
    assert result['drift']['automatic_suspension_applied'] is True
    assert certification._certificate_store['probation-1']['certificate_state'] == 'suspended-by-drift'
    assert go_live._go_live_store['123']['continuous_mode_active'] is False
    assert supervisor._circuit_store['123']['state'] == 'open'


def test_warning_queue_drift_does_not_suspend(monkeypatch) -> None:
    monkeypatch.setattr(drift, '_baseline_metrics', lambda chat_id: {
        'delivery_success_rate': 1.0,
        'lifecycle_completion_rate': 1.0,
        'queue_completion_rate': 0.7,
        'dead_letter_rate': 0.0,
        'runtime_reliability_score': 94.0,
    })
    result = _observe(max_reliability_drop=10.0)
    assert result['state'] == 'telegram-certified-slo-warning-drift'
    assert result['drift']['severity'] == 'warning'
    assert go_live._go_live_store['123']['continuous_mode_active'] is True


def test_missing_certificate_is_blocked() -> None:
    try:
        drift.observe_certified_slo(drift.TelegramSLOObservationRequest(actor='operator', certificate_id='missing'))
    except Exception as exc:
        assert getattr(exc, 'status_code', None) == 404
    else:
        raise AssertionError('missing certificate should be blocked')


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.331/observe' in paths
    assert '/auron/demo1/v21.331/status' in paths
    assert '/auron/demo1/v21.331/observations' in paths
    assert '/auron/demo1/v21.331/drifts' in paths
    assert '/auron/demo1/v21.331/command-center' in paths
