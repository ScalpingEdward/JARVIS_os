from fastapi.testclient import TestClient

from app.main import app
from app.schemas.phoenix_demo1_release_candidate_v21_235 import ReleaseCandidateRequest
from app.services.phoenix_demo1_release_candidate_v21_235 import build_release_candidate


def test_release_candidate_is_launch_ready_when_all_gates_pass():
    result = build_release_candidate(ReleaseCandidateRequest(workspace_id='ws-demo', operator_id='operator-demo'))
    assert result.state == 'launch-ready'
    assert result.demo1_launch_ready is True
    assert result.release_packaging_ready is True
    assert result.operator_acceptance_ready is True
    assert result.failed == 0
    assert result.autonomous_high_risk_execution_enabled is False
    assert result.release_candidate == 'PHOENIX-DEMO1-RC1'


def test_release_candidate_manifest_contains_full_launch_chain():
    result = build_release_candidate(ReleaseCandidateRequest())
    assert result.launch_manifest['runtime_readiness'] == '/phoenix/demo1/v21.226/readiness'
    assert result.launch_manifest['operator_acceptance'] == '/phoenix/demo1/v21.233/acceptance'
    assert result.launch_manifest['packaging_readiness'] == '/phoenix/demo1/v21.234/packaging-readiness'
    assert result.launch_manifest['release_candidate_gate'] == '/phoenix/demo1/v21.235/release-candidate'
    assert result.launch_manifest['health'] == '/health'


def test_risk_brain_hard_block_prevents_launch():
    result = build_release_candidate(ReleaseCandidateRequest(risk_brain_hard_block=True))
    assert result.state == 'blocked'
    assert result.demo1_launch_ready is False
    assert result.reasons == ['risk-brain-hard-block']


def test_release_candidate_route_is_live():
    client = TestClient(app)
    response = client.post('/phoenix/demo1/v21.235/release-candidate', json={'workspace_id':'ws-demo','operator_id':'operator-demo'})
    assert response.status_code == 200
    body = response.json()
    assert body['version'] == 'v21.235'
    assert body['state'] == 'launch-ready'
    assert body['demo1_launch_ready'] is True
    assert body['autonomous_high_risk_execution_enabled'] is False
