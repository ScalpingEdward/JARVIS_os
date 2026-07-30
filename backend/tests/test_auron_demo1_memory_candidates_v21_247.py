from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def payload(session: str, command: str, workspace: str = 'demo-v247') -> dict:
    return {
        'session_id': session,
        'workspace_id': workspace,
        'operator_id': 'brano-v247',
        'command': command,
        'risk_brain_hard_block': False,
    }


def test_command_center_registered():
    response = client.get('/auron/demo1/v21.247/command-center')
    assert response.status_code == 200
    assert 'v21.247' in response.text
    assert '/auron/demo1/v21.247/dialogue' in response.text


def test_preference_creates_candidate_not_long_term_memory():
    session = 'candidate-v247-a'
    response = client.post('/auron/demo1/v21.247/dialogue', json=payload(session, 'Ich bevorzuge XAUUSD für mein Trading.'))
    assert response.status_code == 200
    body = response.json()
    assert body['memory_candidate_pending'] is True
    assert 'Soll ich mir das merken?' in body['reply']

    pending = client.get('/auron/demo1/v21.247/memory-candidate', params={'session_id': session, 'workspace_id': 'demo-v247', 'operator_id': 'brano-v247'})
    assert pending.status_code == 200
    assert pending.json()['pending'] is True
    assert 'XAUUSD' in pending.json()['candidate']


def test_confirmation_promotes_candidate_to_long_term_memory():
    session = 'candidate-v247-b'
    client.post('/auron/demo1/v21.247/dialogue', json=payload(session, 'Mein Ziel ist ein ruhiger, systematischer Trading-Prozess.'))
    confirm = client.post('/auron/demo1/v21.247/dialogue', json=payload(session, 'Ja merk dir das'))
    assert confirm.status_code == 200
    body = confirm.json()
    assert body['mode'] == 'memory-candidate-confirmed'
    assert body['memory_candidate_pending'] is False
    assert body['long_term_memory_count'] >= 1


def test_rejection_discards_candidate():
    session = 'candidate-v247-c'
    client.post('/auron/demo1/v21.247/dialogue', json=payload(session, 'Ich mag Charts mit wenig visueller Ablenkung.'))
    reject = client.post('/auron/demo1/v21.247/dialogue', json=payload(session, 'Nein'))
    assert reject.status_code == 200
    assert reject.json()['mode'] == 'memory-candidate-rejected'
    assert reject.json()['memory_candidate_pending'] is False


def test_financial_command_remains_approval_gated():
    response = client.post('/auron/demo1/v21.247/dialogue', json=payload('candidate-v247-fin', 'buy EURUSD now'))
    assert response.status_code == 200
    assert response.json()['state'] == 'approval-required'
    assert response.json()['approval_required'] is True
