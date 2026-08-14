from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_forty_five_monitoring_v21_519 import command_center, router, status


def client() -> TestClient:
    app=FastAPI(); app.include_router(router); return TestClient(app)


def test_routes_registered() -> None:
    paths={route.path for route in router.routes}
    assert '/auron/demo1/v21.519/monitoring/start' in paths
    assert '/auron/demo1/v21.519/monitoring/audit' in paths
    assert '/auron/demo1/v21.519/drift/declare' in paths
    assert '/auron/demo1/v21.519/baseline/certify' in paths
    assert '/auron/demo1/v21.519/status' in paths
    assert '/auron/demo1/v21.519/command-center' in paths


def test_safe_empty_status() -> None:
    result=status(); assert result['external_calls_made']==0; assert result['mode']=='successor-next-generation-forty-five-monitoring-drift-renewed-baseline'


def test_start_phrase_enforced() -> None:
    response=client().post('/auron/demo1/v21.519/monitoring/start',json={'actor':'tester','certification_id':'missing','start_phrase':'WRONG','observed_successor_next_generation_forty_five_hash':'0'*64,'control_state':'healthy','monitoring_reference':'test'})
    assert response.status_code==403


def test_audit_phrase_enforced() -> None:
    response=client().post('/auron/demo1/v21.519/monitoring/audit',json={'actor':'tester','monitoring_id':'missing','audit_phrase':'WRONG','observed_successor_next_generation_forty_five_hash':'0'*64,'control_state':'healthy','audit_statement':'test'})
    assert response.status_code==403


def test_drift_phrase_enforced() -> None:
    response=client().post('/auron/demo1/v21.519/drift/declare',json={'actor':'tester','monitoring_id':'missing','drift_phrase':'WRONG','drift_reference':'test','drift_statement':'test'})
    assert response.status_code==403


def test_baseline_phrase_enforced() -> None:
    response=client().post('/auron/demo1/v21.519/baseline/certify',json={'actor':'tester','monitoring_id':'missing','certification_phrase':'WRONG','baseline_reference':'test','baseline_statement':'test'})
    assert response.status_code==403


def test_missing_certification_fails_closed() -> None:
    response=client().post('/auron/demo1/v21.519/monitoring/start',json={'actor':'tester','certification_id':'missing','start_phrase':'START AURON TELEGRAM SUCCESSOR NEXT GENERATION FORTY FIVE MONITORING','observed_successor_next_generation_forty_five_hash':'0'*64,'control_state':'healthy','monitoring_reference':'test'})
    assert response.status_code==404


def test_command_center_safety() -> None:
    html=command_center(); assert 'AURON v21.519' in html; assert 'no Telegram API call' in html; assert 'external_calls_made=0' in html
