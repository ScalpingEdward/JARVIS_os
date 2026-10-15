// AURON live dashboard. Plain JS, no build step: nginx serves this file and
// proxies /api/ to the api container (same origin, no CORS).
const API = localStorage.getItem('auron_api') || (location.protocol === 'file:' ? 'http://localhost:8000' : '/api');
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (v, d = 2) => Number(v || 0).toLocaleString('de-DE', { minimumFractionDigits: d, maximumFractionDigits: d });
const signed = (v, cur = '') => `<span class="${v > 0 ? 'up' : v < 0 ? 'down' : ''}">${v > 0 ? '+' : ''}${fmt(v)}${cur ? ' ' + esc(cur) : ''}</span>`;
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const nameOf = (a) => a.label || a.profile;  // what people call the account: its group's name

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

// --- the trading tile: the short list -------------------------------------------
function renderTradingTile(o) {
  const t = (o.totals || [])[0];
  if (!t) return;
  tween($('#tTotal'), t.equity);
  $('#tCurrency').textContent = t.currency + (o.totals.length > 1 ? ` + ${o.totals.length - 1} more` : '');
  $('#tToday').innerHTML = `today ${signed(t.pnl_today, t.currency)}`;
  const live = o.accounts.filter((a) => a.state === 'live').length;
  $('#tLive').textContent = live === o.accounts.length ? 'live' : `${live}/${o.accounts.length} live`;
  $('#tLive').classList.toggle('live', live === o.accounts.length);
  $('#tAccounts').innerHTML = '<div class="cap">Accounts</div>' + o.accounts.map((a) => {
    const st = a.state === 'live' ? 'ok' : a.state === 'stale' ? 'warn' : 'bad';
    return `<div class="row"><span class="dot ${st}"></span><span>${esc(nameOf(a))}</span><span>${fmt(a.equity)} ${esc(a.currency)}</span></div>`;
  }).join('');
  const groups = (o.groups || []).filter((g) => g.name !== '(not from a signal)');
  $('#tGroups').innerHTML = groups.length ? groups.map((g) =>
    `<div class="row"><span></span><span>${esc(g.name)}</span><span>${signed(g.pnl_total)}</span></div>`).join('')
    : '<div class="row"><span></span><span class="muted">No group has traded yet</span><span></span></div>';
  $('#kToday').innerHTML = signed(t.pnl_today, t.currency);
  $('#kWeek').innerHTML = signed(t.pnl_week, t.currency);
  $('#kOpen').innerHTML = `${t.open_positions} <small class="muted">${signed(t.open_pnl)}</small>`;
  $('#kTotal').innerHTML = signed(t.pnl_total, t.currency);
  renderTileSpark(o, t.currency);
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
    if (openView === 'trading') { renderTotals(overview); renderAccounts(overview); renderGroups(overview); renderPositions(overview); renderTotalChart(); }
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
    lastInsta = { dash, sched };
    const left = dash.media_pool_available, used = dash.media_pool_used, all = left + used || 1;
    const n = parseNext(sched.next);
    nextAt = n ? n.at : null;
    const label = n ? `next: ${n.kind || 'post'} at ${sched.next.split(' ')[0]}${sched.already_posted_today ? ' · posted today' : ''}` : (sched.next || 'nothing scheduled');
    $('#iNext').textContent = label;
    $('#iBadge').textContent = dash.needs_your_review ? `${dash.needs_your_review} to review` : sched.running ? 'scheduled' : 'paused';
    $('#iBadge').classList.toggle('live', !!sched.running);
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
  } catch (e) { console.warn(e); }
}

