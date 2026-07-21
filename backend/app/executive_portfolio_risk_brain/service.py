from datetime import datetime, timezone
from uuid import UUID

from .models import (
    PortfolioRiskAssessment,
    PortfolioRiskAssessmentCreate,
    PortfolioRiskAudit,
    PortfolioRiskExecuteRequest,
    PortfolioRiskState,
    PortfolioRiskStatus,
)


class PortfolioRiskBrainService:
    def __init__(self) -> None:
        self._records: dict[UUID, PortfolioRiskAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[PortfolioRiskAudit] = []

    def create(self, payload: PortfolioRiskAssessmentCreate) -> PortfolioRiskAssessment:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        state, detail = self._evaluate(payload)
        metrics = self._metrics(payload)
        record = PortfolioRiskAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            **metrics,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _metrics(self, p: PortfolioRiskAssessmentCreate) -> dict[str, float | bool]:
        remaining = max(0.0, p.risk_budget_limit - p.risk_budget_used)
        projected_used = p.risk_budget_used + p.proposed_risk_amount
        projected_heat = projected_used / p.risk_budget_limit * 100
        return {
            "remaining_risk_budget": round(remaining, 2),
            "projected_portfolio_heat_pct": round(projected_heat, 4),
            "max_new_risk_amount": round(remaining, 2),
            "reduce_only": False,
            "trading_halted": False,
        }

    def _evaluate(self, p: PortfolioRiskAssessmentCreate) -> tuple[PortfolioRiskState, str]:
        if p.risk_brain_blocked:
            return PortfolioRiskState.BLOCKED, "upstream Risk Brain hard block"
        if not p.account_state_healthy or p.account_state_version != "19.03":
            return PortfolioRiskState.ACCOUNT_STATE_REQUIRED, "healthy v19.03 account state required"
        if not p.account_risk_approved or not p.prop_rules_approved:
            return PortfolioRiskState.BLOCKED, "account-risk and prop-rule approvals required"
        if p.current_drawdown_pct >= p.hard_halt_drawdown_pct:
            return PortfolioRiskState.HALT_REQUIRED, "hard drawdown halt threshold reached"
        if p.current_drawdown_pct >= p.drawdown_guard_pct:
            return PortfolioRiskState.DRAWDOWN_GUARD, "portfolio drawdown guard active"
        if p.daily_drawdown_pct >= p.daily_loss_guard_pct:
            return PortfolioRiskState.DAILY_LOSS_GUARD, "daily loss guard active"
        if p.margin_level <= p.min_margin_level:
            return PortfolioRiskState.MARGIN_GUARD, "minimum margin level breached"
        if p.largest_symbol_exposure_pct > p.max_symbol_exposure_pct:
            return PortfolioRiskState.CONCENTRATION_GUARD, "symbol concentration limit breached"
        if p.correlated_exposure_pct > p.max_correlated_exposure_pct:
            return PortfolioRiskState.CORRELATION_GUARD, "correlated exposure limit breached"
        if p.risk_budget_used + p.proposed_risk_amount > p.risk_budget_limit:
            return PortfolioRiskState.RISK_BUDGET_EXHAUSTED, "proposed risk exceeds remaining budget"
        projected_heat = (p.risk_budget_used + p.proposed_risk_amount) / p.risk_budget_limit * 100
        if projected_heat > p.max_portfolio_heat_pct or p.portfolio_heat_pct > p.max_portfolio_heat_pct:
            return PortfolioRiskState.PORTFOLIO_HEAT_HIGH, "portfolio heat ceiling breached"
        if not p.human_approved:
            return PortfolioRiskState.APPROVAL_REQUIRED, "human approval required before activation"
        return PortfolioRiskState.RISK_APPROVED, "portfolio risk approved"

    def execute(self, record_id: UUID, workspace_id: str, request: PortfolioRiskExecuteRequest) -> PortfolioRiskAssessment:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("risk assessment not found")
        if request.human_approved is not None:
            record.request.human_approved = request.human_approved
        state, detail = self._evaluate(record.request)
        if request.action == "halt":
            state, detail = PortfolioRiskState.HALT_REQUIRED, "manual governed trading halt"
        elif request.action == "reduce-only":
            state, detail = PortfolioRiskState.REDUCE_ONLY, "manual governed reduce-only mode"
        elif request.action not in {"activate", "reassess", "halt", "reduce-only"}:
            raise ValueError("unsupported risk action")
        record.state, record.detail = state, detail
        metrics = self._metrics(record.request)
        for key, value in metrics.items():
            setattr(record, key, value)
        record.reduce_only = state in {
            PortfolioRiskState.REDUCE_ONLY,
            PortfolioRiskState.DRAWDOWN_GUARD,
            PortfolioRiskState.DAILY_LOSS_GUARD,
            PortfolioRiskState.MARGIN_GUARD,
            PortfolioRiskState.CONCENTRATION_GUARD,
            PortfolioRiskState.CORRELATION_GUARD,
            PortfolioRiskState.RISK_BUDGET_EXHAUSTED,
            PortfolioRiskState.PORTFOLIO_HEAT_HIGH,
        }
        record.trading_halted = state == PortfolioRiskState.HALT_REQUIRED
        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> PortfolioRiskAssessment | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[PortfolioRiskAssessment]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> PortfolioRiskStatus:
        items = self.list_records(workspace_id)
        blocked = {PortfolioRiskState.BLOCKED, PortfolioRiskState.ACCOUNT_STATE_REQUIRED, PortfolioRiskState.FAILED}
        return PortfolioRiskStatus(
            workspace_id=workspace_id,
            total_records=len(items),
            approved_records=sum(item.state == PortfolioRiskState.RISK_APPROVED for item in items),
            blocked_records=sum(item.state in blocked for item in items),
            halted_records=sum(item.trading_halted for item in items),
        )

    def audit_records(self, workspace_id: str) -> list[PortfolioRiskAudit]:
        return [record for record in self._audit if record.workspace_id == workspace_id]

    def _log(self, record: PortfolioRiskAssessment, actor_id: str, action: str) -> None:
        self._audit.append(
            PortfolioRiskAudit(
                record_id=record.id,
                workspace_id=record.workspace_id,
                actor_id=actor_id,
                action=action,
                state=record.state,
                detail=record.detail,
            )
        )


portfolio_risk_brain_service = PortfolioRiskBrainService()
