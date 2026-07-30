from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_v21_245_command_center_is_registered_and_keeps_input_clear_behavior():
    response = client.get('/auron/demo1/v21.245/command-center')
    assert response.status_code == 200
    assert 'v21.245' in response.text
    assert 'CONTEXTUAL MEMORY COMMAND CENTER' in response.text
    assert "E('command').value=''" in response.text
    assert '/auron/demo1/v21.245/dialogue' in response.text


def test_explicit_memory_is_available_to_normal_dialogue_context():
    workspace = 'demo-v245-context'
    operator = 'brano-v245-context'
    remember = client.post('/auron/demo1/v21.245/dialogue', json={
        'session_id': 'v245-memory-write',
        'workspace_id': workspace,
        'operator_id': operator,
        'command': 'Auron, merk dir mein bevorzugter Markt ist XAUUSD.',
        'risk_brain_hard_block': False,
    })
    assert remember.status_code == 200
    assert remember.json()['mode'] == 'memory-write'

    response = client.post('/auron/demo1/v21.245/dialogue', json={
        'session_id': 'v245-normal-dialogue',
        'workspace_id': workspace,
        'operator_id': operator,
        'command': 'Welchen Markt bevorzuge ich?',
        'risk_brain_hard_block': False,
    })
    assert response.status_code == 200
    body = response.json()
    assert body['mode'] == 'conversation'
    assert body['contextual_memory_active'] is True
    assert body['contextual_facts_used'] >= 1
    assert body['long_term_memory_count'] >= 1
    assert 'XAUUSD' in body['reply']


def test_memory_context_endpoint_exposes_operator_scoped_facts():
    workspace = 'demo-v245-endpoint'
    operator = 'brano-v245-endpoint'
    client.post('/auron/demo1/v21.245/dialogue', json={
        'session_id': 'v245-context-write',
        'workspace_id': workspace,
        'operator_id': operator,
        'command': 'Merk dir Dashboard Layout Gamma.',
        'risk_brain_hard_block': False,
    })
    response = client.get('/auron/demo1/v21.245/memory-context', params={
        'workspace_id': workspace,
        'operator_id': operator,
    })
    assert response.status_code == 200
    body = response.json()
    assert body['active'] is True
    assert body['long_term_memory_count'] >= 1
    assert any('Gamma' in fact for fact in body['facts_available_for_context'])


def test_financial_execution_remains_approval_gated_with_contextual_memory():
    response = client.post('/auron/demo1/v21.245/dialogue', json={
        'session_id': 'v245-financial',
        'workspace_id': 'demo',
        'operator_id': 'brano',
        'command': 'buy EURUSD now',
        'risk_brain_hard_block': False,
    })
    assert response.status_code == 200
    body = response.json()
    assert body['state'] == 'approval-required'
    assert body['approval_required'] is True
    assert body['contextual_memory_active'] is True
