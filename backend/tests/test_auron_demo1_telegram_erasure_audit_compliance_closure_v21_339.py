from app.main import app
from app.api.routes import auron_demo1_telegram_erasure_audit_compliance_closure_v21_339 as audit
from app.api.routes import auron_demo1_telegram_certificate_retention_erasure_governance_v21_338 as erasure
from app.api.routes import auron_demo1_telegram_certificate_retirement_governance_v21_337 as retirement
from app.api.routes import auron_demo1_telegram_service_certification_slo_v21_330 as certification
from app.api.routes import auron_demo1_telegram_operational_go_live_acceptance_v21_322 as go_live


def setup_function() -> None:
    audit.reset_telegram_erasure_audit_compliance_closure_store()
    erasure.reset_telegram_certificate_retention_erasure_governance_store()
    retirement.reset_telegram_certificate_retirement_governance_store()
    certification.reset_telegram_service_certification_slo_store()
    go_live.reset_telegram_operational_go_live_acceptance_store()

    source = {
        'certificate_id': 'source-1',
        'certificate_state': 'cryptographically-erased-tombstone',
        'integrity_hash': None,
        'immutable': True,
        'telegram_chat_id': '123',
    }
    successor = {
        'certificate_id': 'successor-1',
        'certificate_state': 'certified',
        'integrity_hash': 'successor-hash',
        'immutable': True,
        'telegram_chat_id': '123',
    }
    certification._certificate_store['source'] = source
    certification._certificate_store['successor'] = successor
    go_live._go_live_store['123'] = {
        'telegram_chat_id': '123',
        'service_certificate_id': 'successor-1',
        'continuous_mode_active': True,
    }
    retirement._archive_store['retirement-1'] = {
        'archive_id': 'archive-1',
        'archive_state': 'cryptographically-erased-tombstone',
        'source_certificate_id': 'source-1',
        'successor_certificate_id': 'successor-1',
        'integrity_hash': 'archive-hash',
        'immutable': True,
    }
    erasure._retention_store['retirement-1'] = {
        'retention_governance_id': 'retention-1',
        'retirement_id': 'retirement-1',
        'retention_state': 'erasure-completed',
        'source_certificate_id': 'source-1',
        'successor_certificate_id': 'successor-1',
    }
    erasure._erasure_store['retirement-1'] = {
        'erasure_id': 'erasure-1',
        'retirement_id': 'retirement-1',
        'source_certificate_id': 'source-1',
        'successor_certificate_id': 'successor-1',
        'erasure_state': 'cryptographic-erasure-evidence-committed',
        'erasure_evidence_hash': 'erasure-hash',
        'immutable': True,
    }


def _start() -> dict:
    return audit.start_independent_erasure_audit(
        audit.TelegramErasureAuditStartRequest(
            actor='independent-auditor',
            retirement_id='retirement-1',
            start_phrase='START AURON TELEGRAM INDEPENDENT ERASURE AUDIT',
            auditor_independence_statement='Auditor is independent from the erasure operator.',
        )
    )


def test_starts_independent_audit_with_immutable_chain_hash() -> None:
    result = _start()
    assert result['state'] == 'telegram-independent-erasure-audit-started'
    assert result['audit']['immutable'] is True
    assert len(result['audit']['evidence_chain_hash']) == 64


def test_attests_valid_erasure_evidence_chain() -> None:
    started = _start()['audit']
    result = audit.attest_erasure_evidence_chain(
        audit.TelegramErasureAuditAttestRequest(
            actor='independent-auditor',
            audit_id=started['audit_id'],
            attestation_phrase='ATTEST AURON TELEGRAM ERASURE EVIDENCE CHAIN',
        )
    )
    assert result['state'] == 'telegram-erasure-evidence-chain-attested'
    assert result['attestation']['attestation_state'] == 'independently-attested-valid-erasure-chain'


def test_closes_compliance_case_after_attestation() -> None:
    started = _start()['audit']
    audit.attest_erasure_evidence_chain(
        audit.TelegramErasureAuditAttestRequest(
            actor='independent-auditor',
            audit_id=started['audit_id'],
            attestation_phrase='ATTEST AURON TELEGRAM ERASURE EVIDENCE CHAIN',
        )
    )
    result = audit.close_erasure_compliance_case(
        audit.TelegramErasureComplianceCloseRequest(
            actor='compliance-officer',
            audit_id=started['audit_id'],
            closure_phrase='CLOSE AURON TELEGRAM ERASURE COMPLIANCE CASE',
            compliance_reference='CMP-2026-001',
        )
    )
    assert result['state'] == 'telegram-erasure-compliance-case-closed'
    assert result['closure']['immutable'] is True


def test_tampered_erasure_evidence_blocks_attestation() -> None:
    started = _start()['audit']
    erasure._erasure_store['retirement-1']['erasure_evidence_hash'] = 'tampered'
    try:
        audit.attest_erasure_evidence_chain(
            audit.TelegramErasureAuditAttestRequest(
                actor='independent-auditor',
                audit_id=started['audit_id'],
                attestation_phrase='ATTEST AURON TELEGRAM ERASURE EVIDENCE CHAIN',
            )
        )
    except Exception as exc:
        assert getattr(exc, 'status_code', None) == 409
    else:
        raise AssertionError('Tampered erasure evidence should block attestation')


def test_start_is_idempotent() -> None:
    first = _start()
    second = _start()
    assert second['idempotent_replay'] is True
    assert second['audit']['audit_id'] == first['audit']['audit_id']


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.339/start' in paths
    assert '/auron/demo1/v21.339/attest' in paths
    assert '/auron/demo1/v21.339/close' in paths
    assert '/auron/demo1/v21.339/status' in paths
    assert '/auron/demo1/v21.339/command-center' in paths
