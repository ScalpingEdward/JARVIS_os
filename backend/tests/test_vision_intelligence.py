import pytest
from pydantic import ValidationError

from app.vision_intelligence.models import (
    AnalysisRequest,
    AnalysisState,
    AnalysisType,
    AssetMutation,
    AssetType,
    BoundingBox,
    RegionKind,
    VisionAssetCreate,
    VisualRegionInput,
)
from app.vision_intelligence.service import VisionIntelligenceService


def asset_payload(workspace: str = "workspace-1") -> VisionAssetCreate:
    return VisionAssetCreate(
        workspace_id=workspace,
        owner_id="owner-1",
        asset_key="dashboard-1",
        title="Trading Dashboard",
        asset_type=AssetType.CHART,
        width=1920,
        height=1080,
        checksum="checksum-123456",
        metadata={"chart_type": "candlestick", "chart_title": "XAUUSD"},
        supplied_regions=[
            VisualRegionInput(region_id="chart", kind=RegionKind.CHART, label="Price chart", confidence=0.95, bounding_box=BoundingBox(x=0.1, y=0.1, width=0.7, height=0.7)),
            VisualRegionInput(region_id="axis", kind=RegionKind.AXIS, text="Price", confidence=0.9, bounding_box=BoundingBox(x=0.82, y=0.1, width=0.1, height=0.7)),
            VisualRegionInput(region_id="legend", kind=RegionKind.LEGEND, text="XAUUSD M15", confidence=0.9, bounding_box=BoundingBox(x=0.1, y=0.02, width=0.2, height=0.05)),
            VisualRegionInput(region_id="secret", kind=RegionKind.TEXT, text="account 123", confidence=0.99, sensitive=True, bounding_box=BoundingBox(x=0.8, y=0.85, width=0.15, height=0.05)),
        ],
    )


def test_create_and_full_analysis():
    service = VisionIntelligenceService()
    asset = service.create_asset(asset_payload())
    result = service.analyze(AnalysisRequest(workspace_id="workspace-1", requester_id="owner-1", asset_id=asset.id, analysis_type=AnalysisType.FULL))
    assert result.state == AnalysisState.COMPLETED
    assert result.chart is not None
    assert result.chart.chart_type == "candlestick"
    assert result.findings
    assert "account 123" not in result.extracted_text
    assert result.external_ai_used is False


def test_workspace_isolation_blocks_analysis():
    service = VisionIntelligenceService()
    asset = service.create_asset(asset_payload())
    result = service.analyze(AnalysisRequest(workspace_id="other", requester_id="owner-1", asset_id=asset.id))
    assert result.state == AnalysisState.BLOCKED


def test_duplicate_checksum_rejected():
    service = VisionIntelligenceService()
    service.create_asset(asset_payload())
    duplicate = asset_payload()
    duplicate.asset_key = "dashboard-2"
    with pytest.raises(ValueError):
        service.create_asset(duplicate)


def test_owner_only_archive_restore():
    service = VisionIntelligenceService()
    asset = service.create_asset(asset_payload())
    assert service.set_active(asset.id, "workspace-1", AssetMutation(requester_id="wrong"), False) is None
    assert service.set_active(asset.id, "workspace-1", AssetMutation(requester_id="owner-1"), False).active is False
    assert service.set_active(asset.id, "workspace-1", AssetMutation(requester_id="owner-1"), True).active is True


def test_safety_rejects_external_calls_and_uploads():
    with pytest.raises(ValidationError):
        asset_payload().model_copy(update={"automatic_cloud_upload": True})
    with pytest.raises(ValidationError):
        asset_payload().model_copy(update={"external_vision_request": True})
    service = VisionIntelligenceService()
    asset = service.create_asset(asset_payload())
    with pytest.raises(ValidationError):
        AnalysisRequest(workspace_id="workspace-1", requester_id="owner-1", asset_id=asset.id, use_external_ai=True)
    with pytest.raises(ValidationError):
        AnalysisRequest(workspace_id="workspace-1", requester_id="owner-1", asset_id=asset.id, use_external_ocr=True)
    with pytest.raises(ValidationError):
        AnalysisRequest(workspace_id="workspace-1", requester_id="owner-1", asset_id=asset.id, upload_asset=True)


def test_bounding_box_must_stay_in_frame():
    with pytest.raises(ValidationError):
        BoundingBox(x=0.9, y=0.1, width=0.2, height=0.2)


def test_status_reports_safety_defaults():
    status = VisionIntelligenceService().status()
    assert status.version == "8.5"
    assert status.metadata_only_analysis is True
    assert status.external_ai_execution is False
    assert status.external_ocr_execution is False
    assert status.automatic_cloud_uploads is False
