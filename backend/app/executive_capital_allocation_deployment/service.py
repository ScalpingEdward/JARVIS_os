from datetime import datetime, timezone
from threading import RLock
from uuid import UUID

from .models import (
    AllocationAssessment,
    AllocationInput,
    AllocationScores,
    AllocationState,
    AllocationStatusResponse,
    AuditRecord,
    DeploymentLine,
)


class ExecutiveCapitalAllocationDeploymentService:
    def __init__(self) -> None:
        self._items: dict[UUID, AllocationAssessment] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(100.0, value)), 2)

    def assess(self, payload: AllocationInput) -> AllocationAssessment:
        with self._lock:
            if any(item.workspace_id == payload.workspace_id and item.source_key == payload.source_key for item in self._items.values()):
                raise ValueError("An allocation assessment with this source key already exists in the workspace")

            deployable = payload.approved_total_capital * (1 - payload.reserve_capital_pct / 100)
            blocked = payload.risk_brain_state in {"blocked", "frozen"} or payload.promotion_state == "blocked"
            ranked = sorted(
                payload.candidates,
                key=lambda item: (item.confidence_score * 0.45 + item.stability_score * 0.4 - item.correlation_score * 0.15),
                reverse=True,
            )
            total_merit = sum(max(1.0, item.confidence_score + item.stability_score - item.correlation_score) for item in ranked)
            plan: list[DeploymentLine] = []
            reasons: list[str] = []

            for item in ranked:
                merit = max(1.0, item.confidence_score + item.stability_score - item.correlation_score)
                weight = merit / total_merit
                cap = deployable * weight
                item_reasons: list[str] = []
                action = "allocate"

                account_cap = payload.approved_total_capital * max(0, payload.max_account_exposure_pct - item.current_account_exposure_pct) / 100
                symbol_cap = payload.approved_total_capital * max(0, payload.max_symbol_exposure_pct - item.current_symbol_exposure_pct) / 100
                strategy_cap = payload.approved_total_capital * payload.max_strategy_exposure_pct / 100
                cap = min(cap, item.requested_capital, account_cap, symbol_cap, strategy_cap)

                if blocked:
                    cap = 0
                    action = "blocked"
                    item_reasons.append("Risk or promotion governance blocks deployment")
                elif not payload.human_approval:
                    cap = 0
                    action = "hold"
                    item_reasons.append("Human deployment approval is required")
                elif item.correlation_score > payload.max_correlation_score:
                    cap *= 0.5
                    action = "reduce"
                    item_reasons.append("Correlation exceeds the configured threshold")
                if account_cap <= 0:
                    cap = 0
                    action = "hold"
                    item_reasons.append("Account concentration limit is exhausted")
                if symbol_cap <= 0:
                    cap = 0
                    action = "hold"
                    item_reasons.append("Symbol concentration limit is exhausted")
                if not item_reasons:
                    item_reasons.append("Candidate fits confidence, stability and concentration limits")

                approved_risk = item.requested_risk_pct * (0.5 if action == "reduce" else 1.0) if cap > 0 else 0.0
                plan.append(
                    DeploymentLine(
                        strategy_id=item.strategy_id,
                        account_id=item.account_id,
                        symbol=item.symbol,
                        approved_capital=round(cap, 2),
                        approved_risk_pct=round(approved_risk, 2),
                        allocation_weight_pct=round((cap / payload.approved_total_capital) * 100, 2),
                        action=action,
                        reasons=item_reasons,
                    )
                )

            allocated = round(sum(item.approved_capital for item in plan), 2)
            reserve = round(payload.approved_total_capital * payload.reserve_capital_pct / 100, 2)
            unallocated = round(max(0.0, payload.approved_total_capital - reserve - allocated), 2)
            correlations = [item.correlation_score for item in payload.candidates]
            concentrations = [max(item.current_account_exposure_pct, item.current_symbol_exposure_pct) for item in payload.candidates]
            diversification = self._clamp(100 - sum(correlations) / len(correlations))
            concentration_safety = self._clamp(100 - sum(concentrations) / len(concentrations))
            risk_alignment = self._clamp(sum(item.stability_score for item in payload.candidates) / len(payload.candidates))
            capital_efficiency = self._clamp(100 * allocated / max(deployable, 1))
            deployment_confidence = self._clamp((diversification + concentration_safety + risk_alignment + capital_efficiency) / 4)

            if blocked:
                state = AllocationState.blocked
                reasons.append("Upstream risk or promotion governance blocks capital deployment")
            elif not payload.human_approval:
                state = AllocationState.hold
                reasons.append("Human approval is missing")
            elif allocated == 0:
                state = AllocationState.hold
                reasons.append("No candidate remains within concentration limits")
            elif any(item.action == "reduce" for item in plan):
                state = AllocationState.deploy_reduced
                reasons.append("Deployment is reduced because correlation requires tighter allocation")
            elif unallocated > deployable * 0.2:
                state = AllocationState.rebalance
                reasons.append("Material deployable capital remains unallocated")
            else:
                state = AllocationState.deploy_full
                reasons.append("Capital is diversified within approved limits")

            record = AllocationAssessment(
                workspace_id=payload.workspace_id,
                actor_id=payload.actor_id,
                source_key=payload.source_key,
                state=state,
                scores=AllocationScores(
                    capital_efficiency=capital_efficiency,
                    diversification=diversification,
                    concentration_safety=concentration_safety,
                    risk_alignment=risk_alignment,
                    deployment_confidence=deployment_confidence,
                ),
                deployment_plan=plan,
                allocated_capital=allocated,
                reserve_capital=reserve,
                unallocated_capital=unallocated,
                reasons=reasons,
                assessed_at=self._now(),
            )
            self._items[record.id] = record
            self._audit.append(AuditRecord(workspace_id=payload.workspace_id, action="capital-allocation-assessed", actor_id=payload.actor_id, assessment_id=record.id, details={"state": state.value, "allocated": allocated, "reserve": reserve}, created_at=self._now()))
            return record

    def list_assessments(self, workspace_id: str) -> list[AllocationAssessment]:
        with self._lock:
            return [item for item in self._items.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> AllocationAssessment | None:
        with self._lock:
            item = self._items.get(assessment_id)
            return item if item and item.workspace_id == workspace_id else None

    def status(self, workspace_id: str) -> AllocationStatusResponse:
        records = self.list_assessments(workspace_id)
        return AllocationStatusResponse(
            assessments=len(records),
            blocked=sum(item.state == AllocationState.blocked for item in records),
            held=sum(item.state == AllocationState.hold for item in records),
            rebalances=sum(item.state == AllocationState.rebalance for item in records),
            reduced_deployments=sum(item.state == AllocationState.deploy_reduced for item in records),
            full_deployments=sum(item.state == AllocationState.deploy_full for item in records),
        )

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        with self._lock:
            return [item for item in self._audit if item.workspace_id == workspace_id]


executive_capital_allocation_deployment_service = ExecutiveCapitalAllocationDeploymentService()
