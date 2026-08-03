from app.main import app
from app.api.routes import auron_demo1_telegram_continuous_conversation_supervisor_v21_323 as supervisor
from app.api.routes import auron_demo1_telegram_continuous_queue_orchestration_v21_324 as queue
from app.api.routes import auron_demo1_telegram_lifecycle_progression_worker_v21_325 as progression
from app.api.routes import auron_demo1_telegram_operational_analytics_health_supervisor_v21_327 as health
from app.api.routes import auron_demo1_telegram_operational_go_live_acceptance_v21_322 as go_live
from app.api.routes import auron_demo1_telegram_operational_runtime_worker_v21_311 as runtime_worker


def setup_function() -> None:
    health.reset_telegram_operational_analytics_health_supervisor_store()
    go_live.reset_telegram_operational_go_live_acceptance_store()
    supervisor.reset_telegram_continuous_conversation_supervisor_store()
    queue.reset_telegram_continuous_queue_orchestration_store()
    progression.reset_telegram_lifecycle_progression_worker_store()
    runtime_worker.reset_telegram_operational_runtime_worker_store()
    go_live._go_live_store['123'] = {
        'go_live_acceptance_id': 'go-live-1',
        'telegram_chat_id': '123',
        'continuous_mode_active': True,
        'go_live_state': 'accepted-continuous-mode-active',
    }


def _evaluate(**overrides) -> dict:
    values = {
        'actor': 'operator',
        'telegram_chat_id': '123',
        'max_failed_worker_calls': 3,
        'max_dead_letters': 2,
        'max_queue_backlog': 20,
        'max_active_sequences': 1,
        'auto_pause_on_critical': True,
    }
    values.update(overrides)
    return health.evaluate_runtime_health(health.TelegramRuntimeHealthEvaluationRequest(**values))


def test_healthy_runtime_snapshot() -> None:
    result = _evaluate()
    assert result['state'] == 'telegram-runtime-health-healthy'
    assert result['snapshot']['health_state'] == 'healthy'
    assert result['anomaly'] is None
    assert go_live._go_live_store['123']['continuous_mode_active'] is True


def test_critical_dead_letter_anomaly_auto_pauses_chat() -> None:
    progression._dead_letter_store['progression-1'] = {
        'progression_id': 'progression-1',
        'telegram_chat_id': '123',
        'dead_letter_id': 'dead-1',
    }
    result = _evaluate(max_dead_letters=0)
    assert result['state'] == 'telegram-runtime-health-critical'
    assert result['anomaly']['auto_pause_applied'] is True
    assert go_live._go_live_store['123']['continuous_mode_active'] is False
    assert supervisor._circuit_store['123']['state'] == 'open'


def test_degraded_queue_backlog_does_not_auto_pause() -> None:
    for index in range(2):
        queue._queue_item_store[f'update-{index}'] = {
            'queue_item_id': f'queue-{index}',
            'update_id': f'update-{index}',
            'telegram_chat_id': '123',
            'queue_state': 'queued-awaiting-supervised-dispatch',
        }
    result = _evaluate(max_queue_backlog=1)
    assert result['state'] == 'telegram-runtime-health-degraded'
    assert result['anomaly']['severity'] == 'degraded'
    assert go_live._go_live_store['123']['continuous_mode_active'] is True


def test_operational_analytics_contains_chat_metrics() -> None:
    analytics = health.operational_analytics()
    assert analytics['chat_count'] == 1
    assert analytics['items'][0]['telegram_chat_id'] == '123'


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.327/evaluate' in paths
    assert '/auron/demo1/v21.327/analytics' in paths
    assert '/auron/demo1/v21.327/anomalies' in paths
    assert '/auron/demo1/v21.327/command-center' in paths
