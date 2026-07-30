from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def payload(session: str, command: str) -> dict:
    return {
        'session_id': session,
        'workspace_id': 'demo-v248',
        'operator_id': 'brano-v248',
        'command': command,
        'risk_brain_hard_block': False,
    }


def test_command_center_registered():
    response = client.get('/auron/demo1/v21.248/command-center')
    assert response.status_code == 200
    assert 'v21.248' in response.text
    assert '/auron/demo1/v21.248/dialogue' in response.text


def test_sets_and_reads_goal_task_and_next_step():
    session = 'state-v248-a'
    goal = client.post('/auron/demo1/v21.248/dialogue', json=payload(session, 'Unser Ziel ist AURON stabil produktionsreif machen.'))
    assert goal.status_code == 200
    assert goal.json()['goal'] == 'AURON stabil produktionsreif machen'

    task = client.post('/auron/demo1/v21.248/dialogue', json=payload(session, 'Wir arbeiten an Conversation State.'))
    assert task.status_code == 200
    assert task.json()['current_task'] == 'Conversation State'

    nxt = client.post('/auron/demo1/v21.248/dialogue', json=payload(session, 'Nächster Schritt ist Goal-aware planning.'))
    assert nxt.status_code == 200
    assert nxt.json()['next_step'] == 'Goal-aware planning'

    state = client.get('/auron/demo1/v21.248/state', params={
        'session_id': session, 'workspace_id': 'demo-v248', 'operator_id': 'brano-v248'
    })
    assert state.status_code == 200
    body = state.json()
    assert body['active'] is True
    assert body['goal'] == 'AURON stabil produktionsreif machen'
    assert body['task'] == 'Conversation State'
    assert body['next_step'] == 'Goal-aware planning'


def test_natural_state_questions_use_active_state():
    session = 'state-v248-b'
    client.post('/auron/demo1/v21.248/dialogue', json=payload(session, 'Wir arbeiten an Smart Memory.'))
    response = client.post('/auron/demo1/v21.248/dialogue', json=payload(session, 'Woran arbeiten wir?'))
    assert response.status_code == 200
    assert 'Smart Memory' in response.json()['reply']


def test_state_clear_only_clears_requested_kind():
    session = 'state-v248-c'
    client.post('/auron/demo1/v21.248/dialogue', json=payload(session, 'Unser Ziel ist Demo fertigstellen.'))
    client.post('/auron/demo1/v21.248/dialogue', json=payload(session, 'Wir arbeiten an UI Tests.'))
    cleared = client.post('/auron/demo1/v21.248/dialogue', json=payload(session, 'Aufgabe erledigt'))
    assert cleared.status_code == 200
    assert cleared.json()['current_task'] is None
    assert cleared.json()['goal'] == 'Demo fertigstellen'


def test_financial_command_stays_approval_gated():
    response = client.post('/auron/demo1/v21.248/dialogue', json=payload('state-v248-fin', 'buy EURUSD now'))
    assert response.status_code == 200
    assert response.json()['state'] == 'approval-required'
    assert response.json()['approval_required'] is True
