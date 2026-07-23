from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from statistics import fmean, pstdev
from uuid import UUID

from app.schemas.market_microstructure_liquidity import (
    MicrostructureAction,
    MicrostructureRecord,
    MicrostructureRecordCreate,
    MicrostructureScores,
    MicrostructureState,
)


@dataclass
class MarketMicrostructureStore:
    records: dict[UUID, MicrostructureRecord] = field(default_factory=dict)
    payloads: dict[UUID, MicrostructureRecordCreate] = field(default_factory=dict)
    source_keys: set[tuple[str, str]] = field(default_factory=set)
    receipts: set[str] = field(default_factory=set)
    audit: list[dict] = field(default_factory=list)

    def create(self, payload: MicrostructureRecordCreate) -> MicrostructureRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self.source_keys:
            raise ValueError("duplicate source_key in workspace")
        now = datetime.now(UTC)
        record = MicrostructureRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            asset_class=payload.asset_class,
            created_at=now,
            updated_at=now,
        )
        self.records[record.id] = record
        self.payloads[record.id] = payload
        self.source_keys.add(source_identity)
        self._audit(record, "create", "system")
        return record

    def list(self, workspace_id: str) -> list[MicrostructureRecord]:
        return [record for record in self.records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: UUID, workspace_id: str) -> MicrostructureRecord:
        record = self.records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise KeyError("record not found")
        return record

    def act(self, record_id: UUID, workspace_id: str, action: MicrostructureAction) -> MicrostructureRecord:
        record = self.get(record_id, workspace_id)
        if action.operation_receipt in self.receipts:
            raise ValueError("operation receipt already used")
        self.receipts.add(action.operation_receipt)
        if action.risk_brain_blocked and action.action in {"approve", "activate", "monitor"}:
            record.state = MicrostructureState.BLOCKED
            record.updated_at = datetime.now(UTC)
            self._audit(record, "risk-brain-block", action.actor, action.reason)
            return record

        transitions = {
            "score": MicrostructureState.SCORED,
            "submit-review": MicrostructureState.REVIEW_REQUIRED,
            "approve": MicrostructureState.APPROVED,
            "activate": MicrostructureState.ACTIVE,
            "monitor": MicrostructureState.MONITORING,
            "suspend": MicrostructureState.SUSPENDED,
            "revoke": MicrostructureState.REVOKED,
            "archive": MicrostructureState.ARCHIVED,
        }
        required = {
            "approve": {MicrostructureState.REVIEW_REQUIRED},
            "activate": {MicrostructureState.APPROVED},
            "monitor": {MicrostructureState.ACTIVE, MicrostructureState.STABLE},
        }
        if action.action in required and record.state not in required[action.action]:
            raise ValueError(f"invalid transition from {record.state} using {action.action}")
        if action.action == "score":
            record.scores = self._score(self.payloads[record_id])
        if action.action == "approve":
            record.approved_by = action.actor
        record.state = transitions[action.action]
        record.updated_at = datetime.now(UTC)
        self._audit(record, action.action, action.actor, action.reason)
        return record

    def _score(self, payload: MicrostructureRecordCreate) -> MicrostructureScores:
        observations = payload.observations
        spreads = [((o.ask - o.bid) / ((o.ask + o.bid) / 2)) * 10_000 for o in observations]
        depth = [o.bid_size + o.ask_size for o in observations]
        imbalances = [
            0.0 if o.bid_size + o.ask_size == 0 else (o.bid_size - o.ask_size) / (o.bid_size + o.ask_size)
            for o in observations
        ]
        venue_mids = [(o.bid + o.ask) / 2 for o in observations]
        spread_stress = min(100.0, fmean(spreads) * 4)
        depth_resilience = min(100.0, fmean(depth) / (1 + fmean(spreads)))
        imbalance = max(-100.0, min(100.0, fmean(imbalances) * 100))
        fragmentation = min(100.0, (pstdev(venue_mids) / max(fmean(venue_mids), 1e-9)) * 100_000)
        cancellation_penalty = fmean(o.cancel_rate for o in observations) * 50
        latency_penalty = min(35.0, fmean(o.latency_ms for o in observations) / 10)
        execution_quality = max(0.0, 100 - spread_stress - cancellation_penalty - latency_penalty)
        confidence = 100 * fmean([payload.provenance_confidence, payload.freshness_score])
        return MicrostructureScores(
            spread_stress=round(spread_stress, 4),
            depth_resilience=round(depth_resilience, 4),
            order_flow_imbalance=round(imbalance, 4),
            fragmentation_risk=round(fragmentation, 4),
            execution_quality=round(execution_quality, 4),
            liquidity_confidence=round(confidence, 4),
        )

    def _audit(self, record: MicrostructureRecord, event: str, actor: str, reason: str | None = None) -> None:
        self.audit.append(
            {
                "record_id": str(record.id),
                "workspace_id": record.workspace_id,
                "event": event,
                "actor": actor,
                "state": record.state.value,
                "reason": reason,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )


market_microstructure_store = MarketMicrostructureStore()
