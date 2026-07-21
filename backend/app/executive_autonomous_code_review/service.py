from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AutonomousCodeReviewAudit,
    AutonomousCodeReviewCreate,
    AutonomousCodeReviewRecord,
    AutonomousCodeReviewStatus,
    CodeReviewExecuteRequest,
    CodeReviewState,
    ReviewFinding,
)


class AutonomousCodeReviewService:
    def __init__(self) -> None:
        self._records: dict[UUID, AutonomousCodeReviewRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[AutonomousCodeReviewAudit] = []

    def create(self, payload: AutonomousCodeReviewCreate) -> AutonomousCodeReviewRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        state, detail, quality, risk, findings, recommendation = self._evaluate(payload)
        record = AutonomousCodeReviewRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            quality_score=quality,
            risk_score=risk,
            findings=findings,
            recommendation=recommendation,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, payload: AutonomousCodeReviewCreate):
        evidence = payload.evidence
        findings: list[ReviewFinding] = []
        if payload.upstream_risk_brain_blocked:
            return CodeReviewState.BLOCKED, "upstream Risk Brain hard block", 0, 100, [], "reject"
        if not payload.v20_02_pr_ready:
            return CodeReviewState.EVIDENCE_REQUIRED, "v20.02 PR-ready evidence required", 0, 100, [], "pending"
        if evidence.branch_name in {"main", "master"}:
            return CodeReviewState.BLOCKED, "review branch may not be main or master", 0, 100, [], "reject"

        quality = 100.0
        risk = 0.0
        if not evidence.ci_passed:
            findings.append(ReviewFinding(category="ci", severity="critical", detail="CI has not passed"))
            quality -= 45
            risk += 45
        if evidence.tests_failed:
            findings.append(ReviewFinding(category="tests", severity="critical", detail=f"{evidence.tests_failed} tests failed"))
            quality -= 35
            risk += 40
        if evidence.tests_added == 0:
            findings.append(ReviewFinding(category="coverage", severity="medium", detail="no new tests were added"))
            quality -= 12
            risk += 10
        if evidence.coverage_pct < 70:
            findings.append(ReviewFinding(category="coverage", severity="high", detail="coverage below 70 percent"))
            quality -= 20
            risk += 20
        if not evidence.diff_reviewed:
            findings.append(ReviewFinding(category="diff", severity="high", detail="diff review evidence missing"))
            quality -= 20
            risk += 20
        if not evidence.rollback_verified:
            findings.append(ReviewFinding(category="rollback", severity="high", detail="rollback plan not verified"))
            quality -= 15
            risk += 15
        if evidence.security_findings:
            for item in evidence.security_findings:
                findings.append(ReviewFinding(category="security", severity="critical", detail=item))
            quality -= min(50, len(evidence.security_findings) * 20)
            risk += min(60, len(evidence.security_findings) * 25)
        if evidence.regression_findings:
            for item in evidence.regression_findings:
                findings.append(ReviewFinding(category="regression", severity="high", detail=item))
            quality -= min(35, len(evidence.regression_findings) * 12)
            risk += min(40, len(evidence.regression_findings) * 15)
        if evidence.protected_paths_changed:
            findings.append(ReviewFinding(category="protected-path", severity="high", detail="protected paths changed"))
            risk += 15
        if evidence.risk_or_execution_changed:
            findings.append(ReviewFinding(category="trading-safety", severity="critical", detail="risk or execution code changed; human review mandatory"))
            risk += 25

        quality = round(max(0, min(100, quality)), 2)
        risk = round(max(0, min(100, risk)), 2)
        critical = any(item.severity == "critical" for item in findings)
        if critical or quality < 70 or risk >= 50:
            return CodeReviewState.CHANGES_REQUIRED, "review found blocking defects", quality, risk, findings, "reject"
        if evidence.protected_paths_changed or evidence.risk_or_execution_changed:
            return CodeReviewState.HUMAN_REVIEW_REQUIRED, "sensitive changes require explicit human review", quality, risk, findings, "human-review"
        return CodeReviewState.REVIEW_PENDING, "automated review passed; merge recommendation awaits confirmation", quality, risk, findings, "conditional-approve"

    def execute(self, record_id: UUID, workspace_id: str, request: CodeReviewExecuteRequest) -> AutonomousCodeReviewRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("code review record not found")
        if request.action == "confirm-human-review":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state not in {CodeReviewState.HUMAN_REVIEW_REQUIRED, CodeReviewState.REVIEW_PENDING}:
                raise ValueError("human review confirmation unavailable")
            record.state = CodeReviewState.REVIEW_PENDING
            record.detail = "human review confirmed; merge recommendation may be issued"
        elif request.action == "recommend-merge":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state != CodeReviewState.REVIEW_PENDING:
                raise ValueError("merge recommendation unavailable")
            record.state = CodeReviewState.MERGE_RECOMMENDED
            record.recommendation = "approve"
            record.detail = "merge recommended; merge remains a separate human-controlled action"
        elif request.action == "reject-merge":
            record.state = CodeReviewState.MERGE_NOT_RECOMMENDED
            record.recommendation = "reject"
            record.detail = "merge not recommended"
        elif request.action == "archive":
            record.state = CodeReviewState.ARCHIVED
            record.detail = "review archived"
        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> AutonomousCodeReviewRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[AutonomousCodeReviewRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> AutonomousCodeReviewStatus:
        records = self.list_records(workspace_id)
        blocked = {CodeReviewState.BLOCKED, CodeReviewState.CHANGES_REQUIRED, CodeReviewState.MERGE_NOT_RECOMMENDED, CodeReviewState.EVIDENCE_REQUIRED}
        return AutonomousCodeReviewStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            recommended_records=sum(record.state == CodeReviewState.MERGE_RECOMMENDED for record in records),
            blocked_records=sum(record.state in blocked for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[AutonomousCodeReviewAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: AutonomousCodeReviewRecord, actor_id: str, action: str) -> None:
        self._audit.append(AutonomousCodeReviewAudit(
            record_id=record.id,
            workspace_id=record.workspace_id,
            actor_id=actor_id,
            action=action,
            state=record.state,
            detail=record.detail,
        ))


autonomous_code_review_service = AutonomousCodeReviewService()
