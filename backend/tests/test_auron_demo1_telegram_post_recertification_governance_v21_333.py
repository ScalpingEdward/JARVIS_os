from app.main import app
from app.api.routes import auron_demo1_telegram_post_recertification_governance_v21_333 as governance
from app.api.routes import auron_demo1_telegram_certification_drift_remediation_v21_332 as remediation
from app.api.routes import auron_demo1_telegram_service_certification_slo_v21_330 as certification
from app.api.routes import auron_demo1_telegram_operational_go_live_acceptance_v21_322 as go_live
from app.api.routes import auron_demo1_telegram_continuous_conversation_supervisor_v21_323 as supervisor


def setup_function() -> None:
    governance.reset_telegram_post_recertification_governance_store()
    remediation.reset_telegram_certification_drift_remediation_store()
    certification.reset_telegram_service_certification_slo_store()
    go_live.reset_telegram_operational_go_live_acceptance_store()
    supervisor.reset_telegram_continuous_conversation_supervisor_store()
    parent = {
        'certificate_id': 'cert-parent',
        'telegram_chat_id': '123',
        'certificate_state': 'superseded-after-drift-remediation',
        'integrity_hash': 'parent-hash',
        'immutable': True,
        'slo_baseline': {'delivery_success_rate': 1.0, 'lifecycle_completion_rate': 1.0, 'queue_completion_rate': 1.0, 'dead_letter_rate': 0.0},
        'runtime_reliability_score': 100.0,
    }
    replacement = {
        'certificate_id': 'cert-replacement',
        'supersedes_certificate_id': 'cert-parent',
        'telegram_chat_id': '123',
        'certificate_state': 'certified',
        'integrity_hash': 'replacement-hash',
        'immutable': True,
        'slo_baseline': {'delivery_success_rate': 1.0, 'lifecycle_completion_rate': 1.0, 'queue_completion_rate': 1.0, 'dead_letter_rate': 0.0},
        'runtime_reliability_score': 100.0,
    }
    certification._certificate_store['parent'] = parent
    certification._certificate_store['replacement'] = replacement
    remediation._recertification_store['drift-1'] = replacement
    go_live._go_live_store['123'] = {'telegram_chat_id': '123', 'continuous_mode_active': True, 'go_live_state': 'recertified-operational-service'}
    supervisor._circuit_store['123'] = {'telegram_chat_id': '123', 'state': 'closed'}


def _start(required: int = 2) -> dict:
    return governance.start_post_recertification_governance(
        governance.TelegramPostRecertificationStartRequest(
            actor='operator', certificate_id='cert-replacement',
            start_phrase='START AURON TELEGRAM POST RECERTIFICATION OBSERVATION',
            required_stable_observations=required, minimum_reliability_score=85.0,
        )
    )


def test_start_verifies_certificate_lineage() -> None:
    result = _start()
    assert result['state'] == 'telegram-post-recertification-governance-started'
    assert result['governance']['lineage']['valid'] is True
    assert result['governance']['lineage']['depth'] == 2


def test_stable_observations_and_completion(monkeypatch) -> None:
    monkeypatch.setattr(governance, '_baseline_metrics', lambda _chat: {'runtime_reliability_score': 100.0})
    started = _start(required=2)['governance']
    for _ in range(2):
        result = governance.observe_post_recertification_governance(
            governance.TelegramPostRecertificationObserveRequest(actor='operator', governance_id=started['governance_id'])
        )
        assert result['state'] == 'telegram-post-recertification-stable-observation-recorded'
    completed = governance.complete_post_recertification_governance(
        governance.TelegramPostRecertificationCompleteRequest(
            actor='operator', governance_id=started['governance_id'],
            completion_phrase='COMPLETE AURON TELEGRAM POST RECERTIFICATION GOVERNANCE',
        )
    )
    assert completed['state'] == 'telegram-post-recertification-governance-completed'
    assert completed['lineage_audit']['immutable'] is True
    assert completed['lineage_audit']['integrity_hash']


def test_degraded_observation_requires_review(monkeypatch) -> None:
    monkeypatch.setattr(governance, '_baseline_metrics', lambda _chat: {'runtime_reliability_score': 40.0})
    started = _start(required=1)['governance']
    result = governance.observe_post_recertification_governance(
        governance.TelegramPostRecertificationObserveRequest(actor='operator', governance_id=started['governance_id'])
    )
    assert result['state'] == 'telegram-post-recertification-governance-review-required'
    assert result['governance']['governance_state'] == 'governance-review-required'


def test_start_is_idempotent() -> None:
    first = _start()
    second = _start()
    assert second['idempotent_replay'] is True
    assert second['governance']['governance_id'] == first['governance']['governance_id']


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}
    assert '/auron/demo1/v21.333/start' in paths
    assert '/auron/demo1/v21.333/observe' in paths
    assert '/auron/demo1/v21.333/complete' in paths
    assert '/auron/demo1/v21.333/lineage-audits' in paths
