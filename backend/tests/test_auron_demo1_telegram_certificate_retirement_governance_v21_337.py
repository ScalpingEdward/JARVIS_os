from fastapi import HTTPException

from app.main import app
from app.api.routes import auron_demo1_telegram_certificate_retirement_governance_v21_337 as retirement
from app.api.routes import auron_demo1_telegram_operational_go_live_acceptance_v21_322 as go_live
from app.api.routes import auron_demo1_telegram_post_renewal_continuity_governance_v21_336 as continuity
from app.api.routes import auron_demo1_telegram_service_certification_slo_v21_330 as certification


def setup_function() -> None:
    retirement.reset_telegram_certificate_retirement_governance_store()
    continuity.reset_telegram_post_renewal_continuity_governance_store()
    certification.reset_telegram_service_certification_slo_store()
    go_live.reset_telegram_operational_go_live_acceptance_store()
    certification._certificate_store['source'] = {
        'certificate_id': 'source-cert',
        'telegram_chat_id': '123',
        'certificate_state': 'superseded-after-governed-renewal',
        'integrity_hash': 'source-hash',
        'immutable': True,
    }
    certification._certificate_store['successor'] = {
        'certificate_id': 'successor-cert',
        'telegram_chat_id': '123',
        'certificate_state': 'certified',
        'integrity_hash': 'successor-hash',
        'immutable': True,
    }
    go_live._go_live_store['123'] = {
        'telegram_chat_id': '123',
        'service_certificate_id': 'successor-cert',
        'continuous_mode_active': True,
    }
    continuity._continuity_store['execution-1'] = {
        'continuity_id': 'continuity-1',
        'renewal_execution_id': 'execution-1',
        'telegram_chat_id': '123',
        'source_certificate_id': 'source-cert',
        'successor_certificate_id': 'successor-cert',
        'continuity_state': 'completed-stable-successor',
        'stabilization_integrity_hash': 'stable-hash',
        'stabilization_evidence_immutable': True,
    }


def _authorize() -> dict:
    return retirement.authorize_certificate_retirement(
        retirement.TelegramCertificateRetirementAuthorizeRequest(
            actor='operator',
            continuity_id='continuity-1',
            authorization_phrase='AUTHORIZE AURON TELEGRAM CERTIFICATE RETIREMENT',
            retention_days=365,
            reason='Successor completed governed stabilization.',
        )
    )


def test_authorizes_immutable_certificate_retirement() -> None:
    result = _authorize()
    assert result['state'] == 'telegram-certificate-retirement-authorized'
    assert result['retirement']['immutable'] is True
    assert len(result['retirement']['integrity_hash']) == 64


def test_commits_read_only_archive_and_preserves_successor() -> None:
    authorized = _authorize()['retirement']
    result = retirement.commit_certificate_retirement(
        retirement.TelegramCertificateRetirementCommitRequest(
            actor='operator',
            retirement_id=authorized['retirement_id'],
            commit_phrase='COMMIT AURON TELEGRAM CERTIFICATE RETIREMENT',
        )
    )
    assert result['state'] == 'telegram-certificate-retirement-committed'
    assert certification._certificate_store['source']['certificate_state'] == 'retired-archived-read-only'
    assert certification._certificate_store['successor']['certificate_state'] == 'certified'
    assert go_live._go_live_store['123']['service_certificate_id'] == 'successor-cert'
    assert result['archive']['immutable'] is True


def test_commit_is_idempotent() -> None:
    authorized = _authorize()['retirement']
    payload = retirement.TelegramCertificateRetirementCommitRequest(
        actor='operator',
        retirement_id=authorized['retirement_id'],
        commit_phrase='COMMIT AURON TELEGRAM CERTIFICATE RETIREMENT',
    )
    retirement.commit_certificate_retirement(payload)
    second = retirement.commit_certificate_retirement(payload)
    assert second['idempotent_replay'] is True


def test_authorization_blocked_without_stable_successor() -> None:
    continuity._continuity_store['execution-1']['continuity_state'] = 'active-successor-stabilization-window'
    try:
        _authorize()
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError('Expected certificate retirement authorization to be blocked')


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.337/authorize' in paths
    assert '/auron/demo1/v21.337/commit' in paths
    assert '/auron/demo1/v21.337/status' in paths
    assert '/auron/demo1/v21.337/archives' in paths
    assert '/auron/demo1/v21.337/command-center' in paths
