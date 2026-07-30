from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix='/phoenix/demo1/v21.240', tags=['phoenix-demo1-interface'])


@router.get('/console', response_class=HTMLResponse)
def console() -> str:
    return r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>PHOENIX Operator Console</title>
<style>
:root{color-scheme:dark;--bg:#070b10;--panel:#0e151d;--panel2:#111c26;--line:#22303d;--text:#eaf2f8;--muted:#8da0af;--accent:#29f0b4;--warn:#f4b942;--bad:#ff5f6d}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 50% -20%,#152836 0,#070b10 42%);font-family:Inter,Segoe UI,Arial,sans-serif;color:var(--text)}
.shell{max-width:1380px;margin:0 auto;padding:24px}.top{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:22px}.brand{display:flex;align-items:center;gap:14px}.orb{width:48px;height:48px;border:2px solid var(--accent);border-radius:50%;box-shadow:0 0 28px #29f0b455,inset 0 0 18px #29f0b433}.title{font-size:22px;font-weight:700;letter-spacing:.08em}.sub{color:var(--muted);font-size:13px}.badge{border:1px solid var(--line);background:var(--panel);padding:8px 12px;border-radius:999px;color:var(--accent);font-size:12px}
.status-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:18px}.status{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:12px}.status strong{display:block;font-size:12px;margin-bottom:7px}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--accent);box-shadow:0 0 10px #29f0b488;margin-right:6px}.muted{color:var(--muted);font-size:12px}
.layout{display:grid;grid-template-columns:1.2fr .8fr;gap:18px}.stack{display:flex;flex-direction:column;gap:18px}.card{background:linear-gradient(180deg,var(--panel),#0a1118);border:1px solid var(--line);border-radius:16px;padding:18px}.card h2{margin:0 0 14px;font-size:14px;letter-spacing:.08em;text-transform:uppercase;color:#b9c8d4}
textarea{width:100%;min-height:120px;background:#070c11;border:1px solid var(--line);border-radius:12px;color:var(--text);padding:14px;font:inherit;resize:vertical}textarea:focus{outline:1px solid var(--accent)}.actions{display:flex;gap:10px;margin-top:12px;flex-wrap:wrap}.btn{border:1px solid var(--line);background:var(--panel2);color:var(--text);padding:10px 14px;border-radius:10px;cursor:pointer}.btn.primary{background:var(--accent);color:#03110d;border-color:var(--accent);font-weight:700}.btn:disabled{opacity:.5;cursor:not-allowed}
.output{margin-top:16px;min-height:120px;background:#070c11;border:1px solid var(--line);border-radius:12px;padding:14px;white-space:pre-wrap;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:13px;color:#cfe7dc}.steps,.history{display:flex;flex-direction:column;gap:9px}.step,.history-item{padding:11px;border:1px solid var(--line);background:var(--panel2);border-radius:10px}.step-head,.history-head{display:flex;justify-content:space-between;gap:8px;align-items:center}.ok{color:var(--accent)}.warn{color:var(--warn)}.bad{color:var(--bad)}.footer{margin-top:14px;color:var(--muted);font-size:11px}.risk{color:var(--accent)}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px}.metric{background:#070c11;border:1px solid var(--line);border-radius:10px;padding:12px}.metric span{display:block;color:var(--muted);font-size:11px;margin-bottom:6px}.metric strong{font-size:18px}.details{font-size:12px;color:#bcd0dc;white-space:pre-wrap;max-height:240px;overflow:auto;background:#070c11;border:1px solid var(--line);border-radius:10px;padding:12px}.empty{color:var(--muted)}
@media(max-width:950px){.layout{grid-template-columns:1fr}.status-grid{grid-template-columns:1fr 1fr}.metrics{grid-template-columns:1fr 1fr}.top{align-items:flex-start;flex-direction:column}}@media(max-width:520px){.status-grid,.metrics{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="shell">
  <div class="top">
    <div class="brand"><div class="orb"></div><div><div class="title">PHOENIX</div><div class="sub">Operator Console · Demo 1 · v21.240</div></div></div>
    <div class="badge" id="overall">CONNECTING</div>
  </div>

  <div class="status-grid">
    <div class="status"><strong>System</strong><span class="dot"></span><span id="s-system">…</span></div>
    <div class="status"><strong>Memory</strong><span class="dot"></span><span id="s-memory">…</span></div>
    <div class="status"><strong>Voice</strong><span class="dot"></span><span id="s-voice">…</span></div>
    <div class="status"><strong>Approvals</strong><span class="dot"></span><span id="s-approvals">…</span></div>
    <div class="status"><strong>Tools</strong><span class="dot"></span><span id="s-tools">…</span></div>
  </div>

  <div class="layout">
    <div class="stack">
      <section class="card">
        <h2>Operator Command</h2>
        <textarea id="command">Phoenix, check TradingView alerts and voice status.</textarea>
        <div class="actions">
          <button class="btn primary" id="run">Run Command</button>
          <button class="btn" id="mic">🎙 Voice</button>
          <button class="btn" id="refresh">Refresh Status</button>
          <button class="btn" id="clearHistory">Clear History</button>
        </div>
        <div class="output" id="output">Ready for operator command.</div>
        <div class="footer">High-risk autonomous execution: <span class="risk">DISABLED</span> · Financial actions require approval.</div>
      </section>

      <section class="card">
        <h2>Live Result</h2>
        <div class="metrics">
          <div class="metric"><span>Result</span><strong id="m-result">—</strong></div>
          <div class="metric"><span>Intents</span><strong id="m-intents">0</strong></div>
          <div class="metric"><span>Steps</span><strong id="m-steps">0</strong></div>
          <div class="metric"><span>Approval</span><strong id="m-approval">NO</strong></div>
        </div>
        <div class="details" id="details">No result yet.</div>
      </section>
    </div>

    <div class="stack">
      <aside class="card">
        <h2>Execution Plan</h2>
        <div class="steps" id="steps"><div class="step muted">No command executed yet.</div></div>
      </aside>
      <aside class="card">
        <h2>Command History</h2>
        <div class="history" id="history"><div class="history-item muted">No commands yet.</div></div>
      </aside>
    </div>
  </div>
</div>
<script>
const el=id=>document.getElementById(id); const history=[];
const safe=t=>String(t??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
const post=async(url,body)=>{const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw new Error('HTTP '+r.status);return r.json()};
async function refresh(){
  try{const d=await post('/phoenix/demo1/v21.230/dashboard',{workspace_id:'demo',operator_id:'brano',risk_brain_hard_block:false});el('overall').textContent=d.state.toUpperCase();el('s-system').textContent=d.state;el('s-memory').textContent=d.memory_provider_bound?'ready':'degraded';el('s-voice').textContent=d.voice_adapter_bound?'ready':'degraded';el('s-approvals').textContent=String(d.pending_approvals)+' pending';el('s-tools').textContent=d.concrete_tool_adapters_bound?'ready':'degraded'}catch(e){el('overall').textContent='OFFLINE';el('output').textContent='Status refresh failed: '+e.message}
}
function renderHistory(){
  if(!history.length){el('history').innerHTML='<div class="history-item muted">No commands yet.</div>';return}
  el('history').innerHTML=history.slice().reverse().map(h=>'<div class="history-item"><div class="history-head"><strong>'+safe(h.command)+'</strong><span class="'+(h.state==='completed'?'ok':h.state==='approval-required'?'warn':'bad')+'">'+safe(h.state)+'</span></div><div class="muted">'+safe(h.time)+' · '+safe(h.summary)+'</div></div>').join('');
}
function renderResult(data){
  const intents=data.detected_intents||[], steps=data.steps||[];el('m-result').textContent=(data.state||'—').toUpperCase();el('m-intents').textContent=String(intents.length);el('m-steps').textContent=String(steps.length);el('m-approval').textContent=data.approval_required?'YES':'NO';
  el('details').textContent=JSON.stringify({detected_intents:intents,selected_capabilities:data.selected_capabilities||[],reasons:data.reasons||[]},null,2);
  el('steps').innerHTML='';
  if(steps.length){steps.forEach(s=>{const d=document.createElement('div');d.className='step';const c=s.state==='completed'?'ok':(s.state==='approval-required'?'warn':'bad');d.innerHTML='<div class="step-head"><strong>'+safe(s.intent)+'</strong><span class="'+c+'">'+safe(s.state)+'</span></div><div class="muted">'+safe(s.adapter_id)+' / '+safe(s.capability)+'</div>';el('steps').appendChild(d)})}
  else if((data.selected_capabilities||[]).length){el('steps').innerHTML=(data.selected_capabilities||[]).map(x=>'<div class="step"><div class="step-head"><strong>'+safe(x)+'</strong><span class="warn">approval required</span></div></div>').join('')}
  else{el('steps').innerHTML='<div class="step muted">No supported intent detected.</div>'}
}
async function run(){
  const command=el('command').value.trim();if(!command)return;el('run').disabled=true;el('output').textContent='PHOENIX is routing the command…';
  try{const data=await post('/phoenix/demo1/v21.238/route-and-execute',{session_id:'ui-'+Date.now(),workspace_id:'demo',operator_id:'brano',command,risk_brain_hard_block:false});el('output').textContent=data.operator_summary||JSON.stringify(data,null,2);renderResult(data);history.push({time:new Date().toLocaleTimeString(),command,state:data.state||'unknown',summary:data.operator_summary||''});renderHistory();if('speechSynthesis' in window&&data.operator_summary){const u=new SpeechSynthesisUtterance(data.operator_summary);u.lang='de-DE';speechSynthesis.cancel();speechSynthesis.speak(u)}}catch(e){el('output').textContent='Execution failed: '+e.message;el('m-result').textContent='ERROR'}finally{el('run').disabled=false;refresh()}
}
el('run').addEventListener('click',run);el('refresh').addEventListener('click',refresh);el('clearHistory').addEventListener('click',()=>{history.length=0;renderHistory()});
el('command').addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter')run()});
el('mic').addEventListener('click',()=>{const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){el('output').textContent='Browser speech recognition is unavailable.';return}const r=new SR();r.lang='de-DE';r.interimResults=false;r.onresult=e=>{el('command').value=e.results[0][0].transcript;run()};r.onerror=e=>el('output').textContent='Voice input error: '+e.error;r.start()});
refresh();
</script>
</body>
</html>'''
