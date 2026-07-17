from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuditRecord, BudgetAction, EvaluationRecord, MeasurementCreate,
    MeasurementRecord, MetricsRecord, Mutation, SLOCreate, SLOHealth, SLORecord,
    SLOState, SLOStatus,
)


class SLOService:
    def __init__(self) -> None:
        self.slos: dict[UUID, SLORecord] = {}
        self.measurements: dict[UUID, MeasurementRecord] = {}
        self.evaluations: dict[UUID, EvaluationRecord] = {}
        self.audit: list[AuditRecord] = []

    def _audit(self, workspace_id: str, action: str, entity_type: str, entity_id: UUID | None, actor_id: str, **details) -> None:
        self.audit.append(AuditRecord(
            workspace_id=workspace_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            details=details,
        ))

    def status(self) -> SLOStatus:
        return SLOStatus(
            slos=len(self.slos),
            measurements=len(self.measurements),
            evaluations=len(self.evaluations),
            exhausted_slos=sum(item.health == SLOHealth.EXHAUSTED for item in self.slos.values()),
        )

    def create_slo(self, payload: SLOCreate) -> SLORecord:
        if any(
            item.workspace_id == payload.workspace_id
            and item.slo_key == payload.slo_key
            and item.state != SLOState.RETIRED
            for item in self.slos.values()
        ):
            raise ValueError("active SLO key already exists")
        data = payload.model_dump(exclude={
            "human_approved", "automatic_activation", "automatic_enforcement", "external_provider"
        })
        item = SLORecord(**data)
        self.slos[item.id] = item
        self._audit(item.workspace_id, "slo.created", "slo", item.id, item.owner_id)
        return item

    def list_slos(self, workspace_id: str) -> list[SLORecord]:
        return [item for item in self.slos.values() if item.workspace_id == workspace_id]

    def get_slo(self, slo_id: UUID, workspace_id: str) -> SLORecord | None:
        item = self.slos.get(slo_id)
        return item if item and item.workspace_id == workspace_id else None

    def set_state(self, slo_id: UUID, workspace_id: str, payload: Mutation, state: SLOState) -> SLORecord | None:
        item = self.slos.get(slo_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"slo.{state.value}", "slo", item.id, payload.requester_id, reason=payload.reason)
        return item

    def record_measurement(self, payload: MeasurementCreate) -> tuple[MeasurementRecord, EvaluationRecord]:
        slo = self.slos.get(payload.slo_id)
        if not slo or slo.workspace_id != payload.workspace_id or slo.state != SLOState.ACTIVE:
            raise ValueError("active workspace SLO not found")
        observed = 100.0 if payload.total_events == 0 else (payload.good_events / payload.total_events) * 100.0
        measurement = MeasurementRecord(
            **payload.model_dump(exclude={"human_approved", "collect_external", "enforce_action"}),
            observed_percent=round(observed, 6),
            error_percent=round(100.0 - observed, 6),
        )
        self.measurements[measurement.id] = measurement

        allowed_error_fraction = max(0.0, (100.0 - slo.objective_percent) / 100.0)
        allowed_bad = payload.total_events * allowed_error_fraction
        consumed_bad = payload.total_events - payload.good_events
        if allowed_bad == 0:
            burn_rate = 0.0 if consumed_bad == 0 else float("inf")
            remaining = 100.0 if consumed_bad == 0 else 0.0
        else:
            burn_rate = consumed_bad / allowed_bad
            remaining = max(0.0, 100.0 * (1.0 - burn_rate))

        if remaining <= slo.critical_budget_remaining_percent:
            health = SLOHealth.EXHAUSTED
            action = BudgetAction.FREEZE_PLANNED
        elif remaining <= slo.warning_budget_remaining_percent or burn_rate >= slo.slow_burn_threshold:
            health = SLOHealth.AT_RISK
            action = BudgetAction.REVIEW
        else:
            health = SLOHealth.HEALTHY
            action = BudgetAction.NONE
        if burn_rate >= slo.fast_burn_threshold:
            action = BudgetAction.ESCALATION_PLANNED

        evaluation = EvaluationRecord(
            workspace_id=slo.workspace_id,
            slo_id=slo.id,
            measurement_id=measurement.id,
            objective_percent=slo.objective_percent,
            observed_percent=measurement.observed_percent,
            allowed_bad_events=round(allowed_bad, 6),
            consumed_bad_events=float(consumed_bad),
            budget_remaining_percent=round(remaining, 6),
            burn_rate=round(burn_rate, 6) if burn_rate != float("inf") else 1_000_000_000.0,
            health=health,
            recommended_action=action,
            requires_review=health != SLOHealth.HEALTHY,
        )
        self.evaluations[evaluation.id] = evaluation
        slo.health = health
        slo.updated_at = datetime.now(timezone.utc)
        self._audit(
            slo.workspace_id,
            "slo.evaluated",
            "evaluation",
            evaluation.id,
            payload.requester_id,
            slo_id=str(slo.id),
            health=health.value,
            burn_rate=evaluation.burn_rate,
        )
        return measurement, evaluation

    def list_measurements(self, workspace_id: str, slo_id: UUID | None = None) -> list[MeasurementRecord]:
        return [
            item for item in self.measurements.values()
            if item.workspace_id == workspace_id and (slo_id is None or item.slo_id == slo_id)
        ]

    def list_evaluations(self, workspace_id: str, slo_id: UUID | None = None) -> list[EvaluationRecord]:
        return [
            item for item in self.evaluations.values()
            if item.workspace_id == workspace_id and (slo_id is None or item.slo_id == slo_id)
        ]

    def metrics(self, workspace_id: str) -> MetricsRecord:
        slos = [item for item in self.slos.values() if item.workspace_id == workspace_id]
        return MetricsRecord(
            workspace_id=workspace_id,
            slos=len(slos),
            active_slos=sum(item.state == SLOState.ACTIVE for item in slos),
            healthy_slos=sum(item.health == SLOHealth.HEALTHY for item in slos),
            at_risk_slos=sum(item.health == SLOHealth.AT_RISK for item in slos),
            exhausted_slos=sum(item.health == SLOHealth.EXHAUSTED for item in slos),
            measurements=sum(item.workspace_id == workspace_id for item in self.measurements.values()),
            evaluations=sum(item.workspace_id == workspace_id for item in self.evaluations.values()),
        )

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self.audit if item.workspace_id == workspace_id]


slo_service = SLOService()
