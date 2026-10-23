// Which cards stand where: the layout lives in AURON's database (/v1/dashboard/layout), so it is the
// same on every screen and AURON can change it on Brano's word -- this page picks that up within
// seconds. Built-in cards are in index.html; added cards (price, copier, notes) are drawn here.
(() => {
  const API_BASE = typeof API !== 'undefined' ? API : '/api';   // app.js's, through the frontend proxy
  const BUILTIN = { trading: 'tileTrading', watch: 'tileWatch', insta: 'tileInstagram', mail: 'tileMail', smart: 'tileSmart' };
  const left = document.getElementById('colLeft'), right = document.getElementById('colRight'), store = document.getElementById('cardStore');
  const escH = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmtN = (v, d = 2) => (v == null ? '–' : Number(v).toLocaleString('de-DE', { minimumFractionDigits: d, maximumFractionDigits: d }));
  let layout = null, watch = null, copier = null, notes = [];

  async function call(method, path, body) {
    const r = await fetch(`${API_BASE}${path}`, { method, headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || `${path}: ${r.status}`);
    return d;
  }

  // ---- added cards ------------------------------------------------------------------------
  function cardEl(id) {
    if (BUILTIN[id]) return document.getElementById(BUILTIN[id]);
    let el = document.getElementById(`card-${id}`);
    const c = layout.custom[id];
    if (!el && c) {
      el = document.createElement('div');
      el.id = `card-${id}`; el.className = `tile a-${c.type} added`; el.dataset.card = id;
      el.style.setProperty('--d', `${-(id.charCodeAt(id.length - 1) % 5)}s`);
      el.innerHTML = '<span class="corner"></span><span class="card-gear" role="button" title="Karte">⚙</span><div class="tile-head"><span class="ac-title"></span><span class="badge ac-badge">–</span></div><div class="ac-body"></div>';
    }
    if (el && c) paintCard(el, c);
    return el;
  }

  function spark(values, up) {
    if (!values?.length) return '';
    const min = Math.min(...values), max = Math.max(...values), w = 200, h = 40;
    const pts = values.map((v, i) => `${(i / Math.max(values.length - 1, 1)) * w},${h - ((v - min) / (max - min || 1)) * h}`).join(' ');
    return `<svg class="ac-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${up ? '#3ddc97' : '#f2647c'}" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>`;
  }

  function paintCard(el, c) {
    const title = el.querySelector('.ac-title'), badge = el.querySelector('.ac-badge'), body = el.querySelector('.ac-body');
    if (c.type === 'price') {
      const name = c.config.name, it = (watch?.items || []).find((x) => x.name.toLowerCase() === name.toLowerCase());
      title.textContent = name;
      if (!it) { badge.textContent = '–'; body.innerHTML = `<p class="muted ac-note">„${escH(name)}“ steht nicht in der Watchlist.</p>`; return; }
      if (it.price == null) { badge.textContent = '–'; body.innerHTML = '<p class="muted ac-note">Keine Kursdaten (bei PU Prime nicht handelbar).</p>'; return; }
      const up = (it.change_pct || 0) >= 0;
      badge.textContent = `${up ? '+' : ''}${fmtN(it.change_pct)} %`; badge.className = `badge ac-badge ${up ? 'up' : 'down'}`;
      body.innerHTML = `<div class="tile-figure"><b>${fmtN(it.price, it.price > 1000 ? 1 : 2)}</b></div>${spark(it.spark, up)}
        <div class="tile-sub">${it.from_high_pct != null ? `${fmtN(it.from_high_pct, 1)} % vom 52W-Hoch` : ''}${it.rsi14 != null ? ` · RSI ${fmtN(it.rsi14, 0)}` : ''}</div>`;
    } else if (c.type === 'copier') {
      title.textContent = 'Kopierer & Bots';
      const accs = copier?.accounts || [];
      badge.textContent = `${accs.filter((a) => a.state === 'live').length}/${accs.length} live`;
      body.innerHTML = accs.length ? accs.map((a) => {
        const st = a.state === 'live' ? (a.halt_reason ? 'warn' : 'ok') : a.state === 'stale' ? 'warn' : 'bad';
        return `<div class="ac-row"><span class="dot ${st}"></span><span class="ac-name">${escH(a.label || a.profile)}</span>
          <span class="ac-eq">${fmtN(a.equity)} ${escH(a.currency)}</span>
          <button type="button" class="ac-btn" data-cp="${escH(a.profile)}" data-act="${a.halt_reason ? 'resume' : 'pause'}"
            title="${a.halt_reason ? 'Fortsetzen' : 'Pausieren – keine neuen Trades'}">${a.halt_reason ? '▶' : '⏸'}</button></div>`;
      }).join('') : '<p class="muted ac-note">Kein Kopierer meldet sich.</p>';
    } else if (c.type === 'notes') {
      title.textContent = 'Notizen';
      badge.textContent = notes.filter((n) => !n.done).length;
      const keep = body.querySelector('.ac-in')?.value || '';
      body.innerHTML = `<form class="ac-add"><input class="ac-in" maxlength="300" placeholder="Neue Notiz …" value="${escH(keep)}" /><button type="submit">＋</button></form>
        <div class="ac-notes">${notes.slice(0, 8).map((n) => `<label class="ac-note-row${n.done ? ' done' : ''}">
          <input type="checkbox" data-note="${n.id}" ${n.done ? 'checked' : ''} /><span>${escH(n.text)}</span>
          ${n.by === 'auron' ? '<small>AURON</small>' : ''}<button type="button" data-del="${n.id}" title="Löschen">✕</button></label>`).join('')
          || '<p class="muted ac-note">Noch nichts notiert. Auch per Chat: „Notier mir …“</p>'}</div>`;
    } else if (c.type === 'clock') {
      paintClock(title, badge, body);
    } else if (c.type === 'positions') {
      paintPositions(title, badge, body);
    } else if (c.type === 'performance') {
      paintPerformance(title, badge, body);
    }
  }

  // ---- Marktuhr: the sessions in their own time zones (summer time included), ICT killzones in New York
  // time. Killzone hours are the common ICT ones -- v1, to be checked against his own trading.
  const SESSIONS = [['Asien', 'Asia/Tokyo', 9 * 60, 18 * 60], ['London', 'Europe/London', 8 * 60, 17 * 60],
    ['New York', 'America/New_York', 8 * 60, 17 * 60]];   // forex sessions, local hours
  const KILLZONES = [['Asien', 20 * 60, 24 * 60], ['London', 2 * 60, 5 * 60], ['NY AM', 7 * 60, 10 * 60],
    ['London Close', 10 * 60, 12 * 60], ['NY PM', 13 * 60 + 30, 16 * 60]];
  function zoneNow(tz) {
    const p = Object.fromEntries(new Intl.DateTimeFormat('en-GB', { timeZone: tz, hourCycle: 'h23', weekday: 'short', hour: '2-digit', minute: '2-digit' })
      .formatToParts(new Date()).map((x) => [x.type, x.value]));
    return { min: Number(p.hour) * 60 + Number(p.minute), weekend: p.weekday === 'Sat' || p.weekday === 'Sun' };
  }
  const dur = (m) => (m >= 60 ? `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')} h` : `${m} min`);
  function paintClock(title, badge, body) {
    title.textContent = 'Marktuhr';
    const rows = SESSIONS.map(([name, tz, a, b]) => {
      const { min, weekend } = zoneNow(tz), open = !weekend && min >= a && min < b;
      const txt = weekend ? 'Wochenende' : open ? `offen · noch ${dur(b - min)}` : `öffnet in ${dur((a - min + 1440) % 1440)}`;
      return `<div class="ac-row mc-row"><span class="dot ${open ? 'ok' : ''}"></span><span class="ac-name">${name}</span><span class="ac-eq">${txt}</span></div>`;
    }).join('');
    const ny = zoneNow('America/New_York');
    const kz = ny.weekend ? null : KILLZONES.find(([, a, b]) => ny.min >= a && ny.min < b);
    const next = KILLZONES.map(([n, a]) => [n, (a - ny.min + 1440) % 1440]).filter(([, m]) => m > 0).sort((x, y) => x[1] - y[1])[0];
    badge.textContent = kz ? kz[0] : '–'; badge.className = `badge ac-badge ${kz ? 'live' : ''}`;
    body.innerHTML = rows + `<p class="ac-note mc-kz">${kz ? `Killzone <b>${kz[0]}</b> · noch ${dur(kz[2] - ny.min)}`
      : ny.weekend ? 'Keine Killzone am Wochenende' : `Nächste Killzone: <b>${next[0]}</b> in ${dur(next[1])}`}</p>`;
  }

  // ---- Offene Trades: every position live (app.js keeps overview fresh every second) ----
  const liveOverview = () => (typeof overview !== 'undefined' && overview) || copier;
  function paintPositions(title, badge, body) {
    title.textContent = 'Offene Trades';
    const accs = liveOverview()?.accounts || [];
    const all = accs.flatMap((a) => (a.open_positions || []).map((p) => ({ ...p, copier: a.profile, cur: a.currency })));
    badge.textContent = all.length;
    if (!all.length) { body.innerHTML = '<p class="muted ac-note">Keine offenen Trades.</p>'; return; }
    const sum = all.reduce((t, p) => t + (p.profit || 0), 0);
    body.innerHTML = all.map((p) => `<div class="ac-row op-row" data-tk="${p.ticket}" data-cp="${escH(p.copier)}" title="Chart öffnen">
        <span class="dot ${p.side === 'buy' ? 'ok' : 'bad'}"></span>
        <span class="ac-name">${escH(p.symbol)} <small>${p.side.toUpperCase()} ${fmtN(p.volume)} · ${escH(p.group || '')}</small></span>
        <span class="ac-eq ${p.profit > 0 ? 'up' : p.profit < 0 ? 'down' : ''}">${p.profit > 0 ? '+' : ''}${fmtN(p.profit)}</span></div>`).join('')
      + `<div class="ac-row op-sum"><span></span><span class="ac-name">Summe</span><span class="ac-eq ${sum > 0 ? 'up' : sum < 0 ? 'down' : ''}">${sum > 0 ? '+' : ''}${fmtN(sum)} ${escH(all[0].cur || '')}</span></div>`;
  }

  // ---- Performance: equity of all accounts over 7 days, and per group today / week / month ----
  let equity = null, equityAt = 0;
  function paintPerformance(title, badge, body) {
    title.textContent = 'Performance';
    const accs = liveOverview()?.accounts || [];
    const monthStart = new Date(new Date().getFullYear(), new Date().getMonth(), 1).getTime() / 1000;
    const g = {};
    for (const a of accs) {
      for (const x of a.groups || []) { const r = g[x.name] ||= { today: 0, week: 0, month: 0 }; r.today += x.pnl_today; r.week += x.pnl_week; }
      for (const t of a.closed || []) if (t.closed >= monthStart) (g[t.group] ||= { today: 0, week: 0, month: 0 }).month += t.profit;
    }
    const month = Object.values(g).reduce((s, r) => s + r.month, 0), cur = accs[0]?.currency || '';
    badge.textContent = 'Monat'; badge.className = 'badge ac-badge';
    const sign = (v) => `<span class="${v > 0 ? 'up' : v < 0 ? 'down' : ''}">${v > 0 ? '+' : ''}${fmtN(v)}</span>`;
    const pts = equity || [];
    body.innerHTML = `<div class="tile-figure"><b class="${month > 0 ? 'up' : month < 0 ? 'down' : ''}">${month > 0 ? '+' : ''}${fmtN(month)}</b> <small class="muted">${escH(cur)} diesen Monat</small></div>
      ${pts.length > 2 ? spark(pts, pts[pts.length - 1] >= pts[0]) + '<small class="muted pf-note">Equity aller Konten · 7 Tage</small>' : ''}
      <div class="pf-grid"><span></span><small>Heute</small><small>Woche</small><small>Monat</small>
      ${Object.entries(g).filter(([, r]) => r.today || r.week || r.month).map(([n, r]) => `<span class="ac-name">${escH(n)}</span><b>${sign(r.today)}</b><b>${sign(r.week)}</b><b>${sign(r.month)}</b>`).join('')}</div>`;
  }
  async function refreshEquity() {
    if (Date.now() - equityAt < 5 * 60000 && equity) return;
    try {
      const h = await call('GET', '/v1/copier/history?hours=168');
      // summed across accounts per five minutes -- only where every account reported, else the sum jumps
      const sums = {}, counts = {}, n = Object.keys(h).length;
      for (const pts of Object.values(h)) for (const p of pts) {
        const k = Math.round(new Date(p.at).getTime() / 300000); sums[k] = (sums[k] || 0) + p.equity; counts[k] = (counts[k] || 0) + 1;
      }
      const full = Object.keys(sums).map(Number).sort((a, b) => a - b).filter((k) => counts[k] === n).map((k) => sums[k]);
      const step = Math.max(1, Math.floor(full.length / 160));
      equity = full.filter((_, i) => i % step === 0); equityAt = Date.now();
    } catch (e) { console.warn('equity', e); }
  }

  // the live cards repaint every second (clock, trades), performance with the data refresh
  setInterval(() => {
    document.querySelectorAll('.tile.added.a-clock, .tile.added.a-positions').forEach((el) => {
      const c = layout?.custom[el.dataset.card]; if (c) paintCard(el, c);
    });
  }, 1000);

  // clicks inside added cards stay in the card
  document.addEventListener('click', async (e) => {
    const card = e.target.closest('.tile.added');
    if (!card) return;
    e.stopPropagation();
    const tk = e.target.closest('[data-tk]');
    if (tk) { window.AURON_chart?.open(tk.dataset.tk, tk.dataset.cp); return; }
    const cp = e.target.closest('button[data-cp]'), del = e.target.closest('[data-del]');
    if (cp) {
      cp.disabled = true;
      try { await call('POST', '/v1/copier/commands', { profile: cp.dataset.cp, action: cp.dataset.act }); cp.textContent = '…'; }
      catch (err) { alert(`Fehler: ${err.message}`); }
      setTimeout(refreshData, 4000);
    }
    if (del) { notes = await call('PATCH', `/v1/dashboard/notes/${del.dataset.del}`, { delete: true }); render(); }
  }, true);
  document.addEventListener('change', async (e) => {
    const box = e.target.closest('input[data-note]');
    if (!box) return;
    notes = await call('PATCH', `/v1/dashboard/notes/${box.dataset.note}`, { done: box.checked }); render();
  });
  document.addEventListener('submit', async (e) => {
    const f = e.target.closest('.ac-add');
    if (!f) return;
    e.preventDefault();
    const inp = f.querySelector('.ac-in'), text = inp.value.trim();
    if (!text) return;
    inp.value = '';
    try { notes = await call('POST', '/v1/dashboard/notes', { text }); } catch (err) { alert(`Fehler: ${err.message}`); }
    render();
  });

  // ---- placing ---------------------------------------------------------------------------
  function render() {
    if (!layout) return;
    const place = (col, ids) => ids.forEach((id) => { const el = cardEl(id); if (el) col.appendChild(el); });
    place(left, layout.left); place(right, layout.right); place(store, layout.hidden);
    // added cards that are gone from the layout
    document.querySelectorAll('.tile.added').forEach((el) => { if (!layout.custom[el.dataset.card]) el.remove(); });
    if (window.AURON_layoutEditor?.isOpen()) window.AURON_layoutEditor.paint();
  }

  async function refreshLayout() {
    try {
      const l = await call('GET', '/v1/dashboard/layout');
      if (!layout || l.updated_at !== layout.updated_at) { layout = l; render(); refreshData(); }
    } catch (e) { console.warn('layout', e); }
  }
  async function refreshData() {
    const types = new Set(Object.values(layout?.custom || {}).map((c) => c.type));
    try {
      if (types.has('price')) watch = await call('GET', '/v1/watchlist');
      if (types.has('copier') || types.has('positions') || types.has('performance')) copier = await call('GET', '/v1/copier/overview');
      if (types.has('performance')) await refreshEquity();
      if (types.has('notes')) notes = await call('GET', '/v1/dashboard/notes');
    } catch (e) { console.warn('cards', e); }
    render();
  }

  // ---- the editor (Settings › Karten) --------------------------------------------------------
  let box = null;
  async function save(next) {
    try { layout = await call('PUT', '/v1/dashboard/layout', next); render(); await refreshData(); }
    catch (err) { alert(`Fehler: ${err.message}`); }
  }
  const strip = () => JSON.parse(JSON.stringify({ left: layout.left, right: layout.right, hidden: layout.hidden, custom: layout.custom }));
  function paintEditor() {
    if (!box || !layout) return;
    const row = (id, side, i, n) => `<div class="le-row"><span class="le-name">${escH(layout.labels[id] || id)}</span>
      ${side !== 'hidden' ? `<button type="button" data-le="up" data-id="${id}" ${i === 0 ? 'disabled' : ''} title="Nach oben">↑</button>
      <button type="button" data-le="down" data-id="${id}" ${i === n - 1 ? 'disabled' : ''} title="Nach unten">↓</button>
      <button type="button" data-le="swap" data-id="${id}" title="Andere Seite">⇄</button>
      <button type="button" data-le="hide" data-id="${id}" title="Ausblenden">◌</button>`
      : `<button type="button" data-le="show" data-id="${id}" title="Einblenden">einblenden</button>`}
      ${layout.custom[id] ? `<button type="button" data-le="del" data-id="${id}" title="Entfernen">✕</button>` : ''}</div>`;
    const col = (title, side) => `<span class="th-label">${title}</span>${layout[side].map((id, i, a) => row(id, side, i, a.length)).join('') || '<p class="th-text">–</p>'}`;
    const names = (watch?.items || []).filter((x) => x.price != null).map((x) => x.name);
    box.innerHTML = col('Links', 'left') + col('Rechts', 'right') + (layout.hidden.length ? col('Ausgeblendet', 'hidden') : '')
      + `<span class="th-label">Karte hinzufügen</span>
      <div class="le-add"><select id="leType">${Object.entries(layout.catalog).map(([k, c]) => `<option value="${k}">${escH(c.name)}</option>`).join('')}</select>
        <select id="leName">${names.map((n) => `<option>${escH(n)}</option>`).join('')}</select>
        <select id="leSide"><option value="right">rechts</option><option value="left">links</option></select>
        <button type="button" data-le="add">＋</button></div>
      <p class="th-text">Auch per Chat: „AURON, zeig mir Gold rechts oben.“</p>
      <button type="button" class="th-reset" data-le="reset">Anordnung zurücksetzen</button>`;
    const syncName = () => { box.querySelector('#leName').style.display = box.querySelector('#leType').value === 'price' ? '' : 'none'; };
    box.querySelector('#leType').addEventListener('change', syncName); syncName();
  }
  async function onEditor(e) {
    const b = e.target.closest('button[data-le]');
    if (!b) return;
    e.stopPropagation();
    const act = b.dataset.le, id = b.dataset.id, next = strip();
    const side = ['left', 'right', 'hidden'].find((s) => next[s].includes(id));
    if (act === 'up' || act === 'down') {
      const a = next[side], i = a.indexOf(id), j = act === 'up' ? i - 1 : i + 1;
      [a[i], a[j]] = [a[j], a[i]];
    } else if (act === 'swap') {
      next[side].splice(next[side].indexOf(id), 1); next[side === 'left' ? 'right' : 'left'].push(id);
    } else if (act === 'hide') {
      next[side].splice(next[side].indexOf(id), 1); next.hidden.push(id);
    } else if (act === 'show') {
      next.hidden.splice(next.hidden.indexOf(id), 1); next.right.push(id);
    } else if (act === 'del') {
      next[side].splice(next[side].indexOf(id), 1); delete next.custom[id];
    } else if (act === 'add') {
      const type = box.querySelector('#leType').value, cid = `${type}-${Math.random().toString(16).slice(2, 8)}`;
      next.custom[cid] = { type, config: type === 'price' ? { name: box.querySelector('#leName').value } : {} };
      next[box.querySelector('#leSide').value].unshift(cid);
    } else if (act === 'reset') {
      if (!confirm('Karten-Anordnung zurücksetzen? Hinzugefügte Karten verschwinden.')) return;
      try { layout = await call('POST', '/v1/dashboard/layout/reset'); render(); } catch (err) { alert(err.message); }
      return;
    }
    await save(next);
  }
  window.AURON_layoutEditor = {
    open(container) {
      box = container; box.addEventListener('click', onEditor);
      if (!watch) call('GET', '/v1/watchlist').then((w) => { watch = w; paintEditor(); }).catch(() => {});
      paintEditor();
    },
    isOpen: () => !!(box && box.isConnected),
    paint: paintEditor,
  };

  // ---- moving a card by hand: hold and drag it, let go where it should stand (Brano, 2026-10-22) ----
  // A short click still opens the card; only a press that moves more than 8 px drags. The card follows
  // the mouse as a see-through copy, a line shows where it lands -- in either column.
  const idOf = (el) => el.dataset.card || Object.keys(BUILTIN).find((k) => BUILTIN[k] === el.id);
  function moveTo(id, side, index) {
    const next = strip();
    for (const s of ['left', 'right', 'hidden']) {
      const i = next[s].indexOf(id);
      if (i >= 0) { next[s].splice(i, 1); if (s === side && i < index) index--; }
    }
    next[side].splice(Math.max(0, Math.min(index, next[side].length)), 0, id);
    return save(next);
  }
  let drag = null, swallowClick = false;
  const mark = document.createElement('div'); mark.className = 'drop-mark'; mark.hidden = true; document.body.append(mark);
  function target(x, y) {   // which column and which place in it the pointer points at
    const side = x < innerWidth / 2 ? 'left' : 'right', col = side === 'left' ? left : right;
    const cards = [...col.children].filter((el) => el.classList.contains('tile') && el !== drag.card);
    let k = cards.length;
    for (let i = 0; i < cards.length; i++) { const r = cards[i].getBoundingClientRect(); if (y < r.top + r.height / 2) { k = i; break; } }
    const cr = col.getBoundingClientRect();
    const lineY = k < cards.length ? cards[k].getBoundingClientRect().top - 11
      : cards.length ? cards[cards.length - 1].getBoundingClientRect().bottom + 11 : cr.top + cr.height / 2;
    const ids = cards.map(idOf);
    const index = k < ids.length ? layout[side].indexOf(ids[k]) : layout[side].length;
    return { side, index, lineY, cr };
  }
  document.addEventListener('pointerdown', (e) => {
    if (e.button !== 0 || e.pointerType === 'touch' || innerWidth <= 1000 || document.documentElement.classList.contains('desk')) return;
    const card = e.target.closest('#colLeft > .tile, #colRight > .tile');
    if (!card || !layout) return;
    const ctl = e.target.closest('button, input, select, textarea, a, label, .card-gear, .pos-x, [role="button"]');
    if (ctl && ctl !== card) return;                    // the card is a button itself; its own controls are not a drag
    e.preventDefault();                                 // no text selection while dragging
    drag = { card, x0: e.clientX, y0: e.clientY, on: false };
  });
  addEventListener('pointermove', (e) => {
    if (!drag) return;
    if (!drag.on) {
      if (Math.hypot(e.clientX - drag.x0, e.clientY - drag.y0) < 8) return;
      const r = drag.card.getBoundingClientRect();
      drag.on = true; drag.dx = drag.x0 - r.left; drag.dy = drag.y0 - r.top;
      drag.ghost = drag.card.cloneNode(true); drag.ghost.removeAttribute('id'); drag.ghost.classList.add('drag-ghost');
      Object.assign(drag.ghost.style, { width: `${r.width}px`, height: `${r.height}px` });
      document.body.append(drag.ghost); drag.card.classList.add('dragging'); document.body.classList.add('card-drag');
    }
    drag.ghost.style.left = `${e.clientX - drag.dx}px`; drag.ghost.style.top = `${e.clientY - drag.dy}px`;
    const t = target(e.clientX, e.clientY);
    drag.t = t; mark.hidden = false;
    Object.assign(mark.style, { left: `${t.cr.left}px`, width: `${t.cr.width}px`, top: `${t.lineY}px` });
  });
  addEventListener('pointerup', () => {
    if (!drag) return;
    const d = drag; drag = null;
    if (!d.on) return;
    swallowClick = true; setTimeout(() => { swallowClick = false; }, 0);   // the click that ends a drag opens nothing
    d.ghost.remove(); d.card.classList.remove('dragging'); document.body.classList.remove('card-drag'); mark.hidden = true;
    if (d.t) moveTo(idOf(d.card), d.t.side, d.t.index);
  });
  document.addEventListener('click', (e) => { if (swallowClick) { e.stopPropagation(); e.preventDefault(); swallowClick = false; } }, true);

  // ---- the card's own place, for the gear on each card (cardview.js, and added cards below) -----------
  function cardActions(el) {
    const id = idOf(el);
    if (!layout || !id) return '';
    const side = ['left', 'right'].find((s) => layout[s].includes(id));
    if (!side) return '';
    const i = layout[side].indexOf(id), n = layout[side].length;
    return [['up', '↑ Nach oben', i === 0], ['down', '↓ Nach unten', i === n - 1],
      ['swap', side === 'left' ? '⇥ Nach rechts' : '⇤ Nach links', false], ['hide', '◌ Ausblenden', false],
      ...(layout.custom[id] ? [['del', '✕ Entfernen', false]] : []), ['all', '▦ Alle Karten …', false]]
      .map(([k, t, off]) => `<span role="button" data-place="${k}" class="${off ? 'off' : ''}">${t}</span>`).join('');
  }
  async function cardAct(el, act) {
    if (act === 'all') { window.AURON_settings?.open('cards'); return; }
    const id = idOf(el), next = strip(), side = ['left', 'right'].find((s) => next[s].includes(id));
    if (!side) return;
    const a = next[side], i = a.indexOf(id);
    if (act === 'up' || act === 'down') { const j = act === 'up' ? i - 1 : i + 1; if (j < 0 || j >= a.length) return; [a[i], a[j]] = [a[j], a[i]]; }
    else if (act === 'swap') { a.splice(i, 1); next[side === 'left' ? 'right' : 'left'].push(id); }
    else if (act === 'hide') { a.splice(i, 1); next.hidden.push(id); }
    else if (act === 'del') { if (!confirm('Diese Karte entfernen?')) return; a.splice(i, 1); delete next.custom[id]; }
    await save(next);
  }
  window.AURON_layout = { actions: cardActions, act: cardAct };

  // added cards (price, copier, notes) get a gear too -- only their place, they have no text settings
  document.addEventListener('click', (e) => {
    const g = e.target.closest('.tile.added > .card-gear');
    const open = document.querySelector('.added-menu:not([hidden])');
    if (open && !e.target.closest('.added-menu') && !g) open.hidden = true;
    if (!g) return;
    e.stopPropagation(); e.preventDefault();
    const card = g.parentElement;
    let menu = document.querySelector(`.added-menu[data-card="${card.id}"]`);
    if (!menu) {
      menu = document.createElement('span'); menu.className = 'card-menu added-menu'; menu.dataset.card = card.id; menu.hidden = true;
      document.body.append(menu);
      menu.addEventListener('click', async (ev) => {
        ev.stopPropagation();
        const b = ev.target.closest('[data-place]');
        if (!b || b.classList.contains('off')) return;
        menu.hidden = true; await cardAct(card, b.dataset.place);
      });
    }
    if (!menu.hidden) { menu.hidden = true; return; }
    if (open) open.hidden = true;
    menu.innerHTML = `<b class="cm-h">Karte</b>${cardActions(card)}`; menu.hidden = false;
    const r = card.getBoundingClientRect(), w = menu.offsetWidth;
    let x = r.left + r.width / 2 < innerWidth / 2 ? r.right + 10 : r.left - w - 10;
    if (x < 8 || x + w > innerWidth - 8) x = Math.min(Math.max(8, r.right - w - 10), innerWidth - w - 8);   // phone: over the card
    menu.style.left = `${x}px`;
    menu.style.top = `${Math.min(Math.max(8, r.top + 8), innerHeight - menu.offsetHeight - 8)}px`;
  }, true);

  refreshLayout();
  setInterval(refreshLayout, 8000);     // AURON may have moved something
  setInterval(refreshData, 30000);
})();
