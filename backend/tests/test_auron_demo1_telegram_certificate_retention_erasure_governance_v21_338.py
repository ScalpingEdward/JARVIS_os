from datetime import datetime, timedelta, timezone

from app.main import app
from app.api.routes import auron_demo1_telegram_certificate_retention_erasure_governance_v21_338 as governance
from app.api.routes import auron_demo1_telegram_certificate_retirement_governance_v21_337 as retirement
from app.api.routes import auron_demo1_telegram_operational_go_live_acceptance_v21_322 as go_live
from app.api.routes import auron_demo1_telegram_service_certification_slo_v21_330 as certification


def setup_function() -> None:
    governance.reset_telegram_certificate_retention_erasure_governance_store()
    retirement.reset_telegram_certificate_retirement_governance_store()
    certification.reset_telegram_service_certification_slo_store()
    go_live.reset_telegram_operational_go_live_acceptance_store()
    now = datetime.now(timezone.utc) - timedelta(days=400)
    source = {
        'certificate_id': 'source-cert', 'telegram_chat_id': '123',
        'certificate_state': 'retired-archived-read-only', 'integrity_hash': 'source-hash', 'immutable': True,
    }
    successor = {
        'certificate_id': 'successor-cert', 'telegram_chat_id': '123',
        'certificate_state': 'certified', 'integrity_hash': 'successor-hash', 'immutable': True,
    }
    certification._certificate_store['source'] = source
    certification._certificate_store['successor'] = successor
    go_live._go_live_store['123'] = {
        'telegram_chat_id': '123', 'service_certificate_id': 'successor-cert',
        'continuous_mode_active': True, 'go_live_state': 'renewed-certified-operational-service',
    }
    retirement._retirement_store['continuity-1'] = {
        'retirement_id': 'retirement-1', 'source_certificate_id': 'source-cert',
        'successor_certificate_id': 'successor-cert', 'telegram_chat_id': '123',
        'retention_days': 365, 'retirement_state': 'committed-retired-archived',
    }
    retirement._archive_store['retirement-1'] = {
        'archive_id': 'archive-1', 'retirement_id': 'retirement-1',
        'source_certificate_id': 'source-cert', 'successor_certificate_id': 'successor-cert',
        'retention_days': 365, 'source_integrity_hash': 'source-hash',
        'archive_state': 'retired-certificate-archived-read-only',
        'integrity_hash': 'archive-hash', 'immutable': True, 'committed_at': now.isoformat(),
    }


def _establish() -> dict:
    return governance.establish_retention_governance(
        governance.TelegramCertificateRetentionEstablishRequest(
            actor='operator', retirement_id='retirement-1',
            establishment_phrase='ESTABLISH AURON TELEGRAM CERTIFICATE RETENTION GOVERNANCE',
        )
    )


def _evaluate() -> dict:
    return governance.evaluate_retention_expiry(
        governance.TelegramCertificateRetentionEvaluateRequest(
            actor='operator', retirement_id='retirement-1', evaluated_at=datetime.now(timezone.utc),
        )
    )


def test_establishes_immutable_retention_governance() -> None:
    result = _establish()
    assert result['state'] == 'telegram-certificate-retention-governance-established'
    assert result['retention']['immutable'] is True
    assert result['retention']['integrity_hash']


def test_expired_retention_becomes_erasure_eligible() -> None:
    _establish()
    result = _evaluate()
    assert result['evaluation']['expired'] is True
    assert result['evaluation']['erasure_eligible'] is True


def test_legal_hold_blocks_erasure() -> None:
    _establish()
    governance.place_legal_hold(governance.TelegramCertificateLegalHoldRequest(
        actor='legal', retirement_id='retirement-1',
        hold_phrase='PLACE AURON TELEGRAM CERTIFICATE LEGAL HOLD',
        legal_basis='Pending regulatory inquiry', reference_id='case-1',
    ))
    result = _evaluate()
    assert result['evaluation']['legal_hold_active'] is True
    assert result['evaluation']['erasure_eligible'] is False
    try:
        governance.commit_cryptographic_erasure(governance.TelegramCertificateErasureCommitRequest(
            actor='operator', retirement_id='retirement-1',
            erasure_phrase='COMMIT AURON TELEGRAM CERTIFICATE CRYPTOGRAPHIC ERASURE',
            erasure_reason='Retention expired',
        ))
    except Exception as exc:
        assert getattr(exc, 'status_code', None) == 409
    else:
        raise AssertionError('Active legal hold should block erasure')


def test_release_then_commit_erasure_preserves_successor() -> None:
    _establish()
    governance.place_legal_hold(governance.TelegramCertificateLegalHoldRequest(
        actor='legal', retirement_id='retirement-1',
        hold_phrase='PLACE AURON TELEGRAM CERTIFICATE LEGAL HOLD',
        legal_basis='Temporary review', reference_id='case-2',
    ))
    governance.release_legal_hold(governance.TelegramCertificateLegalHoldReleaseRequest(
        actor='legal', retirement_id='retirement-1',
        release_phrase='RELEASE AURON TELEGRAM CERTIFICATE LEGAL HOLD',
        release_reason='Review completed',
    ))
    _evaluate()
    result = governance.commit_cryptographic_erasure(governance.TelegramCertificateErasureCommitRequest(
        actor='operator', retirement_id='retirement-1',
        erasure_phrase='COMMIT AURON TELEGRAM CERTIFICATE CRYPTOGRAPHIC ERASURE',
        erasure_reason='Retention expired and no legal hold remains',
    ))
    assert result['state'] == 'telegram-certificate-cryptographic-erasure-committed'
    assert result['erasure']['immutable'] is True
    assert certification._certificate_store['source']['certificate_state'] == 'cryptographically-erased-tombstone'
    assert certification._certificate_store['successor']['certificate_state'] == 'certified'
    assert go_live._go_live_store['123']['service_certificate_id'] == 'successor-cert'


def test_erasure_is_idempotent() -> None:
    _establish()
    _evaluate()
    payload = governance.TelegramCertificateErasureCommitRequest(
        actor='operator', retirement_id='retirement-1',
        erasure_phrase='COMMIT AURON TELEGRAM CERTIFICATE CRYPTOGRAPHIC ERASURE',
        erasure_reason='Retention expired',
    )
    first = governance.commit_cryptographic_erasure(payload)
    second = governance.commit_cryptographic_erasure(payload)
    assert first['erasure']['erasure_id'] == second['erasure']['erasure_id']
    assert second['idempotent_replay'] is True


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.338/establish' in paths
    assert '/auron/demo1/v21.338/evaluate' in paths
    assert '/auron/demo1/v21.338/legal-hold' in paths
    assert '/auron/demo1/v21.338/legal-hold/release' in paths
    assert '/auron/demo1/v21.338/erase' in paths
    assert '/auron/demo1/v21.338/command-center' in paths
