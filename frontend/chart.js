// A position's chart (Brano, 2026-10-21): a click on an open trade -- in the Trading card or the
// trading view -- opens its five-minute candles, straight from the copier's MT5 (/v1/copier/chart),
// with entry, SL and TP as lines. Large: from the Trading card's left edge to the right column's right
// edge, over the planet. Esc or ✕ closes it; the copier stops sending 30 s later on its own.
(() => {
  const LIB = 'https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js';
  const box = document.createElement('section');
  box.className = 'pos-chart'; box.hidden = true;
  box.innerHTML = `<header class="pc-head"><b class="pc-title"></b><span class="pc-pl mono"></span>
      <span class="pc-btns"><button type="button" class="pc-close-pos">Position schließen</button>
      <button type="button" class="pc-x" aria-label="Chart schließen">✕</button></span></header>
    <div class="pc-body"></div><p class="pc-wait muted">Hole die Kerzen aus MT5 …</p>`;
  document.body.append(box);
  const body = box.querySelector('.pc-body'), wait = box.querySelector('.pc-wait');
  let chart = null, series = null, lines = [], pos = null, timer = 0, libReady = null;

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

  function current() {   // the position as the last report and the live numbers know it
    const all = (window.overview?.accounts || overview?.accounts || []).flatMap((a) => (a.open_positions || []).map((p) => ({ ...p, copier: a.profile })));
    return all.find((p) => p.ticket === pos.ticket) || null;
  }

  function header() {
    const p = current() || pos;
    box.querySelector('.pc-title').textContent = `${p.side.toUpperCase()} ${p.symbol} · ${fmt(p.volume)} Lots · ${p.group || ''}`;
    const v = p.profit || 0, pl = box.querySelector('.pc-pl');
    pl.textContent = current() ? `${v > 0 ? '+' : ''}${fmt(v)}` : 'geschlossen';
    pl.className = `pc-pl mono ${v > 0 ? 'up' : v < 0 ? 'down' : ''}`;
    box.querySelector('.pc-close-pos').hidden = !current();
  }

  function levels() {
    lines.forEach((l) => series.removePriceLine(l)); lines = [];
    const p = current() || pos;
    const add = (price, color, title) => { if (price) lines.push(series.createPriceLine({ price, color, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title })); };
    add(p.price_open, '#e9edf5', 'Einstieg'); add(p.sl, '#f2647c', 'SL'); add(p.tp, '#3ddc97', 'TP');
  }

  async function load() {
    if (!pos) return;
    header();
    let d;
    try { d = await (await fetch(`${API}/v1/copier/chart?profile=${encodeURIComponent(pos.copier)}&symbol=${encodeURIComponent(pos.symbol)}`)).json(); } catch { return; }
    if (!d.bars?.length) { wait.hidden = false; return; }
    wait.hidden = true;
    series.setData(d.bars.map(([t, o, h, l, c]) => ({ time: local(t), open: o, high: h, low: l, close: c })));
    levels();
  }

  async function open(p) {
    pos = p; place(); box.hidden = false; wait.hidden = false;
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
  const pick = (ticket, copier) => {
    const all = (overview?.accounts || []).flatMap((a) => (a.open_positions || []).map((p) => ({ ...p, copier: a.profile })));
    const p = all.find((x) => String(x.ticket) === String(ticket) && (!copier || x.copier === copier));
    if (p) open(p);
  };
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
  window.AURON_chart = { open: pick, close };
})();
