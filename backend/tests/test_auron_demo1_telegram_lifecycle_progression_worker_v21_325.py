from fastapi import HTTPException

from app.main import app
from app.api.routes import auron_demo1_telegram_continuous_queue_orchestration_v21_324 as queue
from app.api.routes import auron_demo1_telegram_continuous_conversation_supervisor_v21_323 as supervisor
from app.api.routes import auron_demo1_telegram_lifecycle_progression_worker_v21_325 as worker
from app.api.routes import auron_demo1_telegram_operational_go_live_acceptance_v21_322 as go_live


def setup_function() -> None:
    worker.reset_telegram_lifecycle_progression_worker_store()
    queue.reset_telegram_continuous_queue_orchestration_store()
    supervisor.reset_telegram_continuous_conversation_supervisor_store()
    go_live.reset_telegram_operational_go_live_acceptance_store()
    go_live._go_live_store['123'] = {'go_live_acceptance_id':'go-1','continuous_mode_active':True}
    queue._queue_item_store['u1'] = {'queue_item_id':'q1','update_id':'u1','telegram_chat_id':'123','queue_state':'dispatched-awaiting-lifecycle-progression'}


def _start() -> dict:
    return worker.start_lifecycle_progression(worker.TelegramLifecycleProgressionStartRequest(actor='operator', queue_item_id='q1'))


def test_starts_checkpointed_progression() -> None:
    result = _start()
    assert result['progression']['current_stage'] == 'conversation-dispatch'
    assert queue._queue_item_store['u1']['queue_state'] == 'lifecycle-progression-running'


def test_advances_all_stages_and_completes_queue_item() -> None:
    progression = _start()['progression']
    for stage in worker._STAGES:
        result = worker.commit_lifecycle_checkpoint(worker.TelegramLifecycleCheckpointRequest(actor='operator', progression_id=progression['progression_id'], stage=stage, success=True, evidence_id=f'e-{stage}'))
    assert result['state'] == 'telegram-lifecycle-progression-completed'
    assert queue._queue_item_store['u1']['queue_state'] == 'completed'


def test_retryable_failure_and_recovery() -> None:
    progression = _start()['progression']
    failed = worker.commit_lifecycle_checkpoint(worker.TelegramLifecycleCheckpointRequest(actor='operator', progression_id=progression['progression_id'], stage='conversation-dispatch', success=False, failure_reason='temporary', retryable=True))
    assert failed['progression']['progression_state'] == 'recovery-required'
    recovered = worker.recover_lifecycle_stage(worker.TelegramLifecycleRecoveryRequest(actor='operator', progression_id=progression['progression_id']))
    assert recovered['retry_stage'] == 'conversation-dispatch'


def test_non_retryable_failure_goes_to_dead_letter() -> None:
    progression = _start()['progression']
    result = worker.commit_lifecycle_checkpoint(worker.TelegramLifecycleCheckpointRequest(actor='operator', progression_id=progression['progression_id'], stage='conversation-dispatch', success=False, failure_reason='invalid-contract', retryable=False))
    assert result['state'] == 'telegram-lifecycle-progression-dead-lettered'
    assert queue._queue_item_store['u1']['queue_state'] == 'failed'


def test_stage_mismatch_is_rejected() -> None:
    progression = _start()['progression']
    try:
        worker.commit_lifecycle_checkpoint(worker.TelegramLifecycleCheckpointRequest(actor='operator', progression_id=progression['progression_id'], stage='runtime-worker', success=True))
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError('stage mismatch should be rejected')


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.325/start' in paths
    assert '/auron/demo1/v21.325/checkpoint' in paths
    assert '/auron/demo1/v21.325/dead-letters' in paths
