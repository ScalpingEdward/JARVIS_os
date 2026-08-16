from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.core.auron_command_centre_v21_528 import build_default_command_centre

router = APIRouter(prefix='/auron/command-centre/v21.528', tags=['auron-command-centre'])
service = build_default_command_centre()


class CommandRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    actor: str = Field(min_length=1, max_length=120)


class ApprovalRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=200)
    capability: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=1, max_length=300)
    actor: str = Field(min_length=1, max_length=120)


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(pattern='^(approved|rejected)$')
    decided_by: str = Field(min_length=1, max_length=120)


@router.get('/state')
def state() -> dict:
    return service.snapshot()


@router.post('/commands')
def submit_command(payload: CommandRequest) -> dict:
    try:
        record = service.store.submit_command(payload.text, payload.actor)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        'state': 'command-received-non-executing',
        'command': asdict(record),
        'external_calls_made': 0,
    }


@router.post('/approvals')
def request_approval(payload: ApprovalRequest) -> dict:
    try:
        record = service.store.request_approval(payload.request_id, payload.capability, payload.action, payload.actor)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {'state': 'approval-pending', 'approval': asdict(record), 'external_calls_made': 0}


@router.post('/approvals/{approval_id}/decision')
def decide_approval(approval_id: str, payload: ApprovalDecisionRequest) -> dict:
    try:
        record = service.store.decide_approval(approval_id, payload.decision, payload.decided_by)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {'state': f'approval-{record.state}', 'approval': asdict(record), 'external_calls_made': 0}


@router.get('/ui', response_class=HTMLResponse)
def command_centre_ui() -> str:
    return '''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AURON Command Centre v21.528</title>
<style>
body{font-family:system-ui;background:#0b0f14;color:#e8edf2;margin:0;padding:24px}main{max-width:1100px;margin:auto}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.card{background:#111821;border:1px solid #263241;border-radius:14px;padding:18px}
textarea{width:100%;min-height:120px;box-sizing:border-box;background:#091019;color:#e8edf2;border:1px solid #3b4d61;border-radius:10px;padding:12px}
button{margin-top:10px;padding:10px 14px;border-radius:9px;border:1px solid #50657d;background:#162334;color:#fff;cursor:pointer}
pre{white-space:pre-wrap;word-break:break-word;max-height:360px;overflow:auto}.wide{grid-column:1/-1}.status{font-size:13px;opacity:.78}
@media(max-width:800px){.grid{grid-template-columns:1fr}.wide{grid-column:auto}}
</style></head>
<body><main><h1>AURON Command Centre <small>v21.528</small></h1>
<p class="status">Operational interface · backend state · approvals · audit timeline · command field preserved · provider execution disabled in A5</p>
<div class="grid">
<section class="card wide"><h2>Command</h2><textarea id="cmd" placeholder="Type an operational command..."></textarea>
<input id="actor" value="operator" aria-label="actor"><button onclick="sendCommand()">Submit command</button><pre id="commandResult"></pre></section>
<section class="card"><h2>System / Policy</h2><pre id="system"></pre></section>
<section class="card"><h2>Pending approvals</h2><pre id="approvals"></pre></section>
<section class="card wide"><h2>Audit timeline</h2><pre id="audit"></pre></section>
</div></main>
<script>
async function refresh(){const r=await fetch('/auron/command-centre/v21.528/state');const d=await r.json();
document.getElementById('system').textContent=JSON.stringify({readiness:d.readiness,policy:d.policy,command_execution_enabled:d.command_execution_enabled},null,2);
document.getElementById('approvals').textContent=JSON.stringify(d.pending_approvals,null,2);
document.getElementById('audit').textContent=JSON.stringify({executions:d.audit_timeline,commands:d.recent_commands},null,2)}
async function sendCommand(){const text=document.getElementById('cmd').value;const actor=document.getElementById('actor').value;
const r=await fetch('/auron/command-centre/v21.528/commands',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text,actor})});
const d=await r.json();document.getElementById('commandResult').textContent=JSON.stringify(d,null,2);if(r.ok){document.getElementById('cmd').value='';refresh()}}
refresh();
</script></body></html>'''
