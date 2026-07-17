from collections import deque
from datetime import datetime, timezone
from uuid import UUID

from .models import (
    NodeApproval,
    NodeCompletion,
    NodeRunRecord,
    NodeRunState,
    NodeType,
    RunState,
    WorkflowActivation,
    WorkflowCreate,
    WorkflowDesignerStatus,
    WorkflowRecord,
    WorkflowRunCreate,
    WorkflowRunRecord,
    WorkflowState,
    WorkflowUpdate,
    WorkflowValidation,
)


class WorkflowDesignerService:
    def __init__(self) -> None:
        self._workflows: dict[UUID, WorkflowRecord] = {}
        self._runs: dict[UUID, WorkflowRunRecord] = {}

    def status(self) -> WorkflowDesignerStatus:
        workflows = list(self._workflows.values())
        runs = list(self._runs.values())
        return WorkflowDesignerStatus(
            total_workflows=len(workflows),
            active_workflows=sum(item.state == WorkflowState.ACTIVE for item in workflows),
            total_runs=len(runs),
            running_runs=sum(item.state == RunState.RUNNING for item in runs),
            waiting_approval_runs=sum(item.state == RunState.WAITING_APPROVAL for item in runs),
        )

    def create(self, payload: WorkflowCreate) -> WorkflowRecord:
        record = WorkflowRecord(
            workspace_id=payload.workspace_id.strip(),
            owner_id=payload.owner_id.strip(),
            name=payload.name.strip(),
            description=payload.description.strip(),
            nodes=payload.nodes,
            edges=payload.edges,
        )
        validation = self.validate_graph(record)
        record.validation_errors = validation.errors
        self._workflows[record.id] = record
        return record

    def list_all(self, workspace_id: str) -> list[WorkflowRecord]:
        return sorted(
            [item for item in self._workflows.values() if item.workspace_id == workspace_id.strip()],
            key=lambda item: item.updated_at,
            reverse=True,
        )

    def get(self, workflow_id: UUID, workspace_id: str) -> WorkflowRecord | None:
        record = self._workflows.get(workflow_id)
        if record is None or record.workspace_id != workspace_id.strip():
            return None
        return record

    def update(
        self,
        workflow_id: UUID,
        workspace_id: str,
        requester_id: str,
        payload: WorkflowUpdate,
    ) -> WorkflowRecord | None:
        record = self.get(workflow_id, workspace_id)
        if record is None or record.owner_id != requester_id.strip() or record.state == WorkflowState.ARCHIVED:
            return None
        if payload.name is not None:
            record.name = payload.name.strip()
        if payload.description is not None:
            record.description = payload.description.strip()
        if payload.nodes is not None:
            record.nodes = payload.nodes
        if payload.edges is not None:
            record.edges = payload.edges
        record.version += 1
        record.state = WorkflowState.DRAFT
        record.updated_at = datetime.now(timezone.utc)
        record.validation_errors = self.validate_graph(record).errors
        return record

    def validate(self, workflow_id: UUID, workspace_id: str) -> WorkflowValidation | None:
        record = self.get(workflow_id, workspace_id)
        return None if record is None else self.validate_graph(record)

    def activate(
        self,
        workflow_id: UUID,
        workspace_id: str,
        requester_id: str,
        payload: WorkflowActivation,
    ) -> WorkflowRecord | None:
        record = self.get(workflow_id, workspace_id)
        if record is None or record.owner_id != requester_id.strip():
            return None
        validation = self.validate_graph(record)
        record.validation_errors = validation.errors
        if not validation.valid:
            return record
        record.state = WorkflowState.ACTIVE
        record.updated_at = datetime.now(timezone.utc)
        return record

    def archive(
        self,
        workflow_id: UUID,
        workspace_id: str,
        requester_id: str,
        payload: WorkflowActivation,
    ) -> WorkflowRecord | None:
        record = self.get(workflow_id, workspace_id)
        if record is None or record.owner_id != requester_id.strip():
            return None
        record.state = WorkflowState.ARCHIVED
        record.updated_at = datetime.now(timezone.utc)
        return record

    def start_run(self, workflow_id: UUID, payload: WorkflowRunCreate) -> WorkflowRunRecord | None:
        workflow = self.get(workflow_id, payload.workspace_id)
        if workflow is None or workflow.state != WorkflowState.ACTIVE:
            return None
        validation = self.validate_graph(workflow)
        if not validation.valid or validation.start_node is None:
            return None
        nodes = [NodeRunRecord(node_key=item.key) for item in workflow.nodes]
        run = WorkflowRunRecord(
            workflow_id=workflow.id,
            workflow_version=workflow.version,
            workspace_id=payload.workspace_id.strip(),
            requester_id=payload.requester_id.strip(),
            state=RunState.RUNNING,
            input_data=payload.input_data,
            context=dict(payload.input_data),
            nodes=nodes,
            current_node_keys=[validation.start_node],
        )
        start = self._node_run(run, validation.start_node)
        start.state = NodeRunState.READY
        self._runs[run.id] = run
        self._advance_automatic(run, workflow)
        return run

    def list_runs(self, workspace_id: str) -> list[WorkflowRunRecord]:
        return sorted(
            [item for item in self._runs.values() if item.workspace_id == workspace_id.strip()],
            key=lambda item: item.created_at,
            reverse=True,
        )

    def get_run(self, run_id: UUID, workspace_id: str) -> WorkflowRunRecord | None:
        run = self._runs.get(run_id)
        if run is None or run.workspace_id != workspace_id.strip():
            return None
        return run

    def complete_node(
        self,
        run_id: UUID,
        node_key: str,
        workspace_id: str,
        payload: NodeCompletion,
    ) -> WorkflowRunRecord | None:
        run = self.get_run(run_id, workspace_id)
        if run is None or run.state not in {RunState.RUNNING, RunState.WAITING_APPROVAL}:
            return None
        node_run = self._node_run(run, node_key)
        if node_run is None or node_run.state not in {NodeRunState.READY, NodeRunState.RUNNING}:
            return run
        now = datetime.now(timezone.utc)
        node_run.started_at = node_run.started_at or now
        node_run.completed_at = now
        if payload.success:
            node_run.state = NodeRunState.COMPLETED
            node_run.result = payload.result
            run.context[node_key] = payload.result
            self._move_forward(run, self._workflows[run.workflow_id], node_key)
        else:
            node_run.state = NodeRunState.FAILED
            node_run.error = payload.error or "Node execution failed."
            run.state = RunState.FAILED
            run.current_node_keys = []
        run.updated_at = now
        return run

    def approve_node(
        self,
        run_id: UUID,
        node_key: str,
        workspace_id: str,
        payload: NodeApproval,
    ) -> WorkflowRunRecord | None:
        run = self.get_run(run_id, workspace_id)
        if run is None:
            return None
        node_run = self._node_run(run, node_key)
        if node_run is None or node_run.state != NodeRunState.WAITING_APPROVAL:
            return run
        now = datetime.now(timezone.utc)
        node_run.started_at = node_run.started_at or now
        node_run.completed_at = now
        if not payload.approved:
            node_run.state = NodeRunState.FAILED
            node_run.error = f"Approval denied by {payload.approved_by.strip()}."
            run.state = RunState.CANCELLED
            run.current_node_keys = []
        else:
            node_run.state = NodeRunState.COMPLETED
            node_run.result = {"approved": True, "approved_by": payload.approved_by.strip()}
            run.context[node_key] = node_run.result
            run.state = RunState.RUNNING
            self._move_forward(run, self._workflows[run.workflow_id], node_key)
        run.updated_at = now
        return run

    def cancel_run(self, run_id: UUID, workspace_id: str) -> WorkflowRunRecord | None:
        run = self.get_run(run_id, workspace_id)
        if run is None:
            return None
        if run.state not in {RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED}:
            run.state = RunState.CANCELLED
            run.current_node_keys = []
            run.updated_at = datetime.now(timezone.utc)
        return run

    def validate_graph(self, workflow: WorkflowRecord) -> WorkflowValidation:
        errors: list[str] = []
        keys = [node.key for node in workflow.nodes]
        key_set = set(keys)
        if len(keys) != len(key_set):
            errors.append("Node keys must be unique.")
        starts = [node.key for node in workflow.nodes if node.node_type == NodeType.START]
        ends = [node.key for node in workflow.nodes if node.node_type == NodeType.END]
        if len(starts) != 1:
            errors.append("Workflow must contain exactly one start node.")
        if not ends:
            errors.append("Workflow must contain at least one end node.")
        for edge in workflow.edges:
            if edge.source not in key_set or edge.target not in key_set:
                errors.append(f"Edge {edge.source}->{edge.target} references an unknown node.")
            if edge.source == edge.target:
                errors.append(f"Self-loop is not allowed for node {edge.source}.")
        order = self._topological_order(keys, workflow.edges)
        if len(order) != len(key_set):
            errors.append("Workflow graph contains a cycle.")
        if starts:
            reachable = self._reachable(starts[0], workflow.edges)
            missing = key_set - reachable
            if missing:
                errors.append("Unreachable nodes: " + ", ".join(sorted(missing)) + ".")
        outgoing = {edge.source for edge in workflow.edges}
        for node in workflow.nodes:
            if node.node_type != NodeType.END and node.key not in outgoing:
                errors.append(f"Node {node.key} has no outgoing edge.")
        return WorkflowValidation(
            valid=not errors,
            errors=errors,
            start_node=starts[0] if len(starts) == 1 else None,
            end_nodes=ends,
            topological_order=order,
        )

    @staticmethod
    def _topological_order(keys: list[str], edges) -> list[str]:
        adjacency = {key: [] for key in keys}
        indegree = {key: 0 for key in keys}
        for edge in edges:
            if edge.source in adjacency and edge.target in indegree:
                adjacency[edge.source].append(edge.target)
                indegree[edge.target] += 1
        queue = deque(sorted(key for key, value in indegree.items() if value == 0))
        order: list[str] = []
        while queue:
            key = queue.popleft()
            order.append(key)
            for target in adjacency[key]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
        return order

    @staticmethod
    def _reachable(start: str, edges) -> set[str]:
        adjacency: dict[str, list[str]] = {}
        for edge in edges:
            adjacency.setdefault(edge.source, []).append(edge.target)
        seen: set[str] = set()
        stack = [start]
        while stack:
            key = stack.pop()
            if key in seen:
                continue
            seen.add(key)
            stack.extend(adjacency.get(key, []))
        return seen

    def _move_forward(self, run: WorkflowRunRecord, workflow: WorkflowRecord, source_key: str) -> None:
        run.current_node_keys = [key for key in run.current_node_keys if key != source_key]
        candidates = []
        for edge in workflow.edges:
            if edge.source != source_key:
                continue
            if edge.condition_key is not None and run.context.get(edge.condition_key) != edge.condition_value:
                continue
            candidates.append(edge.target)
        for target in candidates:
            target_run = self._node_run(run, target)
            if target_run is not None and target_run.state == NodeRunState.PENDING:
                target_run.state = NodeRunState.READY
                run.current_node_keys.append(target)
        self._advance_automatic(run, workflow)

    def _advance_automatic(self, run: WorkflowRunRecord, workflow: WorkflowRecord) -> None:
        changed = True
        while changed and run.state == RunState.RUNNING:
            changed = False
            for key in list(run.current_node_keys):
                definition = next(item for item in workflow.nodes if item.key == key)
                node_run = self._node_run(run, key)
                if node_run is None or node_run.state != NodeRunState.READY:
                    continue
                if definition.node_type == NodeType.HUMAN_APPROVAL or definition.requires_human_approval:
                    node_run.state = NodeRunState.WAITING_APPROVAL
                    run.state = RunState.WAITING_APPROVAL
                    continue
                if definition.node_type in {NodeType.START, NodeType.END}:
                    node_run.state = NodeRunState.COMPLETED
                    now = datetime.now(timezone.utc)
                    node_run.started_at = now
                    node_run.completed_at = now
                    if definition.node_type == NodeType.END:
                        run.current_node_keys.remove(key)
                        if not run.current_node_keys:
                            run.state = RunState.COMPLETED
                    else:
                        self._move_forward(run, workflow, key)
                    changed = True
                else:
                    node_run.state = NodeRunState.RUNNING
                    node_run.started_at = datetime.now(timezone.utc)
        run.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _node_run(run: WorkflowRunRecord, node_key: str) -> NodeRunRecord | None:
        return next((item for item in run.nodes if item.node_key == node_key), None)


workflow_designer_service = WorkflowDesignerService()
