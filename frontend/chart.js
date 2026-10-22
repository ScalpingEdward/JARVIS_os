// A position's chart (Brano, 2026-10-21): a click on an open trade -- in the Trading card or the
// trading view -- opens its five-minute candles, straight from the copier's MT5 (/v1/copier/chart),
// with entry, SL and TP as lines. Large: from the Trading card's left edge to the right column's right
// edge, over the planet. Esc or ✕ closes it; the copier stops sending 30 s later on its own.
// Real trading from it (Brano, 2026-10-22), always after a confirmation: drag the SL or TP line and
// the copier moves it in MT5; Buy / Sell below opens a trade by hand on the same account and symbol.
// Timeframes M1..D1 at the top, and every open trade listed below the chart -- a click shows its chart,
// its ✕ closes it (after the same question as everywhere else).
(() => {
  const LIB = 'https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js';
  const TFS = ['M1', 'M5', 'M15', 'H1', 'H4', 'D1'];
  let tf = 'M5', real = null;
  const box = document.createElement('section');
  box.className = 'pos-chart'; box.hidden = true;
  box.innerHTML = `<header class="pc-head"><b class="pc-title"></b><span class="pc-pl mono"></span><span class="pc-sum mono"></span>
      <span class="pc-tf">${TFS.map((t) => `<button type="button" data-tf="${t}">${t}</button>`).join('')}</span>
      <span class="pc-btns"><button type="button" class="pc-close-pos">Position schließen</button>
      <button type="button" class="pc-x" aria-label="Chart schließen">✕</button></span></header>
    <div class="pc-body"></div><p class="pc-wait muted">Hole die Kerzen aus MT5 …</p>
    <div class="pc-list"><table><thead><tr><th>Symbol</th><th>Seite</th><th class="num">Lots</th><th class="num">Einstieg</th>
      <th class="num">SL</th><th class="num">TP</th><th>Gruppe</th><th class="num">P/L</th><th></th></tr></thead><tbody></tbody><tfoot></tfoot></table></div>
    <footer class="pc-trade"><label>Lots <input class="pc-lots" type="number" step="0.01" min="0.01" /></label>
      <label>SL <input class="pc-sl" type="number" step="any" placeholder="–" /></label>
      <label>TP <input class="pc-tp" type="number" step="any" placeholder="–" /></label>
      <button type="button" class="pc-buy">Buy</button><button type="button" class="pc-sell">Sell</button>
      <small class="muted">SL- und TP-Linie lassen sich mit der Maus ziehen</small></footer>`;
  document.body.append(box);
  const body = box.querySelector('.pc-body'), wait = box.querySelector('.pc-wait');
  let chart = null, series = null, lines = [], pos = null, timer = 0, libReady = null;
  let lineOf = {}, drag = null, decimals = 2;
  const moved = {};   // ticket -> {sl|tp: price, until}: a dragged level holds until the copier's next report has it

  const lib = () => libReady || (libReady = new Promise((ok, bad) => {
    if (window.LightweightCharts) return ok();
    const s = document.createElement('script'); s.src = LIB; s.onload = ok; s.onerror = () => bad(new Error('Chart-Bibliothek lädt nicht'));
    document.head.append(s);
  }));
  // the chart library speaks UTC; shifted once, it shows his local time
  const local = (t) => t - new Date(t * 1000).getTimezoneOffset() * 60;

  function place() {
    const l = document.getElementById('colLeft')?.getBoundingClientRect(), r = document.getElementById('colRight')?.getBoundingClientRect();
    if (!l || !r || innerWidth <= 1000) { Object.assign(box.style, { left: '12px', right: '12px', top: '70px', bottom: '110px' }); return; }
    Object.assign(box.style, { left: `${Math.round(l.left)}px`, right: `${Math.round(innerWidth - r.right)}px`,
      top: `${Math.round(Math.min(l.top, r.top))}px`, bottom: `${Math.round(innerHeight - Math.max(l.bottom, r.bottom))}px` });
  }

  const openAll = () => (window.overview?.accounts || overview?.accounts || []).flatMap((a) => (a.open_positions || []).map((p) => ({ ...p, copier: a.profile, cur: a.currency })));
  // all open trades together (Brano, 2026-10-22): one sum per currency, in the header and under the list
  const total = (all) => {
    const by = {};
    all.forEach((p) => { by[p.cur || ''] = (by[p.cur || ''] || 0) + (p.profit || 0); });
    return Object.entries(by).map(([c, v]) => `<span class="${v > 0 ? 'up' : v < 0 ? 'down' : ''}">${v > 0 ? '+' : ''}${fmt(v)} ${esc(c)}</span>`).join(' · ');
  };
  function current() {   // the position as the last report and the live numbers know it
    return openAll().find((p) => p.ticket === pos.ticket) || null;
  }

  function list() {      // every open trade, the shown one marked; ✕ closes, a click shows its chart
    const n = (v) => (v ? String(v) : '–'), all = openAll();
    const sum = all.length ? total(all) : '';
    box.querySelector('.pc-sum').innerHTML = all.length ? `Alle offen (${all.length}): ${sum}` : '';
    box.querySelector('.pc-list tfoot').innerHTML = all.length > 1
      ? `<tr><td colspan="7">Summe · ${all.length} Trades</td><td class="num mono">${sum}</td><td></td></tr>` : '';
    box.querySelector('.pc-list tbody').innerHTML = all.map((p) => {
      const busy = typeof closing !== 'undefined' && closing.has(p.ticket);
      return `<tr data-ticket="${p.ticket}" data-copier="${esc(p.copier)}" class="${p.ticket === pos.ticket ? 'on' : ''}">
        <td>${esc(p.symbol)}</td><td class="${p.side === 'buy' ? 'up' : 'down'}">${p.side.toUpperCase()}</td>
        <td class="num mono">${fmt(p.volume)}</td><td class="num mono">${n(p.price_open)}</td><td class="num mono">${n(p.sl)}</td>
        <td class="num mono">${n(p.tp)}</td><td>${esc(p.group || '')}</td>
        <td class="num mono ${p.profit > 0 ? 'up' : p.profit < 0 ? 'down' : ''}">${p.profit > 0 ? '+' : ''}${fmt(p.profit || 0)}</td>
        <td><span class="pos-x${busy ? ' busy' : ''}" role="button" title="Diese Position schließen" data-t="${p.ticket}" data-p="${esc(p.copier)}"
          data-d="${esc(`${p.side.toUpperCase()} ${p.symbol} ${fmt(p.volume)} Lots (#${p.ticket})`)}">${busy ? '…' : '✕'}</span></td></tr>`;
    }).join('') || '<tr><td colspan="9" class="muted">Keine offenen Trades</td></tr>';
  }
  box.querySelector('.pc-list').addEventListener('click', (e) => {
    const x = e.target.closest('.pos-x');
    if (x) { window.closeOne?.(x); return; }
    const row = e.target.closest('tr[data-ticket]');
    if (row && Number(row.dataset.ticket) !== pos?.ticket) pick(row.dataset.ticket, row.dataset.copier);
  });
  box.querySelector('.pc-tf').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-tf]');
    if (!b || b.dataset.tf === tf) return;
    tf = b.dataset.tf; marks(); series?.setData([]); wait.hidden = false;
    load().then(() => chart?.timeScale().scrollToRealTime());
  });
  const marks = () => box.querySelectorAll('.pc-tf button').forEach((b) => b.classList.toggle('on', b.dataset.tf === tf));
  marks();

  function header() {
    if (!pos.ticket) {                                  // a symbol's own chart: no trade behind it
      const acct = (window.overview?.accounts || overview?.accounts || []).find((a) => a.profile === pos.copier);
      box.querySelector('.pc-title').textContent = `${real || pos.symbol} · Konto ${acct?.label || pos.copier}`;
      box.querySelector('.pc-pl').textContent = ''; box.querySelector('.pc-close-pos').hidden = true;
      return;
    }
    const p = current() || pos;
    box.querySelector('.pc-title').textContent = `${p.side.toUpperCase()} ${p.symbol} · ${fmt(p.volume)} Lots · ${p.group || ''}`;
    const v = p.profit || 0, pl = box.querySelector('.pc-pl');
    pl.textContent = current() ? `${v > 0 ? '+' : ''}${fmt(v)}` : 'geschlossen';
    pl.className = `pc-pl mono ${v > 0 ? 'up' : v < 0 ? 'down' : ''}`;
    box.querySelector('.pc-close-pos').hidden = !current();
  }

  function levels() {
    if (drag) return;                                   // a line in his hand stays where he holds it
    lines.forEach((l) => series.removePriceLine(l)); lines = []; lineOf = {};
    const p = { ...(current() || pos) }, m = moved[p.ticket];
    if (m && Date.now() < m.until) Object.assign(p, m.levels);
    const add = (key, price, color, title) => { if (!price) return; const l = series.createPriceLine({ price, color, lineWidth: key === 'entry' ? 1 : 2, lineStyle: 2, axisLabelVisible: true, title }); lines.push(l); lineOf[key] = { line: l, price }; };
    add('entry', p.price_open, '#e9edf5', 'Einstieg'); add('sl', p.sl, '#f2647c', 'SL ↕'); add('tp', p.tp, '#3ddc97', 'TP ↕');
  }

  // ---- drag SL / TP: grab within 7 px of the line, let go, confirm -- the copier moves it in MT5 ----
  const fix = (v) => Number(v.toFixed(decimals));
  body.addEventListener('mousedown', (e) => {
    if (!current() || !series) return;
    const y = e.clientY - body.getBoundingClientRect().top;
    const hit = ['sl', 'tp'].find((k) => lineOf[k] && Math.abs(series.priceToCoordinate(lineOf[k].price) - y) < 7);
    if (!hit) return;
    drag = { key: hit, price: lineOf[hit].price };
    chart.applyOptions({ handleScroll: false, handleScale: false });
    e.preventDefault();
  });
  addEventListener('mousemove', (e) => {
    if (!drag) return;
    const p = series.coordinateToPrice(e.clientY - body.getBoundingClientRect().top);
    if (p == null) return;
    drag.price = fix(p);
    lineOf[drag.key].line.applyOptions({ price: drag.price, title: `${drag.key.toUpperCase()} ${drag.price}` });
  });
  addEventListener('mouseup', async () => {
    if (!drag) return;
    const d = drag, p = current();
    chart.applyOptions({ handleScroll: true, handleScale: true });
    const ok = p && d.price !== lineOf[d.key].price
      && confirm(`${d.key.toUpperCase()} von #${p.ticket} (${p.symbol}) auf ${d.price} setzen?\nDer Kopierer ändert es in MT5.`);
    if (ok) {
      const sl = d.key === 'sl' ? d.price : '', tp = d.key === 'tp' ? d.price : '';
      try { await send('POST', '/v1/copier/commands', { profile: p.copier, action: `sltp:${p.ticket}:${sl}:${tp}`, confirmed: true }); }
      catch (err) { alert(`Fehler: ${err.message}`); }
      moved[p.ticket] = { levels: { ...(moved[p.ticket]?.levels || {}), [d.key]: d.price }, until: Date.now() + 30000 };
    }
    drag = null; levels();
  });

  // ---- Buy / Sell by hand on this account and symbol ----
  async function trade(side) {
    const p = { ...(current() || pos) };
    if (!p.ticket) p.symbol = real || p.symbol;         // the broker's spelling the copier found (XAUUSD -> XAUUSD.s)
    const lots = box.querySelector('.pc-lots').value, sl = box.querySelector('.pc-sl').value, tp = box.querySelector('.pc-tp').value;
    if (!(Number(lots) > 0)) { alert('Lots angeben'); return; }
    if (!confirm(`${side.toUpperCase()} ${p.symbol} ${lots} Lots\nSL ${sl || '–'} · TP ${tp || '–'}\nKonto: ${p.copier}\n\nJetzt zum Marktpreis eröffnen?`)) return;
    try {
      await send('POST', '/v1/copier/commands', { profile: p.copier, action: `open:${p.symbol}:${side}:${lots}:${sl}:${tp}`, confirmed: true });
      window.AURON_voice?.note(`Auftrag gesendet: ${side.toUpperCase()} ${p.symbol} ${lots} Lots -- der Kopierer eröffnet ihn in bis zu 20 s.`);
    } catch (err) { alert(`Fehler: ${err.message}`); }
  }
  box.querySelector('.pc-buy').addEventListener('click', () => trade('buy'));
  box.querySelector('.pc-sell').addEventListener('click', () => trade('sell'));

  async function load() {
    if (!pos) return;
    header(); list();
    let d;
    try { d = await (await fetch(`${API}/v1/copier/chart?profile=${encodeURIComponent(pos.copier)}&symbol=${encodeURIComponent(pos.symbol)}&tf=${tf}`)).json(); } catch { return; }
    if (d.name) real = d.name;
    if (!d.bars?.length) { wait.hidden = false; return; }
    wait.hidden = true;
    series.setData(d.bars.map(([t, o, h, l, c]) => ({ time: local(t), open: o, high: h, low: l, close: c })));
    decimals = Math.min(5, Math.max(...d.bars.slice(-30).map((b) => (String(b[4]).split('.')[1] || '').length), 1));
    levels();
  }

  async function open(p, frame) {
    pos = p; real = null; place();
    if (frame) { tf = frame; marks(); } box.hidden = false; wait.hidden = false;
    box.querySelector('.pc-lots').value = p.volume || 0.01;
    box.querySelector('.pc-sl').value = ''; box.querySelector('.pc-tp').value = '';
    try { await lib(); } catch (e) { wait.textContent = e.message; return; }
    if (!chart) {
      chart = LightweightCharts.createChart(body, {
        autoSize: true, layout: { background: { color: 'transparent' }, textColor: '#9fb0c8', fontFamily: 'Inter, "Segoe UI", sans-serif' },
        grid: { vertLines: { color: 'rgba(255,255,255,.04)' }, horzLines: { color: 'rgba(255,255,255,.04)' } },
        rightPriceScale: { borderColor: 'rgba(255,255,255,.08)' },
        timeScale: { borderColor: 'rgba(255,255,255,.08)', timeVisible: true, secondsVisible: false },
        crosshair: { mode: 1 },
      });
      series = chart.addCandlestickSeries({ upColor: '#3ddc97', downColor: '#f2647c', borderVisible: false, wickUpColor: '#3ddc97', wickDownColor: '#f2647c' });
    } else series.setData([]);
    clearInterval(timer);
    await load();
    chart.timeScale().scrollToRealTime();
    timer = setInterval(load, 2000);
  }

  function close() { box.hidden = true; pos = null; clearInterval(timer); }

  box.querySelector('.pc-x').addEventListener('click', close);
  box.querySelector('.pc-close-pos').addEventListener('click', (e) => {
    const p = current(); if (!p) return;
    const b = e.currentTarget;
    Object.assign(b.dataset, { t: p.ticket, p: p.copier, d: `${p.side.toUpperCase()} ${p.symbol} ${fmt(p.volume)} Lots (#${p.ticket})` });
    window.closeOne?.(b);
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !box.hidden) close(); });
  addEventListener('resize', () => { if (!box.hidden) place(); });

  // a click on a trade: in the card (not on its ✕ -- that closes the trade), and in the view's table
  const pick = (ticket, copier, frame) => {
    const all = (overview?.accounts || []).flatMap((a) => (a.open_positions || []).map((p) => ({ ...p, copier: a.profile })));
    const p = all.find((x) => String(x.ticket) === String(ticket) && (!copier || x.copier === copier));
    if (p) open(p, frame);
  };
  // any symbol, with or without a trade (AURON: "zeig mir Gold auf 15 Minuten")
  const symbol = (sym, copier, frame) => open({ symbol: sym, copier, ticket: null }, frame);
  document.getElementById('tGroups')?.addEventListener('click', (e) => {
    const row = e.target.closest('.grp-pos > div[data-ticket]');
    if (!row || e.target.closest('.pos-x')) return;
    e.stopPropagation(); e.preventDefault();
    pick(row.dataset.ticket, row.dataset.copier);
  });
  document.getElementById('positions')?.addEventListener('click', (e) => {
    const row = e.target.closest('tr[data-ticket]');
    if (!row || e.target.closest('button')) return;
    pick(row.dataset.ticket, row.dataset.copier);
  });
  window.AURON_chart = { open: pick, symbol, close };
})();
