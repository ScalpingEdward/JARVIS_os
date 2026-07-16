from datetime import datetime, timezone
from uuid import UUID

from .models import RuleKind, StrategyCreate, StrategyListResponse, StrategyRecord, StrategyStatus, StrategyStatusResponse, ValidationIssue


class StrategyBuilderService:
    def __init__(self) -> None:
        self._strategies: dict[UUID, StrategyRecord] = {}

    def reset(self) -> None:
        self._strategies.clear()

    def create(self, payload: StrategyCreate) -> StrategyRecord:
        record = StrategyRecord(**payload.model_dump())
        self._strategies[record.id] = record
        return record

    def get(self, strategy_id: UUID) -> StrategyRecord | None:
        return self._strategies.get(strategy_id)

    def list_all(self, status: StrategyStatus | None = None) -> StrategyListResponse:
        items = list(self._strategies.values())
        if status is not None:
            items = [item for item in items if item.status == status]
        items.sort(key=lambda item: item.updated_at, reverse=True)
        return StrategyListResponse(items=items, count=len(items))

    def validate(self, strategy_id: UUID) -> StrategyRecord | None:
        strategy = self._strategies.get(strategy_id)
        if strategy is None:
            return None
        issues: list[ValidationIssue] = []
        enabled = [rule for rule in strategy.rules if rule.enabled]
        entries = [rule for rule in enabled if rule.kind == RuleKind.entry]
        exits = [rule for rule in enabled if rule.kind == RuleKind.exit]
        filters = [rule for rule in enabled if rule.kind == RuleKind.filter]
        if not entries:
            issues.append(ValidationIssue(severity="error", code="missing_entry", message="No enabled entry rule"))
        if not exits:
            issues.append(ValidationIssue(severity="error", code="missing_exit", message="No enabled exit rule"))
        if strategy.risk.risk_per_trade_pct > strategy.risk.max_daily_risk_pct:
            issues.append(ValidationIssue(severity="error", code="risk_budget_invalid", message="Risk per trade exceeds daily risk budget"))
        if not strategy.risk.stop_loss_required:
            issues.append(ValidationIssue(severity="error", code="stop_loss_required", message="A stop loss is required"))
        if not filters:
            issues.append(ValidationIssue(severity="warning", code="no_market_filter", message="No market or session filter is enabled"))
        has_errors = any(issue.severity == "error" for issue in issues)
        strategy.issues = issues
        strategy.status = StrategyStatus.invalid if has_errors else StrategyStatus.validated
        strategy.backtest_ready = not has_errors
        strategy.updated_at = datetime.now(timezone.utc)
        strategy.version += 1
        return strategy

    def status(self) -> StrategyStatusResponse:
        records = list(self._strategies.values())
        return StrategyStatusResponse(
            strategies=len(records),
            validated=sum(item.status == StrategyStatus.validated for item in records),
            backtest_ready=sum(item.backtest_ready for item in records),
        )


strategy_builder_service = StrategyBuilderService()
