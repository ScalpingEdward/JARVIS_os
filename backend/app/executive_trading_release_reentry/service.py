from datetime import datetime, timezone
from threading import RLock
from uuid import UUID

from .models import (
    AuditRecord,
    ReentryStage,
    ReleaseAssessment,
    ReleaseAssessmentCreate,
    ReleaseScores,
    ReleaseState,
    ReleaseStatusResponse,
    VerificationState,
)


class ExecutiveTradingReleaseReentryService:
    def __init__(self) -> None:
        self._items: dict[UUID, ReleaseAssessment] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(100.0, value)), 2)

    @staticmethod
    def _plan(final_state: ReleaseState, multiplier: float) -> list[ReentryStage]:
        stages = [
            ReentryStage(stage=1, mode=ReleaseState.shadow_only, max_risk_multiplier=0, minimum_observation_trades=5, minimum_stable_minutes=30, requirements=["No critical incident recurrence", "Data and broker health remain stable"]),
        ]
        if final_state in {ReleaseState.reduced_live, ReleaseState.full_live}:
            stages.append(ReentryStage(stage=2, mode=ReleaseState.reduced_live, max_risk_multiplier=min(multiplier, 0.25), minimum_observation_trades=5, minimum_stable_minutes=60, requirements=["Shadow verification passed", "Risk Brain remains normal or reduced"]))
        if final_state == ReleaseState.full_live:
            stages.append(ReentryStage(stage=3, mode=ReleaseState.reduced_live, max_risk_multiplier=min(multiplier, 0.5), minimum_observation_trades=10, minimum_stable_minutes=120, requirements=["No execution anomalies", "Readiness remains ready or conditional"]))
            stages.append(ReentryStage(stage=4, mode=ReleaseState.full_live, max_risk_multiplier=multiplier, minimum_observation_trades=20, minimum_stable_minutes=240, requirements=["Human release approval confirmed", "All verification gates remain passed"]))
        return stages

    def assess(self, payload: ReleaseAssessmentCreate) -> ReleaseAssessment:
        with self._lock:
            if any(item.workspace_id == payload.workspace_id and item.source_key == payload.source_key for item in self._items.values()):
                raise ValueError("A release assessment with this source key already exists in the workspace")

            failed = [gate.name for gate in payload.verification_gates if gate.state == VerificationState.failed and gate.blocking]
            warnings = [gate.name for gate in payload.verification_gates if gate.state == VerificationState.warning or (gate.state == VerificationState.failed and not gate.blocking)]
            reasons: list[str] = []

            hard_block = (
                payload.open_critical_incidents > 0
                or payload.incident_recovery_state not in {"resolved", "verified"}
                or payload.data_integrity_score < 70
                or payload.readiness_state == "blocked"
                or payload.risk_state in {"blocked", "frozen"}
                or payload.trading_decision in {"reject", "freeze"}
                or bool(failed)
            )

            gate_score = 100.0 if not payload.verification_gates else sum(gate.score for gate in payload.verification_gates) / len(payload.verification_gates)
            recovery_validation = self._clamp(payload.recovery_confidence * 0.55 + payload.data_integrity_score * 0.45)
            operational_stability = self._clamp(payload.stability_score - payload.open_warning_incidents * 5)
            risk_clearance = 100.0 if payload.risk_state == "normal" else 65.0 if payload.risk_state == "reduced" else 0.0
            evidence_quality = self._clamp(gate_score)
            release_confidence = self._clamp(recovery_validation * 0.3 + operational_stability * 0.25 + risk_clearance * 0.25 + evidence_quality * 0.2)

            if hard_block:
                state = ReleaseState.blocked
                multiplier = 0.0
                reasons.append("One or more mandatory safety gates prevent release")
            elif not payload.human_release_approved:
                state = ReleaseState.shadow_only
                multiplier = 0.0
                reasons.append("Human release approval is still required")
            elif payload.readiness_state == "wait" or payload.trading_decision in {"delay", "shadow"} or release_confidence < 65:
                state = ReleaseState.shadow_only
                multiplier = 0.0
                reasons.append("System must prove stability in shadow mode before live re-entry")
            elif warnings or payload.open_warning_incidents > 0 or payload.risk_state == "reduced" or payload.trading_decision == "reduce" or release_confidence < 85:
                state = ReleaseState.reduced_live
                multiplier = min(payload.requested_risk_multiplier, 0.5)
                reasons.append("Controlled live re-entry is permitted with reduced exposure")
            else:
                state = ReleaseState.full_live
                multiplier = payload.requested_risk_multiplier
                reasons.append("All release gates passed and full governed re-entry is permitted")

            if failed:
                reasons.append(f"Blocking gates failed: {', '.join(failed)}")
            if warnings:
                reasons.append(f"Non-blocking gate warnings: {', '.join(warnings)}")

            record = ReleaseAssessment(
                workspace_id=payload.workspace_id,
                actor_id=payload.actor_id,
                source_key=payload.source_key,
                symbol=payload.symbol,
                account_profile=payload.account_profile,
                state=state,
                approved_risk_multiplier=multiplier,
                scores=ReleaseScores(
                    recovery_validation=recovery_validation,
                    operational_stability=operational_stability,
                    risk_clearance=risk_clearance,
                    evidence_quality=evidence_quality,
                    release_confidence=release_confidence,
                ),
                failed_gates=failed,
                warnings=warnings,
                reasons=reasons,
                reentry_plan=self._plan(state, multiplier),
                assessed_at=self._now(),
            )
            self._items[record.id] = record
            self._audit.append(AuditRecord(workspace_id=payload.workspace_id, action="trading-release-assessed", actor_id=payload.actor_id, assessment_id=record.id, details={"state": state.value, "risk_multiplier": multiplier, "confidence": release_confidence}, created_at=self._now()))
            return record

    def list_assessments(self, workspace_id: str) -> list[ReleaseAssessment]:
        with self._lock:
            return [item for item in self._items.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> ReleaseAssessment | None:
        with self._lock:
            item = self._items.get(assessment_id)
            return item if item and item.workspace_id == workspace_id else None

    def status(self, workspace_id: str) -> ReleaseStatusResponse:
        records = self.list_assessments(workspace_id)
        return ReleaseStatusResponse(
            assessments=len(records),
            blocked=sum(item.state == ReleaseState.blocked for item in records),
            shadow_only=sum(item.state == ReleaseState.shadow_only for item in records),
            reduced_live=sum(item.state == ReleaseState.reduced_live for item in records),
            full_live=sum(item.state == ReleaseState.full_live for item in records),
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        with self._lock:
            return [item for item in self._audit if item.workspace_id == workspace_id]


executive_trading_release_reentry_service = ExecutiveTradingReleaseReentryService()
