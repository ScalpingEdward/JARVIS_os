from datetime import datetime, timezone
from uuid import UUID

from .models import (
    StrategyIntelligenceAudit,
    StrategyIntelligenceState,
    StrategyIntelligenceStatus,
    StrategyRoutingCreate,
    StrategyRoutingExecuteRequest,
    StrategyRoutingRecord,
    StrategySignalResult,
)


class StrategyIntelligenceRouterService:
    def __init__(self) -> None:
        self._records: dict[UUID, StrategyRoutingRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[StrategyIntelligenceAudit] = []

    def create(self, payload: StrategyRoutingCreate) -> StrategyRoutingRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        state, detail, results, selected = self._evaluate(payload)
        record = StrategyRoutingRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            results=results,
            **selected,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, p: StrategyRoutingCreate):
        results: list[StrategySignalResult] = []
        candidates = []
        selected = {
            "selected_strategy_id": None,
            "selected_signal_id": None,
            "selected_symbol": None,
            "selected_side": None,
            "approved_risk": 0.0,
        }
        if p.upstream_risk_brain_blocked:
            return StrategyIntelligenceState.BLOCKED, "upstream Risk Brain hard block", results, selected
        if not p.allocation_approved:
            return StrategyIntelligenceState.ALLOCATION_REQUIRED, "v19.05 allocation-approved evidence required", results, selected
        if not p.account_risk_approved or not p.prop_rules_approved:
            return StrategyIntelligenceState.RISK_REJECTED, "account-risk and prop-rule approval required", results, selected

        for signal in p.signals:
            reason = None
            if signal.age_seconds > signal.max_age_seconds:
                reason = "signal stale"
            elif signal.duplicate:
                reason = "duplicate signal"
            elif signal.cooldown_active:
                reason = "strategy cooldown active"
            elif signal.confidence < p.minimum_confidence:
                reason = "confidence below threshold"
            elif signal.quality_score < p.minimum_quality:
                reason = "quality below threshold"
            elif signal.expected_rr < p.minimum_rr:
                reason = "expected RR below threshold"
            elif signal.correlation_score > p.maximum_correlation:
                reason = "correlation ceiling exceeded"
            elif signal.compatible_regimes and signal.market_regime not in signal.compatible_regimes:
                reason = "market regime mismatch"
            elif not signal.multi_timeframe_confirmed:
                reason = "multi-timeframe confirmation required"
            elif signal.proposed_risk > p.available_risk_budget:
                reason = "available risk budget exceeded"

            score = (
                signal.confidence * 0.35
                + signal.quality_score * 0.35
                + min(signal.expected_rr, 5.0) / 5.0 * 20
                + max(0, 10 - signal.priority * 0.05)
                - signal.correlation_score * 20
            )
            result = StrategySignalResult(
                strategy_id=signal.strategy_id,
                signal_id=signal.signal_id,
                score=round(score, 4),
                rejected=reason is not None,
                rejection_reason=reason,
            )
            results.append(result)
            if reason is None:
                candidates.append((signal, result))

        if not candidates:
            return StrategyIntelligenceState.SIGNAL_INVALID, "no eligible strategy signal", results, selected

        directions: dict[str, set[str]] = {}
        for signal, _ in candidates:
            directions.setdefault(signal.symbol, set()).add(signal.side.lower())
        conflicts = {symbol for symbol, sides in directions.items() if len(sides) > 1}
        if conflicts:
            for signal, result in candidates:
                if signal.symbol in conflicts:
                    result.rejected = True
                    result.rejection_reason = "same-symbol directional conflict"
            candidates = [(s, r) for s, r in candidates if s.symbol not in conflicts]
            if not candidates:
                return StrategyIntelligenceState.CONFLICT_DETECTED, "all eligible signals conflict", results, selected

        winner, winner_result = max(candidates, key=lambda item: (item[1].score, -item[0].priority))
        winner_result.selected = True
        selected.update(
            selected_strategy_id=winner.strategy_id,
            selected_signal_id=winner.signal_id,
            selected_symbol=winner.symbol,
            selected_side=winner.side.lower(),
            approved_risk=round(min(winner.proposed_risk, p.available_risk_budget), 2),
        )
        return StrategyIntelligenceState.APPROVAL_REQUIRED, "best governed signal selected; human approval required", results, selected

    def execute(self, record_id: UUID, workspace_id: str, request: StrategyRoutingExecuteRequest) -> StrategyRoutingRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("strategy routing record not found")
        approved = request.human_approved if request.human_approved is not None else record.request.human_approved
        if request.action == "route":
            if not approved:
                raise ValueError("human approval required for signal routing")
            if record.state != StrategyIntelligenceState.APPROVAL_REQUIRED:
                raise ValueError("signal cannot be routed from current state")
            record.state = StrategyIntelligenceState.ROUTED
            record.detail = "selected signal routed to governed execution boundary"
        elif request.action == "monitor":
            if record.state != StrategyIntelligenceState.ROUTED:
                raise ValueError("monitoring requires routed signal")
            record.state = StrategyIntelligenceState.MONITORING
            record.detail = "routed strategy signal under monitoring"
        else:
            raise ValueError("unsupported action")
        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> StrategyRoutingRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[StrategyRoutingRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> StrategyIntelligenceStatus:
        records = self.list_records(workspace_id)
        blocked = {
            StrategyIntelligenceState.BLOCKED,
            StrategyIntelligenceState.ALLOCATION_REQUIRED,
            StrategyIntelligenceState.SIGNAL_INVALID,
            StrategyIntelligenceState.CONFLICT_DETECTED,
            StrategyIntelligenceState.RISK_REJECTED,
            StrategyIntelligenceState.FAILED,
        }
        return StrategyIntelligenceStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            routed_records=sum(r.state in {StrategyIntelligenceState.ROUTED, StrategyIntelligenceState.MONITORING} for r in records),
            blocked_records=sum(r.state in blocked for r in records),
        )

    def audit_records(self, workspace_id: str) -> list[StrategyIntelligenceAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: StrategyRoutingRecord, actor_id: str, action: str) -> None:
        self._audit.append(
            StrategyIntelligenceAudit(
                record_id=record.id,
                workspace_id=record.workspace_id,
                actor_id=actor_id,
                action=action,
                state=record.state,
                detail=record.detail,
            )
        )


strategy_intelligence_router_service = StrategyIntelligenceRouterService()
