from uuid import UUID

from .models import (
    BacktestComparison,
    BacktestComparisonRequest,
    BacktestJob,
    BacktestJobCreate,
    BacktestMetrics,
    BacktestingLabStatus,
    SplitMode,
)


class BacktestingLabService:
    def __init__(self) -> None:
        self._jobs: dict[UUID, BacktestJob] = {}

    def reset(self) -> None:
        self._jobs.clear()

    def status(self) -> BacktestingLabStatus:
        return BacktestingLabStatus(
            jobs=len(self._jobs),
            completed_jobs=sum(job.status.value == "completed" for job in self._jobs.values()),
        )

    def create(self, payload: BacktestJobCreate) -> BacktestJob:
        cost_penalty = (
            payload.costs.spread_points * 0.03
            + payload.costs.slippage_points * 0.04
            + payload.costs.commission_per_lot * 0.01
        )
        data_factor = min(payload.dataset.bars / 20_000, 1.0)
        walk_forward_bonus = 4.0 if payload.split_mode == SplitMode.walk_forward else 0.0
        risk_penalty = max(payload.risk_per_trade_pct - 1.0, 0) * 3.0
        net_profit = round(8.0 + data_factor * 7.0 - cost_penalty - risk_penalty, 2)
        drawdown = round(3.5 + payload.risk_per_trade_pct * 2.2 + cost_penalty * 0.3, 2)
        trades = max(20, int(payload.dataset.bars / 300))
        metrics = BacktestMetrics(
            net_profit_pct=net_profit,
            max_drawdown_pct=drawdown,
            win_rate_pct=round(51.0 + data_factor * 8.0, 2),
            profit_factor=round(max(0.1, 1.25 + data_factor * 0.55 - cost_penalty * 0.02), 2),
            expectancy_r=round(0.18 + data_factor * 0.22 - cost_penalty * 0.01, 2),
            trades=trades,
            sharpe_ratio=round(0.8 + data_factor * 0.9 - risk_penalty * 0.04, 2),
            stability_score=round(min(100.0, 58.0 + data_factor * 25.0 + walk_forward_bonus), 2),
        )
        warnings: list[str] = []
        if payload.split_mode == SplitMode.full_sample:
            warnings.append("Use walk-forward validation before considering deployment.")
        if payload.dataset.bars < 5_000:
            warnings.append("Dataset may be too small for robust conclusions.")
        if metrics.max_drawdown_pct > 10:
            warnings.append("Maximum drawdown exceeds conservative funded-account tolerance.")
        job = BacktestJob(request=payload, metrics=metrics, warnings=warnings)
        self._jobs[job.id] = job
        return job

    def list_all(self) -> list[BacktestJob]:
        return sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)

    def get(self, job_id: UUID) -> BacktestJob | None:
        return self._jobs.get(job_id)

    def compare(self, payload: BacktestComparisonRequest) -> BacktestComparison:
        jobs = [self._jobs[job_id] for job_id in payload.job_ids if job_id in self._jobs]
        if len(jobs) != len(payload.job_ids):
            raise KeyError("one or more backtest jobs were not found")

        def score(job: BacktestJob) -> float:
            return (
                job.metrics.net_profit_pct * 1.3
                + job.metrics.profit_factor * 12
                + job.metrics.sharpe_ratio * 10
                + job.metrics.stability_score * 0.35
                - job.metrics.max_drawdown_pct * 1.8
            )

        ranked = sorted(jobs, key=score, reverse=True)
        best = ranked[0]
        return BacktestComparison(
            ranked_job_ids=[job.id for job in ranked],
            best_job_id=best.id,
            rationale=[
                "Ranking balances return, profit factor, Sharpe ratio, stability and drawdown.",
                f"Best candidate: {best.id} with {best.metrics.net_profit_pct}% net profit and {best.metrics.max_drawdown_pct}% max drawdown.",
                "Results remain research evidence and require human review before any forward test.",
            ],
        )


backtesting_lab_service = BacktestingLabService()
