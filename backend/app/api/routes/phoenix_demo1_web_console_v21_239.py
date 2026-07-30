from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix='/phoenix/demo1/v21.239', tags=['phoenix-demo1-interface'])


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
.shell{max-width:1220px;margin:0 auto;padding:24px}.top{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:22px}.brand{display:flex;align-items:center;gap:14px}.orb{width:48px;height:48px;border:2px solid var(--accent);border-radius:50%;box-shadow:0 0 28px #29f0b455,inset 0 0 18px #29f0b433}.title{font-size:22px;font-weight:700;letter-spacing:.08em}.sub{color:var(--muted);font-size:13px}.badge{border:1px solid var(--line);background:var(--panel);padding:8px 12px;border-radius:999px;color:var(--accent);font-size:12px}
.grid{display:grid;grid-template-columns:1.25fr .75fr;gap:18px}.card{background:linear-gradient(180deg,var(--panel),#0a1118);border:1px solid var(--line);border-radius:16px;padding:18px}.card h2{margin:0 0 14px;font-size:14px;letter-spacing:.08em;text-transform:uppercase;color:#b9c8d4}.status-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:18px}.status{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:12px}.status strong{display:block;font-size:12px;margin-bottom:7px}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--accent);box-shadow:0 0 10px #29f0b488;margin-right:6px}.muted{color:var(--muted);font-size:12px}
textarea{width:100%;min-height:130px;background:#070c11;border:1px solid var(--line);border-radius:12px;color:var(--text);padding:14px;font:inherit;resize:vertical}textarea:focus{outline:1px solid var(--accent)}.actions{display:flex;gap:10px;margin-top:12px}.btn{border:1px solid var(--line);background:var(--panel2);color:var(--text);padding:10px 14px;border-radius:10px;cursor:pointer}.btn.primary{background:var(--accent);color:#03110d;border-color:var(--accent);font-weight:700}.btn:disabled{opacity:.5;cursor:not-allowed}
.output{margin-top:16px;min-height:170px;background:#070c11;border:1px solid var(--line);border-radius:12px;padding:14px;white-space:pre-wrap;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:13px;color:#cfe7dc}.steps{display:flex;flex-direction:column;gap:9px}.step{padding:11px;border:1px solid var(--line);background:var(--panel2);border-radius:10px}.step-head{display:flex;justify-content:space-between;gap:8px}.ok{color:var(--accent)}.warn{color:var(--warn)}.bad{color:var(--bad)}.footer{margin-top:14px;color:var(--muted);font-size:11px}.risk{color:var(--accent)}
@media(max-width:850px){.grid{grid-template-columns:1fr}.status-grid{grid-template-columns:1fr 1fr}.top{align-items:flex-start;flex-direction:column}}@media(max-width:520px){.status-grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="shell">
  <div class="top">
    <div class="brand"><div class="orb"></div><div><div class="title">PHOENIX</div><div class="sub">Operator Console · Demo 1 · v21.239</div></div></div>
    <div class="badge" id="overall">CONNECTING</div>
  </div>

  <div class="status-grid" id="statusGrid">
    <div class="status"><strong>System</strong><span class="dot"></span><span id="s-system">…</span></div>
    <div class="status"><strong>Memory</strong><span class="dot"></span><span id="s-memory">…</span></div>
    <div class="status"><strong>Voice</strong><span class="dot"></span><span id="s-voice">…</span></div>
    <div class="status"><strong>Approvals</strong><span class="dot"></span><span id="s-approvals">…</span></div>
    <div class="status"><strong>Tools</strong><span class="dot"></span><span id="s-tools">…</span></div>
  </div>

  <div class="grid">
    <section class="card">
      <h2>Operator Command</h2>
      <textarea id="command" placeholder="Phoenix, check TradingView alerts and voice status.">Phoenix, check system readiness and available tools.</textarea>
      <div class="actions">
        <button class="btn primary" id="run">Run Command</button>
        <button class="btn" id="mic">🎙 Voice</button>
        <button class="btn" id="refresh">Refresh Status</button>
      </div>
      <div class="output" id="output">Ready for operator command.</div>
      <div class="footer">High-risk autonomous execution: <span class="risk">DISABLED</span> · Financial actions require approval.</div>
    </section>

    <aside class="card">
      <h2>Execution Plan</h2>
      <div class="steps" id="steps"><div class="step muted">No command executed yet.</div></div>
    </aside>
  </div>
</div>
<script>
const el=id=>document.getElementById(id);
const post=async(url,body)=>{const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw new Error('HTTP '+r.status);return r.json()};
async function refresh(){
  try{
    const d=await post('/phoenix/demo1/v21.230/dashboard',{workspace_id:'demo',operator_id:'brano',risk_brain_hard_block:false});
    el('overall').textContent=d.state.toUpperCase();
    el('s-system').textContent=d.state;
    el('s-memory').textContent=d.memory_provider_bound?'ready':'degraded';
    el('s-voice').textContent=d.voice_adapter_bound?'ready':'degraded';
    el('s-approvals').textContent=String(d.pending_approvals)+' pending';
    el('s-tools').textContent=d.concrete_tool_adapters_bound?'ready':'degraded';
  }catch(e){el('overall').textContent='OFFLINE';el('output').textContent='Status refresh failed: '+e.message}
}
async function run(){
  const command=el('command').value.trim(); if(!command)return;
  el('run').disabled=true; el('output').textContent='PHOENIX is routing the command…'; el('steps').innerHTML='';
  try{
    const data=await post('/phoenix/demo1/v21.238/route-and-execute',{session_id:'ui-'+Date.now(),workspace_id:'demo',operator_id:'brano',command,risk_brain_hard_block:false});
    el('output').textContent=data.operator_summary || JSON.stringify(data,null,2);
    const selected=data.selected_capabilities||[]; const steps=data.steps||[];
    if(steps.length){
      steps.forEach(s=>{const d=document.createElement('div');d.className='step';const c=s.state==='completed'?'ok':(s.state==='approval-required'?'warn':'bad');d.innerHTML='<div class="step-head"><strong>'+s.intent+'</strong><span class="'+c+'">'+s.state+'</span></div><div class="muted">'+s.adapter_id+' / '+s.capability+'</div>';el('steps').appendChild(d)});
    } else if(selected.length){
      selected.forEach(x=>{const d=document.createElement('div');d.className='step';d.innerHTML='<div class="step-head"><strong>'+x+'</strong><span class="warn">approval required</span></div>';el('steps').appendChild(d)});
    } else {el('steps').innerHTML='<div class="step muted">No supported intent detected.</div>'}
    if('speechSynthesis' in window && data.operator_summary){const u=new SpeechSynthesisUtterance(data.operator_summary);u.lang='de-DE';speechSynthesis.cancel();speechSynthesis.speak(u)}
  }catch(e){el('output').textContent='Execution failed: '+e.message}
  finally{el('run').disabled=false;refresh()}
}
el('run').addEventListener('click',run);el('refresh').addEventListener('click',refresh);
el('command').addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter')run()});
el('mic').addEventListener('click',()=>{const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){el('output').textContent='Browser speech recognition is unavailable.';return}const r=new SR();r.lang='de-DE';r.interimResults=false;r.onresult=e=>{el('command').value=e.results[0][0].transcript;run()};r.onerror=e=>el('output').textContent='Voice input error: '+e.error;r.start()});
refresh();
</script>
</body>
</html>'''
