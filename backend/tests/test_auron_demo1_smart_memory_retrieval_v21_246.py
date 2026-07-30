from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _post(command: str, workspace: str = 'demo-v246', operator: str = 'brano-v246'):
    return client.post('/auron/demo1/v21.246/dialogue', json={
        'session_id': 'v246-session', 'workspace_id': workspace, 'operator_id': operator,
        'command': command, 'risk_brain_hard_block': False,
    })


def test_v21_246_command_center_registered():
    response = client.get('/auron/demo1/v21.246/command-center')
    assert response.status_code == 200
    assert 'v21.246' in response.text
    assert '/auron/demo1/v21.246/dialogue' in response.text
    assert 'SMART MEMORY COMMAND CENTER' in response.text


def test_retrieval_prefers_relevant_fact():
    _post('Merk dir mein bevorzugter Markt ist XAUUSD.')
    _post('Merk dir mein Lieblingsessen ist Thai Curry.')
    result = client.get('/auron/demo1/v21.246/memory-retrieval', params={
        'q': 'Welchen Markt bevorzuge ich?', 'workspace_id': 'demo-v246', 'operator_id': 'brano-v246'
    })
    assert result.status_code == 200
    items = result.json()['items']
    assert items
    assert 'XAUUSD' in items[0]['content']


def test_dialogue_reports_retrieved_memory_count():
    response = _post('Welchen Markt bevorzuge ich?')
    assert response.status_code == 200
    body = response.json()
    assert body['smart_memory_retrieval'] is True
    assert body['retrieved_fact_count'] >= 1


def test_memory_commands_still_work():
    response = _post('Merk dir mein Testwort ist GAMMA246.', workspace='memory-v246', operator='memory-v246')
    assert response.status_code == 200
    assert response.json()['mode'] == 'memory-write'
    assert response.json()['smart_memory_retrieval'] is True


def test_financial_command_stays_approval_gated():
    response = _post('buy EURUSD now')
    assert response.status_code == 200
    assert response.json()['state'] == 'approval-required'
    assert response.json()['approval_required'] is True
