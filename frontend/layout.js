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
      el.innerHTML = '<span class="corner"></span><div class="tile-head"><span class="ac-title"></span><span class="badge ac-badge">–</span></div><div class="ac-body"></div>';
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
    }
  }

  // clicks inside added cards stay in the card
  document.addEventListener('click', async (e) => {
    const card = e.target.closest('.tile.added');
    if (!card) return;
    e.stopPropagation();
    const cp = e.target.closest('[data-cp]'), del = e.target.closest('[data-del]');
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
      if (types.has('copier')) copier = await call('GET', '/v1/copier/overview');
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

  refreshLayout();
  setInterval(refreshLayout, 8000);     // AURON may have moved something
  setInterval(refreshData, 30000);
})();
