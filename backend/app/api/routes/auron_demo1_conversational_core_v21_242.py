from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.models.contracts import ModelRequest
from app.models.router import model_router
from app.schemas.phoenix_demo1_intent_router_v21_238 import IntentRouteRequest
from app.services.phoenix_demo1_intent_router_v21_238 import execute_operator_command

router = APIRouter(prefix='/auron/demo1/v21.242', tags=['auron-demo1-interface'])


class DialogueRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=200)
    workspace_id: str = Field(default='demo', min_length=1, max_length=200)
    operator_id: str = Field(default='brano', min_length=1, max_length=200)
    command: str = Field(min_length=1, max_length=4000)
    risk_brain_hard_block: bool = False


def _human_summary(result) -> str:
    intents = set(result.detected_intents or [])
    if result.state == 'blocked':
        return 'Die Anfrage wurde vom Risk Brain blockiert.'
    if result.state == 'approval-required':
        return 'Dafür ist deine Freigabe erforderlich. Ich führe keine finanzielle Aktion autonom aus.'
    parts: list[str] = []
    if 'system-status' in intents:
        parts.append('Systemstatus geprüft')
    if 'memory-search' in intents:
        parts.append('Memory geprüft')
    if 'voice-status' in intents:
        parts.append('Voice geprüft')
    if 'approval-inbox' in intents:
        parts.append('Freigaben geprüft')
    if 'tradingview-alerts' in intents:
        parts.append('TradingView-Alerts geprüft')
    elif 'tradingview-status' in intents:
        parts.append('TradingView geprüft')
    if 'tool-registry' in intents:
        parts.append('Tools geprüft')
    if parts:
        return '. '.join(parts) + '. Alles abgeschlossen.'
    return 'Auftrag abgeschlossen.'


def _fallback_reply(command: str) -> str:
    text = command.lower().strip()
    greetings = ('hallo', 'hi ', 'hey', 'guten morgen', 'guten tag', 'master brano', 'bin hier', 'ich bin da')
    if any(term in text for term in greetings):
        return 'Willkommen zurück, Master Brano. AURON ist online und bereit. Was möchtest du tun?'

    providers = model_router.available_providers()
    provider = 'openai' if 'openai' in providers else ('anthropic' if 'anthropic' in providers else None)
    if provider:
        prompt = (
            'Du bist AURON, ein präziser persönlicher AI-Operator. Antworte auf Deutsch kurz, natürlich und direkt. '
            'Du darfst keine nicht vorhandenen Tool-Aktionen behaupten. Finanzielle oder andere High-Risk-Aktionen benötigen Freigabe. '
            'Wenn der Nutzer nur redet, antworte normal. Nutzername: Master Brano.\n\nNutzer: ' + command
        )
        try:
            return model_router.generate(ModelRequest(prompt=prompt, task_type='operator_dialogue'), provider_name=provider).content
        except Exception:
            pass
    return 'Ich habe dich verstanden, aber dafür ist noch keine ausführbare Fähigkeit verbunden. Du kannst normal mit mir sprechen oder mir einen unterstützten System-, Memory-, Voice-, TradingView-, Approval- oder Tool-Auftrag geben.'


