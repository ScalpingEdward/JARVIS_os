from fastapi import HTTPException

from app.main import app
from app.api.routes import auron_demo1_telegram_continuous_conversation_supervisor_v21_323 as supervisor
from app.api.routes import auron_demo1_telegram_operational_go_live_acceptance_v21_322 as go_live


def setup_function() -> None:
    supervisor.reset_telegram_continuous_conversation_supervisor_store()
    go_live.reset_telegram_operational_go_live_acceptance_store()
    go_live._go_live_store['123'] = {
        'go_live_acceptance_id': 'go-live-1',
        'telegram_chat_id': '123',
        'continuous_mode_active': True,
        'go_live_state': 'accepted-continuous-mode-active',
        'max_messages_per_minute': 2,
        'max_concurrent_conversations': 1,
    }


def _admit(update_id: str, sequence_key: str = 'seq-1') -> dict:
    return supervisor.admit_continuous_conversation(
        supervisor.TelegramConversationAdmissionRequest(
            actor='operator', telegram_chat_id='123', update_id=update_id, sequence_key=sequence_key
        )
    )


def test_admits_and_sequences_one_conversation() -> None:
    result = _admit('update-1')
    assert result['state'] == 'telegram-continuous-conversation-admitted'
    assert result['supervision']['supervision_state'] == 'admitted-sequenced-in-progress'
    assert supervisor._active_sequence_store['123']['update_id'] == 'update-1'


def test_blocks_parallel_conversation_for_same_chat() -> None:
    _admit('update-1')
    try:
        _admit('update-2', 'seq-2')
    except HTTPException as exc:
        assert exc.status_code == 409
        assert 'chat_sequence_available' in exc.detail['blockers']
    else:
        raise AssertionError('parallel conversation should be blocked')


def test_completion_releases_chat_sequence() -> None:
    _admit('update-1')
    result = supervisor.complete_continuous_conversation(
        supervisor.TelegramConversationCompletionRequest(
            actor='operator', telegram_chat_id='123', update_id='update-1', success=True
        )
    )
    assert result['supervision']['supervision_state'] == 'completed'
    assert '123' not in supervisor._active_sequence_store
    assert _admit('update-2')['state'] == 'telegram-continuous-conversation-admitted'


def test_three_failures_open_safety_circuit_and_pause_go_live() -> None:
    for index in range(3):
        update_id = f'failed-{index}'
        _admit(update_id, f'seq-{index}')
        supervisor.complete_continuous_conversation(
            supervisor.TelegramConversationCompletionRequest(
                actor='operator', telegram_chat_id='123', update_id=update_id,
                success=False, failure_reason='provider-failure'
            )
        )
    assert supervisor._circuit_store['123']['state'] == 'open'
    assert go_live._go_live_store['123']['continuous_mode_active'] is False


def test_circuit_reset_requires_explicit_phrase() -> None:
    supervisor._circuit_store['123'] = {
        'telegram_chat_id': '123', 'state': 'open', 'consecutive_failures': 3,
        'opened_at': 'now', 'opened_reason': 'test', 'reset_at': None, 'reset_by': None,
    }
    result = supervisor.reset_safety_circuit(
        supervisor.TelegramCircuitResetRequest(
            actor='operator', telegram_chat_id='123',
            reset_phrase='RESET AURON TELEGRAM SAFETY CIRCUIT'
        )
    )
    assert result['circuit']['state'] == 'closed'
    assert result['circuit']['consecutive_failures'] == 0


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.323/admit' in paths
    assert '/auron/demo1/v21.323/circuit/reset' in paths
    assert '/auron/demo1/v21.323/command-center' in paths
