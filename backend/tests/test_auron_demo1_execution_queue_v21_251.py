from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def payload(session: str, command: str, workspace: str = 'demo-v251') -> dict:
    return {
        'session_id': session,
        'workspace_id': workspace,
        'operator_id': 'brano-v251',
        'command': command,
        'risk_brain_hard_block': False,
    }


def seed_plan(session: str) -> None:
    client.post('/auron/demo1/v21.251/dialogue', json=payload(session, 'Unser Ziel ist AURON stabil testen'))
    client.post('/auron/demo1/v21.251/dialogue', json=payload(session, 'Wir arbeiten an System status prüfen'))
    client.post('/auron/demo1/v21.251/dialogue', json=payload(session, 'Nächster Schritt ist TradingView status prüfen'))
    created = client.post('/auron/demo1/v21.251/dialogue', json=payload(session, 'Plane unser Ziel'))
    assert created.status_code == 200
    assert created.json()['plan_active'] is True


def test_command_center_registered():
    response = client.get('/auron/demo1/v21.251/command-center')
    assert response.status_code == 200
    assert 'v21.251' in response.text
    assert '/auron/demo1/v21.251/dialogue' in response.text


def test_builds_ordered_dependency_queue():
    session = 'queue-v251-a'
    seed_plan(session)
    response = client.post('/auron/demo1/v21.251/dialogue', json=payload(session, 'Baue Execution Queue'))
    assert response.status_code == 200
    body = response.json()
    assert body['mode'] == 'execution-queue-built'
    assert body['queue_count'] >= 2
    assert body['execution_queue'][0]['depends_on'] is None
    assert body['execution_queue'][1]['depends_on'] == 1
    assert body['queue_ready_item']['index'] == 1


def test_dependency_unlocks_after_completion():
    session = 'queue-v251-b'
    seed_plan(session)
    client.post('/auron/demo1/v21.251/dialogue', json=payload(session, 'Baue Execution Queue'))
    completed = client.post('/auron/demo1/v21.251/dialogue', json=payload(session, 'Queue Schritt erledigt'))
    assert completed.status_code == 200
    body = completed.json()
    assert body['queue_completed_count'] == 1
    assert body['queue_ready_item'] is not None
    assert body['queue_ready_item']['index'] == 2


def test_queue_does_not_execute_financial_work():
    session = 'queue-v251-fin'
    client.post('/auron/demo1/v21.251/dialogue', json=payload(session, 'Unser Ziel ist Trading kontrollieren'))
    client.post('/auron/demo1/v21.251/dialogue', json=payload(session, 'Nächster Schritt ist buy EURUSD now'))
    client.post('/auron/demo1/v21.251/dialogue', json=payload(session, 'Plane unser Ziel'))
    built = client.post('/auron/demo1/v21.251/dialogue', json=payload(session, 'Baue Execution Queue'))
    assert built.status_code == 200
    queue = built.json()['execution_queue']
    assert queue
    # Queueing is scheduling metadata only; it never reports tool execution.
    assert all(item['status'] == 'queued' for item in queue)
