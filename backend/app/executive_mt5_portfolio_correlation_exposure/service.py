from uuid import UUID

from .models import (
    AuditRecord,
    PortfolioExposureAssessment,
    PortfolioExposureAssessmentCreate,
    PortfolioExposureExecuteRequest,
    PortfolioExposureState,
    PortfolioExposureStatus,
)


class PortfolioCorrelationExposureService:
    def __init__(self) -> None:
        self._records: dict[UUID, PortfolioExposureAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def _evaluate(self, payload: PortfolioExposureAssessmentCreate) -> tuple[PortfolioExposureState, list[str]]:
        if payload.risk_brain_blocked:
            return PortfolioExposureState.BLOCKED, ["Risk Brain blocked portfolio exposure"]
        if not payload.trading_window_ready:
            return PortfolioExposureState.TRADING_WINDOW_REQUIRED, ["v18.92 trading-window dependency is not ready"]
        if payload.snapshot_age_seconds > payload.max_snapshot_age_seconds:
            return PortfolioExposureState.SNAPSHOT_STALE, ["Position or account snapshot is stale"]
        if payload.correlation_age_seconds > payload.max_correlation_age_seconds:
            return PortfolioExposureState.CORRELATION_DATA_STALE, ["Correlation matrix is stale"]
        if payload.terminal_error:
            return PortfolioExposureState.FAILED, [payload.terminal_error]

        existing_symbol_notional = sum(p.notional for p in payload.positions if p.symbol == payload.proposed_symbol)
        if existing_symbol_notional + payload.proposed_notional > payload.max_symbol_notional:
            return PortfolioExposureState.SYMBOL_EXPOSURE_EXCEEDED, ["Proposed trade exceeds symbol notional limit"]

        currencies = {payload.proposed_base_currency, payload.proposed_quote_currency}
        for currency in currencies:
            current = sum(
                p.notional
                for p in payload.positions
                if currency in {p.base_currency, p.quote_currency}
            )
            if current + payload.proposed_notional > payload.max_currency_notional:
                return PortfolioExposureState.CURRENCY_EXPOSURE_EXCEEDED, [f"Proposed trade exceeds {currency} exposure limit"]

        directional = sum(p.notional for p in payload.positions if p.side == payload.proposed_side)
        if directional + payload.proposed_notional > payload.max_directional_notional:
            return PortfolioExposureState.DIRECTIONAL_EXPOSURE_EXCEEDED, ["Proposed trade exceeds directional exposure limit"]

        portfolio_risk = sum(p.risk_amount for p in payload.positions) + payload.proposed_risk_amount
        if portfolio_risk > payload.max_portfolio_risk_amount:
            return PortfolioExposureState.PORTFOLIO_RISK_EXCEEDED, ["Proposed trade exceeds portfolio risk budget"]

        open_symbols = {p.symbol for p in payload.positions}
        for pair in payload.correlations:
            matched = (
                pair.symbol_a == payload.proposed_symbol and pair.symbol_b in open_symbols
            ) or (
                pair.symbol_b == payload.proposed_symbol and pair.symbol_a in open_symbols
            )
            if matched and abs(pair.coefficient) > payload.max_pair_correlation:
                return PortfolioExposureState.CORRELATION_LIMIT_EXCEEDED, ["Proposed symbol exceeds pair-correlation limit"]

        if payload.projected_margin_level_percent < payload.minimum_margin_level_percent:
            return PortfolioExposureState.MARGIN_REJECTED, ["Projected margin level is below configured minimum"]
        if not payload.account_risk_approved or not payload.prop_rules_approved:
            return PortfolioExposureState.RISK_REJECTED, ["Account-risk and prop-rule approval are mandatory"]
        if not payload.human_approved:
            return PortfolioExposureState.APPROVAL_REQUIRED, ["Human approval is required"]
        if payload.positions and not payload.rebalance_plan_defined:
            return PortfolioExposureState.REBALANCE_REQUIRED, ["Portfolio rebalance plan is required for active exposure"]
        return PortfolioExposureState.PORTFOLIO_READY, []

    def create(self, payload: PortfolioExposureAssessmentCreate) -> PortfolioExposureAssessment:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("Duplicate source_key in workspace")
        state, reasons = self._evaluate(payload)
        record = PortfolioExposureAssessment(state=state, reasons=reasons, payload=payload)
        self._records[record.id] = record
        self._source_keys.add(key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, action="assessment-created", actor_id=payload.actor_id, record_id=record.id))
        return record

    def execute(self, record_id: UUID, workspace_id: str, request: PortfolioExposureExecuteRequest) -> PortfolioExposureAssessment:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("Portfolio exposure assessment not found")
        updated_payload = record.payload.model_copy(update=request.model_dump(exclude={"actor_id"}, exclude_none=True))
        state, reasons = self._evaluate(updated_payload)
        updated = record.model_copy(update={"payload": updated_payload, "state": state, "reasons": reasons})
        self._records[record_id] = updated
        self._audit.append(AuditRecord(workspace_id=workspace_id, action="portfolio-exposure-executed", actor_id=request.actor_id, record_id=record_id))
        return updated

    def get(self, record_id: UUID, workspace_id: str) -> PortfolioExposureAssessment | None:
        record = self._records.get(record_id)
        return record if record and record.payload.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[PortfolioExposureAssessment]:
        return [record for record in self._records.values() if record.payload.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> PortfolioExposureStatus:
        records = self.list_records(workspace_id)
        return PortfolioExposureStatus(workspace_id=workspace_id, latest_state=records[-1].state if records else None, count=len(records))

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]


portfolio_correlation_exposure_service = PortfolioCorrelationExposureService()
