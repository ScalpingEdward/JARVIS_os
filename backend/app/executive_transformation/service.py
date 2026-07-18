from datetime import datetime, timezone
from threading import RLock
from uuid import UUID

from .models import (
    AuditRecord,
    ExecutiveTransformationPortfolio,
    ProgramAssessment,
    ProgramStatus,
    ProgressUpdate,
    TransformationAssessment,
    TransformationPortfolioCreate,
    TransformationStatusResponse,
)


class ExecutiveTransformationService:
    def __init__(self) -> None:
        self._portfolios: dict[UUID, ExecutiveTransformationPortfolio] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _write_audit(self, workspace_id: str, action: str, actor_id: str, portfolio_id: UUID | None = None, details: dict | None = None) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, action=action, actor_id=actor_id, portfolio_id=portfolio_id, details=details or {}, created_at=self._now()))

    def create(self, payload: TransformationPortfolioCreate) -> ExecutiveTransformationPortfolio:
        now = self._now()
        record = ExecutiveTransformationPortfolio(**payload.model_dump(), created_at=now, updated_at=now)
        with self._lock:
            if any(item.workspace_id == payload.workspace_id and item.title == payload.title for item in self._portfolios.values()):
                raise ValueError("A transformation portfolio with this title already exists in the workspace")
            self._portfolios[record.id] = record
            self._write_audit(payload.workspace_id, "transformation-portfolio-created", payload.owner_id, record.id, {"programs": len(payload.programs)})
        return record

    def list_portfolios(self, workspace_id: str) -> list[ExecutiveTransformationPortfolio]:
        with self._lock:
            return [item for item in self._portfolios.values() if item.workspace_id == workspace_id]

    def get(self, portfolio_id: UUID, workspace_id: str) -> ExecutiveTransformationPortfolio | None:
        with self._lock:
            record = self._portfolios.get(portfolio_id)
            return record if record is not None and record.workspace_id == workspace_id else None

    def update_progress(self, portfolio_id: UUID, workspace_id: str, payload: ProgressUpdate) -> ExecutiveTransformationPortfolio:
        with self._lock:
            record = self._portfolios.get(portfolio_id)
            if record is None or record.workspace_id != workspace_id:
                raise KeyError("Transformation portfolio not found")
            programs = []
            found = False
            for program in record.programs:
                if program.program_key != payload.program_key:
                    programs.append(program)
                    continue
                found = True
                benefits = [benefit.model_copy(update={"realized_value": payload.realized_benefits.get(benefit.key, benefit.realized_value)}) for benefit in program.benefits]
                programs.append(program.model_copy(update={"progress": payload.progress, "spent": payload.spent, "risk_score": payload.risk_score, "benefits": benefits}))
            if not found:
                raise ValueError("Program not found")
            updated = record.model_copy(update={"programs": programs, "assessment": None, "version": record.version + 1, "updated_at": self._now()})
            self._portfolios[portfolio_id] = updated
            self._write_audit(workspace_id, "transformation-progress-updated", payload.actor_id, portfolio_id, {"program_key": payload.program_key})
            return updated

    @staticmethod
    def _topological_order(programs) -> list[str]:
        graph = {item.program_key: set(item.dependencies) for item in programs}
        result: list[str] = []
        while graph:
            ready = sorted(key for key, deps in graph.items() if not deps)
            if not ready:
                raise ValueError("Transformation program dependency graph contains a cycle")
            result.extend(ready)
            for key in ready:
                graph.pop(key)
            for deps in graph.values():
                deps.difference_update(ready)
        return result

    def assess(self, portfolio_id: UUID, workspace_id: str, actor_id: str) -> ExecutiveTransformationPortfolio:
        with self._lock:
            record = self._portfolios.get(portfolio_id)
            if record is None or record.workspace_id != workspace_id:
                raise KeyError("Transformation portfolio not found")
            order = self._topological_order(record.programs)
            assessments: list[ProgramAssessment] = []
            blockers: list[str] = []
            for program in record.programs:
                readiness = (program.readiness.stakeholder_alignment + program.readiness.capability_readiness + program.readiness.adoption_readiness + program.readiness.communication_readiness) / 4
                if program.benefits:
                    benefit_score = sum(min(100.0, max(0.0, benefit.realized_value / benefit.target_value * 100 if benefit.target_value else 100.0)) * benefit.weight / 100 for benefit in program.benefits)
                else:
                    benefit_score = program.progress
                budget_utilization = program.spent / program.budget * 100 if program.budget else 0.0
                health = max(0.0, min(100.0, program.progress * 0.35 + readiness * 0.25 + benefit_score * 0.25 + (100 - program.risk_score) * 0.15))
                item_blockers = []
                if budget_utilization > 100:
                    item_blockers.append("Budget exceeded")
                if readiness < 60:
                    item_blockers.append("Change readiness below threshold")
                unmet = [dep for dep in program.dependencies if next(item for item in record.programs if item.program_key == dep).progress < 100]
                if unmet:
                    item_blockers.append(f"Incomplete dependencies: {', '.join(unmet)}")
                    blockers.append(f"{program.program_key}: {', '.join(unmet)}")
                status = ProgramStatus.completed if program.progress >= 100 else ProgramStatus.at_risk if health < 60 or item_blockers else ProgramStatus.active
                assessments.append(ProgramAssessment(program_key=program.program_key, health_score=round(health, 2), readiness_score=round(readiness, 2), benefits_realization=round(benefit_score, 2), budget_utilization=round(budget_utilization, 2), status=status, blockers=item_blockers))
            health = sum(item.health_score for item in assessments) / len(assessments)
            benefits = sum(item.benefits_realization for item in assessments) / len(assessments)
            readiness = sum(item.readiness_score for item in assessments) / len(assessments)
            spent = sum(item.spent for item in record.programs)
            utilization = spent / record.portfolio_budget * 100
            recommendations = []
            if blockers:
                recommendations.append("Resolve dependency blockers before advancing downstream programs")
            if utilization > 90 and health < 80:
                recommendations.append("Escalate budget efficiency review to executive steering")
            if readiness < 70:
                recommendations.append("Increase stakeholder, capability, adoption and communication readiness")
            summary = f"Portfolio health is {health:.2f} with {benefits:.2f}% benefits realization and {readiness:.2f}% change readiness. Human steering remains mandatory."
            assessment = TransformationAssessment(assessed_at=self._now(), portfolio_health=round(health, 2), benefits_realization=round(benefits, 2), change_readiness=round(readiness, 2), budget_utilization=round(utilization, 2), assessments=assessments, critical_path=order, dependency_blockers=blockers, recommendations=recommendations, executive_summary=summary)
            updated = record.model_copy(update={"assessment": assessment, "version": record.version + 1, "updated_at": self._now()})
            self._portfolios[portfolio_id] = updated
            self._write_audit(workspace_id, "transformation-portfolio-assessed", actor_id, portfolio_id, {"portfolio_health": assessment.portfolio_health, "at_risk": sum(item.status == ProgramStatus.at_risk for item in assessments)})
            return updated

    def status(self, workspace_id: str) -> TransformationStatusResponse:
        records = self.list_portfolios(workspace_id)
        return TransformationStatusResponse(portfolios=len(records), assessed_portfolios=sum(item.assessment is not None for item in records), at_risk_programs=sum(item.status == ProgramStatus.at_risk for record in records if record.assessment for item in record.assessment.assessments))

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        with self._lock:
            return [item for item in self._audit if item.workspace_id == workspace_id]


executive_transformation_service = ExecutiveTransformationService()