// --- health: top bar, system tile, AURON's own line ------------------------------
async function refreshHealth() {
  const svcs = [];
  try { const h = await get('/health'); svcs.push(['API', h.status === 'healthy' ? 'ok' : 'warn']); } catch { svcs.push(['API', 'bad']); }
  try { const t = await get('/v1/telegram-instagram/status'); svcs.push(['Telegram bot', t.bot_reachable ? 'ok' : 'bad']); } catch { svcs.push(['Telegram bot', 'bad']); }
  (overview?.accounts || []).forEach((a) => svcs.push([`Copier ${nameOf(a)}`, a.state === 'live' ? 'ok' : a.state === 'stale' ? 'warn' : 'bad']));
  $('#health').innerHTML = svcs.map(([n, c]) => `<span class="svc" title="${esc(n)}"><span class="dot ${c}"></span><span>${esc(n)}</span></span>`).join('');
  $('#sList').innerHTML = svcs.map(([n, c]) => `<div class="row"><span class="dot ${c}"></span><span>${esc(n)}</span><span>${c === 'ok' ? 'online' : c === 'warn' ? 'late' : 'offline'}</span></div>`).join('');
  const bad = svcs.filter(([, c]) => c !== 'ok').length;
  $('#core').classList.toggle('degraded', bad > 0);
  window.auronHead?.setDegraded(bad > 0);
  lastHealth = { bad, total: svcs.length, down: svcs.filter(([, c]) => c !== 'ok').map(([n]) => n) };
  $('#sBadge').textContent = bad ? `${bad} down` : 'all online';
  $('#sBadge').classList.toggle('live', !bad);
  const copiers = (overview?.accounts || []).filter((a) => a.state === 'live').length;
  $('#coreLine').textContent = bad ? `${bad} of ${svcs.length} systems need attention` : `online · ${copiers} copier${copiers === 1 ? '' : 's'} live`;
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
const TITLES = { trading: 'Trading', instagram: 'Instagram' };

function morph(panel, rect, reverse) {
  const end = panel.getBoundingClientRect();
  const from = `translate(${rect.left - end.left}px, ${rect.top - end.top}px) scale(${rect.width / end.width}, ${rect.height / end.height})`;
  const frames = [{ transform: from, opacity: .3, borderRadius: '22px' }, { transform: 'none', opacity: 1 }];
  return panel.animate(reverse ? frames.reverse() : frames, { duration: reduced ? 0 : 520, easing: 'cubic-bezier(.2,.8,.2,1)' }).finished;
}

function open(view, fromTile, push = true) {
  openView = view; openedFrom = fromTile;
  document.querySelectorAll('.side a').forEach((n) => n.classList.toggle('active', n.dataset.nav === view));
  $('#detailTitle').textContent = TITLES[view];
  document.querySelectorAll('.view').forEach((v) => v.classList.toggle('active', v.dataset.view === view));
  $('#detail').hidden = false;
  document.body.classList.add('locked');
  $('#detailPanel').scrollTop = 0;
  if (push) history_.pushState({ view }, '', `#${view}`);
  if (view === 'trading' && overview) { renderTotals(overview); renderAccounts(overview); renderGroups(overview); renderPositions(overview); renderTotalChart(); }
  if (fromTile) morph($('#detailPanel'), fromTile.getBoundingClientRect(), false);
  $('#close').focus();
}

async function close(push = true) {
  if (!openView) return;
  const tile = openedFrom;
  openView = null;
  document.querySelectorAll('.side a').forEach((n) => n.classList.toggle('active', n.dataset.nav === 'hub'));
  if (tile && !reduced) await morph($('#detailPanel'), tile.getBoundingClientRect(), true).catch(() => {});
  $('#detail').hidden = true;
  document.body.classList.remove('locked');
  if (push && location.hash) history_.back();
  tile?.focus();
}

const history_ = window.history;
// A click: AURON turns to the card and says what is on it, then the full view opens.
let lastInsta = null, lastHealth = null;
const euro = (v) => `${v < 0 ? 'minus ' : v > 0 ? 'plus ' : ''}${Math.abs(v).toLocaleString('de-DE', { maximumFractionDigits: 2 })} Euro`;
function summary(view) {
  if (view === 'trading' && overview?.totals?.length) {
    const t = overview.totals[0], live = overview.accounts.filter((a) => a.state === 'live').length;
    return `Trading. ${live} von ${overview.accounts.length} Konten live. Heute ${euro(t.pnl_today)}, diese Woche ${euro(t.pnl_week)}.`
      + (t.open_positions ? ` ${t.open_positions} Positionen offen.` : ' Keine Position offen.');
  }
  if (view === 'instagram' && lastInsta) {
    const n = parseNext(lastInsta.sched.next);
    return `Instagram. ${n ? `Nächster Post: ${n.kind === 'reel' ? 'ein Reel' : 'ein Beitrag'} um ${lastInsta.sched.next.split(' ')[0]} Uhr.` : 'Nichts geplant.'}`
      + ` ${lastInsta.dash.curated_drafts_pending} Entwürfe bereit, ${lastInsta.dash.media_pool_available} Medien im Pool.`;
  }
  if (view === 'system' && lastHealth) {
    return lastHealth.bad ? `Achtung. ${lastHealth.down.join(', ')} ${lastHealth.bad === 1 ? 'ist' : 'sind'} nicht erreichbar.`
      : `Alle ${lastHealth.total} Systeme online.`;
  }
  return '';
}
function present(view, tile, opensView) {
  const head = window.auronHead;
  head?.lookAt(tile);
  const text = summary(view);
  if (text) head?.speak(text);
  if (opensView) setTimeout(() => open(view, tile), head ? 700 : 0);
}
document.querySelectorAll('.tile[data-view]').forEach((tile) => tile.addEventListener('click', () => present(tile.dataset.view, tile, true)));
$('#tileSystem').addEventListener('click', () => present('system', $('#tileSystem'), false));
const voiceBtn = $('#voice');
const showVoice = () => { const off = localStorage.getItem('auron_voice') === 'off'; voiceBtn.textContent = off ? '🔇' : '🔊'; voiceBtn.classList.toggle('off', off); };
voiceBtn.addEventListener('click', () => {
  localStorage.setItem('auron_voice', localStorage.getItem('auron_voice') === 'off' ? 'on' : 'off');
  if (localStorage.getItem('auron_voice') === 'off') speechSynthesis?.cancel();
  showVoice();
});
showVoice();
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
  $('#date').textContent = now.toLocaleDateString('de-DE');
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

// --- side navigation: the same views the cards open -------------------------------------
document.querySelectorAll('.side a').forEach((a) => a.addEventListener('click', (e) => {
  e.preventDefault();
  const v = a.dataset.nav;
  if (v === 'hub') close(); else open(v, $(`.tile[data-view="${v}"]`));
}));
refreshHealth();  // at once: the bot check takes seconds and must not wait for the rest
refreshHistory().then(refreshTrading).then(refreshHealth).then(() => {
  const v = location.hash.slice(1);
  if (TITLES[v]) open(v, null, false);
});
refreshInstagram();
setInterval(refreshTrading, 5000);
setInterval(refreshHistory, 60000);
setInterval(refreshInstagram, 30000);
setInterval(refreshHealth, 15000);

// --- weather next to the clock (Open-Meteo: free, no key) ------------------------------
// Where: the browser's location if allowed, otherwise Prague. Refreshed every 15 min.
const WEATHER_FALLBACK = { lat: 50.08, lon: 14.43, place: 'Prag' };
const WMO = [
  [[0], '☀', 'klar'], [[1, 2], '⛅', 'leicht bewölkt'], [[3], '☁', 'bewölkt'], [[45, 48], '〰', 'Nebel'],
  [[51, 53, 55, 56, 57], '☂', 'Niesel'], [[61, 63, 65, 66, 67, 80, 81, 82], '☔', 'Regen'],
  [[71, 73, 75, 77, 85, 86], '❄', 'Schnee'], [[95, 96, 99], '⚡', 'Gewitter'],
];
let weatherAt = null;

function locate() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(WEATHER_FALLBACK);
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lon: p.coords.longitude, place: '' }),
      () => resolve(WEATHER_FALLBACK), { timeout: 8000, maximumAge: 3600000 });
  });
}

async function refreshWeather() {
  try {
    weatherAt = weatherAt || await locate();
    const u = `https://api.open-meteo.com/v1/forecast?latitude=${weatherAt.lat}&longitude=${weatherAt.lon}&current=temperature_2m,weather_code&timezone=auto`;
    const r = await fetch(u);
    if (!r.ok) throw new Error(`weather ${r.status}`);
    const c = (await r.json()).current;
    const [, icon, text] = WMO.find(([codes]) => codes.includes(c.weather_code)) || [[], '·', ''];
    $('#weather').innerHTML = `<span class="wi">${icon}</span><b>${Math.round(c.temperature_2m)}°C</b><small>${esc(text)}${weatherAt.place ? ' · ' + esc(weatherAt.place) : ''}</small>`;
  } catch (e) { console.warn(e); }
}
refreshWeather();
setInterval(refreshWeather, 15 * 60 * 1000);
