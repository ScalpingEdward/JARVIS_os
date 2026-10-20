// Settings (the gear in the bottom bar): a menu of sections; "Design" holds everything
// about the look -- room, accent, glass, clock. Kept in this browser (localStorage).
(() => {
  const KEY = 'auron_theme';
  const ACCENTS = [['#4fd8ff', 'Cyan'], ['#f5b84a', 'Gold'], ['#ff7eb6', 'Rosa'], ['#3ddc97', 'Grün'], ['#b88cff', 'Lila'], ['#f2f4f8', 'Weiß']];
  const TINTS = [['#96c8ff', 'Eisblau'], ['#ffd28c', 'Champagner'], ['#ffb4d2', 'Rosé'], ['#b4ffd2', 'Mint'], ['#d2b4ff', 'Flieder'], ['#e6e6e6', 'Neutral'], ['#000000', 'Schwarz'], ['#26292f', 'Graphit'], ['#0b1630', 'Nachtblau']];
  const STYLES = { clear: ['Klar', { blur: 4, glass: 0.6, solid: 0 }], frosted: ['Matt', { blur: 18, glass: 1, solid: 0 }],
    faded: ['Verblasst', { blur: 24, glass: 1, solid: 0 }], solid: ['Massiv', { blur: 18, glass: 1, solid: 1 }] };
  const CLOCKS = { clean: 'Klar', thin: 'Dünn', mono: 'Digital', elegant: 'Elegant', neon: 'Neon', bold: 'Fett' };
  // The planet is drawn cyan; another colour is a hue turn of the whole core (globe, rings, beam).
  const PLANETS = [['#4fd8ff', 'Cyan'], ['#f5b84a', 'Gold'], ['#ff7eb6', 'Rosa'], ['#3ddc97', 'Grün'], ['#b88cff', 'Lila'], ['#ff5a5a', 'Rot'], ['#e8e8e8', 'Silber']];
  const CORES = { planet: 'Planet', bare: 'Ohne Ringe', rings: 'Nur Ringe', off: 'Aus' };
  const CLOCK_COLORS = [['#ffffff', 'Weiß'], ['accent', 'Akzent'], ['#f5b84a', 'Gold'], ['#ff7eb6', 'Rosa'], ['#3ddc97', 'Grün'], ['#9fb0c8', 'Grau']];
  const DEFAULT = { accent: '#4fd8ff', tint: '#96c8ff', style: 'frosted', strength: 100, clock: 'clean', clockSize: 72,
    planet: '#4fd8ff', core: 'planet', clockColor: '#ffffff' };
  const SECTIONS = [
    ['design', '🎨', 'Design', 'Raum, Farben, Glas, Uhr'],
    ['cards', '▦', 'Karten', 'Welche Karten, wo, in welcher Reihenfolge'],
    ['announce', '📣', 'Durchsagen', 'AURON meldet Wichtiges von selbst'],
    ['voice', '🔊', 'Stimme', 'AURONs Stimme wählen und anhören'],
    ['info', 'ℹ', 'Info', 'Was läuft, Versionen, Hinweise'],
  ];
  let t = { ...DEFAULT };
  try { t = { ...DEFAULT, ...JSON.parse(localStorage.getItem(KEY) || '{}') }; } catch { /* private window */ }
  let page = 'home';

  const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(' ');
  function hueOf(hex) {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
    const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
    if (!d) return { h: 0, s: 0 };
    const h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    return { h: (h * 60 + 360) % 360, s: d / (1 - Math.abs(max + min - 1)) };
  }
  function apply() {
    const r = document.documentElement.style, st = STYLES[t.style] || STYLES.frosted;
    r.setProperty('--accent', t.accent);
    r.setProperty('--tint', rgb(t.tint));
    r.setProperty('--blur', `${st[1].blur}px`);
    r.setProperty('--glass', String(st[1].glass * t.strength / 100));
    r.setProperty('--solid', String(st[1].solid));
    r.setProperty('--clock-size', `${t.clockSize}px`);
    document.documentElement.dataset.glass = t.style;
    // a dark glass colour means a dark card: the colour has to cover, not just tint
    const [cr, cg, cb] = rgb(t.tint).split(' ').map(Number);
    document.documentElement.dataset.cards = (0.2126 * cr + 0.7152 * cg + 0.0722 * cb) / 255 < 0.25 ? 'dark' : 'glass';
    document.documentElement.dataset.clock = t.clock;
    // planet colour: turn the cyan core to the chosen hue; grey-ish picks take the colour out instead
    const { h, s } = hueOf(t.planet);
    r.setProperty('--planet-filter', s < 0.15 ? 'grayscale(1) brightness(1.15)' : `hue-rotate(${Math.round(h - 192)}deg) saturate(${s > 0.6 ? 1.15 : 1})`);
    document.documentElement.dataset.core = t.core;
    r.setProperty('--clock-color', t.clockColor === 'accent' ? t.accent : t.clockColor);
  }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(t)); } catch { /* private window */ } window.AURON_look?.changed(); };
  // look.js: the look from AURON's database (AURON may change it) -- and back when changed here
  window.AURON_theme = { get: () => ({ ...t }), set(next) {
    t = { ...DEFAULT, ...next }; try { localStorage.setItem(KEY, JSON.stringify(t)); } catch { /* private window */ }
    apply(); if (!panel.hidden) paint(); } };

  const panel = document.getElementById('themePanel'), btn = document.getElementById('themeBtn');
  const swatches = (list, cur, key) => `<div class="sw">${list.map(([c, n]) =>
    `<button type="button" data-k="${key}" data-v="${c}" title="${n}" style="background:${c}" class="${c === cur ? 'on' : ''}"></button>`).join('')}
    <label class="own" title="eigene Farbe"><input type="color" data-k="${key}" value="${cur}" />+</label></div>`;
  const section = (title, body) => `<section class="th-sec"><h4>${title}</h4>${body}</section>`;
  const now = () => new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });

  function paint() {
    const head = (title, back) => `<div class="th-head">${back ? '<button type="button" class="th-back" data-k="back">‹</button>' : ''}
      <b>${title}</b><button type="button" class="th-close" data-k="close" aria-label="Schließen">✕</button></div>`;
    if (page === 'home') {
      panel.innerHTML = head('Einstellungen') + `<div class="th-menu">${SECTIONS.map(([k, ic, n, d]) =>
        `<button type="button" data-k="page" data-v="${k}"><i>${ic}</i><span><b>${n}</b><small>${d}</small></span><em>›</em></button>`).join('')}</div>`;
      return;
    }
    if (page === 'design') {
      const rooms = window.AURON_room ? window.AURON_room.list() : [];
      const cur = window.AURON_room ? window.AURON_room.get() : '';
      panel.innerHTML = head('Design', true)
        + section('Hintergrund', `<div class="th-rooms">${rooms.map((r) =>
          `<button type="button" data-k="room" data-v="${r.key}" class="${r.key === cur ? 'on' : ''}"><i style="background-image:url('${r.src}')"></i><span>${r.name}</span></button>`).join('')}</div>`)
        + section('Farben', `<span class="th-label">Akzent</span>${swatches(ACCENTS, t.accent, 'accent')}
            <span class="th-label">Glas der Karten</span>${swatches(TINTS, t.tint, 'tint')}`)
        + section('Glas', `<div class="seg">${Object.entries(STYLES).map(([k, [n]]) =>
            `<button type="button" data-k="style" data-v="${k}" class="${k === t.style ? 'on' : ''}">${n}</button>`).join('')}</div>
            <span class="th-label">Farbstärke <b data-out="strength">${t.strength} %</b></span>
            <input type="range" min="20" max="200" step="10" data-k="strength" value="${t.strength}" />`)
        + section('Planet', `<span class="th-label">Farbe</span>${swatches(PLANETS, t.planet, 'planet')}
            <span class="th-label">Form</span><div class="seg">${Object.entries(CORES).map(([k, n]) =>
              `<button type="button" data-k="core" data-v="${k}" class="${k === t.core ? 'on' : ''}">${n}</button>`).join('')}</div>`)
        + section('Uhr', `<span class="th-label">Farbe</span><div class="sw">${CLOCK_COLORS.map(([c, n]) =>
              `<button type="button" data-k="clockColor" data-v="${c}" title="${n}" style="background:${c === 'accent' ? t.accent : c}" class="${c === t.clockColor ? 'on' : ''}">${c === 'accent' ? '<small>A</small>' : ''}</button>`).join('')}
              <label class="own" title="eigene Farbe"><input type="color" data-k="clockColor" value="${t.clockColor === 'accent' ? t.accent : t.clockColor}" />+</label></div>
            <span class="th-label">Schrift</span><div class="th-clocks">${Object.entries(CLOCKS).map(([k, n]) =>
            `<button type="button" data-k="clock" data-v="${k}" class="${k === t.clock ? 'on' : ''}"><b class="ck-${k}">${now()}</b><span>${n}</span></button>`).join('')}</div>
            <span class="th-label">Größe <b data-out="clockSize">${t.clockSize} px</b></span>
            <input type="range" min="40" max="120" step="4" data-k="clockSize" value="${t.clockSize}" />`)
        + '<button type="button" class="th-reset" data-k="reset">Design zurücksetzen</button>';
      return;
    }
    if (page === 'announce') {
      panel.innerHTML = head('Durchsagen', true) + '<div class="an" id="announceEditor"></div>';
      window.AURON_announce?.editor(panel.querySelector('#announceEditor'));
      return;
    }
    if (page === 'cards') {
      panel.innerHTML = head('Karten', true) + '<div class="le" id="cardEditor"></div>';
      window.AURON_layoutEditor?.open(panel.querySelector('#cardEditor'));
      return;
    }
    if (page === 'info') {
      panel.innerHTML = head('Info', true) + section('AURON', `<p class="th-text">Dashboard, Kopierer, Instagram, Post und Smart Money laufen
        auf diesem Laptop. Design-Einstellungen gelten für diesen Browser. Den Status der Dienste zeigt die Leiste unten.</p>`);
    }
  }

  function set(k, v) {
    if (k === 'reset') t = { ...DEFAULT };
    else t[k] = k === 'strength' || k === 'clockSize' ? Number(v) : v;
    apply(); save();
  }
  panel.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-k]');
    if (!b) return;
    const { k, v } = b.dataset;
    if (k === 'close') { panel.hidden = true; page = 'home'; return; }
    if (k === 'back') { page = 'home'; paint(); return; }
    if (k === 'page') {
      if (v === 'voice') { panel.hidden = true; page = 'home'; document.getElementById('chatVoices')?.click(); return; }
      page = v; paint(); return;
    }
    if (k === 'room') { window.AURON_room?.set(v); paint(); return; }
    set(k, v); paint();
  });
  panel.addEventListener('input', (e) => {
    const i = e.target.closest('input[data-k]');
    if (!i) return;
    set(i.dataset.k, i.value);
    const out = panel.querySelector(`[data-out="${i.dataset.k}"]`);
    if (out) out.textContent = i.dataset.k === 'strength' ? `${t.strength} %` : `${t.clockSize} px`;
  });
  panel.addEventListener('change', (e) => { if (e.target.type === 'color') paint(); });
  btn.addEventListener('click', (e) => { e.stopPropagation(); page = 'home'; paint(); panel.hidden = !panel.hidden; });
  apply();
})();
