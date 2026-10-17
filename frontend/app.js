// AURON live dashboard. Plain JS, no build step: nginx serves this file and
// proxies /api/ to the api container (same origin, no CORS).
const API = localStorage.getItem('auron_api') || (location.protocol === 'file:' ? 'http://localhost:8000' : '/api');
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (v, d = 2) => Number(v || 0).toLocaleString('de-DE', { minimumFractionDigits: d, maximumFractionDigits: d });
const signed = (v, cur = '') => `<span class="${v > 0 ? 'up' : v < 0 ? 'down' : ''}">${v > 0 ? '+' : ''}${fmt(v)}${cur ? ' ' + esc(cur) : ''}</span>`;
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const nameOf = (a) => a.label || a.profile;  // what people call the account: its group's name

async function send(method, path, body) {
  const r = await fetch(`${API}${path}`, { method, headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `${path}: ${r.status}`);
  return data;
}

async function get(path) {
  const r = await fetch(`${API}${path}`, { headers: { Accept: 'application/json' } });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

// --- numbers that count to their new value ---------------------------------
const shown = new Map();
function tween(el, to, decimals = 2, suffix = '') {
  if (!el) return;
  const key = el.dataset.k || el.id;
  const from = shown.has(key) ? shown.get(key) : to;
  shown.set(key, to);
  if (from !== to) {
    el.classList.remove('flash-up', 'flash-down');
    void el.offsetWidth;
    el.classList.add(to > from ? 'flash-up' : 'flash-down');
  }
  if (reduced || from === to) { el.innerHTML = fmt(to, decimals) + suffix; return; }
  const t0 = performance.now(), dur = 900;
  const step = (t) => {
    const p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3);
    el.innerHTML = fmt(from + (to - from) * e, decimals) + suffix;
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// --- SVG curves ------------------------------------------------------------
function path(points, w, h, pad = 6) {
  const ys = points.map((p) => p.y);
  let lo = Math.min(...ys), hi = Math.max(...ys);
  if (hi - lo < 1e-9) { lo -= 1; hi += 1; }
  const xs = points.map((p) => p.x), x0 = Math.min(...xs), x1 = Math.max(...xs) || 1;
  const X = (x) => ((x - x0) / ((x1 - x0) || 1)) * w;
  const Y = (y) => pad + (1 - (y - lo) / (hi - lo)) * (h - 2 * pad);
  const pts = points.map((p) => [X(p.x), Y(p.y)]);
  const d = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  return { d, pts, lo, hi };
}

function drawChart(svg, series, color, h) {
  const w = 800;
  if (!series.length) { svg.innerHTML = ''; return; }
  if (series.length === 1) series = [series[0], { ...series[0], x: series[0].x + 1 }];
  const { d, pts, lo, hi } = path(series, w, h);
  const last = pts[pts.length - 1];
  const id = svg.id || 'g' + Math.random().toString(36).slice(2);
  svg.innerHTML = `
    <defs><linearGradient id="${id}-fill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="${color}" stop-opacity=".35"/><stop offset="1" stop-color="${color}" stop-opacity="0"/>
    </linearGradient></defs>
    <path class="area" d="${d} L${w},${h} L0,${h} Z" fill="url(#${id}-fill)"/>
    <path class="line" d="${d}" stroke="${color}"/>
    <circle class="head" cx="${last[0]}" cy="${last[1]}" r="4" fill="${color}"/>
`;
  const line = svg.querySelector('.line');
  line.style.setProperty('--len', Math.ceil(line.getTotalLength()));
}

// --- trading -----------------------------------------------------------------
let overview = null, history = {};  // history: equity points per profile (not window.history)

function renderTotals(o) {
  const totals = o.totals || [];
  if (!totals.length) return;
  $('#totals').innerHTML = totals.map((t) => `
    <div class="total">
      <div class="label">${esc(t.currency)} · ${t.accounts} ACCOUNT${t.accounts === 1 ? '' : 'S'} · EQUITY</div>
      <div class="big"><span data-k="tot-${esc(t.currency)}" id="tot-${esc(t.currency)}"></span><small>${esc(t.currency)}</small></div>
      <div class="chips">
        <span class="chip">today<b>${signed(t.pnl_today)}</b></span>
        <span class="chip">week<b>${signed(t.pnl_week)}</b></span>
        <span class="chip">total<b>${signed(t.pnl_total)}</b></span>
        <span class="chip">open ${t.open_positions}<b>${signed(t.open_pnl)}</b></span>
      </div>
    </div>`).join('');
  totals.forEach((t) => tween($(`#tot-${CSS.escape(t.currency)}`), t.equity));
}

function renderTotalChart() {
  // Sum the profiles of the main currency point by point (5-minute buckets).
  if (!overview) return;
  const main = (overview.totals[0] || {}).currency;
  const profiles = overview.accounts.filter((a) => a.currency === main).map((a) => a.profile);
  const buckets = new Map();
  profiles.forEach((p) => (history[p] || []).forEach((pt) => {
    const b = Math.floor(Date.parse(pt.at) / 300000);
    const cur = buckets.get(b) || {};
    cur[p] = pt.equity;
    buckets.set(b, cur);
  }));
  const keys = [...buckets.keys()].sort((a, b) => a - b);
  const lastSeen = {};
  const series = keys.map((k) => {
    Object.assign(lastSeen, buckets.get(k));
    return { x: k, y: Object.values(lastSeen).reduce((s, v) => s + v, 0) };
  });
  // the live value as the newest point
  const live = overview.accounts.filter((a) => a.currency === main).reduce((s, a) => s + a.equity, 0);
  if (live) series.push({ x: (Date.now() / 300000), y: live });
  drawChart($('#totalChart'), series, '#8fb4ff', 160);
  // Range as text below the curve: SVG text in a stretched viewBox would be distorted.
  const ys = series.map((p) => p.y);
  $('#chartRange').textContent = ys.length ? `24 h · low ${fmt(Math.min(...ys))} · high ${fmt(Math.max(...ys))}` : 'last 24 h';
  $('#chartUpdated').textContent = `updated ${new Date().toLocaleTimeString('de-DE')}`;
}

function renderAccounts(o) {
  const root = $('#accounts');
  root.innerHTML = o.accounts.map((a) => {
    const st = a.state === 'live' ? 'ok' : a.state === 'stale' ? 'warn' : 'bad';
    const today = a.groups.reduce((s, g) => s + g.pnl_today, 0);
    const total = a.groups.reduce((s, g) => s + g.pnl_total, 0);
    const open = a.groups.reduce((s, g) => s + g.open_positions, 0);
    return `
    <article class="card account">
      <div class="head">
        <div><div class="name">${esc(nameOf(a))}</div><div class="meta">${esc(a.account_login)} · ${esc(a.server)}</div></div>
        <span class="state"><span class="dot ${st}"></span>${esc(a.state).toUpperCase()}</span>
      </div>
      <div class="eq"><span data-k="eq-${esc(a.profile)}" id="eq-${esc(a.profile)}"></span> <small class="muted">${esc(a.currency)}</small></div>
      <div class="chips"><span class="chip">today<b>${signed(today)}</b></span><span class="chip">total<b>${signed(total)}</b></span><span class="chip">open<b>${open}</b></span></div>
      <svg class="spark" id="sp-${esc(a.profile)}" viewBox="0 0 800 48" preserveAspectRatio="none"></svg>
      <div class="mini">${a.groups.map((g) => `<div><span>${esc(g.name)}</span><span>${signed(g.pnl_total)}</span></div>`).join('')}</div>
      ${a.halt_reason ? `<div class="halt">⏸ ${esc(a.halt_reason)}</div>` : ''}
      <div class="acc-cmds">
        ${a.halt_reason ? `<button type="button" data-cmd="resume" data-p="${esc(a.profile)}">▶ Fortsetzen</button>`
          : `<button type="button" data-cmd="pause" data-p="${esc(a.profile)}">⏸ Pausieren</button>`}
        <button type="button" class="danger" data-cmd="close_all" data-p="${esc(a.profile)}" data-n="${esc(nameOf(a))}">✖ Alle schließen</button>
        <span class="cmd-msg" id="cm-${esc(a.profile)}"></span>
      </div>
    </article>`;
  }).join('');
  o.accounts.forEach((a) => {
    tween($(`#eq-${CSS.escape(a.profile)}`), a.equity);
    const pts = (history[a.profile] || []).map((p) => ({ x: Date.parse(p.at), y: p.equity }));
    pts.push({ x: Date.now(), y: a.equity });
    const rising = pts.length < 2 || pts[pts.length - 1].y >= pts[0].y;
    drawChart($(`#sp-${CSS.escape(a.profile)}`), pts, rising ? '#3ddc97' : '#f2647c', 48);
  });
}

$('#accounts').addEventListener('click', async (e) => {
  const b = e.target.closest('button[data-cmd]');
  if (!b) return;
  const { cmd, p, n } = b.dataset;
  if (cmd === 'close_all' && !confirm(`Wirklich ALLE Trades von „${n}“ schließen?\nOffene Positionen werden zum Marktpreis geschlossen, Limits gelöscht.`)) return;
  b.disabled = true;
  const msg = $(`#cm-${CSS.escape(p)}`);
  try {
    await send('POST', '/v1/copier/commands', { profile: p, action: cmd, confirmed: cmd === 'close_all' });
    msg.textContent = 'gesendet – der Kopierer führt es in bis zu 20 s aus';
  } catch (err) { msg.textContent = `Fehler: ${err.message}`; }
  setTimeout(() => { b.disabled = false; }, 20000);
});

function renderGroups(o) {
  const groups = (o.groups || []).filter((g) => g.closed_trades || g.open_positions || g.pnl_total);
  if (!groups.length) { $('#groups').innerHTML = '<div class="muted">No group has traded yet.</div>'; return; }
  const max = Math.max(...groups.map((g) => Math.abs(g.pnl_total)), 1);
  $('#groups').innerHTML = groups.map((g) => {
    const share = Math.abs(g.pnl_total) / max * 50;
    const pos = g.pnl_total >= 0;
    return `<div class="bar">
      <div class="row"><span>${esc(g.name)}</span><span>${signed(g.pnl_total, g.currency)}</span></div>
      <div class="rail"><i class="${pos ? 'pos' : 'neg'}" style="left:${pos ? 50 : 50 - share}%;width:${share}%"></i></div>
      <small>${esc(g.accounts.join(', '))} · ${g.closed_trades} closed · today ${signed(g.pnl_today)}</small>
    </div>`;
  }).join('');
}

function renderPositions(o) {
  const rows = o.accounts.flatMap((a) => a.open_positions.map((p) => ({ ...p, profile: nameOf(a), currency: a.currency })));
  $('#openCount').textContent = rows.length;
  $('#noPositions').style.display = rows.length ? 'none' : '';
  $('#positions').innerHTML = rows.length ? '<tr><th>ACCOUNT</th><th>SYMBOL</th><th></th><th>LOTS</th><th>ENTRY</th><th>SL</th><th>TP</th><th>PROFIT</th><th>GROUP</th></tr>' +
    rows.map((p) => `<tr>
      <td>${esc(p.profile)}</td><td>${esc(p.symbol)}</td><td><span class="side ${esc(p.side)}">${esc(p.side).toUpperCase()}</span></td>
      <td class="num">${fmt(p.volume)}</td><td class="num">${fmt(p.price_open)}</td><td class="num">${p.sl ? fmt(p.sl) : '–'}</td>
      <td class="num">${p.tp ? fmt(p.tp) : 'runner'}</td><td class="num"><span data-k="pp-${p.ticket}" id="pp-${p.ticket}"></span></td>
      <td>${esc(p.group)}</td></tr>`).join('') : '';
  rows.forEach((p) => {
    const el = $(`#pp-${p.ticket}`);
    tween(el, p.profit);
    el.className = p.profit > 0 ? 'up' : p.profit < 0 ? 'down' : '';
  });
}

// --- closed trades, newest first, filterable by group -----------------------------
let histGroup = '';
function renderHistory(o) {
  const all = o.accounts.flatMap((a) => (a.closed || []).map((t) => ({ ...t, profile: nameOf(a), currency: a.currency })))
    .sort((a, b) => b.closed - a.closed);
  const groups = [...new Set(all.map((t) => t.group))].sort();
  if (histGroup && !groups.includes(histGroup)) histGroup = '';
  $('#histFilter').innerHTML = groups.length > 1 ? ['', ...groups].map((g) =>
    `<button type="button" class="hchip${g === histGroup ? ' on' : ''}" data-g="${esc(g)}">${g ? esc(g) : 'Alle'}</button>`).join('') : '';
  const rows = histGroup ? all.filter((t) => t.group === histGroup) : all;
  const sum = rows.reduce((s, t) => s + t.profit, 0);
  $('#histCount').textContent = rows.length;
  $('#histSum').innerHTML = rows.length ? `<span class="${sum >= 0 ? 'up' : 'down'}">${signed(sum)}</span> · ${rows.filter((t) => t.profit > 0).length} im Plus` : '';
  $('#noHistory').style.display = rows.length ? 'none' : '';
  const why = (t) => /\[tp/i.test(t.comment) ? 'TP' : /\[sl/i.test(t.comment) ? (Math.abs(t.profit) < 0.05 ? 'Break-even' : t.profit > 0 ? 'SL im Plus' : 'SL') : 'geschlossen';
  const when = (s) => new Date(s * 1000).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  $('#history').innerHTML = rows.length ? '<tr><th>GESCHLOSSEN</th><th>ACCOUNT</th><th>SYMBOL</th><th></th><th>LOTS</th><th>ENTRY</th><th>EXIT</th><th>WIE</th><th>PROFIT</th><th>GROUP</th></tr>'
    + rows.map((t) => `<tr><td>${when(t.closed)}</td><td>${esc(t.profile)}</td><td>${esc(t.symbol)}</td>
      <td><span class="side ${esc(t.side)}">${esc(t.side).toUpperCase()}</span></td><td class="num">${fmt(t.volume)}</td>
      <td class="num">${t.price_open ? fmt(t.price_open) : '–'}</td><td class="num">${fmt(t.price_close)}</td><td>${why(t)}</td>
      <td class="num ${t.profit > 0 ? 'up' : t.profit < 0 ? 'down' : ''}">${signed(t.profit)}</td><td>${esc(t.group)}</td></tr>`).join('') : '';
}
$('#histFilter').addEventListener('click', (e) => {
  const b = e.target.closest('.hchip');
  if (!b) return;
  histGroup = b.dataset.g;
  if (overview) renderHistory(overview);
});

// --- the trading tile: the short list -------------------------------------------
function renderTradingTile(o) {
  const t = (o.totals || [])[0];
  if (!t) return;
  tween($('#tTotal'), t.equity);
  $('#tCurrency').textContent = t.currency + (o.totals.length > 1 ? ` + ${o.totals.length - 1} more` : '');
  $('#tToday').innerHTML = `heute ${signed(t.pnl_today, t.currency)}`;
  const live = o.accounts.filter((a) => a.state === 'live').length;
  $('#tLive').textContent = live === o.accounts.length ? 'live' : `${live}/${o.accounts.length} live`;
  $('#tLive').classList.toggle('live', live === o.accounts.length);
  const groups = (o.groups || []).filter((g) => g.name !== '(not from a signal)');
  const stateOf = Object.fromEntries(o.accounts.map((a) => [a.profile, a.state]));
  const copier = (g) => {  // the group's copiers: all live -> ok, any late -> warn, else bad
    const states = (g.accounts || []).map((p) => stateOf[p]);
    return states.length && states.every((x) => x === 'live') ? 'ok' : states.some((x) => x === 'live' || x === 'stale') ? 'warn' : 'bad';
  };
  $('#tGroups').innerHTML = '<div class="cap"><span>Gruppen</span><span>heute</span><span>gesamt</span></div>' + (groups.length ? groups.map((g) =>
    `<div class="row grp"><span class="dot ${copier(g)}" title="Kopierer ${copier(g) === 'ok' ? 'online' : 'nicht online'}"></span><span>${esc(g.name)}</span>`
    + `<span class="mono">${signed(g.pnl_today)}</span><span>${signed(g.pnl_total)}</span></div>`).join('')
    : '<div class="row"><span></span><span class="muted">Noch keine Gruppe hat gehandelt</span><span></span></div>');
  $('#kToday').innerHTML = signed(t.pnl_today, t.currency);
  $('#kWeek').innerHTML = signed(t.pnl_week, t.currency);
  $('#kOpen').innerHTML = `${t.open_positions} <small class="muted">${signed(t.open_pnl)}</small>`;
  $('#kTotal').innerHTML = signed(t.pnl_total, t.currency);
  renderTileSpark(o, t.currency);
  // ring 1: one light per group -- green when up today (open trades included), red when down, white when flat
  ringLights('.o1', groups.map((g) => { const v = (g.pnl_today || 0) + (g.open_pnl || 0); return v > 0.005 ? 'g' : v < -0.005 ? 'r' : 'w'; }));
}

// The lights on one of the planet's rings, spread evenly around it.
function ringLights(sel, states) {
  const ring = document.querySelector(sel);
  if (!ring) return;
  const key = states.join(',');
  if (ring.dataset.lights === key) return;
  ring.dataset.lights = key;
  ring.innerHTML = (states.length ? states : ['w']).map((c, i, all) => {
    const a = (i / all.length) * 2 * Math.PI;
    return `<i class="${c}" style="left:calc(${50 + 50 * Math.sin(a)}% );top:calc(${50 - 50 * Math.cos(a)}% - 6px)"></i>`;
  }).join('');
}

function renderTileSpark(o, currency) {
  // The same 24 h equity line as the trading view, small and in the card.
  const profiles = o.accounts.filter((a) => a.currency === currency).map((a) => a.profile);
  const buckets = new Map();
  profiles.forEach((p) => (history[p] || []).forEach((pt) => {
    const k = Math.floor(Date.parse(pt.at) / 300000);
    buckets.set(k, { ...(buckets.get(k) || {}), [p]: pt.equity });
  }));
  const last = {}, series = [...buckets.keys()].sort((a, b) => a - b).map((k) => (Object.assign(last, buckets.get(k)), { x: k, y: Object.values(last).reduce((s, v) => s + v, 0) }));
  series.push({ x: Date.now() / 300000, y: o.accounts.filter((a) => a.currency === currency).reduce((s, a) => s + a.equity, 0) });
  drawChart($('#tSpark'), series, series[series.length - 1].y >= series[0].y ? '#3ddc97' : '#f2647c', 60);
}

async function refreshTrading() {
  try {
    overview = await get('/v1/copier/overview');
    renderTradingTile(overview);
    if (openView === 'trading') { renderTotals(overview); renderAccounts(overview); renderGroups(overview); renderPositions(overview); renderHistory(overview); renderTotalChart(); }
  } catch (e) { console.warn(e); }
}

async function refreshHistory() {
  try { history = await get('/v1/copier/history?hours=24'); if (openView === 'trading') { renderTotalChart(); renderAccounts(overview); } } catch (e) { console.warn(e); }
}

// --- instagram ---------------------------------------------------------------
let nextAt = null;

function parseNext(s) {
  // "19:00 reel" -> today (or tomorrow) at 19:00
  const m = /^(\d{1,2}):(\d{2})\s*(.*)$/.exec(s || '');
  if (!m) return null;
  const d = new Date(); d.setHours(+m[1], +m[2], 0, 0);
  if (d < new Date()) d.setDate(d.getDate() + 1);
  return { at: d, kind: m[3] };
}

function tickCountdown() {
  let text = '–';
  if (nextAt) {
    let s = Math.max(0, Math.round((nextAt - new Date()) / 1000));
    const h = Math.floor(s / 3600); s %= 3600;
    const m = Math.floor(s / 60); s %= 60;
    text = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }
  $('#countdown').textContent = text;
  $('#iCountdown').textContent = text;
}

async function refreshInstagram() {
  try {
    const [dash, sched] = await Promise.all([get('/v1/instagram/dashboard'), get('/v1/telegram-instagram/schedule')]);
    const left = dash.media_pool_available, used = dash.media_pool_used, all = left + used || 1;
    const n = parseNext(sched.next);
    nextAt = n ? n.at : null;
    const label = n ? `next: ${n.kind || 'post'} at ${sched.next.split(' ')[0]}${sched.already_posted_today ? ' · posted today' : ''}` : (sched.next || 'nothing scheduled');
    $('#iNext').textContent = label;
    $('#iBadge').textContent = dash.needs_your_review ? `${dash.needs_your_review} to review` : sched.running ? 'scheduled' : 'paused';
    $('#iBadge').classList.toggle('live', !!sched.running);
    // ring 2: Instagram -- green posted today, orange waiting for the slot or a decision, red when the schedule is not running
    ringLights('.o2', [!sched.running ? 'r' : sched.already_posted_today ? 'g' : 'o']);
    $('#nextKind').textContent = label;
    $('#iList').innerHTML = [['In pool', left], ['Drafts', dash.curated_drafts_pending], ['To review', dash.needs_your_review], ['Posted', dash.posted_total]]
      .map(([k, v]) => `<div class="row"><span></span><span>${k}</span><span>${esc(v)}</span></div>`).join('');
    tween($('#poolLeft'), left, 0);
    $('#poolArc').style.strokeDashoffset = 327 * (1 - left / all);
    $('#instaStats').innerHTML = [
      ['drafts', dash.curated_drafts_pending], ['to review', dash.needs_your_review], ['ready', dash.approved_ready_to_publish],
      ['posted', dash.posted_total], ['failed', dash.post_failed], ['used', used],
    ].map(([k, v]) => `<div><b>${esc(v)}</b><small>${k}</small></div>`).join('');
    $('#recent').innerHTML = (dash.recent_candidates || []).slice(0, 8).map((c) =>
      `<li><span>${esc(c.post_format.replace('_', ' '))} · ${esc(c.status)}</span><span>${new Date(c.created_at).toLocaleDateString('de-DE')}</span></li>`).join('');
    tickCountdown();
  } catch (e) { console.warn(e); ringLights('.o2', ['r']); }  // no answer from the API: trouble
}

// --- health: top bar, system tile, AURON's own line ------------------------------
async function refreshHealth() {
  const svcs = [];
  try { const h = await get('/health'); svcs.push(['API', h.status === 'healthy' ? 'ok' : 'warn']); } catch { svcs.push(['API', 'bad']); }
  try { const t = await get('/v1/telegram-instagram/status'); svcs.push(['Telegram bot', t.bot_reachable ? 'ok' : 'bad']); } catch { svcs.push(['Telegram bot', 'bad']); }
  try {  // the last good backup: green under 30 h, amber under 48 h, red after
    const b = await get('/v1/backup/status');
    const h = b.age_hours;
    svcs.push([h == null ? 'Backup · nie' : `Backup · vor ${h < 1 ? '<1' : Math.round(h)} h`, h == null ? 'bad' : h < 30 ? 'ok' : h < 48 ? 'warn' : 'bad']);
  } catch { /* the API is down; that shows already */ }
  (overview?.accounts || []).forEach((a) => svcs.push([`Copier ${nameOf(a)}`, a.state === 'live' ? 'ok' : a.state === 'stale' ? 'warn' : 'bad']));
  $('#sysbar').innerHTML = svcs.filter(([n]) => !n.startsWith('Copier ')).map(([n, c]) =>
    `<span><span class="dot ${c}"></span>${esc(n)}${n.startsWith('Backup') ? '' : ` · ${c === 'ok' ? 'online' : c === 'warn' ? 'late' : 'offline'}`}</span>`).join('');
  const bad = svcs.filter(([, c]) => c !== 'ok').length;
  $('#core').classList.toggle('degraded', bad > 0);
}

// --- 3D tiles: tilt toward the pointer ---------------------------------------------
document.querySelectorAll('.tile').forEach((tile) => {
  if (reduced || matchMedia('(hover: none)').matches) return;
  tile.addEventListener('pointermove', (e) => {
    const r = tile.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
    tile.style.setProperty('--ry', `${(x - .5) * 8}deg`);
    tile.style.setProperty('--rx', `${(.5 - y) * 8}deg`);
    tile.style.setProperty('--mx', `${x * 100}%`);
    tile.style.setProperty('--my', `${y * 100}%`);
  });
  tile.addEventListener('pointerleave', () => { tile.style.setProperty('--rx', '0deg'); tile.style.setProperty('--ry', '0deg'); });
});

// --- opening a tile into its full view (it grows out of the tile and back) --------
let openView = null, openedFrom = null;
const TITLES = { trading: 'Trading', instagram: 'Instagram', watchlist: 'Watchlist', smart: 'Smart Money' };

function morph(panel, rect, reverse) {
  const end = panel.getBoundingClientRect();
  const from = `translate(${rect.left - end.left}px, ${rect.top - end.top}px) scale(${rect.width / end.width}, ${rect.height / end.height})`;
  const frames = [{ transform: from, opacity: .3, borderRadius: '22px' }, { transform: 'none', opacity: 1 }];
  return panel.animate(reverse ? frames.reverse() : frames, { duration: reduced ? 0 : 520, easing: 'cubic-bezier(.2,.8,.2,1)' }).finished;
}

function open(view, fromTile, push = true) {
  openView = view; openedFrom = fromTile;
  $('#detailTitle').textContent = TITLES[view];
  document.querySelectorAll('.view').forEach((v) => v.classList.toggle('active', v.dataset.view === view));
  $('#detail').hidden = false;
  document.body.classList.add('locked');
  $('#detailPanel').scrollTop = 0;
  if (push) history_.pushState({ view }, '', `#${view}`);
  if (view === 'watchlist' && watch) renderWatchView(watch);
  if (view === 'smart') renderSmartView();
  if (view === 'trading' && overview) { renderTotals(overview); renderAccounts(overview); renderGroups(overview); renderPositions(overview); renderHistory(overview); renderTotalChart(); }
  if (fromTile) morph($('#detailPanel'), fromTile.getBoundingClientRect(), false);
  $('#close').focus();
}

async function close(push = true) {
  if (!openView) return;
  const tile = openedFrom;
  openView = null;
  if (tile && !reduced) await morph($('#detailPanel'), tile.getBoundingClientRect(), true).catch(() => {});
  $('#detail').hidden = true;
  document.body.classList.remove('locked');
  if (push && location.hash) history_.back();
  tile?.focus();
}

const history_ = window.history;
document.querySelectorAll('.tile[data-view]').forEach((tile) => tile.addEventListener('click', () => open(tile.dataset.view, tile)));
$('#close').addEventListener('click', () => close());
$('#detail').addEventListener('click', (e) => { if (e.target.id === 'detail') close(); });
addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });
addEventListener('popstate', () => {           // the phone's back button
  const v = location.hash.slice(1);
  if (TITLES[v]) open(v, $(`.tile[data-view="${v}"]`), false); else close(false);
});

// --- loops ---------------------------------------------------------------------
setInterval(() => {
  const now = new Date();
  $('#clock').textContent = now.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  $('#date').textContent = now.toLocaleDateString('de-DE', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  tickCountdown();
}, 1000);

// --- the whole scene leans toward the pointer ----------------------------------------
if (!reduced && matchMedia('(hover: hover)').matches) {
  addEventListener('pointermove', (e) => {
    const x = e.clientX / innerWidth - .5, y = e.clientY / innerHeight - .5;
    $('#scene').style.setProperty('--sy', `${x * 6}deg`);
    $('#scene').style.setProperty('--sx', `${-y * 4}deg`);
  });
}

// --- a slow field of points behind everything, near ones linked by faint lines ------------
(function field() {
  const c = $('#field'), g = c.getContext('2d');
  let w, h, pts;
  const size = () => {
    w = c.width = innerWidth * devicePixelRatio; h = c.height = innerHeight * devicePixelRatio;
    pts = Array.from({ length: Math.round(innerWidth * innerHeight / 14000) }, () => ({
      x: Math.random() * w, y: Math.random() * h, vx: (Math.random() - .5) * .15, vy: (Math.random() - .5) * .15, r: Math.random() * 1.4 + .3,
    }));
  };
  size(); addEventListener('resize', size);
  const link = 120 * devicePixelRatio;
  const draw = () => {
    g.clearRect(0, 0, w, h);
    for (const p of pts) {
      p.x = (p.x + p.vx + w) % w; p.y = (p.y + p.vy + h) % h;
      g.fillStyle = 'rgba(120,210,255,.55)'; g.beginPath(); g.arc(p.x, p.y, p.r * devicePixelRatio, 0, 7); g.fill();
    }
    g.lineWidth = devicePixelRatio * .6;
    for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++) {
      const dx = pts[i].x - pts[j].x, dy = pts[i].y - pts[j].y, d = Math.hypot(dx, dy);
      if (d < link) { g.strokeStyle = `rgba(79,216,255,${.12 * (1 - d / link)})`; g.beginPath(); g.moveTo(pts[i].x, pts[i].y); g.lineTo(pts[j].x, pts[j].y); g.stroke(); }
    }
    if (!reduced) requestAnimationFrame(draw);
  };
  draw();
})();

refreshHealth();  // at once: the bot check takes seconds and must not wait for the rest
refreshHistory().then(refreshTrading).then(refreshHealth).then(() => {
  const v = location.hash.slice(1);
  if (TITLES[v]) open(v, null, false);
});
refreshInstagram();
setInterval(refreshTrading, 5000);
setInterval(refreshHistory, 60000);
setInterval(refreshInstagram, 30000);

// --- post: important mail and reply drafts (backend/app/mail) ---------------------------
async function refreshMail() {
  try {
    const m = await get('/v1/mail?important_only=true&days=14');
    const open = m.items.filter((i) => !i.done);
    $('#mBadge').textContent = !m.connected ? 'nicht verbunden' : m.error ? 'Fehler' : open.length ? `${open.length} wichtig` : 'alles ruhig';
    $('#mBadge').classList.toggle('live', m.connected && !m.error);
    $('#mBadge').title = m.error || '';
    const who = (f) => esc((f.split('<')[0].trim().replace(/"/g, '') || f).slice(0, 40));
    $('#mList').innerHTML = open.slice(0, 3).map((i) => `<div class="row mail"><b title="${esc(i.subject)}">${who(i.from)} · ${esc(i.subject)}</b>`
      + `<button type="button" class="ok" data-done="${esc(i.id)}" title="Erledigt">✓</button><small>${esc(i.summary)}</small></div>`).join('')
      || '<div class="row"><span class="muted">Keine wichtige Post.</span></div>';
    $('#mDrafts').innerHTML = m.drafts.map((d) => `<div class="mail-draft"><b>Entwurf an ${who(d.to)}</b> · ${esc(d.subject)}`
      + `<p>${esc(d.body)}</p><div class="btns"><button type="button" class="go" data-send="${esc(d.id)}">Senden</button>`
      + `<button type="button" data-discard="${esc(d.id)}">Verwerfen</button></div></div>`).join('');
  } catch (e) { console.warn(e); $('#mBadge').textContent = 'offline'; }
}
$('#tileMail').addEventListener('click', async (e) => {
  const b = e.target.closest('button');
  if (!b) {  // anywhere else on the card: the mailbox itself
    // A plain link, not window.open(url, '_blank', 'noopener'): that third argument makes Edge open a
    // borderless popup from the fullscreen app window -- blank, and with no way to close it (2026-10-17).
    if (!e.target.closest('.card-gear, .card-menu')) {
      const a = Object.assign(document.createElement('a'), { href: 'https://mail.google.com/mail/u/0/#inbox', target: '_blank', rel: 'noopener noreferrer' });
      a.click();
    }
    return;
  }
  b.disabled = true;
  try {
    if (b.dataset.send) await send('POST', `/v1/mail/drafts/${b.dataset.send}/send`);
    else if (b.dataset.discard) await send('POST', `/v1/mail/drafts/${b.dataset.discard}/discard`);
    else if (b.dataset.done) await send('POST', `/v1/mail/${b.dataset.done}/done`, { done: true });
  } catch (err) { alert(`Fehler: ${err.message}`); }
  refreshMail();
});
refreshMail();
setInterval(refreshMail, 60000);

// --- smart money: macro dates and insider trades (backend/app/smartmoney) -------------------
let smart = null;
function renderBacktest(bt) {
  if (!bt) { $('#btTable').innerHTML = '<tr><td class="muted">Noch kein Test gelaufen (tools/insider_backtest.py).</td></tr>'; $('#btMeta').textContent = ''; return; }
  $('#btMeta').textContent = `${bt.with_prices} Fälle · ${bt.quarters[0] || ''}–${bt.quarters[bt.quarters.length - 1] || ''}`;
  const H = ['5', '20', '60', '120'];
  const cell = (st) => (!st || !st.n ? '<td class="num muted">–</td>'
    : `<td class="num"><span class="${st.avg > 0 ? 'up' : st.avg < 0 ? 'down' : ''}">${st.avg > 0 ? '+' : ''}${(st.avg * 100).toFixed(1)} %</span>`
      + `<small class="bt-hit">${Math.round(st.hit * 100)} % · ${st.n}</small></td>`);
  const block = (title, table, order) => {
    const keys = order ? order.filter((k) => table[k]) : Object.keys(table);
    return `<tr class="bt-sec"><td colspan="5">${title}</td></tr>` + keys.map((k) => `<tr><td>${esc(k)}</td>${H.map((h) => cell(table[k][h])).join('')}</tr>`).join('');
  };
  $('#btTable').innerHTML = '<tr><th></th><th>5 TAGE</th><th>20 TAGE</th><th>60 TAGE</th><th>120 TAGE</th></tr>'
    + block('Gesamt', bt.overall, ['Käufe', 'Große Verkäufe'])
    + block('Wer kauft', bt.by_role, ['CEO/CFO', 'Officer', 'Director', '10%-Owner', 'Other'])
    + block('Einzeln oder Cluster', bt.by_cluster, ['Cluster', 'Einzeln'])
    + block('Wie viel', bt.by_size, ['≥ 1 Mio $', '100k–1 Mio $', '< 100k $']);
}

let biFilter = 'folgen';
function renderInsiders(list) {
  list = list || [];
  const counts = { folgen: 0, aussortieren: 0, offen: 0 };
  list.forEach((x) => counts[x.verdict]++);
  $('#biCount').textContent = list.length ? `${counts.folgen} folgen · ${counts.aussortieren} aussortieren · ${counts.offen} offen` : '';
  $('#biFilter').innerHTML = [['folgen', 'Folgen'], ['aussortieren', 'Aussortieren'], ['offen', 'Offen'], ['', 'Alle']].map(([k, n]) =>
    `<button type="button" class="hchip${k === biFilter ? ' on' : ''}" data-bi="${k}">${n}</button>`).join('');
  const rows = list.filter((x) => !biFilter || x.verdict === biFilter);
  $('#biTable').innerHTML = rows.length ? '<tr><th>INSIDER</th><th>AKTIE</th><th>ROLLE</th><th>KÄUFE</th><th>VERKÄUFE</th><th>RICHTIG</th><th>VORSPRUNG 60T</th><th>URTEIL</th></tr>'
    + rows.map((x) => `<tr><td>${esc(x.owner)}</td><td><b>${esc(x.ticker)}</b></td><td class="muted">${esc(x.role)}</td><td class="num">${x.buys}</td><td class="num">${x.sales}</td>`
      + `<td class="num">${Math.round(x.right * 100)} %</td><td class="num ${x.edge > 0 ? 'up' : 'down'}">${x.edge > 0 ? '+' : ''}${(x.edge * 100).toFixed(1)} %</td>`
      + `<td><span class="verdict ${x.verdict}">${x.verdict}</span></td></tr>`).join('')
    : '<tr><td class="muted">Noch keine Bilanz – erst der Backtest.</td></tr>';
}
$('#biFilter').addEventListener('click', (e) => { const b = e.target.closest('[data-bi]'); if (!b) return; biFilter = b.dataset.bi; renderInsiders(smart?.backtest?.by_insider); });

function renderSmartView() {
  const s = smart;
  if (!s) return;
  renderBacktest(s.backtest);
  renderInsiders(s.backtest?.by_insider);
  const verdictOf = Object.fromEntries((s.backtest?.by_insider || []).map((x) => [`${x.owner.toLowerCase()}|${x.ticker}`, x]));
  const day = (iso) => new Date(iso).toLocaleString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  $('#smMacro').innerHTML = s.macro.length ? '<tr><th>WANN</th><th></th><th>TERMIN</th><th>PROGNOSE</th><th>VORHER</th></tr>'
    + s.macro.map((e) => `<tr><td>${esc(day(e.at))}</td><td>${esc(e.currency)}</td><td>${esc(e.title_de ? `${e.title_de} (${e.title})` : e.title)}</td>`
      + `<td class="num">${esc(e.forecast || '–')}</td><td class="num">${esc(e.previous || '–')}</td></tr>`).join('')
    : '<tr><td class="muted">Keine großen Termine mehr diese Woche – der neue Kalender kommt sonntags.</td></tr>';
  const cl = Object.entries(s.clusters || {});
  $('#smClusterCount').textContent = cl.length;
  $('#smClusters').innerHTML = cl.length ? cl.map(([t, o]) => `<div><b>${esc(t)}</b>: ${o.map(esc).join(', ')}</div>`).join('') : 'Keine Häufung in den letzten 14 Tagen.';
  $('#smCount').textContent = s.insider.length;
  const money = (v) => (v >= 1e6 ? `${(v / 1e6).toFixed(2)} Mio $` : `${Math.round(v).toLocaleString('de-DE')} $`);
  $('#smInsider').innerHTML = !s.insider_connected ? '<tr><td class="muted">SEC-Kontakt fehlt.</td></tr>'
    : '<tr><th>DATUM</th><th>AKTIE</th><th>INSIDER</th><th>FUNKTION</th><th></th><th>STÜCK</th><th>KURS</th><th>WERT</th><th>BILANZ</th><th></th></tr>'
      + s.insider.map((t) => `<tr><td>${esc(new Date(t.traded_on).toLocaleDateString('de-DE'))}</td><td><b>${esc(t.name)}</b> <span class="muted">${esc(t.ticker)}</span></td>`
        + `<td>${esc(t.owner)}</td><td class="muted">${esc(t.title || '')}</td><td><span class="side ${t.code === 'P' ? 'buy' : 'sell'}">${t.code === 'P' ? 'KAUF' : 'VERKAUF'}</span></td>`
        + `<td class="num">${Math.round(t.shares || 0).toLocaleString('de-DE')}</td><td class="num">${fmt(t.price || 0)}</td><td class="num">${money(t.value)}</td>`
        + `<td>${(() => { const v = verdictOf[`${t.owner.toLowerCase()}|${t.ticker}`]; return v ? `<span class="verdict ${v.verdict}" title="${Math.round(v.right * 100)} % richtig in ${v.n} Trades">${v.verdict}</span>` : '<span class="muted">–</span>'; })()}</td>`
        + `<td>${t.url ? `<a href="${esc(t.url)}" target="_blank" rel="noopener">SEC</a>` : ''}</td></tr>`).join('');
}

async function refreshSmart() {
  try {
    const s = await get('/v1/smartmoney');
    smart = s;
    if (openView === 'smart') renderSmartView();
    const now = Date.now();
    const when = (iso) => new Date(iso).toLocaleString('de-DE', { weekday: 'short', hour: '2-digit', minute: '2-digit' });
    const ev = s.macro.slice(0, 3).map((e) => {
      const soon = Date.parse(e.at) - now < 3 * 3600e3;
      return `<div class="row ev"><span class="when ${soon ? 'soon' : ''}">${esc(when(e.at))}</span>`
        + `<span title="${esc(e.title)}">${esc(e.currency)} ${esc(e.title_de || e.title)}</span><span class="muted">${esc(e.forecast || '')}</span></div>`;
    }).join('');
    $('#sMacro').innerHTML = '<div class="cap"><span>Makro diese Woche</span></div>' + (ev || '<div class="row"><span class="muted">Keine großen Termine mehr</span></div>');
    const cl = Object.entries(s.clusters || {}).map(([t, o]) => `<div class="row ins cluster"><span class="bs P">${o.length}× KAUF</span><span>${esc(t)} – mehrere Insider</span><span></span></div>`);
    const big = (v) => (v >= 1e6 ? `${(v / 1e6).toFixed(1)} Mio $` : `${Math.round(v / 1e3)}k $`);
    const ins = s.insider.filter((t) => t.code === 'P' || t.value >= 1e6).slice(0, 3).map((t) =>
      `<div class="row ins"><span class="bs ${t.code}">${t.code === 'P' ? 'KAUF' : 'VERKAUF'}</span>`
      + `<span title="${esc(t.owner)} · ${esc(t.title)}">${esc(t.name)} · ${esc(t.owner.split(' ').slice(0, 2).join(' '))}</span><span class="mono">${big(t.value)}</span></div>`);
    $('#sInsider').innerHTML = '<div class="cap"><span>Insider (30 Tage)</span></div>'
      + (!s.insider_connected ? '<div class="row"><span class="muted">SEC-Kontakt fehlt noch</span></div>'
        : [...cl, ...ins].join('') || '<div class="row"><span class="muted">Keine Käufe auf deiner Watchlist</span></div>');
    $('#sBadge').textContent = Object.keys(s.clusters || {}).length ? 'Cluster!' : s.macro.length ? `${s.macro.length} Termine` : 'ruhig';
    $('#sBadge').classList.toggle('live', !s.macro_error);
  } catch (e) { console.warn(e); $('#sBadge').textContent = 'offline'; }
}
refreshSmart();
setInterval(refreshSmart, 120000);
setInterval(refreshHealth, 15000);

// --- weather next to the clock (Open-Meteo: free, no key) ------------------------------
// Where: the device's location if allowed (named via OpenStreetMap), otherwise Bad Kissingen.
// Refreshed every 15 min.
const WEATHER_FALLBACK = { lat: 50.20, lon: 10.08, place: 'Bad Kissingen' };
const WMO = [
  [[0], 'sun', 'klar'], [[1, 2], 'partly', 'leicht bewölkt'], [[3], 'cloud', 'bewölkt'], [[45, 48], 'fog', 'Nebel'],
  [[51, 53, 55, 56, 57], 'drizzle', 'Niesel'], [[61, 63, 65, 66, 67, 80, 81, 82], 'rain', 'Regen'],
  [[71, 73, 75, 77, 85, 86], 'snow', 'Schnee'], [[95, 96, 99], 'storm', 'Gewitter'],
];

// Animated weather icons, drawn here (styles.css moves them): the sun pulses, rain and snow
// fall out of the cloud, lightning flashes, fog drifts; strong wind adds sliding gusts.
function weatherIcon(kind, day, windy) {
  const cloud = (cls = '') => `<path class="wx-cloud ${cls}" d="M19 46h28a11 11 0 0 0 0-22 15 15 0 0 0-29-3A10 10 0 0 0 19 46z"/>`;
  const sun = (x = 32, y = 30, r = 10) => `<g class="wx-sun" style="transform-origin:${x}px ${y}px">`
    + [0, 45, 90, 135, 180, 225, 270, 315].map((a) => `<line x1="${x}" y1="${y - r - 4}" x2="${x}" y2="${y - r - 9}" transform="rotate(${a} ${x} ${y})"/>`).join('')
    + `<circle cx="${x}" cy="${y}" r="${r}"/></g>`;
  const moon = (x = 32, y = 30) => `<path class="wx-moon" d="M${x + 6} ${y - 13}a14 14 0 1 0 8 22 11 11 0 1 1-8-22z"/>`;
  const fall = (cls, n) => Array.from({ length: n }, (_, i) => `<line class="${cls}" x1="${22 + i * 9}" y1="49" x2="${20 + i * 9}" y2="55" style="animation-delay:${(i * 0.33).toFixed(2)}s"/>`).join('');
  const flakes = () => [0, 1, 2].map((i) => `<circle class="wx-flake" cx="${23 + i * 9}" cy="51" r="2" style="animation-delay:${i * 0.6}s"/>`).join('');
  const parts = {
    sun: () => (day ? sun() : moon()),
    partly: () => (day ? sun(24, 22, 8) : moon(22, 22)) + cloud('front'),
    cloud: () => cloud('drift'),
    fog: () => [0, 1, 2].map((i) => `<line class="wx-fog" x1="12" y1="${26 + i * 9}" x2="52" y2="${26 + i * 9}" style="animation-delay:${i * 0.8}s"/>`).join(''),
    drizzle: () => cloud() + fall('wx-drop slow', 3),
    rain: () => cloud() + fall('wx-drop', 4),
    snow: () => cloud() + flakes(),
    storm: () => cloud('dark') + '<path class="wx-bolt" d="M33 40l-6 10h6l-3 9 9-12h-6l4-7z"/>' + fall('wx-drop', 2),
  };
  const gust = windy ? '<path class="wx-wind" d="M6 20h22a4 4 0 1 0-4-4"/><path class="wx-wind w2" d="M10 58h26a4 4 0 1 1-4 4"/>' : '';
  return `<svg class="wx wx-${kind}" viewBox="0 0 64 64" aria-hidden="true">${(parts[kind] || parts.cloud)()}${gust}</svg>`;
}
let weatherAt = null;

function locate() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(WEATHER_FALLBACK);
    navigator.geolocation.getCurrentPosition(
      async (p) => {
        const at = { lat: p.coords.latitude, lon: p.coords.longitude, place: '' };
        try {  // the town's name for the coordinates (OpenStreetMap Nominatim, once per load)
          const r = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&zoom=10&accept-language=de&lat=${at.lat}&lon=${at.lon}`);
          const a = (await r.json()).address || {};
          at.place = a.city || a.town || a.village || a.municipality || a.county || '';
        } catch { /* coordinates are enough for the weather */ }
        resolve(at);
      },
      () => resolve(WEATHER_FALLBACK), { timeout: 8000, maximumAge: 3600000 });
  });
}

async function refreshWeather() {
  try {
    // An unanswered location prompt never calls back at all (its timeout only starts after
    // a yes) -- so after 10 s the weather comes from the fallback place instead of never.
    weatherAt = weatherAt || await Promise.race([locate(), new Promise((r) => setTimeout(() => r(WEATHER_FALLBACK), 10000))]);
    const u = `https://api.open-meteo.com/v1/forecast?latitude=${weatherAt.lat}&longitude=${weatherAt.lon}&current=temperature_2m,weather_code,is_day,wind_speed_10m&timezone=auto`;
    const r = await fetch(u);
    if (!r.ok) throw new Error(`weather ${r.status}`);
    const c = (await r.json()).current;
    const [, kind, text] = WMO.find(([codes]) => codes.includes(c.weather_code)) || [[], 'cloud', ''];
    const windy = (c.wind_speed_10m || 0) >= 30;  // km/h: a fresh breeze and up gets gusts in the icon
    $('#weather').innerHTML = `<div class="wtop">${weatherIcon(kind, c.is_day !== 0, windy)}<b>${Math.round(c.temperature_2m)}°C</b></div>`
      + `<span class="wtext">${esc(text)}${windy ? ', windig' : ''}${weatherAt.place ? ` · ${esc(weatherAt.place)}` : ''}</span>`;
  } catch (e) { console.warn(e); setTimeout(refreshWeather, 60000); }  // e.g. Open-Meteo 503: try again in a minute, not in 15
}
refreshWeather();
setInterval(refreshWeather, 15 * 60 * 1000);

// --- the room: room.js places and animates it -------------------------------------------

// --- watchlist (signal_copier/market_feed.py -> /v1/watchlist) ---------------------------
let watch = null;
const pctTxt = (v) => (v === null || v === undefined ? '–' : `${v > 0 ? '+' : ''}${fmt(v)} %`);
const pctCls = (v) => (v > 0 ? 'up' : v < 0 ? 'down' : '');
const priceTxt = (v) => (v === null || v === undefined ? '–' : fmt(v, v >= 1000 ? 0 : v >= 10 ? 2 : 4));
function spark(values, w = 58, h = 20) {
  if (!values || values.length < 2) return `<svg viewBox="0 0 ${w} ${h}"></svg>`;
  const lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1;
  const pts = values.map((v, i) => `${(i / (values.length - 1) * w).toFixed(1)},${(h - 2 - (v - lo) / span * (h - 4)).toFixed(1)}`).join(' ');
  const c = values[values.length - 1] >= values[0] ? '#3ddc97' : '#f2647c';
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${c}" stroke-width="1.6"/></svg>`;
}
function renderWatch(w) {
  const top = w.items.filter((i) => i.top).sort((a, b) => a.top - b.top);
  $('#wTop').innerHTML = top.map((i) => `<div class="row"><span class="wname">${esc(i.name)}</span>${spark(i.spark)}`
    + `<span class="wpx">${priceTxt(i.price)}</span><span class="wch ${pctCls(i.change_pct)}">${pctTxt(i.change_pct)}</span></div>`).join('');
  $('#wBadge').textContent = w.stale ? 'keine Daten' : `+${w.items.length - top.length} weitere`;
  $('#wBadge').classList.toggle('live', !w.stale);
  if (openView === 'watchlist') renderWatchView(w);
}
const openRows = new Set();
function renderWatchView(w) {
  // Not while Brano is typing in one of the fields: a refresh would wipe what he wrote.
  if ($('#watchGroups').contains(document.activeElement) && document.activeElement.matches('input, textarea')) return;
  const groups = {};
  w.items.forEach((i) => (groups[i.category] = groups[i.category] || []).push(i));
  const order = ['Krypto', 'Rohstoffe', 'Indizes', 'Devisen', 'Aktien'];
  const name = (i) => `<b>${esc(i.name)}</b>${i.reason ? `<small class="why">${esc(i.reason)}</small>` : ''}`;
  const detail = (i) => `<tr class="wdetail" data-for="${esc(i.name)}" ${openRows.has(i.name) ? '' : 'hidden'}><td colspan="8">
      <div class="wform">
        <label>Warum empfohlen<textarea rows="2" data-f="reason" placeholder="z. B. starkes Wachstum im Rechenzentrum, Dividende …">${esc(i.reason)}</textarea></label>
        <label>Von wem<input data-f="by" value="${esc(i.recommended_by)}" placeholder="Name" /></label>
        <div class="wbtns"><button class="wbtn" data-act="save">Speichern</button><button class="wbtn primary" data-act="analyse">AURON-Analyse</button><span class="wmsg"></span></div>
      </div>
      ${i.analysis ? `<div class="wanalysis">${esc(i.analysis)}<small>AURON · ${new Date(i.analysis_at).toLocaleString('de-DE')} · Beobachtung, keine Empfehlung</small></div>` : ''}
    </td></tr>`;
  const row = (i) => (i.price === null || i.price === undefined
    ? `<tr class="wrow" data-name="${esc(i.name)}"><td>${name(i)}</td><td></td><td class="nodata" colspan="6">keine Daten – bei PU Prime nicht handelbar</td></tr>`
    : `<tr class="wrow" data-name="${esc(i.name)}"><td>${name(i)}</td><td>${spark(i.spark, 80, 22)}</td><td class="num">${priceTxt(i.price)}</td>`
      + `<td class="num ${pctCls(i.change_pct)}">${pctTxt(i.change_pct)}</td><td class="num ${pctCls(i.from_high_pct)}">${pctTxt(i.from_high_pct)}</td>`
      + `<td class="num ${pctCls(i.vs_sma200_pct)}">${pctTxt(i.vs_sma200_pct)}</td><td class="num">${i.rsi14 ?? '–'}</td>`
      + `<td class="notes">${(i.notes || []).map((n) => `<span class="note">${esc(n)}</span>`).join('')}${i.analysis ? '<span class="note ai">AURON-Analyse</span>' : ''}</td></tr>`) + detail(i);
  $('#watchGroups').innerHTML = Object.keys(groups).sort((a, b) => order.indexOf(a) - order.indexOf(b)).map((g) =>
    `<section class="card"><div class="label">${esc(g)} <span class="count">${groups[g].length}</span></div><div class="table-wrap"><table class="watch-table">`
    + '<tr><th>NAME</th><th></th><th>KURS</th><th>HEUTE</th><th>VOM 52W-HOCH</th><th>VS 200 TAGE</th><th>RSI</th><th>HINWEISE</th></tr>'
    + groups[g].slice().sort((a, b) => (b.notes?.length || 0) - (a.notes?.length || 0)).map(row).join('')
    + '</table></div></section>').join('');
}

// one listener for the whole view: open a row, save its reason, ask AURON
$('#watchGroups').addEventListener('click', async (e) => {
  const rowEl = e.target.closest('.wrow');
  if (rowEl) {
    const n = rowEl.dataset.name, d = rowEl.nextElementSibling;
    d.hidden = !d.hidden;
    d.hidden ? openRows.delete(n) : openRows.add(n);
    return;
  }
  const btn = e.target.closest('.wbtn');
  if (!btn) return;
  const d = btn.closest('.wdetail'), name = d.dataset.for, msg = d.querySelector('.wmsg');
  const body = { reason: d.querySelector('[data-f=reason]').value, recommended_by: d.querySelector('[data-f=by]').value };
  btn.disabled = true;
  try {
    msg.textContent = btn.dataset.act === 'save' ? 'speichere …' : 'AURON denkt nach …';
    await send('PUT', `/v1/watchlist/reasons/${encodeURIComponent(name)}`, body);
    if (btn.dataset.act === 'analyse') await send('POST', `/v1/watchlist/analyse/${encodeURIComponent(name)}`);
    document.activeElement?.blur();
    watch = await get('/v1/watchlist');
    renderWatch(watch);
  } catch (err) { msg.textContent = `Fehler: ${err.message}`; btn.disabled = false; }
});

async function refreshWatch() {
  try { watch = await get('/v1/watchlist'); renderWatch(watch); } catch (e) { console.warn(e); }
}
refreshWatch();
setInterval(refreshWatch, 60000);
