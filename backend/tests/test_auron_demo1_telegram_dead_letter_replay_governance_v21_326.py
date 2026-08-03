from fastapi import HTTPException

from app.main import app
from app.api.routes import auron_demo1_telegram_dead_letter_replay_governance_v21_326 as replay
from app.api.routes import auron_demo1_telegram_lifecycle_progression_worker_v21_325 as progression
from app.api.routes import auron_demo1_telegram_continuous_queue_orchestration_v21_324 as queue
from app.api.routes import auron_demo1_telegram_continuous_conversation_supervisor_v21_323 as supervisor
from app.api.routes import auron_demo1_telegram_operational_go_live_acceptance_v21_322 as go_live


def setup_function() -> None:
    replay.reset_telegram_dead_letter_replay_governance_store()
    progression.reset_telegram_lifecycle_progression_worker_store()
    queue.reset_telegram_continuous_queue_orchestration_store()
    supervisor.reset_telegram_continuous_conversation_supervisor_store()
    go_live.reset_telegram_operational_go_live_acceptance_store()
    go_live._go_live_store['123'] = {'continuous_mode_active': True}
    queue._queue_item_store['u1'] = {'queue_item_id': 'q1', 'update_id': 'u1', 'telegram_chat_id': '123', 'queue_state': 'failed', 'failure_reason': 'boom'}
    progression._progression_store['q1'] = {'progression_id': 'p1', 'queue_item_id': 'q1', 'update_id': 'u1', 'telegram_chat_id': '123', 'current_stage': 'runtime-worker', 'progression_state': 'dead-lettered', 'checkpoint_history': [{'stage': 'runtime-worker'}], 'dead_letter_id': 'd1'}
    progression._dead_letter_store['p1'] = {'dead_letter_id': 'd1', 'progression_id': 'p1', 'queue_item_id': 'q1', 'update_id': 'u1', 'telegram_chat_id': '123', 'failed_stage': 'runtime-worker', 'checkpoint_history': [{'stage': 'runtime-worker'}]}


def _request(phrase: str = 'REPLAY ONE AURON DEAD LETTER'):
    return replay.TelegramDeadLetterReplayRequest(actor='operator', progression_id='p1', replay_phrase=phrase, recovery_evidence_id='evidence-1', reason='provider recovered')


def test_replay_updates_full_chain() -> None:
    result = replay.replay_dead_letter(_request())
    assert result['state'] == 'telegram-dead-letter-replay-authorized'
    assert result['replay']['immutable'] is True
    assert len(result['replay']['integrity_hash']) == 64
    assert progression._progression_store['q1']['progression_state'] == 'running-awaiting-checkpoint'
    assert queue._queue_item_store['u1']['queue_state'] == 'lifecycle-progression-running'


def test_replay_is_idempotent() -> None:
    replay.replay_dead_letter(_request())
    result = replay.replay_dead_letter(_request())
    assert result['idempotent_replay'] is True


def test_wrong_phrase_is_rejected() -> None:
    try:
        replay.replay_dead_letter(_request('wrong'))
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError('wrong replay phrase should be rejected')


def test_open_circuit_blocks_replay() -> None:
    supervisor._circuit_store['123'] = {'state': 'open'}
    try:
        replay.replay_dead_letter(_request())
    except HTTPException as exc:
        assert exc.status_code == 409
        assert 'safety_circuit_closed' in exc.detail['blockers']
    else:
        raise AssertionError('open circuit should block replay')


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.326/replay' in paths
    assert '/auron/demo1/v21.326/metrics' in paths
    assert '/auron/demo1/v21.326/command-center' in paths
