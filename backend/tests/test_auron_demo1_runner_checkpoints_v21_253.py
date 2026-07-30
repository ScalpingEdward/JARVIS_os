from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def payload(session: str, command: str, workspace: str = 'demo-v253', hard_block: bool = False) -> dict:
    return {
        'session_id': session,
        'workspace_id': workspace,
        'operator_id': 'brano-v253',
        'command': command,
        'risk_brain_hard_block': hard_block,
    }


def post(session: str, command: str, hard_block: bool = False):
    return client.post('/auron/demo1/v21.253/dialogue', json=payload(session, command, hard_block=hard_block))


def prepare_queue(session: str):
    assert post(session, 'Unser Ziel ist Systemstatus prüfen').status_code == 200
    assert post(session, 'Nächster Schritt ist system status prüfen').status_code == 200
    assert post(session, 'Plane unser Ziel').status_code == 200
    response = post(session, 'Baue Execution Queue')
    assert response.status_code == 200
    assert response.json()['queue_count'] >= 1


def test_command_center_registered():
    response = client.get('/auron/demo1/v21.253/command-center')
    assert response.status_code == 200
    assert 'v21.253' in response.text
    assert '/auron/demo1/v21.253/dialogue' in response.text
    assert 'CHECKPOINTED QUEUE RUNNER COMMAND CENTER' in response.text


def test_pause_persists_and_blocks_runner_start():
    session = 'checkpoint-v253-pause'
    prepare_queue(session)
    paused = post(session, 'Pausiere Queue Runner')
    assert paused.status_code == 200
    body = paused.json()
    assert body['mode'] == 'queue-runner-paused'
    assert body['runner_paused'] is True
    assert body['runner_checkpoint'] is not None

    run = post(session, 'Starte sicheren Queue Run')
    assert run.status_code == 200
    assert run.json()['mode'] == 'queue-runner-paused'
    assert run.json()['runner_stop_reason'] == 'paused'


def test_resume_continues_from_persistent_queue_checkpoint():
    session = 'checkpoint-v253-resume'
    prepare_queue(session)
    post(session, 'Pausiere Queue Runner')
    resumed = post(session, 'Queue Runner fortsetzen')
    assert resumed.status_code == 200
    body = resumed.json()
    assert body['runner_paused'] is False
    assert body['runner_checkpoint'] is not None
    assert body['runner_checkpoint']['completed'] >= 1


def test_checkpoint_endpoint_reports_saved_position():
    session = 'checkpoint-v253-read'
    prepare_queue(session)
    post(session, 'Pausiere Queue Runner')
    response = client.get(
        '/auron/demo1/v21.253/runner-checkpoint',
        params={'session_id': session, 'workspace_id': 'demo-v253', 'operator_id': 'brano-v253'},
    )
    assert response.status_code == 200
    body = response.json()
    assert body['runner_paused'] is True
    assert body['runner_checkpoint'] is not None
    assert body['runner_checkpoint']['stop_reason'] == 'operator-pause'


def test_risk_brain_block_survives_resume():
    session = 'checkpoint-v253-risk'
    prepare_queue(session)
    post(session, 'Pausiere Queue Runner')
    resumed = post(session, 'Queue Runner fortsetzen', hard_block=True)
    assert resumed.status_code == 200
    body = resumed.json()
    assert body['runner_paused'] is False
    assert body['runner_executed_count'] == 0
    assert body['runner_stop_reason'] == 'blocked'
