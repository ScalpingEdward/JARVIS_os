from uuid import UUID

from .models import (
    BacktestComparison,
    BacktestComparisonRequest,
    BacktestJob,
    BacktestJobCreate,
    BacktestingLabStatus,
)


class BacktestUnavailable(RuntimeError):
    """No real backtest can run here -- said instead of inventing metrics."""


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
        """Refuses: there is no price data behind this lab yet.

        Until 2026-10-18 this computed net profit, win rate, Sharpe and the rest from a formula over
        the request (bars, costs, risk) -- no prices involved -- and returned them as a completed
        backtest. A strategy "tested" here got plausible numbers that meant nothing. It comes back
        when a job runs the strategy over real bars (the honest pattern: smartmoney/backtest.py,
        prices from MT5 via tools/insider_backtest.py)."""
        raise BacktestUnavailable(
            f"no price data connected -- this lab does not run real backtests yet "
            f"({payload.dataset.symbol} {payload.dataset.timeframe} was not tested)")

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
