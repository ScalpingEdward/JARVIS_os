from app.main import app
from app.api.routes import auron_demo1_telegram_restoration_probation_v21_329 as probation
from app.api.routes import auron_demo1_telegram_runtime_health_remediation_v21_328 as remediation
from app.api.routes import auron_demo1_telegram_operational_analytics_health_supervisor_v21_327 as health
from app.api.routes import auron_demo1_telegram_operational_go_live_acceptance_v21_322 as go_live
from app.api.routes import auron_demo1_telegram_continuous_conversation_supervisor_v21_323 as supervisor


def setup_function() -> None:
    probation.reset_telegram_restoration_probation_store()
    remediation.reset_telegram_runtime_health_remediation_store()
    health.reset_telegram_operational_analytics_health_supervisor_store()
    go_live.reset_telegram_operational_go_live_acceptance_store()
    supervisor.reset_telegram_continuous_conversation_supervisor_store()
    go_live._go_live_store['123'] = {
        'go_live_acceptance_id': 'go-live-1',
        'telegram_chat_id': '123',
        'continuous_mode_active': True,
        'go_live_state': 'restored-after-health-remediation',
    }
    remediation._remediation_store['anomaly-1'] = {
        'remediation_id': 'remediation-1',
        'anomaly_id': 'anomaly-1',
        'telegram_chat_id': '123',
        'remediation_state': 'restored',
    }
    supervisor._circuit_store['123'] = {
        'telegram_chat_id': '123',
        'state': 'closed',
        'consecutive_failures': 0,
    }


def _start(**overrides) -> dict:
    values = {
        'actor': 'operator',
        'anomaly_id': 'anomaly-1',
        'start_phrase': 'START AURON TELEGRAM RESTORATION PROBATION',
        'observation_window_minutes': 30,
        'required_healthy_observations': 2,
        'rollback_on_degraded': False,
    }
    values.update(overrides)
    return probation.start_restoration_probation(probation.TelegramRestorationProbationStartRequest(**values))


def _snapshot(state: str, snapshot_id: str) -> None:
    health._health_snapshot_store['123'] = {
        'health_snapshot_id': snapshot_id,
        'telegram_chat_id': '123',
        'health_state': state,
    }


def test_start_probation_after_restoration() -> None:
    result = _start()
    assert result['state'] == 'telegram-restoration-probation-started'
    assert result['probation']['probation_state'] == 'active-observation-window'
    assert go_live._go_live_store['123']['go_live_state'] == 'restoration-probation-active'


def test_healthy_observations_allow_completion() -> None:
    started = _start()['probation']
    for index in range(2):
        _snapshot('healthy', f'health-{index}')
        probation.observe_restoration_probation(
            probation.TelegramRestorationProbationObserveRequest(
                actor='operator', probation_id=started['probation_id']
            )
        )
    result = probation.complete_restoration_probation(
        probation.TelegramRestorationProbationCompleteRequest(
            actor='operator',
            probation_id=started['probation_id'],
            completion_phrase='COMPLETE AURON TELEGRAM RESTORATION PROBATION',
        )
    )
    assert result['state'] == 'telegram-restoration-probation-completed'
    assert result['probation']['probation_state'] == 'completed-stable'


def test_critical_observation_rolls_back_service() -> None:
    started = _start()['probation']
    _snapshot('critical', 'health-critical')
    result = probation.observe_restoration_probation(
        probation.TelegramRestorationProbationObserveRequest(
            actor='operator', probation_id=started['probation_id']
        )
    )
    assert result['state'] == 'telegram-restoration-probation-rolled-back'
    assert go_live._go_live_store['123']['continuous_mode_active'] is False
    assert supervisor._circuit_store['123']['state'] == 'open'


def test_degraded_observation_can_trigger_configured_rollback() -> None:
    started = _start(rollback_on_degraded=True)['probation']
    _snapshot('degraded', 'health-degraded')
    result = probation.observe_restoration_probation(
        probation.TelegramRestorationProbationObserveRequest(
            actor='operator', probation_id=started['probation_id']
        )
    )
    assert result['probation']['probation_state'] == 'rolled-back'


def test_start_is_idempotent() -> None:
    first = _start()
    second = _start()
    assert second['idempotent_replay'] is True
    assert second['probation']['probation_id'] == first['probation']['probation_id']


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.329/start' in paths
    assert '/auron/demo1/v21.329/observe' in paths
    assert '/auron/demo1/v21.329/complete' in paths
    assert '/auron/demo1/v21.329/command-center' in paths
