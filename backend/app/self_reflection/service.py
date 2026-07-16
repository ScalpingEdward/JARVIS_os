from collections import Counter
from uuid import UUID

from .models import (
    ExperimentCreate,
    ExperimentRecord,
    ImprovementProposal,
    Outcome,
    ReflectionStatus,
    ReviewCreate,
    ReviewDomain,
    ReviewRecord,
)


class ReflectionService:
    def __init__(self) -> None:
        self._reviews: dict[UUID, ReviewRecord] = {}
        self._proposals: dict[UUID, ImprovementProposal] = {}
        self._experiments: dict[UUID, ExperimentRecord] = {}

    def reset(self) -> None:
        self._reviews.clear()
        self._proposals.clear()
        self._experiments.clear()

    def add_review(self, payload: ReviewCreate) -> ReviewRecord:
        review = ReviewRecord(**payload.model_dump())
        self._reviews[review.id] = review
        return review

    def list_reviews(self, domain: ReviewDomain | None = None) -> list[ReviewRecord]:
        values = list(self._reviews.values())
        if domain is not None:
            values = [item for item in values if item.domain == domain]
        return values

    def discover_patterns(self, minimum_occurrences: int = 2) -> list[dict[str, object]]:
        failure_counts = Counter(
            failure.strip().lower()
            for review in self._reviews.values()
            for failure in review.failures
            if failure.strip()
        )
        blocker_counts = Counter(
            blocker.strip().lower()
            for review in self._reviews.values()
            for blocker in review.blockers
            if blocker.strip()
        )
        patterns: list[dict[str, object]] = []
        for category, counts in (("failure", failure_counts), ("blocker", blocker_counts)):
            for label, count in counts.most_common():
                if count >= minimum_occurrences:
                    patterns.append({"category": category, "pattern": label, "occurrences": count})
        return patterns

    def propose_improvements(self) -> list[ImprovementProposal]:
        existing = {(item.title, item.rationale) for item in self._proposals.values()}
        created: list[ImprovementProposal] = []
        for pattern in self.discover_patterns():
            title = f"Reduce recurring {pattern['category']}: {pattern['pattern']}"
            rationale = f"Observed {pattern['occurrences']} times across completed reviews."
            if (title, rationale) in existing:
                continue
            matching = [
                review.id
                for review in self._reviews.values()
                if str(pattern["pattern"]) in [x.strip().lower() for x in review.failures + review.blockers]
            ]
            proposal = ImprovementProposal(
                title=title,
                rationale=rationale,
                expected_benefit=min(90.0, 45.0 + 5.0 * int(pattern["occurrences"])),
                risk=25.0,
                confidence=min(0.95, 0.5 + 0.08 * int(pattern["occurrences"])),
                supporting_review_ids=matching,
            )
            self._proposals[proposal.id] = proposal
            created.append(proposal)
        return created

    def list_proposals(self) -> list[ImprovementProposal]:
        return list(self._proposals.values())

    def approve_proposal(self, proposal_id: UUID) -> ImprovementProposal | None:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            return None
        proposal.approved = True
        return proposal

    def create_experiment(self, payload: ExperimentCreate) -> ExperimentRecord:
        proposal = self._proposals.get(payload.proposal_id)
        if proposal is None:
            raise ValueError("Proposal not found")
        if not proposal.approved:
            raise ValueError("Human approval required before experiment creation")
        record = ExperimentRecord(**payload.model_dump())
        self._experiments[record.id] = record
        return record

    def list_experiments(self) -> list[ExperimentRecord]:
        return list(self._experiments.values())

    def lessons(self) -> dict[str, object]:
        reviews = list(self._reviews.values())
        average_score = round(sum(item.score for item in reviews) / len(reviews), 2) if reviews else 0.0
        successes = Counter(item for review in reviews for item in review.successes)
        failures = Counter(item for review in reviews for item in review.failures)
        return {
            "average_score": average_score,
            "successful_reviews": sum(item.outcome == Outcome.success for item in reviews),
            "top_successes": successes.most_common(5),
            "top_failures": failures.most_common(5),
            "patterns": self.discover_patterns(),
        }

    def status(self) -> ReflectionStatus:
        return ReflectionStatus(
            reviews=len(self._reviews),
            proposals=len(self._proposals),
            experiments=len(self._experiments),
            approved_proposals=sum(item.approved for item in self._proposals.values()),
        )


reflection_service = ReflectionService()
