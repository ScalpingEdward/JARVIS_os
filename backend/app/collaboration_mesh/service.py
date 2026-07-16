from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AgentContribution,
    CollaborationMission,
    ConsensusVote,
    MeshAgent,
    MeshAgentCreate,
    MeshStatus,
    MissionCreate,
    MissionState,
    VoteDecision,
)


class CollaborationMeshService:
    def __init__(self) -> None:
        self._agents: dict[UUID, MeshAgent] = {}
        self._missions: dict[UUID, CollaborationMission] = {}

    def reset(self) -> None:
        self._agents.clear()
        self._missions.clear()

    def register_agent(self, payload: MeshAgentCreate) -> MeshAgent:
        agent = MeshAgent(**payload.model_dump())
        self._agents[agent.id] = agent
        return agent

    def agents(self) -> list[MeshAgent]:
        return sorted(self._agents.values(), key=lambda item: (not item.available, item.role, item.name))

    def create_mission(self, payload: MissionCreate) -> CollaborationMission:
        mission = CollaborationMission(**payload.model_dump())
        candidates = [
            agent for agent in self._agents.values()
            if agent.available and (not payload.required_capabilities or set(payload.required_capabilities) & set(agent.capabilities))
        ]
        mission.assigned_agent_ids = [agent.id for agent in candidates]
        mission.state = MissionState.active if candidates else MissionState.blocked
        mission.human_approval_required = payload.critical
        if not candidates:
            mission.conflicts.append("No available agent matches the required capabilities")
        self._missions[mission.id] = mission
        return mission

    def missions(self) -> list[CollaborationMission]:
        return sorted(self._missions.values(), key=lambda item: item.created_at, reverse=True)

    def get_mission(self, mission_id: UUID) -> CollaborationMission | None:
        return self._missions.get(mission_id)

    def contribute(self, mission_id: UUID, contribution: AgentContribution) -> CollaborationMission | None:
        mission = self._missions.get(mission_id)
        if mission is None or contribution.agent_id not in mission.assigned_agent_ids:
            return None
        mission.contributions.append(contribution)
        mission.state = MissionState.waiting_consensus
        self._detect_conflicts(mission)
        mission.updated_at = datetime.now(timezone.utc)
        return mission

    def vote(self, mission_id: UUID, vote: ConsensusVote) -> CollaborationMission | None:
        mission = self._missions.get(mission_id)
        if mission is None or vote.agent_id not in mission.assigned_agent_ids:
            return None
        mission.votes = [item for item in mission.votes if item.agent_id != vote.agent_id]
        mission.votes.append(vote)
        self._calculate_consensus(mission)
        mission.updated_at = datetime.now(timezone.utc)
        return mission

    def status(self) -> MeshStatus:
        missions = list(self._missions.values())
        return MeshStatus(
            agents=len(self._agents),
            available_agents=sum(agent.available for agent in self._agents.values()),
            missions=len(missions),
            active_missions=sum(item.state == MissionState.active for item in missions),
            blocked_missions=sum(item.state == MissionState.blocked for item in missions),
            awaiting_consensus=sum(item.state == MissionState.waiting_consensus for item in missions),
        )

    def _calculate_consensus(self, mission: CollaborationMission) -> None:
        weighted_total = 0.0
        possible = 0.0
        for vote in mission.votes:
            agent = self._agents.get(vote.agent_id)
            weight = (agent.confidence_weight if agent else 1) * vote.confidence
            possible += weight
            if vote.decision == VoteDecision.approve:
                weighted_total += weight
            elif vote.decision == VoteDecision.reject:
                weighted_total -= weight
        mission.consensus_score = round(max(0, weighted_total / possible), 4) if possible else 0
        voted_agents = {vote.agent_id for vote in mission.votes}
        quorum = len(voted_agents) >= max(1, len(mission.assigned_agent_ids) // 2 + 1)
        if quorum and mission.consensus_score >= mission.consensus_threshold:
            mission.state = MissionState.waiting_consensus if mission.human_approval_required else MissionState.completed
            mission.final_recommendation = self._synthesize(mission)
        elif quorum and any(vote.decision == VoteDecision.reject for vote in mission.votes):
            mission.state = MissionState.blocked
            mission.conflicts.append("Agent consensus rejected the proposed outcome")
        else:
            mission.state = MissionState.waiting_consensus

    @staticmethod
    def _detect_conflicts(mission: CollaborationMission) -> None:
        recommendations = {item.recommendation.strip().lower() for item in mission.contributions if item.recommendation}
        if len(recommendations) > 1 and "Conflicting agent recommendations require resolution" not in mission.conflicts:
            mission.conflicts.append("Conflicting agent recommendations require resolution")

    @staticmethod
    def _synthesize(mission: CollaborationMission) -> str:
        ranked = sorted(mission.contributions, key=lambda item: item.confidence, reverse=True)
        return ranked[0].recommendation or ranked[0].summary if ranked else "Consensus reached without a written recommendation"


collaboration_mesh_service = CollaborationMeshService()
