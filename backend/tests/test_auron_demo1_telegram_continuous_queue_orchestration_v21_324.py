from fastapi import HTTPException

from app.main import app
from app.api.routes import auron_demo1_telegram_continuous_conversation_supervisor_v21_323 as supervisor
from app.api.routes import auron_demo1_telegram_continuous_queue_orchestration_v21_324 as queue
from app.api.routes import auron_demo1_telegram_operational_go_live_acceptance_v21_322 as go_live


def setup_function() -> None:
    queue.reset_telegram_continuous_queue_orchestration_store()
    supervisor.reset_telegram_continuous_conversation_supervisor_store()
    go_live.reset_telegram_operational_go_live_acceptance_store()
    go_live._go_live_store['123'] = {
        'go_live_acceptance_id': 'go-live-1',
        'telegram_chat_id': '123',
        'continuous_mode_active': True,
        'go_live_state': 'accepted-continuous-mode-active',
        'max_messages_per_minute': 10,
        'max_concurrent_conversations': 1,
    }
    supervisor._supervision_store['update-1'] = {
        'supervision_id': 'supervision-1',
        'update_id': 'update-1',
        'telegram_chat_id': '123',
        'supervision_state': 'admitted-sequenced-in-progress',
    }


def _enqueue(update_id: str = 'update-1', priority: int = 100) -> dict:
    return queue.enqueue_continuous_conversation(
        queue.TelegramContinuousQueueEnqueueRequest(
            actor='operator', telegram_chat_id='123', update_id=update_id, priority=priority
        )
    )


def test_enqueues_admitted_supervision() -> None:
    result = _enqueue()
    assert result['state'] == 'telegram-continuous-conversation-queued'
    assert result['queue_item']['queue_state'] == 'queued-awaiting-supervised-dispatch'


def test_enqueue_is_idempotent() -> None:
    first = _enqueue()
    second = _enqueue()
    assert second['idempotent_replay'] is True
    assert second['queue_item']['queue_item_id'] == first['queue_item']['queue_item_id']


def test_dispatches_highest_priority_pending_item() -> None:
    supervisor._supervision_store['update-2'] = {
        'supervision_id': 'supervision-2', 'update_id': 'update-2',
        'telegram_chat_id': '123', 'supervision_state': 'admitted-sequenced-in-progress'
    }
    _enqueue('update-1', 200)
    _enqueue('update-2', 10)
    result = queue.dispatch_next_continuous_conversation(
        queue.TelegramContinuousQueueDispatchRequest(actor='operator', telegram_chat_id='123')
    )
    assert result['queue_item']['update_id'] == 'update-2'
    assert result['queue_item']['queue_state'] == 'dispatched-awaiting-lifecycle-progression'


def test_dispatch_blocks_when_chat_sequence_busy() -> None:
    _enqueue()
    supervisor._active_sequence_store['123'] = {'update_id': 'busy'}
    try:
        queue.dispatch_next_continuous_conversation(
            queue.TelegramContinuousQueueDispatchRequest(actor='operator', telegram_chat_id='123')
        )
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError('busy per-chat sequence should block dispatch')


def test_complete_dispatched_queue_item() -> None:
    _enqueue()
    dispatched = queue.dispatch_next_continuous_conversation(
        queue.TelegramContinuousQueueDispatchRequest(actor='operator', telegram_chat_id='123')
    )
    result = queue.complete_queue_item(
        queue.TelegramContinuousQueueCompleteRequest(
            actor='operator', queue_item_id=dispatched['queue_item']['queue_item_id'], success=True
        )
    )
    assert result['queue_item']['queue_state'] == 'completed'


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.324/enqueue' in paths
    assert '/auron/demo1/v21.324/dispatch-next' in paths
    assert '/auron/demo1/v21.324/command-center' in paths
