// AURON live dashboard. Plain JS, no build step: nginx serves this file and
// proxies /api/ to the api container (same origin, no CORS).
const API = localStorage.getItem('auron_api') || (location.protocol === 'file:' ? 'http://localhost:8000' : '/api');
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (v, d = 2) => Number(v || 0).toLocaleString('de-DE', { minimumFractionDigits: d, maximumFractionDigits: d });
const signed = (v, cur = '') => `<span class="${v > 0 ? 'up' : v < 0 ? 'down' : ''}">${v > 0 ? '+' : ''}${fmt(v)}${cur ? ' ' + esc(cur) : ''}</span>`;
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

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
    ${h > 100 ? `<text x="4" y="14">${fmt(hi)}</text><text x="4" y="${h - 4}">${fmt(lo)}</text>` : ''}`;
  const line = svg.querySelector('.line');
  line.style.setProperty('--len', Math.ceil(line.getTotalLength()));
}

// --- trading -----------------------------------------------------------------
let overview = null, history = {};

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
  drawChart($('#totalChart'), series, '#7c9cff', 180);
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
        <div><div class="name">${esc(a.profile)}</div><div class="meta">${esc(a.account_login)} · ${esc(a.server)}</div></div>
        <span class="state"><span class="dot ${st}"></span>${esc(a.state).toUpperCase()}</span>
      </div>
      <div class="eq"><span data-k="eq-${esc(a.profile)}" id="eq-${esc(a.profile)}"></span> <small class="muted">${esc(a.currency)}</small></div>
      <div class="chips"><span class="chip">today<b>${signed(today)}</b></span><span class="chip">total<b>${signed(total)}</b></span><span class="chip">open<b>${open}</b></span></div>
      <svg class="spark" id="sp-${esc(a.profile)}" viewBox="0 0 800 54" preserveAspectRatio="none"></svg>
      <div class="mini">${a.groups.map((g) => `<div><span>${esc(g.name)}</span><span>${signed(g.pnl_total)}</span></div>`).join('')}</div>
    </article>`;
  }).join('');
  o.accounts.forEach((a) => {
    tween($(`#eq-${CSS.escape(a.profile)}`), a.equity);
    const pts = (history[a.profile] || []).map((p) => ({ x: Date.parse(p.at), y: p.equity }));
    pts.push({ x: Date.now(), y: a.equity });
    const rising = pts.length < 2 || pts[pts.length - 1].y >= pts[0].y;
    drawChart($(`#sp-${CSS.escape(a.profile)}`), pts, rising ? '#2ee59d' : '#ff5d7a', 54);
  });
}

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
  const rows = o.accounts.flatMap((a) => a.open_positions.map((p) => ({ ...p, profile: a.profile, currency: a.currency })));
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

async function refreshTrading() {
  try {
    overview = await get('/v1/copier/overview');
    renderTotals(overview); renderAccounts(overview); renderGroups(overview); renderPositions(overview); renderTotalChart();
  } catch (e) { console.warn(e); }
}

async function refreshHistory() {
  try { history = await get('/v1/copier/history?hours=24'); renderTotalChart(); if (overview) renderAccounts(overview); } catch (e) { console.warn(e); }
}

// --- instagram ---------------------------------------------------------------
let nextAt = null, nextLabel = '–';

function parseNext(s) {
  // "19:00 reel" -> today (or tomorrow) at 19:00
  const m = /^(\d{1,2}):(\d{2})\s*(.*)$/.exec(s || '');
  if (!m) return null;
  const d = new Date(); d.setHours(+m[1], +m[2], 0, 0);
  if (d < new Date()) d.setDate(d.getDate() + 1);
  return { at: d, kind: m[3] };
}

function tickCountdown() {
  if (!nextAt) { $('#countdown').textContent = '–'; return; }
  let s = Math.max(0, Math.round((nextAt - new Date()) / 1000));
  const h = Math.floor(s / 3600); s %= 3600;
  const m = Math.floor(s / 60); s %= 60;
  $('#countdown').textContent = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

async function refreshInstagram() {
  try {
    const [dash, sched] = await Promise.all([get('/v1/instagram/dashboard'), get('/v1/telegram-instagram/schedule')]);
    const left = dash.media_pool_available, used = dash.media_pool_used, all = left + used || 1;
    tween($('#poolLeft'), left, 0);
    $('#poolArc').style.strokeDashoffset = 327 * (1 - left / all);
    const n = parseNext(sched.next);
    nextAt = n ? n.at : null;
    nextLabel = n ? `${n.kind || 'post'} at ${sched.next.split(' ')[0]}${sched.already_posted_today ? ' · posted today' : ''}` : (sched.next || 'nothing scheduled');
    $('#nextKind').textContent = nextLabel;
    $('#instaStats').innerHTML = [
      ['drafts', dash.curated_drafts_pending], ['to review', dash.needs_your_review], ['ready', dash.approved_ready_to_publish],
      ['posted', dash.posted_total], ['failed', dash.post_failed], ['used', used],
    ].map(([k, v]) => `<div><b>${esc(v)}</b><small>${k}</small></div>`).join('');
    $('#recent').innerHTML = (dash.recent_candidates || []).slice(0, 4).map((c) =>
      `<li><span>${esc(c.post_format.replace('_', ' '))} · ${esc(c.status)}</span><span>${new Date(c.created_at).toLocaleDateString('de-DE')}</span></li>`).join('');
    tickCountdown();
  } catch (e) { console.warn(e); }
}

// --- health ------------------------------------------------------------------
async function refreshHealth() {
  const pills = [];
  const pill = (name, cls) => pills.push(`<span class="pill"><span class="dot ${cls}"></span>${esc(name)}</span>`);
  try { const h = await get('/health'); pill('API', h.status === 'healthy' ? 'ok' : 'warn'); } catch { pill('API', 'bad'); }
  try { const t = await get('/v1/telegram-instagram/status'); pill('Telegram bot', t.bot_reachable ? 'ok' : 'bad'); } catch { pill('Telegram bot', 'bad'); }
  (overview?.accounts || []).forEach((a) => pill(`copier ${a.profile}`, a.state === 'live' ? 'ok' : a.state === 'stale' ? 'warn' : 'bad'));
  $('#health').innerHTML = pills.join('');
}

// --- loops ---------------------------------------------------------------------
setInterval(() => { $('#clock').textContent = new Date().toLocaleTimeString('de-DE'); tickCountdown(); }, 1000);
refreshHistory().then(refreshTrading).then(refreshHealth);
refreshInstagram();
setInterval(refreshTrading, 5000);
setInterval(refreshHistory, 60000);
setInterval(refreshInstagram, 30000);
setInterval(refreshHealth, 15000);
