from uuid import UUID

from .models import (
    CheckState,
    DiagnosticCheck,
    ReadinessRun,
    ReadinessRunCreate,
    ReadinessStatus,
)


class ReadinessCenterService:
    """Evaluates whether PHOENIX is safe and sufficiently configured to launch."""

    def __init__(self) -> None:
        self._runs: dict[UUID, ReadinessRun] = {}

    def reset(self) -> None:
        self._runs.clear()

    def run(self, payload: ReadinessRunCreate) -> ReadinessRun:
        checks = [DiagnosticCheck(**item.model_dump()) for item in payload.checks]
        required = [item for item in checks if item.required]
        blocked = [item for item in required if item.state == CheckState.blocked]
        unknown = [item for item in required if item.state == CheckState.unknown]
        degraded = [item for item in required if item.state == CheckState.degraded]
        ready = [item for item in required if item.state == CheckState.ready]

        denominator = max(len(required), 1)
        score = round((len(ready) + (0.5 * len(degraded))) / denominator, 3)
        launch_allowed = not blocked and not unknown and score >= 0.75
        state = self._state(blocked=blocked, unknown=unknown, degraded=degraded, launch_allowed=launch_allowed)

        blockers = [f"{item.name}: {item.detail or 'required check blocked'}" for item in blocked + unknown]
        warnings = [f"{item.name}: {item.detail or 'degraded'}" for item in degraded]
        actions = self._actions(blocked + unknown + degraded)
        if launch_allowed:
            actions.insert(0, f"Launch advisory mode for {payload.owner_salutation}; keep all gated actions manual.")

        record = ReadinessRun(
            environment=payload.environment,
            owner_salutation=payload.owner_salutation,
            state=state,
            score=score,
            launch_allowed=launch_allowed,
            blockers=blockers,
            warnings=warnings,
            next_actions=actions,
            checks=checks,
        )
        self._runs[record.id] = record
        return record.model_copy(deep=True)

    def list_all(self) -> list[ReadinessRun]:
        return [item.model_copy(deep=True) for item in sorted(self._runs.values(), key=lambda x: x.created_at, reverse=True)]

    def get(self, run_id: UUID) -> ReadinessRun | None:
        item = self._runs.get(run_id)
        return item.model_copy(deep=True) if item else None

    def latest(self) -> ReadinessRun | None:
        items = self.list_all()
        return items[0] if items else None

    def status(self) -> ReadinessStatus:
        latest = self.latest()
        if latest is None:
            return ReadinessStatus()
        return ReadinessStatus(
            latest_state=latest.state,
            latest_score=latest.score,
            total_runs=len(self._runs),
            launch_allowed=latest.launch_allowed,
            open_blockers=len(latest.blockers),
        )

    @staticmethod
    def _state(*, blocked: list[DiagnosticCheck], unknown: list[DiagnosticCheck], degraded: list[DiagnosticCheck], launch_allowed: bool) -> CheckState:
        if blocked or unknown:
            return CheckState.blocked
        if launch_allowed and not degraded:
            return CheckState.ready
        return CheckState.degraded

    @staticmethod
    def _actions(checks: list[DiagnosticCheck]) -> list[str]:
        actions: list[str] = []
        for item in checks:
            recommendation = item.remediation or f"Review and repair {item.name}."
            if recommendation not in actions:
                actions.append(recommendation)
        return actions


readiness_center_service = ReadinessCenterService()
