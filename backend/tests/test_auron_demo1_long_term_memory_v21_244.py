from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_command_center_clears_input_after_submit():
    response = client.get('/auron/demo1/v21.244/command-center')
    assert response.status_code == 200
    assert 'v21.244' in response.text
    assert "E('command').value=''" in response.text
    assert '/auron/demo1/v21.244/dialogue' in response.text


def test_explicit_remember_and_recall():
    remember = client.post('/auron/demo1/v21.244/dialogue', json={
        'session_id': 'ltm-a', 'workspace_id': 'demo-v244', 'operator_id': 'brano-v244',
        'command': 'Auron, merk dir mein Testcode ist ALPHA-244.', 'risk_brain_hard_block': False,
    })
    assert remember.status_code == 200
    body = remember.json()
    assert body['mode'] == 'memory-write'
    assert body['long_term_memory_count'] >= 1

    recall = client.post('/auron/demo1/v21.244/dialogue', json={
        'session_id': 'ltm-b', 'workspace_id': 'demo-v244', 'operator_id': 'brano-v244',
        'command': 'Was hast du dir gemerkt?', 'risk_brain_hard_block': False,
    })
    assert recall.status_code == 200
    assert 'ALPHA-244' in recall.json()['reply']


def test_specific_forget_removes_matching_fact():
    client.post('/auron/demo1/v21.244/dialogue', json={
        'session_id': 'forget-a', 'workspace_id': 'demo-forget-v244', 'operator_id': 'brano-v244',
        'command': 'Merk dir Lieblingsmarker BETA-244', 'risk_brain_hard_block': False,
    })
    response = client.post('/auron/demo1/v21.244/dialogue', json={
        'session_id': 'forget-b', 'workspace_id': 'demo-forget-v244', 'operator_id': 'brano-v244',
        'command': 'Vergiss BETA-244', 'risk_brain_hard_block': False,
    })
    assert response.status_code == 200
    assert response.json()['mode'] == 'memory-delete'
    assert response.json()['long_term_memory_count'] == 0


def test_bulk_forget_requires_specific_target():
    response = client.post('/auron/demo1/v21.244/dialogue', json={
        'session_id': 'forget-all', 'workspace_id': 'demo-v244', 'operator_id': 'brano-v244',
        'command': 'Vergiss alles', 'risk_brain_hard_block': False,
    })
    assert response.status_code == 200
    assert response.json()['state'] == 'confirmation-required'


def test_financial_command_stays_approval_gated():
    response = client.post('/auron/demo1/v21.244/dialogue', json={
        'session_id': 'financial-v244', 'workspace_id': 'demo', 'operator_id': 'brano',
        'command': 'buy EURUSD now', 'risk_brain_hard_block': False,
    })
    assert response.status_code == 200
    assert response.json()['state'] == 'approval-required'
    assert response.json()['approval_required'] is True
