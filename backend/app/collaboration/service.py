from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AgentRole,
    CollaborationCreate,
    CollaborationRecord,
    CollaborationStatus,
    ContributionCreate,
    ContributionRecord,
    ContributionStatus,
    ReviewCreate,
    ReviewRecord,
)


class CollaborationError(ValueError):
    pass


class CollaborationService:
    def __init__(self) -> None:
        self._sessions: dict[UUID, CollaborationRecord] = {}

    def reset(self) -> None:
        self._sessions.clear()

    def create(self, payload: CollaborationCreate) -> CollaborationRecord:
        names = [item.name for item in payload.participants]
        if len(names) != len(set(names)):
            raise CollaborationError("Participant names must be unique")
        if not any(item.role == AgentRole.reviewer for item in payload.participants):
            raise CollaborationError("At least one reviewer is required")
        session = CollaborationRecord(**payload.model_dump(), status=CollaborationStatus.active)
        self._sessions[session.id] = session
        return session

    def list_all(self) -> list[CollaborationRecord]:
        return sorted(self._sessions.values(), key=lambda item: item.created_at, reverse=True)

    def get(self, session_id: UUID) -> CollaborationRecord:
        session = self._sessions.get(session_id)
        if session is None:
            raise CollaborationError("Collaboration not found")
        return session

    def contribute(self, session_id: UUID, payload: ContributionCreate) -> CollaborationRecord:
        session = self.get(session_id)
        self._participant(session, payload.participant_name)
        if session.status in {CollaborationStatus.resolved, CollaborationStatus.escalated}:
            raise CollaborationError("Collaboration is terminal")
        session.contributions.append(ContributionRecord(**payload.model_dump()))
        session.status = CollaborationStatus.reviewing
        self._touch(session)
        return session

    def review(self, session_id: UUID, contribution_id: UUID, payload: ReviewCreate) -> CollaborationRecord:
        session = self.get(session_id)
        participant = self._participant(session, payload.reviewer_name)
        if participant.role not in {AgentRole.reviewer, AgentRole.decision_maker}:
            raise CollaborationError("Participant is not allowed to review")
        contribution = self._contribution(session, contribution_id)
        if any(item.contribution_id == contribution_id and item.reviewer_name == payload.reviewer_name for item in session.reviews):
            raise CollaborationError("Reviewer already reviewed this contribution")
        session.reviews.append(ReviewRecord(**payload.model_dump(), contribution_id=contribution_id))
        approvals = sum(item.approved for item in session.reviews if item.contribution_id == contribution_id)
        rejections = sum(not item.approved for item in session.reviews if item.contribution_id == contribution_id)
        if approvals >= session.required_reviews:
            contribution.status = ContributionStatus.accepted
            session.selected_contribution_id = contribution.id
            session.status = CollaborationStatus.resolved
        elif rejections >= session.required_reviews:
            contribution.status = ContributionStatus.rejected
            session.conflict_reason = "Required reviewers rejected the contribution"
            session.status = CollaborationStatus.escalated
        self._touch(session)
        return session

    def compare(self, session_id: UUID) -> dict[str, object]:
        session = self.get(session_id)
        return {
            "session_id": str(session.id),
            "contributions": [
                {
                    "id": str(item.id),
                    "participant": item.participant_name,
                    "status": item.status,
                    "approvals": sum(r.approved for r in session.reviews if r.contribution_id == item.id),
                    "rejections": sum(not r.approved for r in session.reviews if r.contribution_id == item.id),
                }
                for item in session.contributions
            ],
            "selected_contribution_id": str(session.selected_contribution_id) if session.selected_contribution_id else None,
            "status": session.status,
        }

    @staticmethod
    def _participant(session: CollaborationRecord, name: str):
        for participant in session.participants:
            if participant.name == name:
                return participant
        raise CollaborationError("Participant not found")

    @staticmethod
    def _contribution(session: CollaborationRecord, contribution_id: UUID) -> ContributionRecord:
        for contribution in session.contributions:
            if contribution.id == contribution_id:
                return contribution
        raise CollaborationError("Contribution not found")

    @staticmethod
    def _touch(session: CollaborationRecord) -> None:
        session.updated_at = datetime.now(timezone.utc)


collaboration_service = CollaborationService()
