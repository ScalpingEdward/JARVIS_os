from __future__ import annotations

from datetime import datetime
from secrets import token_urlsafe

from .models import (
    AuditEvent,
    ChartAnnotation,
    ScenarioAction,
    ScenarioCommand,
    ScenarioDirection,
    ScenarioState,
    TradeScenarioCreate,
    TradeScenarioRecord,
)


class TradeScenarioError(RuntimeError):
    pass


class TradeScenarioVisualizerService:
    """Builds reviewable chart overlays without placing or modifying trades."""

    def __init__(self) -> None:
        self._records: dict[str, TradeScenarioRecord] = {}
        self._source_index: dict[tuple[str, str], str] = {}
        self._audit: list[AuditEvent] = []
        self._used_review_tokens: set[str] = set()
        self._used_publish_receipts: set[str] = set()

    def status(self) -> dict[str, object]:
        return {
            "module": "trade-scenario-visualizer",
            "version": "21.13",
            "status": "operational",
            "records": len(self._records),
            "safety_boundary": "visualization-only",
        }

    def create(self, payload: TradeScenarioCreate, actor: str = "system") -> TradeScenarioRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_index:
            raise TradeScenarioError(f"duplicate source_key; existing record={self._source_index[key]}")

        rr = self._risk_reward(payload)
        notes: list[str] = []
        if payload.risk_brain_hard_block:
            state = ScenarioState.BLOCKED
            notes.append("Risk Brain hard block is authoritative.")
        elif not payload.setup_evidence:
            state = ScenarioState.EVIDENCE_REQUIRED
            notes.append("Setup evidence is required before chart publication.")
        elif min(rr) < payload.risk_reward_minimum:
            state = ScenarioState.HUMAN_REVIEW_REQUIRED
            notes.append("One or more targets fall below the configured minimum risk/reward.")
        elif payload.confidence_score < 60:
            state = ScenarioState.HUMAN_REVIEW_REQUIRED
            notes.append("Low-confidence scenario requires explicit human review.")
        else:
            state = ScenarioState.READY

        record = TradeScenarioRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            symbol=payload.symbol.upper(),
            timeframe=payload.timeframe,
            direction=payload.direction,
            state=state,
            thesis=payload.thesis,
            entry_price=payload.entry_price,
            stop_price=payload.stop_price,
            target_prices=payload.target_prices,
            risk_reward_ratios=rr,
            confidence_score=payload.confidence_score,
            annotations=self._annotations(payload),
            tradingview_payload=self._tradingview_payload(payload, rr),
            notes=notes,
        )
        self._records[record.id] = record
        self._source_index[key] = record.id
        self._append_audit(record, actor, "create", None, record.state.value)
        return record

    def list(self, workspace_id: str) -> list[TradeScenarioRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> TradeScenarioRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise TradeScenarioError("record not found")
        return record

    def execute(self, workspace_id: str, record_id: str, action: ScenarioAction) -> TradeScenarioRecord:
        record = self.get(workspace_id, record_id)
        before = record.state.value

        if action.command == ScenarioCommand.APPROVE:
            if record.state not in {ScenarioState.READY, ScenarioState.HUMAN_REVIEW_REQUIRED}:
                raise TradeScenarioError("scenario is not approvable")
            token = action.review_token or token_urlsafe(24)
            if token in self._used_review_tokens:
                raise TradeScenarioError("review token replay detected")
            self._used_review_tokens.add(token)
            record.review_token = token
            record.state = ScenarioState.APPROVED
        elif action.command == ScenarioCommand.PUBLISH:
            if record.state != ScenarioState.APPROVED:
                raise TradeScenarioError("only approved scenarios can be published")
            if not action.publish_receipt:
                raise TradeScenarioError("publish receipt is required")
            if action.publish_receipt in self._used_publish_receipts:
                raise TradeScenarioError("publish receipt replay detected")
            self._used_publish_receipts.add(action.publish_receipt)
            record.publish_receipt = action.publish_receipt
            record.state = ScenarioState.PUBLISHED
        elif action.command == ScenarioCommand.INVALIDATE:
            if record.state == ScenarioState.ARCHIVED:
                raise TradeScenarioError("archived scenario cannot be invalidated")
            record.state = ScenarioState.INVALIDATED
            if action.reason:
                record.notes.append(action.reason)
        elif action.command == ScenarioCommand.ARCHIVE:
            record.state = ScenarioState.ARCHIVED

        record.updated_at = datetime.utcnow()
        self._append_audit(record, action.actor, action.command.value, before, record.state.value)
        return record

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    @staticmethod
    def _risk_reward(payload: TradeScenarioCreate) -> list[float]:
        risk = abs(payload.entry_price - payload.stop_price)
        if risk == 0:
            raise TradeScenarioError("entry and stop cannot be equal")
        return [round(abs(target - payload.entry_price) / risk, 3) for target in payload.target_prices]

    @staticmethod
    def _annotations(payload: TradeScenarioCreate) -> list[ChartAnnotation]:
        annotations = [
            ChartAnnotation(annotation_type="line", label="Entry", price=payload.entry_price),
            ChartAnnotation(annotation_type="line", label="Stop loss", price=payload.stop_price),
        ]
        annotations.extend(
            ChartAnnotation(annotation_type="line", label=f"TP{index}", price=target)
            for index, target in enumerate(payload.target_prices, start=1)
        )
        annotations.extend(
            ChartAnnotation(
                annotation_type="box",
                label=zone.label,
                price_low=zone.low,
                price_high=zone.high,
                metadata={"kind": zone.kind},
            )
            for zone in payload.zones
        )
        annotations.extend(
            ChartAnnotation(
                annotation_type="label" if point.kind == "note" else "arrow",
                label=point.label,
                price=point.price,
                timestamp=point.timestamp,
                metadata={"kind": point.kind},
            )
            for point in payload.points
        )
        return annotations

    @staticmethod
    def _tradingview_payload(payload: TradeScenarioCreate, rr: list[float]) -> dict[str, object]:
        return {
            "schema": "phoenix.trade-scenario.v1",
            "symbol": payload.symbol.upper(),
            "timeframe": payload.timeframe,
            "direction": payload.direction.value,
            "entry": payload.entry_price,
            "stop": payload.stop_price,
            "targets": [
                {"price": target, "risk_reward": ratio}
                for target, ratio in zip(payload.target_prices, rr, strict=True)
            ],
            "thesis": payload.thesis,
            "zones": [zone.model_dump() for zone in payload.zones],
            "points": [point.model_dump(mode="json") for point in payload.points],
            "execution_enabled": False,
        }

    def _append_audit(
        self,
        record: TradeScenarioRecord,
        actor: str,
        action: str,
        from_state: str | None,
        to_state: str,
    ) -> None:
        self._audit.append(
            AuditEvent(
                workspace_id=record.workspace_id,
                record_id=record.id,
                action=action,
                actor=actor,
                from_state=from_state,
                to_state=to_state,
            )
        )
