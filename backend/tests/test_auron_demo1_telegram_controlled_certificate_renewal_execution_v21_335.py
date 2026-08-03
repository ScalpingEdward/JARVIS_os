from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.main import app
from app.api.routes import auron_demo1_telegram_certificate_renewal_governance_v21_334 as governance
from app.api.routes import auron_demo1_telegram_controlled_certificate_renewal_execution_v21_335 as execution
from app.api.routes import auron_demo1_telegram_continuous_conversation_supervisor_v21_323 as supervisor
from app.api.routes import auron_demo1_telegram_operational_go_live_acceptance_v21_322 as go_live
from app.api.routes import auron_demo1_telegram_service_certification_slo_v21_330 as certification


def setup_function() -> None:
    execution.reset_telegram_controlled_certificate_renewal_execution_store()
    governance.reset_telegram_certificate_renewal_governance_store()
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
    certification._certificate_store['current'] = certificate
    go_live._go_live_store['123'] = {
        'telegram_chat_id': '123',
        'continuous_mode_active': True,
        'go_live_state': 'certified-operational-service',
        'service_certificate_id': 'certificate-2',
    }
    supervisor._circuit_store['123'] = {'telegram_chat_id': '123', 'state': 'closed'}
    governance._renewal_policy_store['certificate-2'] = {
        'renewal_policy_id': 'policy-1',
        'certificate_id': 'certificate-2',
        'telegram_chat_id': '123',
        'minimum_reliability_score': 85.0,
        'maximum_lineage_depth': 10,
        'policy_state': 'renewal-scheduled',
        'immutable': True,
        'integrity_hash': 'policy-hash',
    }
    governance._renewal_schedule_store['certificate-2'] = {
        'renewal_schedule_id': 'schedule-1',
        'certificate_id': 'certificate-2',
        'telegram_chat_id': '123',
        'renewal_policy_id': 'policy-1',
        'schedule_state': 'scheduled-awaiting-controlled-renewal-execution',
        'immutable': True,
        'integrity_hash': 'schedule-hash',
    }


def _execute() -> dict:
    return execution.execute_certificate_renewal(
        execution.TelegramCertificateRenewalExecuteRequest(
            actor='operator',
            certificate_id='certificate-2',
            execution_phrase='EXECUTE AURON TELEGRAM CERTIFICATE RENEWAL',
        )
    )


def test_issues_immutable_successor_without_deactivating_source() -> None:
    result = _execute()
    assert result['state'] == 'telegram-certificate-renewal-successor-issued'
    assert result['successor_certificate']['immutable'] is True
    assert result['successor_certificate']['certificate_state'] == 'issued-awaiting-zero-downtime-handover'
    assert certification._certificate_store['current']['certificate_state'] == 'certified'
    assert result['source_certificate_remains_active'] is True


def test_renewal_execution_is_idempotent() -> None:
    first = _execute()
    second = _execute()
    assert second['idempotent_replay'] is True
    assert second['execution']['renewal_execution_id'] == first['execution']['renewal_execution_id']


def test_commits_zero_downtime_handover() -> None:
    started = _execute()['execution']
    result = execution.commit_certificate_handover(
        execution.TelegramCertificateHandoverCommitRequest(
            actor='operator',
            renewal_execution_id=started['renewal_execution_id'],
            commit_phrase='COMMIT AURON TELEGRAM CERTIFICATE HANDOVER',
        )
    )
    assert result['state'] == 'telegram-certificate-handover-committed'
    assert result['service_interruption_detected'] is False
    assert result['active_certificate']['certificate_state'] == 'certified'
    assert certification._certificate_store['current']['certificate_state'] == 'superseded-after-governed-renewal'
    assert go_live._go_live_store['123']['continuous_mode_active'] is True
    assert go_live._go_live_store['123']['service_certificate_id'] == result['active_certificate']['certificate_id']


def test_handover_fails_closed_and_keeps_source_active() -> None:
    started = _execute()['execution']
    supervisor._circuit_store['123']['state'] = 'open'
    try:
        execution.commit_certificate_handover(
            execution.TelegramCertificateHandoverCommitRequest(
                actor='operator',
                renewal_execution_id=started['renewal_execution_id'],
                commit_phrase='COMMIT AURON TELEGRAM CERTIFICATE HANDOVER',
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert 'safety_circuit_closed' in exc.detail['blockers']
    else:
        raise AssertionError('Expected handover to fail closed')
    assert certification._certificate_store['current']['certificate_state'] == 'certified'
    assert go_live._go_live_store['123']['continuous_mode_active'] is True


def test_execution_requires_governed_schedule() -> None:
    governance._renewal_schedule_store.clear()
    try:
        _execute()
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError('Expected missing renewal schedule to block execution')


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.335/execute' in paths
    assert '/auron/demo1/v21.335/handover/commit' in paths
    assert '/auron/demo1/v21.335/status' in paths
    assert '/auron/demo1/v21.335/executions' in paths
    assert '/auron/demo1/v21.335/handovers' in paths
    assert '/auron/demo1/v21.335/command-center' in paths
