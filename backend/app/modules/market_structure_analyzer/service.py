from __future__ import annotations

from datetime import datetime, timezone
from secrets import token_urlsafe

from .models import (
    AuditEvent,
    MarketBias,
    MarketStructureCreate,
    MarketStructureRecord,
    StructureAction,
    StructureCommand,
    StructureSignal,
    StructureState,
)


class MarketStructureError(RuntimeError):
    pass


class MarketStructureAnalyzerService:
    """Governed SMC/ICT structure analysis. It never places or modifies trades."""

    def __init__(self) -> None:
        self._records: dict[str, MarketStructureRecord] = {}
        self._source_index: dict[tuple[str, str], str] = {}
        self._audit: list[AuditEvent] = []
        self._used_approval_tokens: set[str] = set()
        self._used_receipts: set[str] = set()

    def status(self) -> dict[str, object]:
        return {
            "module": "market-structure-analyzer",
            "version": "21.14",
            "status": "operational",
            "records": len(self._records),
            "safety_boundary": "analysis-only",
        }

    def create(self, payload: MarketStructureCreate, actor: str = "system") -> MarketStructureRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_index:
            raise MarketStructureError(f"duplicate source_key; existing record={self._source_index[key]}")

        if payload.risk_brain_hard_block:
            state = StructureState.BLOCKED
            findings = ["Risk Brain hard block is authoritative."]
            record = self._base_record(payload, state, findings)
        elif not payload.evidence_refs:
            state = StructureState.EVIDENCE_REQUIRED
            findings = ["Market-structure evidence references are required."]
            record = self._base_record(payload, state, findings)
        else:
            record = self._analyze(payload)

        self._records[record.id] = record
        self._source_index[key] = record.id
        self._log(record, "create", actor, None, record.state.value, "; ".join(record.findings))
        return record

    def list(self, workspace_id: str) -> list[MarketStructureRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> MarketStructureRecord:
        record = self._records.get(record_id)
        if not record or record.workspace_id != workspace_id:
            raise MarketStructureError("record not found")
        return record

    def execute(self, workspace_id: str, record_id: str, action: StructureAction) -> MarketStructureRecord:
        record = self.get(workspace_id, record_id)
        before = record.state.value

        if action.command == StructureCommand.APPROVE:
            if record.state not in {StructureState.STRUCTURE_READY, StructureState.HUMAN_REVIEW_REQUIRED}:
                raise MarketStructureError("record is not approvable")
            token = action.approval_token or token_urlsafe(24)
            if token in self._used_approval_tokens:
                raise MarketStructureError("approval token replay detected")
            self._used_approval_tokens.add(token)
            record.approval_token = token
            record.state = StructureState.APPROVED
        elif action.command == StructureCommand.ISSUE:
            if record.state != StructureState.APPROVED:
                raise MarketStructureError("only approved structure can be issued")
            if not action.downstream_receipt:
                raise MarketStructureError("downstream receipt is required")
            if action.downstream_receipt in self._used_receipts:
                raise MarketStructureError("downstream receipt replay detected")
            self._used_receipts.add(action.downstream_receipt)
            record.downstream_receipt = action.downstream_receipt
            record.state = StructureState.ISSUED_TO_VISUALIZER
        elif action.command == StructureCommand.INVALIDATE:
            if record.state == StructureState.ARCHIVED:
                raise MarketStructureError("archived record cannot be invalidated")
            record.state = StructureState.INVALIDATED
        elif action.command == StructureCommand.ARCHIVE:
            record.state = StructureState.ARCHIVED

        if action.reason:
            record.findings.append(action.reason)
        record.updated_at = datetime.now(timezone.utc)
        self._log(record, action.command.value, action.actor, before, record.state.value, action.reason or "")
        return record

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    @staticmethod
    def _base_record(
        payload: MarketStructureCreate,
        state: StructureState,
        findings: list[str],
    ) -> MarketStructureRecord:
        return MarketStructureRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            symbol=payload.symbol.upper(),
            timeframe=payload.timeframe,
            higher_timeframe=payload.higher_timeframe,
            state=state,
            findings=findings,
        )

    def _analyze(self, payload: MarketStructureCreate) -> MarketStructureRecord:
        highs = [item.price for item in payload.swings if item.kind == "high"]
        lows = [item.price for item in payload.swings if item.kind == "low"]
        if len(highs) < 2 or len(lows) < 2:
            raise MarketStructureError("at least two swing highs and two swing lows are required")

        bullish_structure = highs[-1] > highs[-2] and lows[-1] > lows[-2]
        bearish_structure = highs[-1] < highs[-2] and lows[-1] < lows[-2]
        bias = MarketBias.BULLISH if bullish_structure else MarketBias.BEARISH if bearish_structure else MarketBias.NEUTRAL

        range_high = max(highs[-2:])
        range_low = min(lows[-2:])
        span = max(range_high - range_low, 1e-9)
        position = max(0.0, min(100.0, (payload.current_price - range_low) / span * 100))

        active_zones = [zone for zone in payload.zones if not zone.mitigated]
        liquidity_prices = [
            price
            for zone in active_zones
            if zone.kind == "liquidity"
            for price in (zone.low, zone.high)
        ]
        above = [price for price in liquidity_prices if price > payload.current_price]
        below = [price for price in liquidity_prices if price < payload.current_price]

        weighted = [
            ("structure", bias != MarketBias.NEUTRAL, 25.0, f"Detected {bias.value} swing structure."),
            ("bos", payload.bos_confirmed, 15.0, "Break of structure confirmation."),
            ("choch", payload.choch_confirmed, 10.0, "Change of character confirmation."),
            ("liquidity-sweep", payload.liquidity_sweep, 15.0, "Liquidity sweep confirmation."),
            ("displacement", payload.displacement_confirmed, 15.0, "Displacement confirmation."),
            ("active-zone", bool(active_zones), 10.0, "Unmitigated point-of-interest zone available."),
            ("session", payload.session_alignment, 10.0, "Trading-session alignment."),
        ]
        signals = [
            StructureSignal(
                key=key,
                present=present,
                weight=weight,
                contribution=weight if present else 0,
                detail=detail,
            )
            for key, present, weight, detail in weighted
        ]
        score = sum(item.contribution for item in signals)
        findings: list[str] = []
        if payload.news_risk_active:
            score = max(0.0, score - 25)
            findings.append("Active news risk reduced the confluence score by 25 points.")
        if bias == MarketBias.BULLISH and position > 70:
            findings.append("Bullish structure is trading in premium; pullback confirmation is preferred.")
        if bias == MarketBias.BEARISH and position < 30:
            findings.append("Bearish structure is trading in discount; retracement confirmation is preferred.")
        if bias == MarketBias.NEUTRAL:
            findings.append("Swing structure is mixed and directional conviction is limited.")

        state = (
            StructureState.STRUCTURE_READY
            if score >= payload.minimum_confluence_score and bias != MarketBias.NEUTRAL and not payload.news_risk_active
            else StructureState.HUMAN_REVIEW_REQUIRED
        )
        if score < payload.minimum_confluence_score:
            findings.append("Confluence score is below the configured minimum.")

        return MarketStructureRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            symbol=payload.symbol.upper(),
            timeframe=payload.timeframe,
            higher_timeframe=payload.higher_timeframe,
            state=state,
            bias=bias,
            confluence_score=round(score, 2),
            premium_discount_position=round(position, 2),
            nearest_liquidity_above=min(above) if above else None,
            nearest_liquidity_below=max(below) if below else None,
            active_zones=active_zones,
            signals=signals,
            findings=findings,
        )

    def _log(
        self,
        record: MarketStructureRecord,
        action: str,
        actor: str,
        from_state: str | None,
        to_state: str,
        detail: str,
    ) -> None:
        self._audit.append(
            AuditEvent(
                workspace_id=record.workspace_id,
                record_id=record.id,
                action=action,
                actor=actor,
                from_state=from_state,
                to_state=to_state,
                detail=detail,
            )
        )
