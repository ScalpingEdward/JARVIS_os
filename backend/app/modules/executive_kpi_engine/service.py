import hashlib
from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ExecutiveKPIAudit,
    ExecutiveKPICreate,
    ExecutiveKPIExecuteRequest,
    ExecutiveKPIRecord,
    ExecutiveKPIState,
    ExecutiveKPIStatus,
    KPIIndicator,
)


class ExecutiveKPIService:
    def __init__(self) -> None:
        self._records: dict[UUID, ExecutiveKPIRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._roadmap_records: set[tuple[str, str]] = set()
        self._receipts: set[tuple[str, str]] = set()
        self._audit: list[ExecutiveKPIAudit] = []

    def create(self, payload: ExecutiveKPICreate) -> ExecutiveKPIRecord:
        source_key = (payload.workspace_id, payload.source_key)
        roadmap_key = (payload.workspace_id, payload.roadmap_record_id)
        if source_key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        if roadmap_key in self._roadmap_records:
            raise ValueError("roadmap record already consumed")

        state, detail, indicators, coverage, governance = self._evaluate(payload)
        record = ExecutiveKPIRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            indicators=indicators,
            coverage_score=coverage,
            governance_score=governance,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._roadmap_records.add(roadmap_key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, payload: ExecutiveKPICreate):
        if payload.upstream_risk_brain_blocked:
            return ExecutiveKPIState.BLOCKED, "upstream Risk Brain hard block", [], 0, 0
        if not payload.v21_05_roadmap_approved:
            return ExecutiveKPIState.EVIDENCE_REQUIRED, "approved v21.05 roadmap evidence required", [], 0, 0
        if payload.roadmap_state not in {"approved", "issued-to-kpi"}:
            return ExecutiveKPIState.EVIDENCE_REQUIRED, "roadmap must be approved or issued-to-kpi", [], 0, 0
        if not payload.strategic_metrics or not payload.constraints or not payload.milestones:
            return ExecutiveKPIState.EVIDENCE_REQUIRED, "strategic metrics, constraints and milestones are mandatory", [], 0, 0
        if any(not milestone.dependency_ready for milestone in payload.milestones):
            return ExecutiveKPIState.BLOCKED, "dependency-blocked milestone cannot enter KPI governance", [], 0, 0

        indicators: list[KPIIndicator] = []
        warning_factor = max(0.0, 1 - payload.config.warning_threshold_pct / 100)
        critical_factor = max(0.0, 1 - payload.config.critical_threshold_pct / 100)

        total_budget = sum(item.budget for item in payload.milestones)
        total_value = sum(item.expected_value for item in payload.milestones)
        indicators.extend([
            KPIIndicator(
                key="portfolio-value-realization",
                name="Portfolio value realization",
                category="value",
                owner_role="executive-owner",
                target_value=round(total_value, 2),
                warning_value=round(total_value * warning_factor, 2),
                critical_value=round(total_value * critical_factor, 2),
                unit="currency",
                direction="higher-is-better",
                measurement_frequency=payload.config.measurement_frequency,
            ),
            KPIIndicator(
                key="portfolio-budget-adherence",
                name="Portfolio budget adherence",
                category="financial",
                owner_role="finance-owner",
                target_value=round(total_budget, 2),
                warning_value=round(total_budget * (1 + payload.config.warning_threshold_pct / 100), 2),
                critical_value=round(total_budget * (1 + payload.config.critical_threshold_pct / 100), 2),
                unit="currency",
                direction="lower-is-better",
                measurement_frequency=payload.config.measurement_frequency,
            ),
        ])

        for milestone in payload.milestones:
            indicators.append(KPIIndicator(
                key=f"milestone-{milestone.milestone_id}-completion",
                name=f"{milestone.title} completion",
                category="delivery",
                owner_role=milestone.owner_role,
                target_value=100,
                warning_value=round(100 * warning_factor, 2),
                critical_value=round(100 * critical_factor, 2),
                unit="percent",
                direction="higher-is-better",
                measurement_frequency=payload.config.measurement_frequency,
                source_milestone_id=milestone.milestone_id,
            ))
            indicators.append(KPIIndicator(
                key=f"milestone-{milestone.milestone_id}-value",
                name=f"{milestone.title} expected value",
                category="value",
                owner_role=milestone.owner_role,
                target_value=round(milestone.expected_value, 2),
                warning_value=round(milestone.expected_value * warning_factor, 2),
                critical_value=round(milestone.expected_value * critical_factor, 2),
                unit="currency",
                direction="higher-is-better",
                measurement_frequency=payload.config.measurement_frequency,
                source_milestone_id=milestone.milestone_id,
            ))

        milestone_coverage = min(100.0, len({i.source_milestone_id for i in indicators if i.source_milestone_id}) / len(payload.milestones) * 100)
        metric_coverage = min(100.0, len(indicators) / max(1, len(payload.strategic_metrics) + len(payload.milestones)) * 100)
        coverage = round((milestone_coverage * 0.6) + (metric_coverage * 0.4), 2)
        governance = round(min(100.0, payload.roadmap_confidence * 0.6 + coverage * 0.4), 2)

        if payload.roadmap_confidence < payload.config.minimum_confidence or coverage < 80:
            return ExecutiveKPIState.HUMAN_REVIEW_REQUIRED, "KPI set requires human review for confidence or coverage", indicators, coverage, governance
        return ExecutiveKPIState.KPI_SET_READY, "governed executive KPI set prepared", indicators, coverage, governance

    def execute(self, record_id: UUID, workspace_id: str, request: ExecutiveKPIExecuteRequest) -> ExecutiveKPIRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("executive KPI record not found")

        if request.action == "approve":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state not in {ExecutiveKPIState.KPI_SET_READY, ExecutiveKPIState.HUMAN_REVIEW_REQUIRED}:
                raise ValueError("approval unavailable")
            material = f"{workspace_id}:{record.id}:{record.request.roadmap_record_id}:{record.coverage_score}:{record.governance_score}"
            record.approval_token = hashlib.sha256(material.encode()).hexdigest()
            record.state = ExecutiveKPIState.APPROVED
            record.detail = "executive KPI set approved"
        elif request.action == "issue-to-risk-analysis":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state != ExecutiveKPIState.APPROVED or not record.approval_token:
                raise ValueError("approved KPI set required")
            if not request.risk_analysis_receipt_id:
                raise ValueError("risk analysis receipt id required")
            receipt_key = (workspace_id, request.risk_analysis_receipt_id)
            if receipt_key in self._receipts:
                raise ValueError("risk analysis receipt already consumed")
            self._receipts.add(receipt_key)
            record.issued_receipt_id = request.risk_analysis_receipt_id
            record.state = ExecutiveKPIState.ISSUED_TO_RISK_ANALYSIS
            record.detail = "approved KPI set issued to v21.07 strategic risk analysis"
        elif request.action == "reject":
            record.state = ExecutiveKPIState.REJECTED
            record.detail = request.resolution_note or "executive KPI set rejected"
        elif request.action == "archive":
            record.state = ExecutiveKPIState.ARCHIVED
            record.detail = "executive KPI record archived"
        else:
            raise ValueError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> ExecutiveKPIRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[ExecutiveKPIRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> ExecutiveKPIStatus:
        records = self.list_records(workspace_id)
        blocked_states = {ExecutiveKPIState.BLOCKED, ExecutiveKPIState.EVIDENCE_REQUIRED, ExecutiveKPIState.REJECTED, ExecutiveKPIState.FAILED}
        return ExecutiveKPIStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            ready_records=sum(record.state == ExecutiveKPIState.KPI_SET_READY for record in records),
            approved_records=sum(record.state == ExecutiveKPIState.APPROVED for record in records),
            issued_records=sum(record.state == ExecutiveKPIState.ISSUED_TO_RISK_ANALYSIS for record in records),
            review_records=sum(record.state == ExecutiveKPIState.HUMAN_REVIEW_REQUIRED for record in records),
            blocked_records=sum(record.state in blocked_states for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[ExecutiveKPIAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: ExecutiveKPIRecord, actor_id: str, action: str) -> None:
        self._audit.append(ExecutiveKPIAudit(
            record_id=record.id,
            workspace_id=record.workspace_id,
            actor_id=actor_id,
            action=action,
            state=record.state,
            detail=record.detail,
        ))


executive_kpi_service = ExecutiveKPIService()
