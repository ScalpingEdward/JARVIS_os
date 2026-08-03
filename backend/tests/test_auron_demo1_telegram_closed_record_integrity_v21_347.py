from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.auron_demo1_telegram_closed_record_integrity_v21_347 import (
    _AUDIT_PHRASE,
    _RETAIN_PHRASE,
    _REVALIDATE_PHRASE,
    reset_telegram_closed_record_integrity_store,
)
from app.api.routes.auron_demo1_telegram_post_offboarding_closure_v21_346 import (
    _archive_store,
    _closure_store,
    _risk_review_store,
)

client = TestClient(app)


def setup_function() -> None:
    reset_telegram_closed_record_integrity_store()
    _archive_store.clear()
    _closure_store.clear()
    _risk_review_store.clear()


def seed_closed_archive() -> str:
    archive_id = 'archive-347-test'
    _archive_store['retention-347-test'] = {
        'archive_id': archive_id,
        'archive_hash': 'archive-hash',
        'archive_reference': 'archive-ref',
        'retention_id': 'retention-347-test',
        'archive_state': 'archived-final-lifecycle-closed',
        'immutable': True,
    }
    _risk_review_store[archive_id] = {
        'risk_review_id': 'review-347-test',
        'integrity_hash': 'review-hash',
        'risk_rating': 'low',
        'closure_eligible': True,
        'immutable': True,
    }
    _closure_store[archive_id] = {
        'closure_id': 'closure-347-test',
        'integrity_hash': 'closure-hash',
        'closure_reference': 'closure-ref',
        'closure_state': 'final-disclosure-lifecycle-closed',
        'immutable': True,
    }
    return archive_id


def test_v21_347_routes_registered_and_empty_status_safe() -> None:
    response = client.get('/auron/demo1/v21.347/status')
    assert response.status_code == 200
    assert response.json()['retained_records'] == 0
    assert client.get('/auron/demo1/v21.347/command-center').status_code == 200


def test_retain_audit_and_revalidate_closed_record() -> None:
    archive_id = seed_closed_archive()
    retained = client.post('/auron/demo1/v21.347/record/retain', json={
        'actor': 'test-operator',
        'archive_id': archive_id,
        'retain_phrase': _RETAIN_PHRASE,
        'retention_days': 2555,
        'audit_interval_days': 180,
    })
    assert retained.status_code == 200
    record = retained.json()['record']
    assert record['record_state'] == 'retained-closed-disclosure-record'

    audited = client.post('/auron/demo1/v21.347/integrity/audit', json={
        'actor': 'test-auditor',
        'record_id': record['record_id'],
        'audit_phrase': _AUDIT_PHRASE,
    })
    assert audited.status_code == 200
    assert audited.json()['audit']['audit_state'] == 'closed-record-integrity-verified'

    revalidated = client.post('/auron/demo1/v21.347/closure/revalidate', json={
        'actor': 'test-reviewer',
        'record_id': record['record_id'],
        'revalidation_phrase': _REVALIDATE_PHRASE,
        'revalidation_reference': 'annual-review-2026',
    })
    assert revalidated.status_code == 200
    assert revalidated.json()['revalidation']['revalidation_state'] == 'final-lifecycle-closure-revalidated'


def test_invalid_retain_phrase_fails_closed() -> None:
    archive_id = seed_closed_archive()
    response = client.post('/auron/demo1/v21.347/record/retain', json={
        'actor': 'test-operator',
        'archive_id': archive_id,
        'retain_phrase': 'INVALID',
    })
    assert response.status_code == 403


def test_integrity_drift_requires_reopen_before_revalidation() -> None:
    archive_id = seed_closed_archive()
    retained = client.post('/auron/demo1/v21.347/record/retain', json={
        'actor': 'test-operator',
        'archive_id': archive_id,
        'retain_phrase': _RETAIN_PHRASE,
    }).json()['record']

    _archive_store['retention-347-test']['archive_hash'] = 'tampered-hash'
    audited = client.post('/auron/demo1/v21.347/integrity/audit', json={
        'actor': 'test-auditor',
        'record_id': retained['record_id'],
        'audit_phrase': _AUDIT_PHRASE,
    })
    assert audited.status_code == 200
    assert audited.json()['audit']['drift_detected'] is True

    blocked = client.post('/auron/demo1/v21.347/closure/revalidate', json={
        'actor': 'test-reviewer',
        'record_id': retained['record_id'],
        'revalidation_phrase': _REVALIDATE_PHRASE,
        'revalidation_reference': 'blocked-review',
    })
    assert blocked.status_code == 409