@router.post('/dialogue')
def dialogue(req: DialogueRequest) -> dict:
    execution = execute_operator_command(IntentRouteRequest(
        session_id=req.session_id,
        workspace_id=req.workspace_id,
        operator_id=req.operator_id,
        command=req.command,
        risk_brain_hard_block=req.risk_brain_hard_block,
    ))
    if execution.state == 'unsupported':
        reply = _fallback_reply(req.command)
        return {
            'state': 'conversation', 'mode': 'conversation', 'reply': reply,
            'detected_intents': [], 'steps': [], 'approval_required': False,
        }
    return {
        'state': execution.state, 'mode': 'capability', 'reply': _human_summary(execution),
        'detected_intents': execution.detected_intents,
        'steps': [step.model_dump(mode='json') for step in execution.steps],
        'approval_required': execution.approval_required,
    }


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    return r'''<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AURON Command Center</title>
<style>
:root{color-scheme:dark;--bg:#03070c;--panel:#08121bcc;--line:#163244;--text:#e9f8ff;--muted:#7896a8;--cyan:#25f0c0;--warn:#ffbf52}*{box-sizing:border-box}body{margin:0;overflow:hidden;background:radial-gradient(circle at 50% 45%,#0b2130 0,#050b12 34%,#020509 75%);font-family:Inter,Segoe UI,Arial,sans-serif;color:var(--text)}
.shell{height:100vh;padding:14px;display:grid;grid-template-rows:54px 1fr 62px;gap:10px}.top,.bottom{display:flex;align-items:center;justify-content:space-between;border:1px solid var(--line);background:#061019aa;backdrop-filter:blur(12px);border-radius:14px;padding:0 16px}.brand{display:flex;align-items:center;gap:12px}.mini{width:29px;height:29px;border:1px solid var(--cyan);border-radius:50%;box-shadow:0 0 18px #25f0c088}.title{font-weight:800;letter-spacing:.18em}.sub,.muted{font-size:10px;color:var(--muted)}.ready{color:var(--cyan);font-size:11px}.main{display:grid;grid-template-columns:255px minmax(420px,1fr) 285px;gap:10px;min-height:0}.rail{display:flex;flex-direction:column;gap:10px;min-height:0}.card{border:1px solid var(--line);background:linear-gradient(180deg,#0a151ecc,#061019cc);backdrop-filter:blur(12px);border-radius:14px;padding:12px;overflow:auto}.card h3{font-size:10px;letter-spacing:.14em;color:#a9c8d8;margin:0 0 10px}.stat{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #102634;font-size:11px}.dot{width:7px;height:7px;border-radius:50%;display:inline-block;background:var(--cyan);box-shadow:0 0 9px var(--cyan);margin-right:7px}.center{position:relative;border:1px solid var(--line);border-radius:18px;overflow:hidden;background:radial-gradient(circle at center,#0a2633 0,#061019 35%,#03080d 72%)}
.grid{position:absolute;inset:0;opacity:.22;background-image:linear-gradient(#1d4d5f 1px,transparent 1px),linear-gradient(90deg,#1d4d5f 1px,transparent 1px);background-size:42px 42px;transform:perspective(500px) rotateX(62deg) scale(1.8);transform-origin:center 70%}.core-wrap{position:absolute;left:50%;top:45%;transform:translate(-50%,-50%);width:390px;height:390px}.orbit{position:absolute;inset:0;border:1px solid #2bf0c02b;border-radius:50%;animation:spin 18s linear infinite}.orbit.o2{inset:45px;border-style:dashed;animation-duration:12s;animation-direction:reverse}.orbit.o3{inset:90px;animation-duration:8s}.core{position:absolute;left:50%;top:50%;width:130px;height:130px;transform:translate(-50%,-50%);border-radius:50%;background:radial-gradient(circle at 38% 32%,#cafff1 0,#32f1c9 5%,#087b82 24%,#062735 58%,#02070b 75%);box-shadow:0 0 35px #25f0c088,0 0 100px #20cfff33,inset -18px -18px 35px #0009;animation:pulse 3.2s ease-in-out infinite}.core:after{content:'';position:absolute;inset:-15px;border:1px solid #66ffe044;border-radius:50%;animation:pulse 2s infinite}.node{position:absolute;width:12px;height:12px;border:2px solid var(--cyan);background:#071018;border-radius:50%;box-shadow:0 0 13px var(--cyan)}.n1{left:48px;top:90px}.n2{right:42px;top:122px}.n3{left:88px;bottom:50px}.n4{right:94px;bottom:42px}.n5{left:188px;top:8px}.core-label{position:absolute;left:50%;top:calc(45% + 92px);transform:translateX(-50%);text-align:center}.core-label strong{font-size:13px;letter-spacing:.2em}.core-label div{font-size:10px;color:var(--cyan);margin-top:5px}.activity{position:absolute;left:18px;right:18px;bottom:18px;display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.chip{padding:9px;border:1px solid var(--line);border-radius:9px;background:#07131dcc;font-size:10px;color:#9fbccc;text-align:center}.command{position:absolute;left:50%;top:18px;transform:translateX(-50%);width:min(650px,80%);display:flex;gap:8px}.command input{flex:1;background:#041018dd;border:1px solid #205067;color:var(--text);border-radius:999px;padding:12px 17px;outline:none}.btn{background:#0b1b26;border:1px solid #24506a;color:var(--text);border-radius:999px;padding:0 15px;cursor:pointer}.btn.primary{background:var(--cyan);color:#02100c;border-color:var(--cyan);font-weight:700}.log{font:11px ui-monospace,Consolas,monospace;color:#a8c9d7;white-space:pre-wrap;line-height:1.55}.avatar{height:135px;display:grid;place-items:center}.head{width:74px;height:92px;border:1px solid #2beac0;border-radius:44% 44% 48% 48%;background:linear-gradient(145deg,#123243,#06131c);box-shadow:0 0 28px #25f0c044;position:relative}.eye{position:absolute;top:39px;width:12px;height:4px;background:var(--cyan);box-shadow:0 0 8px var(--cyan)}.eye.l{left:16px}.eye.r{right:16px}.mouth{position:absolute;left:27px;bottom:20px;width:20px;height:1px;background:#38a8bd}.bars{display:flex;gap:3px;align-items:center;height:22px}.bars i{display:block;width:3px;background:var(--cyan);height:6px;animation:eq 1s ease-in-out infinite}.screen-buttons{display:flex;gap:8px}.screen-buttons button{font-size:10px;padding:7px 10px}.bottom .statusline{font:11px ui-monospace,Consolas,monospace;color:#9ebccc}.risk{color:var(--warn)}
@keyframes spin{to{transform:rotate(360deg)}}@keyframes pulse{50%{filter:brightness(1.22);box-shadow:0 0 55px #25f0c0aa,0 0 130px #20cfff44,inset -18px -18px 35px #0009}}@keyframes eq{50%{height:20px}}@media(max-width:1050px){body{overflow:auto}.shell{height:auto;min-height:100vh}.main{grid-template-columns:1fr}.center{height:620px}.rail{display:grid;grid-template-columns:1fr 1fr}}
</style></head><body><div class="shell"><header class="top"><div class="brand"><div class="mini"></div><div><div class="title">AURON</div><div class="sub">CONVERSATIONAL COMMAND CENTER · v21.242</div></div></div><div class="ready" id="overall">● CONNECTING</div></header>
<main class="main"><aside class="rail"><section class="card"><h3>SYSTEM MATRIX</h3><div class="stat"><span><i class="dot"></i>System</span><b id="sys">…</b></div><div class="stat"><span><i class="dot"></i>Memory</span><b id="mem">…</b></div><div class="stat"><span><i class="dot"></i>Voice</span><b id="voice">…</b></div><div class="stat"><span><i class="dot"></i>Approvals</span><b id="approvals">…</b></div><div class="stat"><span><i class="dot"></i>Tools</span><b id="tools">…</b></div></section><section class="card" style="flex:1"><h3>LIVE ACTIVITY</h3><div class="log" id="log">AURON online. Bereit.</div></section></aside>
<section class="center"><div class="grid"></div><div class="command"><input id="command" value="Auron, Master Brano ist hier."><button class="btn" id="mic">🎙</button><button class="btn primary" id="run">RUN</button></div><div class="core-wrap"><div class="orbit"><i class="node n1"></i><i class="node n2"></i><i class="node n3"></i><i class="node n4"></i><i class="node n5"></i></div><div class="orbit o2"></div><div class="orbit o3"></div><div class="core"></div></div><div class="core-label"><strong>AURON CORE</strong><div id="corestate">STANDBY</div></div><div class="activity"><div class="chip" id="intent">INTENTS · 0</div><div class="chip" id="steps">STEPS · 0</div><div class="chip" id="approval">APPROVAL · NO</div><div class="chip" id="channel">VOICE · READY</div></div></section>
<aside class="rail"><section class="card"><h3>AURON AVATAR</h3><div class="avatar"><div class="head"><i class="eye l"></i><i class="eye r"></i><i class="mouth"></i></div></div><div style="text-align:center"><b>AURON</b><div class="muted">Awaiting MASTER Brano</div></div></section><section class="card" style="flex:1"><h3>ACTIVE PROCESSES</h3><div id="processes" class="log">No active execution.</div></section><section class="card"><h3>DISPLAY MATRIX</h3><div class="screen-buttons"><button class="btn" onclick="setView('trading')">SCREEN 1</button><button class="btn" onclick="setView('core')">SCREEN 2</button><button class="btn" onclick="setView('agents')">SCREEN 3</button></div><div class="muted" id="viewmsg" style="margin-top:9px">Core view active</div></section></aside></main>
<footer class="bottom"><div class="statusline" id="summary">READY FOR OPERATOR INPUT</div><div class="bars"><i></i><i></i><i></i><i></i></div><div class="statusline">HIGH-RISK AUTONOMY: <span class="risk">DISABLED</span></div></footer></div>
<script>
const E=id=>document.getElementById(id),safe=x=>String(x??'');async function post(u,b){const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});if(!r.ok)throw Error('HTTP '+r.status);return r.json()}function addLog(t){E('log').textContent=new Date().toLocaleTimeString()+'  '+t+'\n'+E('log').textContent}
async function refresh(){try{const d=await post('/phoenix/demo1/v21.230/dashboard',{workspace_id:'demo',operator_id:'brano',risk_brain_hard_block:false});E('overall').textContent='● '+d.state.toUpperCase();E('sys').textContent=d.state;E('mem').textContent=d.memory_provider_bound?'ready':'degraded';E('voice').textContent=d.voice_adapter_bound?'ready':'degraded';E('approvals').textContent=d.pending_approvals+' pending';E('tools').textContent=d.concrete_tool_adapters_bound?'ready':'degraded';E('channel').textContent='VOICE · '+(d.voice_adapter_bound?'READY':'OFFLINE')}catch(e){E('overall').textContent='● OFFLINE';addLog('Statusfehler')}}
function pickVoice(){const vs=speechSynthesis.getVoices();const de=vs.filter(v=>/^de/i.test(v.lang));const score=v=>{const n=v.name.toLowerCase();let s=0;if(n.includes('conrad'))s+=100;if(n.includes('natural'))s+=60;if(n.includes('microsoft'))s+=30;if(n.includes('google'))s+=20;if(n.includes('male'))s+=10;return s};return de.sort((a,b)=>score(b)-score(a))[0]||vs[0]}
function speak(text){if(!('speechSynthesis'in window)||!text)return;const u=new SpeechSynthesisUtterance(text);u.lang='de-DE';u.rate=.96;u.pitch=.9;const v=pickVoice();if(v)u.voice=v;speechSynthesis.cancel();speechSynthesis.speak(u)}
async function run(){const c=E('command').value.trim();if(!c)return;E('corestate').textContent='THINKING';E('run').disabled=true;addLog('YOU > '+c);try{const d=await post('/auron/demo1/v21.242/dialogue',{session_id:'auron-'+Date.now(),workspace_id:'demo',operator_id:'brano',command:c,risk_brain_hard_block:false});const intents=d.detected_intents||[],steps=d.steps||[];E('intent').textContent='INTENTS · '+intents.length;E('steps').textContent='STEPS · '+steps.length;E('approval').textContent='APPROVAL · '+(d.approval_required?'YES':'NO');E('corestate').textContent=d.mode==='conversation'?'DIALOGUE':safe(d.state).toUpperCase();E('summary').textContent=d.reply;E('processes').textContent=steps.length?steps.map((s,i)=>(i+1)+'. '+(s.intent||s.capability)+' ['+s.state+']').join('\n'):'No active execution.';addLog('AURON > '+d.reply);speak(d.reply)}catch(e){E('corestate').textContent='ERROR';addLog('AURON > Fehler bei der Verarbeitung.')}finally{E('run').disabled=false;refresh()}}
E('run').onclick=run;E('command').onkeydown=e=>{if(e.key==='Enter')run()};E('mic').onclick=()=>{const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){addLog('Voice input unavailable');return}const r=new SR();r.lang='de-DE';r.onresult=e=>{E('command').value=e.results[0][0].transcript;run()};r.start()};function setView(v){E('viewmsg').textContent=v.toUpperCase()+' view selected';addLog('VIEW > '+v)}speechSynthesis.onvoiceschanged=()=>pickVoice();refresh();setInterval(refresh,15000);
</script></body></html>'''
