from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.api.routes.auron_demo1_conversational_core_v21_242 import DialogueRequest
from app.api.routes.auron_demo1_execution_policy_controller_v21_258 import (
    _policy,
    command_center as v21_258_command_center,
    dialogue as v21_258_dialogue,
)
from app.memory.models import MemoryCreate, MemoryPriority
from app.memory.service import memory_service

router = APIRouter(prefix='/auron/demo1/v21.259', tags=['auron-demo1-policy-decision-ledger'])
LEDGER_CATEGORY = 'auron-policy-decision-ledger'
MAX_LEDGER_ITEMS = 50


def _scope(req: DialogueRequest) -> set[str]:
    return {f'session:{req.session_id}', f'workspace:{req.workspace_id}', f'operator:{req.operator_id}'}


def _records(req: DialogueRequest) -> list:
    required = _scope(req)
    rows = [item for item in memory_service.list_all(category=LEDGER_CATEGORY) if required.issubset(set(item.tags))]
    return sorted(rows, key=lambda item: item.created_at)


def _tag_value(tags: set[str], prefix: str, default: str = '') -> str:
    return next((tag.split(':', 1)[1] for tag in tags if tag.startswith(prefix)), default)


def _serialize(item) -> dict:
    tags = set(item.tags)
    return {
        'decision_id': _tag_value(tags, 'decision-id:'),
        'command': item.content,
        'policy_mode': _tag_value(tags, 'policy-mode:'),
        'policy_reason': _tag_value(tags, 'policy-reason:'),
        'allowed': _tag_value(tags, 'allowed:') == 'true',
        'approval_required': _tag_value(tags, 'approval-required:') == 'true',
        'health_score': int(_tag_value(tags, 'health-score:', '0') or 0),
        'admission': _tag_value(tags, 'admission:'),
        'created_at': item.created_at.isoformat(),
    }


def _trim(req: DialogueRequest) -> None:
    rows = _records(req)
    overflow = max(0, len(rows) - MAX_LEDGER_ITEMS)
    for item in rows[:overflow]:
        memory_service.delete(item.id)


def _record_decision(req: DialogueRequest, policy: dict) -> dict:
    decision_id = uuid4().hex[:12]
    admission = policy.get('admission') or {}
    health_score = int(admission.get('health_score') or 0)
    classification = str(admission.get('classification') or 'unknown')
    memory_service.create(
        MemoryCreate(
            content=req.command.strip()[:500],
            category=LEDGER_CATEGORY,
            priority=MemoryPriority.high,
            tags=[
                *_scope(req),
                f'decision-id:{decision_id}',
                f'policy-mode:{policy.get("mode", "unknown")}',
                f'policy-reason:{policy.get("reason", "unknown")}',
                f'allowed:{str(bool(policy.get("allowed"))).lower()}',
                f'approval-required:{str(bool(policy.get("approval_required"))).lower()}',
                f'health-score:{health_score}',
                f'admission:{classification}',
            ],
        )
    )
    _trim(req)
    return {'decision_id': decision_id, 'recorded': True}


def _latest(req: DialogueRequest) -> dict | None:
    rows = _records(req)
    return _serialize(rows[-1]) if rows else None


def _ledger(req: DialogueRequest, limit: int = 10) -> list[dict]:
    safe_limit = max(1, min(limit, MAX_LEDGER_ITEMS))
    return [_serialize(item) for item in _records(req)[-safe_limit:]][::-1]


def _explain(decision: dict | None) -> str:
    if not decision:
        return 'Noch keine Policy-Entscheidung im Ledger.'
    return (
        f"Decision {decision['decision_id']}: {decision['policy_mode']}. "
        f"Grund: {decision['policy_reason']}. "
        f"Allowed: {'ja' if decision['allowed'] else 'nein'}. "
        f"Approval: {'ja' if decision['approval_required'] else 'nein'}. "
        f"Health: {decision['health_score']}/100."
    )


def _command(req: DialogueRequest) -> dict | None:
    text = ' '.join(req.command.casefold().strip(' .!?').split())
    if text in {'letzte policy entscheidung', 'zeige letzte policy entscheidung', 'last policy decision', 'warum wurde das entschieden'}:
        latest = _latest(req)
        return {
            'state': 'completed',
            'mode': 'policy-decision-explain',
            'reply': _explain(latest),
            'detected_intents': ['policy-decision-ledger'],
            'steps': [],
            'approval_required': False,
            'decision': latest,
        }
    if text in {'policy ledger', 'zeige policy ledger', 'decision ledger', 'zeige entscheidungen'}:
        items = _ledger(req, 10)
        return {
            'state': 'completed',
            'mode': 'policy-decision-ledger',
            'reply': f'Policy Ledger: {len(items)} letzte Entscheidungen verfügbar.',
            'detected_intents': ['policy-decision-ledger'],
            'steps': [],
            'approval_required': False,
            'decisions': items,
        }
    return None


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    direct = _command(req)
    if direct is not None:
        return direct

    policy = _policy(req)
    receipt = _record_decision(req, policy)
    result = v21_258_dialogue(req)
    result['policy_receipt'] = receipt
    result['policy_decision'] = {
        'mode': policy.get('mode'),
        'reason': policy.get('reason'),
        'allowed': bool(policy.get('allowed')),
        'approval_required': bool(policy.get('approval_required')),
    }
    return result


@router.get('/ledger')
def ledger(session_id: str = 'ledger', workspace_id: str = 'demo', operator_id: str = 'brano', limit: int = 10) -> dict:
    req = DialogueRequest(session_id=session_id, workspace_id=workspace_id, operator_id=operator_id, command='ledger')
    items = _ledger(req, limit)
    return {'count': len(items), 'items': items, 'max_items': MAX_LEDGER_ITEMS}


@router.get('/latest-decision')
def latest_decision(session_id: str = 'ledger', workspace_id: str = 'demo', operator_id: str = 'brano') -> dict:
    req = DialogueRequest(session_id=session_id, workspace_id=workspace_id, operator_id=operator_id, command='latest')
    return {'decision': _latest(req)}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    html = v21_258_command_center()
    html = html.replace('v21.258', 'v21.259')
    html = html.replace('AURON EXECUTION POLICY COMMAND CENTER', 'AURON POLICY DECISION LEDGER COMMAND CENTER')
    return html
