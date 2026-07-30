from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def payload(session: str, command: str, workspace: str = 'demo-v249') -> dict:
    return {
        'session_id': session,
        'workspace_id': workspace,
        'operator_id': 'brano-v249',
        'command': command,
        'risk_brain_hard_block': False,
    }


def test_command_center_registered():
    response = client.get('/auron/demo1/v21.249/command-center')
    assert response.status_code == 200
    assert 'v21.249' in response.text
    assert '/auron/demo1/v21.249/dialogue' in response.text


def test_plan_requires_goal():
    response = client.post('/auron/demo1/v21.249/dialogue', json=payload('v249-no-goal', 'Plane unser Ziel'))
    assert response.status_code == 200
    assert response.json()['mode'] == 'goal-plan-missing-goal'
    assert response.json()['plan_active'] is False


def test_goal_builds_ordered_plan_and_sets_next_step():
    session = 'v249-plan'
    client.post('/auron/demo1/v21.249/dialogue', json=payload(session, 'Unser Ziel ist AURON produktionsreif machen'))
    client.post('/auron/demo1/v21.249/dialogue', json=payload(session, 'Wir arbeiten an Goal-aware Planning'))
    client.post('/auron/demo1/v21.249/dialogue', json=payload(session, 'Nächster Schritt ist Planner testen'))

    response = client.post('/auron/demo1/v21.249/dialogue', json=payload(session, 'Plane unser Ziel'))
    assert response.status_code == 200
    body = response.json()
    assert body['mode'] == 'goal-plan-created'
    assert body['plan_active'] is True
    assert body['plan_step_count'] >= 3
    assert body['plan_current_step']
    assert body['next_step'] == body['plan_current_step']

    plan = client.get('/auron/demo1/v21.249/plan', params={
        'session_id': session,
        'workspace_id': 'demo-v249',
        'operator_id': 'brano-v249',
    })
    assert plan.status_code == 200
    assert plan.json()['active'] is True
    assert plan.json()['count'] == body['plan_step_count']


def test_plan_step_completion_advances_progress():
    session = 'v249-progress'
    client.post('/auron/demo1/v21.249/dialogue', json=payload(session, 'Unser Ziel ist Demo abschließen'))
    created = client.post('/auron/demo1/v21.249/dialogue', json=payload(session, 'Plane unser Ziel')).json()
    first = created['plan_current_step']

    completed = client.post('/auron/demo1/v21.249/dialogue', json=payload(session, 'Planschritt erledigt'))
    assert completed.status_code == 200
    body = completed.json()
    assert body['mode'] == 'goal-plan-step-complete'
    assert body['plan_done_count'] == 1
    assert body['plan_current_step'] != first


def test_show_plan_returns_progress():
    session = 'v249-show'
    client.post('/auron/demo1/v21.249/dialogue', json=payload(session, 'Unser Ziel ist Release vorbereiten'))
    client.post('/auron/demo1/v21.249/dialogue', json=payload(session, 'Plane unser Ziel'))
    response = client.post('/auron/demo1/v21.249/dialogue', json=payload(session, 'Zeig Plan'))
    assert response.status_code == 200
    assert response.json()['mode'] == 'goal-plan-read'
    assert 'Plan:' in response.json()['reply']


def test_financial_command_remains_approval_gated():
    response = client.post('/auron/demo1/v21.249/dialogue', json=payload('v249-fin', 'buy EURUSD now'))
    assert response.status_code == 200
    assert response.json()['state'] == 'approval-required'
    assert response.json()['approval_required'] is True
