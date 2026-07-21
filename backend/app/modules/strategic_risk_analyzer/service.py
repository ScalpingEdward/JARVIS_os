from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from secrets import token_urlsafe

from .models import (
    AuditEntry,
    RiskAssessment,
    RiskState,
    StrategicRiskCreate,
    StrategicRiskExecute,
    StrategicRiskRecord,
)


class StrategicRiskService:
    def __init__(self) -> None:
        self._records: dict[str, StrategicRiskRecord] = {}
        self._audits: list[AuditEntry] = []
        self._source_keys: set[tuple[str, str]] = set()
        self._receipts: set[str] = set()
        self._signals: dict[str, StrategicRiskCreate] = {}

    def status(self) -> dict[str, object]:
        return {
            "module": "strategic-risk-analyzer",
            "version": "21.07",
            "status": "ready",
            "records": len(self._records),
            "safety_boundary": "analysis-and-governance-only",
        }

    def create(self, payload: StrategicRiskCreate, actor: str = "system") -> StrategicRiskRecord:
        source_identity = (payload.workspace_id, payload.source_key)
        if source_identity in self._source_keys:
            raise ValueError("duplicate source_key in workspace")

        reasons: list[str] = []
        if payload.risk_brain_status == "blocked":
            state = RiskState.BLOCKED
            reasons.append("upstream Risk Brain hard block")
        elif not payload.executive_kpi_approved or not payload.executive_kpi_evidence:
            state = RiskState.EVIDENCE_REQUIRED
            reasons.append("approved v21.06 KPI evidence is required")
        elif any(signal.dependency_blocked for signal in payload.signals):
            state = RiskState.BLOCKED
            reasons.append("dependency-blocked risk signal present")
        else:
            state = RiskState.ANALYSIS_PENDING

        record = StrategicRiskRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            executive_kpi_record_id=payload.executive_kpi_record_id,
            state=state,
            portfolio_confidence=payload.portfolio_confidence,
            risk_appetite=payload.risk_appetite,
            max_residual_exposure=payload.max_residual_exposure,
            reasons=reasons,
        )
        self._records[record.record_id] = record
        self._signals[record.record_id] = payload
        self._source_keys.add(source_identity)
        self._audit(record, "create", actor, state.value)
        return record

    def list(self, workspace_id: str) -> list[StrategicRiskRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, record_id: str, workspace_id: str) -> StrategicRiskRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise KeyError("record not found")
        return record

    def execute(self, record_id: str, workspace_id: str, command: StrategicRiskExecute) -> StrategicRiskRecord:
        record = self.get(record_id, workspace_id)
        if command.action == "analyze":
            self._analyze(record, command.actor)
        elif command.action == "approve":
            self._approve(record, command)
        elif command.action == "reject":
            record.state = RiskState.REJECTED
            record.reasons.append(command.reason or "rejected by human reviewer")
            self._touch(record)
            self._audit(record, "reject", command.actor, record.reasons[-1])
        elif command.action == "issue":
            self._issue(record, command)
        elif command.action == "archive":
            record.state = RiskState.ARCHIVED
            self._touch(record)
            self._audit(record, "archive", command.actor, "record archived")
        return record

    def audit(self, workspace_id: str) -> list[AuditEntry]:
        return [entry for entry in self._audits if entry.workspace_id == workspace_id]

    def _analyze(self, record: StrategicRiskRecord, actor: str) -> None:
        if record.state != RiskState.ANALYSIS_PENDING:
            raise ValueError("record is not eligible for analysis")
        payload = self._signals[record.record_id]
        assessments: list[RiskAssessment] = []
        for signal in payload.signals:
            inherent = min(100.0, signal.probability * signal.impact * (0.7 + signal.velocity / 200))
            mitigation_strength = min(75.0, 20 + len(signal.mitigation.split()) * 2.5)
            detectability_penalty = (100 - signal.detectability) * 0.12
            residual = max(0.0, min(100.0, inherent * (1 - mitigation_strength / 100) + detectability_penalty))
            if residual >= 70:
                severity, treatment = "critical", "avoid"
            elif residual >= 45:
                severity, treatment = "high", "escalate"
            elif residual >= 20:
                severity, treatment = "moderate", "mitigate"
            else:
                severity, treatment = "low", "accept"
            assessments.append(RiskAssessment(
                signal_id=signal.signal_id,
                inherent_score=round(inherent, 2),
                mitigation_strength=round(mitigation_strength, 2),
                residual_score=round(residual, 2),
                severity=severity,
                treatment=treatment,
                rationale=f"{signal.category} risk evaluated against probability, impact, velocity and detectability",
            ))

        record.assessments = assessments
        record.aggregate_inherent_risk = round(sum(a.inherent_score for a in assessments) / len(assessments), 2)
        record.aggregate_residual_risk = round(sum(a.residual_score for a in assessments) / len(assessments), 2)
        categories = Counter(signal.category for signal in payload.signals)
        record.concentration_score = round(max(categories.values()) / len(payload.signals) * 100, 2)
        record.critical_risk_count = sum(a.severity == "critical" for a in assessments)

        needs_review = (
            record.aggregate_residual_risk > record.max_residual_exposure
            or record.critical_risk_count > 0
            or record.concentration_score >= 60
            or record.portfolio_confidence < 60
        )
        record.state = RiskState.HUMAN_REVIEW_REQUIRED if needs_review else RiskState.RISK_REGISTER_READY
        if needs_review:
            record.reasons.append("residual exposure, concentration, critical risk or confidence requires human review")
        self._touch(record)
        self._audit(record, "analyze", actor, record.state.value)

    def _approve(self, record: StrategicRiskRecord, command: StrategicRiskExecute) -> None:
        if record.state not in {RiskState.RISK_REGISTER_READY, RiskState.HUMAN_REVIEW_REQUIRED}:
            raise ValueError("record is not eligible for approval")
        if record.critical_risk_count and not command.reason:
            raise ValueError("critical-risk approval requires explicit rationale")
        record.approval_token = token_urlsafe(24)
        record.state = RiskState.APPROVED
        self._touch(record)
        self._audit(record, "approve", command.actor, command.reason or "approved by human reviewer")

    def _issue(self, record: StrategicRiskRecord, command: StrategicRiskExecute) -> None:
        if record.state != RiskState.APPROVED:
            raise ValueError("only approved records may be issued")
        if not command.approval_token or command.approval_token != record.approval_token:
            raise ValueError("invalid approval token")
        if not command.receipt:
            raise ValueError("downstream receipt is required")
        if command.receipt in self._receipts:
            raise ValueError("receipt replay detected")
        self._receipts.add(command.receipt)
        record.downstream_receipt = command.receipt
        record.state = RiskState.ISSUED_TO_INVESTMENT_DECISION
        self._touch(record)
        self._audit(record, "issue", command.actor, "issued to v21.08 investment decision boundary")

    def _touch(self, record: StrategicRiskRecord) -> None:
        record.updated_at = datetime.now(timezone.utc)

    def _audit(self, record: StrategicRiskRecord, action: str, actor: str, detail: str) -> None:
        self._audits.append(AuditEntry(
            workspace_id=record.workspace_id,
            record_id=record.record_id,
            action=action,
            actor=actor,
            detail=detail,
        ))


service = StrategicRiskService()
