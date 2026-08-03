from fastapi import HTTPException

from app.main import app
from app.api.routes import auron_demo1_telegram_runtime_health_remediation_v21_328 as remediation
from app.api.routes import auron_demo1_telegram_operational_analytics_health_supervisor_v21_327 as health
from app.api.routes import auron_demo1_telegram_operational_go_live_acceptance_v21_322 as go_live
from app.api.routes import auron_demo1_telegram_continuous_conversation_supervisor_v21_323 as supervisor


def setup_function() -> None:
    remediation.reset_telegram_runtime_health_remediation_store()
    health.reset_telegram_operational_analytics_health_supervisor_store()
    go_live.reset_telegram_operational_go_live_acceptance_store()
    supervisor.reset_telegram_continuous_conversation_supervisor_store()
    go_live._go_live_store['123'] = {
        'go_live_acceptance_id': 'go-live-1',
        'telegram_chat_id': '123',
        'continuous_mode_active': False,
        'go_live_state': 'paused-by-runtime-health-supervisor',
    }
    health._health_snapshot_store['123'] = {
        'health_snapshot_id': 'snapshot-1',
        'telegram_chat_id': '123',
        'health_state': 'healthy',
    }
    health._anomaly_store['anomaly-1'] = {
        'anomaly_id': 'anomaly-1',
        'health_snapshot_id': 'snapshot-critical',
        'telegram_chat_id': '123',
        'severity': 'critical',
        'blockers': ['dead_letters_within_limit'],
    }
    supervisor._circuit_store['123'] = {'telegram_chat_id': '123', 'state': 'open'}


def _ack() -> dict:
    return remediation.acknowledge_runtime_anomaly(
        remediation.TelegramRuntimeAnomalyAcknowledgeRequest(
            actor='operator',
            anomaly_id='anomaly-1',
            acknowledgement_phrase='ACKNOWLEDGE AURON TELEGRAM RUNTIME ANOMALY',
            remediation_plan='Verify health, clear blockers and restore under operator control.',
        )
    )


def test_acknowledges_runtime_anomaly() -> None:
    result = _ack()
    assert result['state'] == 'telegram-runtime-anomaly-acknowledged'
    assert result['remediation']['remediation_state'] == 'acknowledged-awaiting-health-restoration'


def test_acknowledgement_is_idempotent() -> None:
    first = _ack()
    second = _ack()
    assert second['idempotent_replay'] is True
    assert second['remediation']['remediation_id'] == first['remediation']['remediation_id']


def test_restores_service_after_clean_health_evidence() -> None:
    _ack()
    result = remediation.restore_runtime_service(
        remediation.TelegramRuntimeServiceRestoreRequest(
            actor='operator',
            anomaly_id='anomaly-1',
            restore_phrase='RESTORE AURON TELEGRAM CONTINUOUS SERVICE',
            evidence_id='evidence-clean-1',
        )
    )
    assert result['state'] == 'telegram-runtime-service-restored'
    assert go_live._go_live_store['123']['continuous_mode_active'] is True
    assert supervisor._circuit_store['123']['state'] == 'closed'


def test_restore_requires_acknowledgement() -> None:
    try:
        remediation.restore_runtime_service(
            remediation.TelegramRuntimeServiceRestoreRequest(
                actor='operator', anomaly_id='anomaly-1',
                restore_phrase='RESTORE AURON TELEGRAM CONTINUOUS SERVICE',
                evidence_id='evidence-clean-1',
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError('restoration should require acknowledgement')


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.328/acknowledge' in paths
    assert '/auron/demo1/v21.328/restore' in paths
    assert '/auron/demo1/v21.328/status' in paths
    assert '/auron/demo1/v21.328/command-center' in paths
