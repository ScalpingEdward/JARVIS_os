from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_v21_243_command_center_uses_stable_browser_session():
    response = client.get('/auron/demo1/v21.243/command-center')
    assert response.status_code == 200
    assert 'v21.243' in response.text
    assert "localStorage.getItem('auron-session-id')" in response.text
    assert '/auron/demo1/v21.243/dialogue' in response.text


def test_dialogue_persists_conversation_turns():
    session_id = 'test-v21-243-persistent-context'
    first = client.post('/auron/demo1/v21.243/dialogue', json={
        'session_id': session_id,
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'command': 'Auron, Master Brano ist hier.',
        'risk_brain_hard_block': False,
    })
    assert first.status_code == 200
    assert first.json()['memory_persisted'] is True

    second = client.post('/auron/demo1/v21.243/dialogue', json={
        'session_id': session_id,
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'command': 'Was habe ich gerade gesagt?',
        'risk_brain_hard_block': False,
    })
    assert second.status_code == 200
    assert second.json()['context_turns'] >= 3

    context = client.get('/auron/demo1/v21.243/context', params={
        'session_id': session_id,
        'workspace_id': 'demo',
        'operator_id': 'brano',
    })
    assert context.status_code == 200
    body = context.json()
    assert body['persistent'] is True
    assert body['count'] >= 4
    assert any(turn['content'] == 'Auron, Master Brano ist hier.' for turn in body['turns'])
    assert any(turn['content'] == 'Was habe ich gerade gesagt?' for turn in body['turns'])


def test_capability_execution_is_also_written_to_context():
    session_id = 'test-v21-243-capability-context'
    response = client.post('/auron/demo1/v21.243/dialogue', json={
        'session_id': session_id,
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'command': 'Auron, check system readiness.',
        'risk_brain_hard_block': False,
    })
    assert response.status_code == 200
    body = response.json()
    assert body['mode'] == 'capability'
    assert body['memory_persisted'] is True
    assert body['context_turns'] >= 2


def test_financial_execution_remains_approval_gated_with_memory():
    response = client.post('/auron/demo1/v21.243/dialogue', json={
        'session_id': 'test-v21-243-financial',
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'command': 'buy EURUSD now',
        'risk_brain_hard_block': False,
    })
    assert response.status_code == 200
    body = response.json()
    assert body['state'] == 'approval-required'
    assert body['approval_required'] is True
    assert body['memory_persisted'] is True
