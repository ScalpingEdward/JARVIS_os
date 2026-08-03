from fastapi import HTTPException

from app.api.routes.auron_demo1_telegram_mobile_conversation_bridge_v21_290 import _binding_store
from app.api.routes.auron_demo1_telegram_phone_validation_reconciliation_v21_321 import _reconciliation_store
from app.api.routes.auron_demo1_telegram_production_activation_gate_v21_303 import _activation_store
from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import (
    TelegramContinuousModePauseRequest,
    TelegramOperationalGoLiveRequest,
    accept_operational_go_live,
    pause_continuous_mode,
    reset_telegram_operational_go_live_acceptance_store,
    router,
)


def setup_function() -> None:
    reset_telegram_operational_go_live_acceptance_store()
    _binding_store.clear()
    _reconciliation_store.clear()
    _activation_store.clear()


def _seed() -> None:
    _binding_store['12345'] = {
        'binding_id': 'binding-1',
        'telegram_chat_id': '12345',
        'telegram_user_id': '77',
        'operator_id': 'operator-1',
        'workspace_id': 'workspace-1',
        'active': True,
    }
    _reconciliation_store['validation-1'] = {
        'reconciliation_id': 'reconciliation-1',
        'validation_run_id': 'validation-1',
        'telegram_chat_id': '12345',
        'operator_id': 'operator-1',
        'workspace_id': 'workspace-1',
        'validation_passed': True,
        'reconciliation_state': 'passed',
        'integrity_hash': 'a' * 64,
        'immutable': True,
    }
    _activation_store['activation-key'] = {
        'activation_id': 'activation-1',
        'active': True,
        'production_transport_authorized': True,
    }


def _request() -> TelegramOperationalGoLiveRequest:
    return TelegramOperationalGoLiveRequest(
        actor='operator-1',
        validation_run_id='validation-1',
        telegram_chat_id='12345',
        acceptance_phrase='ACCEPT AURON TELEGRAM OPERATIONAL GO LIVE',
        max_messages_per_minute=10,
        max_concurrent_conversations=1,
        enable_continuous_mode=True,
    )


def test_accepts_validated_go_live_and_is_idempotent() -> None:
    _seed()
    result = accept_operational_go_live(_request())
    assert result['state'] == 'telegram-operational-go-live-accepted'
    assert result['acceptance']['continuous_mode_active'] is True
    assert result['acceptance']['external_calls_made'] == 0

    replay = accept_operational_go_live(_request())
    assert replay['idempotent_replay'] is True


def test_blocks_without_passed_validation() -> None:
    _seed()
    _reconciliation_store['validation-1']['validation_passed'] = False
    try:
        accept_operational_go_live(_request())
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError('Expected HTTPException')


def test_pause_requires_phrase_and_stops_mode() -> None:
    _seed()
    accept_operational_go_live(_request())
    result = pause_continuous_mode(TelegramContinuousModePauseRequest(
        actor='operator-1',
        telegram_chat_id='12345',
        pause_phrase='PAUSE AURON TELEGRAM CONTINUOUS MODE',
        reason='manual safety stop',
    ))
    assert result['state'] == 'telegram-continuous-mode-paused'
    assert result['acceptance']['continuous_mode_active'] is False


def test_router_contains_go_live_routes() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.322/accept' in paths
    assert '/auron/demo1/v21.322/pause' in paths
    assert '/auron/demo1/v21.322/command-center' in paths
