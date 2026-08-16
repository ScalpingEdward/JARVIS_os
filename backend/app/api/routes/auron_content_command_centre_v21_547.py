from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.content.auron_content_command_centre_v21_547 import build_default_content_command_centre

router = APIRouter(prefix='/auron/command-centre/content/v21.547', tags=['auron-content-command-centre'])
service = build_default_content_command_centre()


class AutomationRequest(BaseModel):
    account_id: str
    cadence: str
    action: str = 'prepare-and-schedule'
    enabled: bool = False
    operator_approved: bool = False


@router.get('/state')
def state() -> dict:
    return service.snapshot()


@router.get('/accounts/{account_id}')
def account(account_id: str) -> dict:
    try:
        return service.account_view(account_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post('/automations/{automation_id}')
def automation(automation_id: str, payload: AutomationRequest) -> dict:
    try:
        item = service.configure_automation(
            automation_id,
            payload.account_id,
            cadence=payload.cadence,
            action=payload.action,
            enabled=payload.enabled,
            operator_approved=payload.operator_approved,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {'automation': item, 'external_calls_made': 0}


@router.get('/ui', response_class=HTMLResponse)
def ui() -> str:
    return '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AURON Content Command Centre v21.547</title><style>
body{font-family:system-ui;background:#0a0f15;color:#eaf0f6;margin:0;padding:24px}main{max-width:1200px;margin:auto}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.card{background:#111923;border:1px solid #253344;border-radius:14px;padding:16px}.wide{grid-column:1/-1}textarea{width:100%;min-height:105px;background:#081019;color:#eef;border:1px solid #40556d;border-radius:10px;padding:12px;box-sizing:border-box}button{padding:9px 12px;background:#182a3d;color:#fff;border:1px solid #49627d;border-radius:9px;cursor:pointer}pre{white-space:pre-wrap;max-height:420px;overflow:auto}.muted{opacity:.72}@media(max-width:800px){.grid{grid-template-columns:1fr}.wide{grid-column:auto}}</style></head>
<body><main><h1>AURON Content Command Centre <small>v21.547</small></h1><p class="muted">Brands · accounts · calendar · approvals · dry-runs · publish reconciliation · recurring automation policy · provider write disabled by default</p>
<div class="grid"><section class="card wide"><h2>Command</h2><textarea id="cmd" placeholder="Operational command field preserved..."></textarea><button onclick="note()">Submit note</button><pre id="cmdout"></pre></section>
<section class="card wide"><h2>Calendar / Accounts</h2><pre id="accounts"></pre></section><section class="card"><h2>Automations</h2><pre id="automations"></pre></section><section class="card"><h2>Safety</h2><pre id="safety"></pre></section></div></main>
<script>async function refresh(){const r=await fetch('/auron/command-centre/content/v21.547/state');const d=await r.json();accounts.textContent=JSON.stringify({brands:d.brands,accounts:d.accounts,calendar:d.calendar},null,2);automations.textContent=JSON.stringify(d.automations,null,2);safety.textContent=JSON.stringify({provider_write_enabled_by_default:d.provider_write_enabled_by_default,recurring_automation_bypasses_approval:d.recurring_automation_bypasses_approval,external_calls_made:d.external_calls_made},null,2)}function note(){cmdout.textContent='Command field active. Content commands remain non-publishing unless routed through C4-C7 approval and provider boundaries.'}refresh()</script></body></html>'''
