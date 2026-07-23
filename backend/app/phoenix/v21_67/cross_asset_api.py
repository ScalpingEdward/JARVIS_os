"""Framework-neutral API contract for PHOENIX v21.67.

The application adapter can bind these handlers to FastAPI routes under
/v1/cross-asset without granting execution authority.
"""

from __future__ import annotations

from dataclasses import asdict

from .cross_asset_governance import CrossAssetGovernance
from .cross_asset_models import AssetClass, AssetObservation, CrossAssetRecord


class CrossAssetAPI:
    def __init__(self, service: CrossAssetGovernance | None = None) -> None:
        self.service = service or CrossAssetGovernance()

    def status(self) -> dict[str, object]:
        return {
            "module": "PHOENIX v21.67",
            "name": "Autonomous Cross-Asset Intelligence Governance",
            "healthy": True,
            "execution_authority": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create_record(self, payload: dict[str, object]) -> dict[str, object]:
        observations = [
            AssetObservation(
                symbol=str(item["symbol"]),
                asset_class=AssetClass(str(item["asset_class"])),
                return_score=float(item["return_score"]),
                volatility_score=float(item["volatility_score"]),
                liquidity_score=float(item["liquidity_score"]),
                stress_score=float(item["stress_score"]),
                freshness=float(item["freshness"]),
                confidence=float(item["confidence"]),
                provenance=str(item["provenance"]),
            )
            for item in payload.get("observations", [])
        ]
        record = CrossAssetRecord(
            record_id=str(payload["record_id"]),
            workspace_id=str(payload["workspace_id"]),
            source_key=str(payload["source_key"]),
            observations=observations,
            correlations={str(k): float(v) for k, v in dict(payload.get("correlations", {})).items()},
            risk_blocked=bool(payload.get("risk_blocked", False)),
        )
        return asdict(self.service.create(record))

    def get_record(self, workspace_id: str, record_id: str) -> dict[str, object]:
        return asdict(self.service.get(workspace_id, record_id))

    def score_record(self, workspace_id: str, record_id: str) -> dict[str, object]:
        return asdict(self.service.score(workspace_id, record_id))

    def action(self, workspace_id: str, record_id: str, payload: dict[str, object]) -> dict[str, object]:
        action = str(payload["action"])
        actor = str(payload["actor"])
        receipt = str(payload["receipt"])
        if action == "approve":
            return asdict(self.service.approve(workspace_id, record_id, actor, receipt))
        if action == "suspend":
            return asdict(self.service.suspend(workspace_id, record_id, actor, receipt))
        raise ValueError("unsupported governed action")

    def audit(self, workspace_id: str) -> list[dict[str, object]]:
        return self.service.audit(workspace_id)


ROUTES = (
    ("GET", "/v1/cross-asset/status"),
    ("POST", "/v1/cross-asset/records"),
    ("GET", "/v1/cross-asset/records"),
    ("GET", "/v1/cross-asset/records/{record_id}"),
    ("POST", "/v1/cross-asset/records/{record_id}/actions"),
    ("GET", "/v1/cross-asset/audit"),
)
