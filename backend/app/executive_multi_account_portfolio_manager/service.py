from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AccountAllocationResult,
    MultiAccountAllocationCreate,
    MultiAccountAllocationExecuteRequest,
    MultiAccountAllocationRecord,
    MultiAccountPortfolioAudit,
    MultiAccountPortfolioState,
    MultiAccountPortfolioStatus,
)


class MultiAccountPortfolioManagerService:
    def __init__(self) -> None:
        self._records: dict[UUID, MultiAccountAllocationRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[MultiAccountPortfolioAudit] = []

    def create(self, payload: MultiAccountAllocationCreate) -> MultiAccountAllocationRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        state, detail, allocations, metrics = self._evaluate(payload)
        record = MultiAccountAllocationRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            allocations=allocations,
            **metrics,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, p: MultiAccountAllocationCreate):
        total_balance = sum(a.balance for a in p.accounts)
        total_equity = sum(a.equity for a in p.accounts)
        total_current_risk = sum(a.current_risk for a in p.accounts)
        eligible = []
        results: list[AccountAllocationResult] = []
        for account in p.accounts:
            reason = None
            if not account.enabled:
                reason = "account disabled"
            elif not account.account_risk_approved:
                reason = "account-risk approval required"
            elif not account.prop_rules_approved:
                reason = "prop-rule approval required"
            elif account.health_score < 50:
                reason = "account health degraded"
            elif account.current_risk >= account.max_risk:
                reason = "account capacity exhausted"
            capacity = max(0.0, account.max_risk - account.current_risk)
            score = max(0.0, account.health_score * (1 - account.correlation_score) * (account.equity / max(total_equity, 0.01)))
            result = AccountAllocationResult(account_id=account.account_id, capacity_remaining=round(capacity, 2), capital_allocation_score=round(score, 4), excluded=reason is not None, exclusion_reason=reason)
            results.append(result)
            if reason is None and capacity > 0:
                eligible.append((account, result, score))

        metrics = {
            "total_balance": round(total_balance, 2),
            "total_equity": round(total_equity, 2),
            "total_current_risk": round(total_current_risk, 2),
            "allocated_total_risk": 0.0,
            "portfolio_heat_pct": round(total_current_risk / max(p.max_portfolio_risk, 0.01) * 100, 4),
            "portfolio_health_score": round(sum(a.health_score for a in p.accounts) / len(p.accounts), 2),
        }
        if p.upstream_risk_brain_blocked:
            return MultiAccountPortfolioState.BLOCKED, "upstream Risk Brain hard block", results, metrics
        if not p.portfolio_risk_approved:
            return MultiAccountPortfolioState.PORTFOLIO_STATE_REQUIRED, "v19.04 risk-approved evidence required", results, metrics
        if not eligible:
            return MultiAccountPortfolioState.CAPACITY_EXHAUSTED, "no eligible account capacity", results, metrics
        available_portfolio = max(0.0, p.max_portfolio_risk - total_current_risk)
        target = min(p.requested_total_risk, available_portfolio, sum(item[1].capacity_remaining for item in eligible))
        if target <= 0:
            return MultiAccountPortfolioState.CAPACITY_EXHAUSTED, "portfolio risk capacity exhausted", results, metrics
        score_total = sum(item[2] for item in eligible)
        for _, result, score in eligible:
            weight = score / score_total if score_total > 0 else 1 / len(eligible)
            result.allocated_risk = round(min(result.capacity_remaining, target * weight), 2)
            result.weight_pct = round(weight * 100, 4)
        allocated = sum(r.allocated_risk for r in results)
        metrics["allocated_total_risk"] = round(allocated, 2)
        metrics["portfolio_heat_pct"] = round((total_current_risk + allocated) / max(p.max_portfolio_risk, 0.01) * 100, 4)
        if metrics["portfolio_heat_pct"] > p.max_portfolio_heat_pct:
            return MultiAccountPortfolioState.CAPITAL_CONSTRAINED, "portfolio heat ceiling exceeded", results, metrics
        weights = [r.weight_pct for r in results if not r.excluded]
        if weights and max(weights) - min(weights) > p.rebalance_threshold_pct:
            state, detail = MultiAccountPortfolioState.REBALANCING_REQUIRED, "allocation concentration requires rebalancing"
        elif any(r.excluded for r in results):
            state, detail = MultiAccountPortfolioState.ACCOUNT_EXCLUDED, "allocation prepared with excluded accounts"
        else:
            state, detail = MultiAccountPortfolioState.ALLOCATION_PENDING, "multi-account allocation ready for human approval"
        return state, detail, results, metrics

    def execute(self, record_id: UUID, workspace_id: str, request: MultiAccountAllocationExecuteRequest) -> MultiAccountAllocationRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("allocation record not found")
        approved = request.human_approved if request.human_approved is not None else record.request.human_approved
        if request.action == "rebalance":
            if not approved:
                raise ValueError("human approval required for rebalancing")
            record.state, record.detail = MultiAccountPortfolioState.MONITORING, "approved allocation rebalancing under monitoring"
        elif request.action == "activate":
            if not approved:
                raise ValueError("human approval required for allocation activation")
            if record.state in {MultiAccountPortfolioState.BLOCKED, MultiAccountPortfolioState.PORTFOLIO_STATE_REQUIRED, MultiAccountPortfolioState.CAPACITY_EXHAUSTED, MultiAccountPortfolioState.CAPITAL_CONSTRAINED}:
                raise ValueError("allocation cannot be activated from current state")
            record.state, record.detail = MultiAccountPortfolioState.ALLOCATION_APPROVED, "multi-account allocation approved"
        else:
            raise ValueError("unsupported action")
        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> MultiAccountAllocationRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[MultiAccountAllocationRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> MultiAccountPortfolioStatus:
        records = self.list_records(workspace_id)
        healthy = {MultiAccountPortfolioState.ALLOCATION_APPROVED, MultiAccountPortfolioState.MONITORING, MultiAccountPortfolioState.HEALTHY}
        blocked = {MultiAccountPortfolioState.BLOCKED, MultiAccountPortfolioState.CAPACITY_EXHAUSTED, MultiAccountPortfolioState.CAPITAL_CONSTRAINED, MultiAccountPortfolioState.FAILED}
        return MultiAccountPortfolioStatus(workspace_id=workspace_id, total_records=len(records), healthy_records=sum(r.state in healthy for r in records), blocked_records=sum(r.state in blocked for r in records))

    def audit_records(self, workspace_id: str) -> list[MultiAccountPortfolioAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: MultiAccountAllocationRecord, actor_id: str, action: str) -> None:
        self._audit.append(MultiAccountPortfolioAudit(record_id=record.id, workspace_id=record.workspace_id, actor_id=actor_id, action=action, state=record.state, detail=record.detail))


multi_account_portfolio_manager_service = MultiAccountPortfolioManagerService()
