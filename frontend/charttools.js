// Tools on the chart (Brano, 2026-10-23): horizontal line, trend line, zone, Fibonacci, measure, EMA 20/50/200.
// Drawn on a layer over the candles, by time and price, so they stay put when scrolling, zooming or switching the
// timeframe. Kept per symbol in this browser. A right-click on a drawing removes it, 🗑 removes all, Esc stops a tool.
// The colours follow the dashboard's accent.
(() => {
  const C = () => window.AURON_chart?.ctx?.();
  const KEY = 'auron_drawings';
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch { return {}; } };
  let all = load(), tool = null, first = null, hover = null, measure = null, emaOn = new Set(), ema = {}, cv = null, raf = 0;
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(all)); } catch { /* private window */ } };
  const accent = () => getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#4fd8ff';
  const FIB = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
  const rgba = (hex, a) => { const h = hex.replace('#', ''); const n = parseInt(h.length === 3 ? h.replace(/./g, '$&$&') : h, 16);
    return `rgba(${n >> 16 & 255}, ${n >> 8 & 255}, ${n & 255}, ${a})`; };

  // ---- time <-> x, also between bars and beyond the last one ----
  function xOf(c, t) {
    const b = c.bars;
    if (!b.length) return null;
    let lo = 0, hi = b.length - 1;
    if (t >= b[hi].time) return c.chart.timeScale().logicalToCoordinate(hi + (t - b[hi].time) / c.step);
    if (t <= b[0].time) return c.chart.timeScale().logicalToCoordinate((t - b[0].time) / c.step);
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (b[m].time <= t) lo = m; else hi = m; }
    return c.chart.timeScale().logicalToCoordinate(lo + (t - b[lo].time) / (b[hi].time - b[lo].time));
  }
  function point(c, e) {
    const r = c.body.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
    const lg = c.chart.timeScale().coordinateToLogical(x), b = c.bars, i = Math.max(0, Math.min(b.length - 1, Math.floor(lg)));
    const time = b.length ? b[i].time + (lg - i) * c.step : 0;
    return { time, price: c.series.coordinateToPrice(y) };
  }

  // ---- the layer ----
  function layer(c) {
    if (cv && cv.parentElement === c.body) return cv;
    cv = document.createElement('canvas'); cv.className = 'pc-draw';
    c.body.append(cv);
    return cv;
  }
  function draw() {
    raf = 0;
    const c = C();
    if (!c || c.box.hidden) return;
    const canvas = layer(c), w = c.body.clientWidth, h = c.body.clientHeight, dpr = devicePixelRatio || 1;
    if (canvas.width !== w * dpr || canvas.height !== h * dpr) { canvas.width = w * dpr; canvas.height = h * dpr; canvas.style.width = `${w}px`; canvas.style.height = `${h}px`; }
    const g = canvas.getContext('2d'), ac = accent(), plotW = w - (c.chart.priceScale('right').width() || 60);
    g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h);
    g.save(); g.beginPath(); g.rect(0, 0, plotW, h); g.clip();
    g.font = '11px Inter, "Segoe UI", sans-serif'; g.lineWidth = 1.5;
    const yOf = (p) => c.series.priceToCoordinate(p), fmt = (p) => Number(p).toFixed(c.decimals);
    const items = [...(all[c.sym] || []), ...(first && hover && tool !== 'hline' ? [{ type: tool, a: first, b: hover, ghost: true }] : [])];
    for (const d of items) {
      g.strokeStyle = ac; g.fillStyle = ac; g.globalAlpha = d.ghost ? 0.6 : 1; g.setLineDash([]);
      if (d.type === 'hline') {
        const y = yOf(d.a.price); if (y == null) continue;
        g.setLineDash([6, 4]); g.beginPath(); g.moveTo(0, y); g.lineTo(plotW, y); g.stroke(); g.setLineDash([]);
        g.fillText(fmt(d.a.price), plotW - 60, y - 4);
        continue;
      }
      const x1 = xOf(c, d.a.time), x2 = xOf(c, d.b.time), y1 = yOf(d.a.price), y2 = yOf(d.b.price);
      if ([x1, x2, y1, y2].some((v) => v == null)) continue;
      if (d.type === 'trend') { g.beginPath(); g.moveTo(x1, y1); g.lineTo(x2, y2); g.stroke(); }
      if (d.type === 'zone') {
        g.globalAlpha = d.ghost ? 0.1 : 0.14; g.fillRect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1));
        g.globalAlpha = d.ghost ? 0.6 : 0.9; g.strokeRect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1));
      }
      if (d.type === 'fib') {
        const left = Math.min(x1, x2);
        for (const f of FIB) {
          const p = d.b.price + (d.a.price - d.b.price) * f, y = yOf(p);
          if (y == null) continue;
          g.globalAlpha = f === 0 || f === 1 ? 0.95 : f === 0.5 || f === 0.618 ? 0.85 : 0.55;
          g.beginPath(); g.moveTo(left, y); g.lineTo(plotW, y); g.stroke();
          g.fillText(`${(f * 100).toFixed(1)} %  ${fmt(p)}`, left + 4, y - 3);
        }
        g.globalAlpha = 0.35; g.setLineDash([4, 4]); g.beginPath(); g.moveTo(x1, y1); g.lineTo(x2, y2); g.stroke();
      }
    }
    if (measure?.a && measure?.b) {                     // the ruler: pips, %, candles, time
      const m = measure, x1 = xOf(c, m.a.time), x2 = xOf(c, m.b.time), y1 = yOf(m.a.price), y2 = yOf(m.b.price);
      if (![x1, x2, y1, y2].some((v) => v == null)) {
        const up = m.b.price >= m.a.price, col = up ? '#3ddc97' : '#f2647c';
        g.globalAlpha = 0.16; g.fillStyle = col; g.fillRect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1));
        g.globalAlpha = 1; g.strokeStyle = col; g.strokeRect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1));
        const dp = m.b.price - m.a.price, pips = dp / c.pip, pct = dp / m.a.price * 100, bars = Math.round(Math.abs(m.b.time - m.a.time) / c.step);
        const mins = Math.round(Math.abs(m.b.time - m.a.time) / 60), span = mins >= 1440 ? `${Math.floor(mins / 1440)} T ${Math.floor(mins % 1440 / 60)} h` : mins >= 60 ? `${Math.floor(mins / 60)} h ${mins % 60} m` : `${mins} m`;
        const txt = `${dp >= 0 ? '+' : ''}${pips.toFixed(1)} Pips · ${pct >= 0 ? '+' : ''}${pct.toFixed(2)} % · ${bars} Kerzen · ${span}`;
        const tw = g.measureText(txt).width + 14, tx = Math.min(Math.max(x2 - tw / 2, 4), plotW - tw - 4), ty = up ? Math.min(y1, y2) - 26 : Math.max(y1, y2) + 6;
        g.fillStyle = 'rgba(6,10,18,.9)'; g.fillRect(tx, ty, tw, 20); g.fillStyle = col; g.fillText(txt, tx + 7, ty + 14);
      }
    }
    g.restore();
    raf = requestAnimationFrame(draw);
  }
  const kick = () => { if (!raf) raf = requestAnimationFrame(draw); };

  // ---- EMA, from the chart's closes ----
  function emaData(bars, n) {
    const k = 2 / (n + 1), out = [];
    let e = null;
    bars.forEach((b, i) => { e = e == null ? b.close : b.close * k + e * (1 - k); if (i >= n - 1) out.push({ time: b.time, value: e }); });
    return out;
  }
  function refreshEma() {
    const c = C();
    if (!c) return;
    const shades = { 20: 1, 50: 0.7, 200: 0.45 };
    for (const n of [20, 50, 200]) {
      if (emaOn.has(n)) {
        ema[n] ||= c.chart.addLineSeries({ lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
        ema[n].applyOptions({ color: rgba(accent(), shades[n]), lineStyle: n === 200 ? 2 : 0 });
        ema[n].setData(emaData(c.bars, n));
      } else if (ema[n]) { c.chart.removeSeries(ema[n]); delete ema[n]; }
    }
  }

  // ---- the buttons ----
  function setTool(t) {
    const c = C();
    tool = tool === t ? null : t; first = null; hover = null; if (t !== 'measure') measure = null;
    document.querySelectorAll('.pc-tools [data-tool]').forEach((b) => b.classList.toggle('on', b.dataset.tool === tool));
    c?.chart.applyOptions({ handleScroll: !tool, handleScale: !tool });
    c?.body.classList.toggle('drawing', !!tool);
    kick();
  }
  document.addEventListener('click', (e) => {
    const b = e.target.closest('.pc-tools button');
    if (!b) return;
    const c = C();
    if (b.dataset.tool) setTool(b.dataset.tool);
    if (b.dataset.ema) { const n = Number(b.dataset.ema); emaOn.has(n) ? emaOn.delete(n) : emaOn.add(n); b.classList.toggle('on', emaOn.has(n)); refreshEma(); }
    if (b.dataset.clear && c && confirm(`Alle Zeichnungen auf ${c.sym} löschen?`)) { delete all[c.sym]; measure = null; save(); kick(); }
  });

  // ---- drawing with the mouse (before the SL/TP drag in chart.js sees it) ----
  document.addEventListener('mousedown', (e) => {
    const c = C();
    if (!tool || !c || !c.body.contains(e.target) || e.button !== 0) return;
    e.stopPropagation(); e.preventDefault();
    const p = point(c, e);
    if (tool === 'hline') { (all[c.sym] ||= []).push({ type: 'hline', a: p }); save(); setTool(null); return; }
    if (tool === 'measure') {
      if (!first) { first = p; measure = { a: p, b: p }; kick(); return; }
      measure = { a: first, b: p };                     // stays on the chart until the next tool or Esc
      const keep = measure; setTool(null); measure = keep; kick(); return;
    }
    if (!first) { first = p; hover = p; kick(); return; }
    (all[c.sym] ||= []).push({ type: tool, a: first, b: p }); save();
    setTool(null);
  }, true);
  document.addEventListener('mousemove', (e) => {
    const c = C();
    if (!tool || !first || !c || !c.body.contains(e.target)) return;
    hover = point(c, e);
    if (tool === 'measure') measure = { a: first, b: hover };
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && tool) { e.stopImmediatePropagation(); setTool(null); measure = null; } }, true);
  // right-click on a drawing removes it
  document.addEventListener('contextmenu', (e) => {
    const c = C();
    if (!c || !c.body.contains(e.target) || !(all[c.sym] || []).length) return;
    const r = c.body.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
    const near = (all[c.sym] || []).findIndex((d) => {
      const ya = c.series.priceToCoordinate(d.a.price);
      if (d.type === 'hline') return Math.abs(ya - y) < 7;
      const yb = c.series.priceToCoordinate(d.b.price), xa = xOf(c, d.a.time), xb = xOf(c, d.b.time);
      if (d.type === 'zone') return x >= Math.min(xa, xb) - 4 && x <= Math.max(xa, xb) + 4 && y >= Math.min(ya, yb) - 4 && y <= Math.max(ya, yb) + 4;
      if (d.type === 'fib') return FIB.some((f) => Math.abs(c.series.priceToCoordinate(d.b.price + (d.a.price - d.b.price) * f) - y) < 6) && x >= Math.min(xa, xb) - 4;
      const t = Math.max(0, Math.min(1, ((x - xa) * (xb - xa) + (y - ya) * (yb - ya)) / ((xb - xa) ** 2 + (yb - ya) ** 2 || 1)));
      return Math.hypot(x - (xa + t * (xb - xa)), y - (ya + t * (yb - ya))) < 7;
    });
    if (near < 0) return;
    e.preventDefault();
    all[c.sym].splice(near, 1); save(); kick();
  });

  // chart.js: new candles (load) and a new chart (open)
  document.addEventListener('auron:chartdata', () => { refreshEma(); kick(); });
  document.addEventListener('auron:chartclose', () => { setTool(null); measure = null; });
})();
