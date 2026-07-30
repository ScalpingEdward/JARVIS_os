from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def payload(session: str, command: str, risk: bool = False) -> dict:
    return {
        'session_id': session,
        'workspace_id': 'demo-v252',
        'operator_id': 'brano-v252',
        'command': command,
        'risk_brain_hard_block': risk,
    }


def post(session: str, command: str, risk: bool = False):
    return client.post('/auron/demo1/v21.252/dialogue', json=payload(session, command, risk))


def prepare(session: str, next_step: str, risk: bool = False):
    assert post(session, 'Unser Ziel ist AURON sicher fertigstellen', risk).status_code == 200
    assert post(session, f'Nächster Schritt ist {next_step}', risk).status_code == 200
    assert post(session, 'Plane unser Ziel', risk).status_code == 200
    built = post(session, 'Baue Execution Queue', risk)
    assert built.status_code == 200
    return built.json()


def test_command_center_registered():
    response = client.get('/auron/demo1/v21.252/command-center')
    assert response.status_code == 200
    assert 'v21.252' in response.text
    assert '/auron/demo1/v21.252/dialogue' in response.text


def test_empty_runner_stops_without_execution():
    response = post('runner-v252-empty', 'Starte sicheren Queue Run')
    assert response.status_code == 200
    body = response.json()
    assert body['mode'] == 'queue-runner-empty'
    assert body['runner_stop_reason'] == 'empty'


def test_safe_runner_executes_low_risk_then_stops_on_manual_step():
    session = 'runner-v252-safe'
    prepare(session, 'check system readiness')
    response = post(session, 'Starte sicheren Queue Run')
    assert response.status_code == 200
    body = response.json()
    assert body['runner_executed_count'] >= 1
    assert body['runner_executed'][0]['execution_state'] == 'completed'
    assert body['queue_completed_count'] >= 1
    assert body['runner_stop_reason'] in {'conversation/manual', 'queue-complete', 'batch-limit'}


def test_runner_stops_before_financial_approval_step():
    session = 'runner-v252-financial'
    prepare(session, 'buy EURUSD now')
    response = post(session, 'Starte sicheren Queue Run')
    assert response.status_code == 200
    body = response.json()
    assert body['runner_executed_count'] == 0
    assert body['runner_stop_reason'] == 'approval-required'
    assert body['approval_required'] is True


def test_risk_brain_block_prevents_batch_execution():
    session = 'runner-v252-blocked'
    prepare(session, 'check system readiness', risk=True)
    response = post(session, 'Starte sicheren Queue Run', risk=True)
    assert response.status_code == 200
    body = response.json()
    assert body['runner_executed_count'] == 0
    assert body['runner_stop_reason'] == 'blocked'
