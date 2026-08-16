from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.trading.auron_trading_command_centre_v21_539 import build_default_trading_command_centre

router = APIRouter(prefix='/auron/command-centre/trading/v21.539', tags=['auron-trading-command-centre'])
service = build_default_trading_command_centre()


class KillControlRequest(BaseModel):
    global_kill_switch: bool
    account_kill_switch: bool


@router.get('/state')
def state() -> dict:
    return service.snapshot()


@router.get('/accounts/{account_id}')
def account(account_id: str) -> dict:
    try:
        return service.account_view(account_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post('/accounts/{account_id}/kill-controls')
def kill_controls(account_id: str, payload: KillControlRequest) -> dict:
    try:
        return service.set_kill_controls(
            account_id,
            global_kill_switch=payload.global_kill_switch,
            account_kill_switch=payload.account_kill_switch,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get('/ui', response_class=HTMLResponse)
def ui() -> str:
    return '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AURON Trading Command Centre v21.539</title><style>
body{font-family:system-ui;background:#0a0f15;color:#eaf0f6;margin:0;padding:24px}main{max-width:1200px;margin:auto}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.card{background:#111923;border:1px solid #253344;border-radius:14px;padding:16px}.wide{grid-column:1/-1}textarea{width:100%;min-height:105px;background:#081019;color:#eef;border:1px solid #40556d;border-radius:10px;padding:12px;box-sizing:border-box}button{padding:9px 12px;background:#182a3d;color:#fff;border:1px solid #49627d;border-radius:9px;cursor:pointer}pre{white-space:pre-wrap;max-height:420px;overflow:auto}.muted{opacity:.72}@media(max-width:800px){.grid{grid-template-columns:1fr}.wide{grid-column:auto}}</style></head>
<body><main><h1>AURON Trading Command Centre <small>v21.539</small></h1><p class="muted">Multi-account state · DD headroom · canary · paper/live decisions · alerts · kill controls · provider write disabled by default</p>
<div class="grid"><section class="card wide"><h2>Command</h2><textarea id="cmd" placeholder="Operational command field preserved..."></textarea><button onclick="note()">Submit note</button><pre id="cmdout"></pre></section>
<section class="card wide"><h2>Trading Accounts</h2><pre id="accounts"></pre></section><section class="card"><h2>Paper Executions</h2><pre id="paper"></pre></section><section class="card"><h2>Safety</h2><pre id="safety"></pre></section></div></main>
<script>async function refresh(){const r=await fetch('/auron/command-centre/trading/v21.539/state');const d=await r.json();accounts.textContent=JSON.stringify(d.accounts,null,2);paper.textContent=JSON.stringify(d.paper_executions,null,2);safety.textContent=JSON.stringify({provider_write_enabled:d.provider_write_enabled,live_execution_default:d.live_execution_default,external_calls_made:d.external_calls_made},null,2)}function note(){cmdout.textContent='Command field active. Trading commands remain non-executing until explicitly wired through approved action routes.'}refresh()</script></body></html>'''
