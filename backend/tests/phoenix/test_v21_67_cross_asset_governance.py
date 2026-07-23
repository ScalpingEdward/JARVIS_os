from backend.app.phoenix.v21_67.cross_asset_governance import CrossAssetGovernance, GovernanceError
from backend.app.phoenix.v21_67.cross_asset_models import AssetClass, AssetObservation, CrossAssetRecord, CrossAssetState


def make_record(record_id="r1", workspace="w1", source="s1", blocked=False):
    return CrossAssetRecord(
        record_id=record_id,
        workspace_id=workspace,
        source_key=source,
        risk_blocked=blocked,
        observations=[
            AssetObservation("SPX", AssetClass.EQUITY, 0.6, 0.4, 0.8, 0.2, 0.9, 0.9, "market"),
            AssetObservation("DXY", AssetClass.FX, -0.4, 0.3, 0.9, 0.2, 0.9, 0.8, "market"),
            AssetObservation("US10Y", AssetClass.RATES, 0.2, 0.2, 0.85, 0.25, 0.95, 0.85, "market"),
        ],
        correlations={"SPX:DXY": -0.6, "SPX:US10Y": 0.35, "DXY:US10Y": 0.25},
    )


def test_lifecycle_scoring_approval_and_audit():
    service = CrossAssetGovernance()
    service.create(make_record())
    score = service.score("w1", "r1")
    assert score.confidence > 0.5
    approved = service.approve("w1", "r1", "human-reviewer", "receipt-1")
    assert approved.state == CrossAssetState.ACTIVE
    assert len(service.audit("w1")) == 3


def test_replay_protection():
    service = CrossAssetGovernance()
    service.create(make_record())
    service.score("w1", "r1")
    service.approve("w1", "r1", "reviewer", "same-receipt")
    try:
        service.suspend("w1", "r1", "reviewer", "same-receipt")
        assert False, "expected replay detection"
    except GovernanceError:
        pass


def test_workspace_isolation_and_duplicate_source_key():
    service = CrossAssetGovernance()
    service.create(make_record())
    service.create(make_record("r2", "w2", "s1"))
    try:
        service.get("w2", "r1")
        assert False, "expected workspace isolation"
    except GovernanceError:
        pass
    try:
        service.create(make_record("r3", "w1", "s1"))
        assert False, "expected duplicate source key protection"
    except GovernanceError:
        pass


def test_risk_brain_block_is_authoritative():
    service = CrossAssetGovernance()
    service.create(make_record(blocked=True))
    score = service.score("w1", "r1")
    assert score.recommended_state == CrossAssetState.BLOCKED
    try:
        service.approve("w1", "r1", "reviewer", "receipt-2")
        assert False, "expected hard block"
    except GovernanceError:
        pass
