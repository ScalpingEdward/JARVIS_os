from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AnalysisRequest, AnalysisState, AnalysisType, AssetMutation, AssetType, AuditRecord,
    ChartInsight, RegionKind, UIInsight, VisionAnalysisRecord, VisionAssetCreate,
    VisionAssetRecord, VisionIntelligenceStatus, VisualFinding,
)


class VisionIntelligenceService:
    def __init__(self) -> None:
        self.assets: dict[UUID, VisionAssetRecord] = {}
        self.analyses: list[VisionAnalysisRecord] = []
        self.audit: list[AuditRecord] = []

    def _audit(self, workspace_id: str, actor_id: str, action: str, object_type: str, object_id: str, **details) -> None:
        self.audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, action=action, object_type=object_type, object_id=object_id, details=details))

    def create_asset(self, payload: VisionAssetCreate) -> VisionAssetRecord:
        for item in self.assets.values():
            if item.workspace_id == payload.workspace_id and (item.asset_key == payload.asset_key or item.checksum == payload.checksum):
                raise ValueError("duplicate asset key or checksum")
        record = VisionAssetRecord(**payload.model_dump(exclude={"human_approved", "automatic_cloud_upload", "external_vision_request", "external_ocr_request"}))
        self.assets[record.id] = record
        self._audit(record.workspace_id, record.owner_id, "asset.created", "vision_asset", str(record.id))
        return record

    def list_assets(self, workspace_id: str, include_inactive: bool = False) -> list[VisionAssetRecord]:
        return [a for a in self.assets.values() if a.workspace_id == workspace_id and (include_inactive or a.active)]

    def get_asset(self, asset_id: UUID, workspace_id: str) -> VisionAssetRecord | None:
        item = self.assets.get(asset_id)
        return item if item and item.workspace_id == workspace_id else None

    def set_active(self, asset_id: UUID, workspace_id: str, payload: AssetMutation, active: bool) -> VisionAssetRecord | None:
        item = self.get_asset(asset_id, workspace_id)
        if item is None or item.owner_id != payload.requester_id:
            return None
        item.active = active
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, payload.requester_id, "asset.restored" if active else "asset.archived", "vision_asset", str(asset_id), reason=payload.reason)
        return item

    def analyze(self, payload: AnalysisRequest) -> VisionAnalysisRecord:
        asset = self.get_asset(payload.asset_id, payload.workspace_id)
        if asset is None or not asset.active:
            result = VisionAnalysisRecord(workspace_id=payload.workspace_id, requester_id=payload.requester_id, asset_id=payload.asset_id, analysis_type=payload.analysis_type, state=AnalysisState.BLOCKED, asset_classification=AssetType.OTHER, blocked_reason="asset not found in workspace or inactive")
            self.analyses.append(result)
            return result

        regions = asset.supplied_regions
        extracted_text = [r.text for r in regions if r.text and not r.sensitive]
        citations = [f"asset:{asset.id}#region:{r.region_id}" for r in regions]
        findings: list[VisualFinding] = []
        for r in regions:
            if r.sensitive:
                findings.append(VisualFinding(code="sensitive-region", category="privacy", description="Sensitive visual region detected; content redacted", confidence=r.confidence, region_id=r.region_id, citation=f"asset:{asset.id}#region:{r.region_id}"))
            elif not r.label and not r.text:
                findings.append(VisualFinding(code="unlabeled-region", category="quality", description="Region has no label or extracted text", confidence=0.6, region_id=r.region_id, citation=f"asset:{asset.id}#region:{r.region_id}"))

        chart = None
        if payload.analysis_type in {AnalysisType.ANALYZE_CHART, AnalysisType.FULL} or asset.asset_type == AssetType.CHART:
            chart_regions = [r for r in regions if r.kind in {RegionKind.CHART, RegionKind.AXIS, RegionKind.LEGEND, RegionKind.TEXT}]
            chart = ChartInsight(
                chart_type=str(asset.metadata.get("chart_type", "unknown")),
                title=str(asset.metadata.get("chart_title", asset.title)),
                axis_labels=[r.text or r.label for r in chart_regions if r.kind == RegionKind.AXIS and (r.text or r.label)],
                legend_labels=[r.text or r.label for r in chart_regions if r.kind == RegionKind.LEGEND and (r.text or r.label)],
                visible_values=[r.text for r in chart_regions if r.kind == RegionKind.TEXT and r.text],
                caveats=["No pixel-level model executed; insights use supplied metadata only"],
                confidence=0.8 if chart_regions else 0.2,
            )

        ui = None
        if payload.analysis_type in {AnalysisType.ANALYZE_UI, AnalysisType.FULL} or asset.asset_type in {AssetType.UI_CAPTURE, AssetType.SCREENSHOT}:
            ui = UIInsight(
                controls=[r.label for r in regions if r.kind in {RegionKind.BUTTON, RegionKind.INPUT} and r.label],
                forms=[r.label for r in regions if r.kind == RegionKind.INPUT and r.label],
                warnings=[r.text for r in regions if "warning" in r.label.lower() or "error" in r.label.lower()],
                sensitive_regions=[r.region_id for r in regions if r.sensitive],
            )

        summary = f"{asset.title}: {len(regions)} supplied regions, {len(extracted_text)} readable text regions, {len(findings)} findings."
        result = VisionAnalysisRecord(workspace_id=payload.workspace_id, requester_id=payload.requester_id, asset_id=asset.id, analysis_type=payload.analysis_type, state=AnalysisState.COMPLETED, asset_classification=asset.asset_type, summary=summary, extracted_text=extracted_text, findings=findings, chart=chart, ui=ui, citations=citations)
        self.analyses.append(result)
        self._audit(payload.workspace_id, payload.requester_id, "analysis.completed", "vision_analysis", str(result.id), asset_id=str(asset.id))
        return result

    def list_analyses(self, workspace_id: str, asset_id: UUID | None = None) -> list[VisionAnalysisRecord]:
        return [a for a in self.analyses if a.workspace_id == workspace_id and (asset_id is None or a.asset_id == asset_id)]

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [a for a in self.audit if a.workspace_id == workspace_id]

    def status(self) -> VisionIntelligenceStatus:
        return VisionIntelligenceStatus(assets=len(self.assets), analyses=len(self.analyses), completed_analyses=sum(a.state == AnalysisState.COMPLETED for a in self.analyses), blocked_analyses=sum(a.state == AnalysisState.BLOCKED for a in self.analyses), supplied_regions=sum(len(a.supplied_regions) for a in self.assets.values()), findings=sum(len(a.findings) for a in self.analyses))


vision_intelligence_service = VisionIntelligenceService()
