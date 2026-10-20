// A gear on every card (shows on hover): how the card lays out its list -- rows or small tiles --
// and how its text looks: size (A− / A+), the numbers' size on their own, and one of six typefaces,
// for this card or all of them. Kept per card in this browser.
// Sizes are applied exactly as chosen -- no automatic stepping back, which made the card jump
// between sizes on every refresh (Brano, 2026-10-19). Only the letters grow, paddings stay. A+ greys
// out where the next step would no longer fit: the column taller than the screen, or a number
// running over its neighbour.
(() => {
  const KEY = 'auron_cardview', STYLE_KEY = 'auron_cardstyle';
  const CARDS = { tileTrading: '#tGroups', tileWatch: '#wTop', tileInstagram: '#iList', tileMail: '#mList', tileSmart: '#sInsider' };
  // the typefaces (index.html loads them from Google Fonts); "std" is the dashboard's own
  const FONTS = {
    std: ['Standard', 'Inter, "Segoe UI", system-ui, sans-serif'],
    exo: ['Exo 2', '"Exo 2", "Segoe UI", sans-serif'],
    rajdhani: ['Rajdhani', 'Rajdhani, "Segoe UI", sans-serif'],
    sora: ['Sora', 'Sora, "Segoe UI", sans-serif'],
    oxanium: ['Oxanium', 'Oxanium, "Segoe UI", sans-serif'],
    manrope: ['Manrope', 'Manrope, "Segoe UI", sans-serif'],
  };
  const SIZES = [0.9, 1, 1.12, 1.25, 1.4, 1.55];
  const NUMS = [0.9, 1, 1.12, 1.25, 1.4, 1.55];   // on top of the text size, numbers only
  // numbers -- and everything inside them (the coloured +/− spans in Heute/Woche/Offen/Gesamt)
  const NUM_SEL = '.tile-figure b, .kpis b, .tile-list .row > span:last-child, .tile-list .row.grp > span:nth-child(3), .mono, .wpx, .wch, .grp-eq';
  const DEFAULT = { size: 1.12, font: 'std', num: 1 };   // a little larger than before (Brano, 2026-10-19)
  const load = (k) => { try { return JSON.parse(localStorage.getItem(k) || '{}'); } catch { return {}; } };
  let views = load(KEY), styles = load(STYLE_KEY);
  const store = () => { try { localStorage.setItem(KEY, JSON.stringify(views)); localStorage.setItem(STYLE_KEY, JSON.stringify(styles)); } catch { /* private window */ } };
  const save = () => { store(); window.AURON_look?.changed(); };
  const styleOf = (id) => ({ ...DEFAULT, ...(styles[id] || {}) });

  // Only the letters grow -- paddings, gaps and the card's width stay. Nothing is dropped from the
  // card ("alles bleibt auf der Karte"); a larger size makes the card a little taller.
  const textEls = (card) => [...card.querySelectorAll('*')].filter((el) => !(el instanceof SVGElement) && !el.closest('.card-gear, .corner'));
  const spillCount = (card) => [...card.querySelectorAll(NUM_SEL), ...card.querySelectorAll('.tile-list .row, .kpis > div, .tile-head, .tile-figure')]
    .filter((el) => el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 1).length
    // neighbours in a row that run into each other (a badge wider than its column)
    + [...card.querySelectorAll('.tile-list .row')].reduce((t, row) => {
      const c = [...row.children].filter((el) => el.offsetWidth);
      return t + c.slice(1).filter((el, k) => Math.abs(el.offsetTop - c[k].offsetTop) < 8 && c[k].offsetLeft + c[k].scrollWidth > el.offsetLeft + 1).length;
    }, 0);

  function size(id) {
    const card = document.getElementById(id);
    if (!card) return;
    const st = styleOf(id), els = textEls(card);
    els.forEach((el) => { el.style.fontSize = ''; });
    card.style.height = '';
    if (st.size === 1 && st.num === 1) return;
    // read every size first, then write -- one layout pass, not hundreds
    const base = els.map((el) => parseFloat(getComputedStyle(el).fontSize) || 0);
    const num = els.map((el) => !!el.closest(NUM_SEL));
    els.forEach((el, k) => { el.style.fontSize = `${(base[k] * st.size * (num[k] ? st.num : 1)).toFixed(2)}px`; });
  }
  const fitAll = () => Object.keys(CARDS).forEach(size);

  // Would one step more still fit? Tried for real (no paint in between) and put back. "Fits" is where
  // the column really stands on the screen -- below the AURON mark, above the bottom edge -- not a
  // fixed height: that one was too tight, and once a column was above it, every step up was locked,
  // even back to a size that had just been shown.
  const TOP_FREE = 56, BOTTOM_FREE = 8;
  function roomFor(id, key, list) {
    const card = document.getElementById(id), st = styleOf(id), k = list.indexOf(st[key]);
    if (!card || k >= list.length - 1) return false;
    const desk = document.documentElement.classList.contains('desk');
    const box = desk ? card : card.parentElement;
    const onScreen = () => { const r = box.getBoundingClientRect();
      return desk ? r.height <= innerHeight * 0.5 : r.top >= TOP_FREE && r.bottom <= innerHeight - BOTTOM_FREE; };
    const spill = spillCount(card);
    styles[id] = { ...st, [key]: list[k + 1] }; size(id);
    const ok = spillCount(card) <= spill && (innerWidth <= 1000 || onScreen());   // phone, narrow window: the page scrolls anyway
    styles[id] = st; size(id);
    return ok;
  }

  function apply(id) {
    document.querySelector(CARDS[id])?.classList.toggle('as-tiles', views[id] === 'tiles');
    const card = document.getElementById(id);
    if (!card) return;
    const st = styleOf(id);
    card.style.zoom = '';
    card.style.fontFamily = st.font === 'std' ? '' : FONTS[st.font][1];
    card.dataset.font = st.font;
    size(id);
  }
  // the lists are re-rendered with every refresh: fit again once the new rows are in
  let queued = false;
  const refitNow = () => { if (queued) return; queued = true; queueMicrotask(() => { queued = false; fitAll(); }); };

  for (const id of Object.keys(CARDS)) {
    const card = document.getElementById(id);
    if (!card) continue;
    const gear = document.createElement('span');
    gear.className = 'card-gear'; gear.setAttribute('role', 'button'); gear.title = 'Ansicht der Karte'; gear.textContent = '⚙';
    const menu = document.createElement('span');
    menu.className = 'card-menu'; menu.hidden = true;
    const paint = () => {
      const st = styleOf(id), i = SIZES.indexOf(st.size), j = NUMS.indexOf(st.num);
      const moreText = roomFor(id, 'size', SIZES), moreNum = roomFor(id, 'num', NUMS);
      menu.innerHTML = `<b class="cm-h">Ansicht</b>`
        + [['list', '☰ Liste'], ['tiles', '▦ Kacheln']].map(([v, t]) =>
          `<span role="button" data-v="${v}" class="${(views[id] || 'list') === v ? 'on' : ''}">${t}</span>`).join('')
        + `<b class="cm-h">Schriftgröße</b><span class="cm-size"><i role="button" data-size="-1" class="${i <= 0 ? 'off' : ''}">A−</i>`
        + `<em>${Math.round(st.size * 100)} %</em><i role="button" data-size="1" class="${moreText ? '' : 'off'}">A+</i></span>`
        + (!moreText && i < SIZES.length - 1 ? '<small class="cm-note">größer passt nicht auf den Bildschirm</small>' : '')
        + `<b class="cm-h">Zahlen</b><span class="cm-size"><i role="button" data-num="-1" class="${j <= 0 ? 'off' : ''}">A−</i>`
        + `<em>${Math.round(st.num * 100)} %</em><i role="button" data-num="1" class="${moreNum ? '' : 'off'}">A+</i></span>`
        + (!moreNum && j < NUMS.length - 1 ? '<small class="cm-note">größer passt nicht mehr</small>' : '')
        + `<b class="cm-h">Schriftart</b>`
        + Object.entries(FONTS).map(([k, [n, fam]]) =>
          `<span role="button" data-font="${k}" class="${st.font === k ? 'on' : ''}" style='font-family:${fam}'>${n}</span>`).join('')
        + `<span role="button" data-all="1" class="cm-all">Für alle Karten übernehmen</span>`;
    };
    card.append(gear);
    // The menu lives on the page, not in the card: inside, it covered the card's own content and a
    // card that clips (Post) cut it off. It opens beside the card, toward the middle of the screen --
    // to the right of a card on the left, to the left of a card on the right.
    menu.dataset.card = id;
    document.body.append(menu);
    const place = () => {
      const r = card.getBoundingClientRect(), w = menu.offsetWidth, h = menu.offsetHeight;
      const onLeft = r.left + r.width / 2 < innerWidth / 2;
      let x = onLeft ? r.right + 10 : r.left - w - 10;
      if (x < 8 || x + w > innerWidth - 8) x = Math.min(Math.max(8, r.right - w - 10), innerWidth - w - 8);   // narrow screen: over the card
      menu.style.left = `${x}px`;
      menu.style.top = `${Math.min(Math.max(8, r.top + 8), innerHeight - h - 8)}px`;
    };
    // the card itself is a button that opens its view -- clicks on the gear and menu stay here
    gear.addEventListener('click', (e) => {
      e.stopPropagation(); e.preventDefault();
      const open = menu.hidden;
      document.querySelectorAll('.card-menu').forEach((m) => { m.hidden = true; document.getElementById(m.dataset.card)?.classList.remove('menu-open'); });
      if (open) { paint(); menu.hidden = false; place(); card.classList.add('menu-open'); }
    });
    menu.addEventListener('click', (e) => {
      e.stopPropagation(); e.preventDefault();
      const b = e.target.closest('[data-v], [data-size], [data-num], [data-font], [data-all]');
      if (!b || b.classList.contains('off')) return;
      const st = styleOf(id);
      if (b.dataset.v) views[id] = b.dataset.v;
      if (b.dataset.size) {
        const i = Math.min(SIZES.length - 1, Math.max(0, SIZES.indexOf(st.size) + Number(b.dataset.size)));
        styles[id] = { ...st, size: SIZES[i] };
      }
      if (b.dataset.num) {
        const j = Math.min(NUMS.length - 1, Math.max(0, NUMS.indexOf(st.num) + Number(b.dataset.num)));
        styles[id] = { ...st, num: NUMS[j] };
      }
      if (b.dataset.font) styles[id] = { ...st, font: b.dataset.font };
      if (b.dataset.all) Object.keys(CARDS).forEach((other) => { styles[other] = { ...styleOf(id) }; apply(other); });
      save(); apply(id); paint(); place();
    });
    // the countdown and the big figure tick every second without changing any height: not a reason to fit again
    // straight in the observer (a microtask, before the browser paints): with a timer in between, new
    // rows showed for a frame at their plain size every refresh and the card flickered (Brano, 2026-10-19)
    new MutationObserver((ms) => { if (ms.some((m) => !(m.target.parentElement || m.target).closest?.('.tile-figure'))) refitNow(); })
      .observe(card, { childList: true, subtree: true, characterData: true });
    apply(id);
  }
  addEventListener('resize', refitNow);
  document.fonts?.ready.then(refitNow);
  // look.js: {cardId: {size, num, font, view}} from AURON's database, and back when changed here
  window.AURON_cards = {
    get: () => Object.fromEntries(Object.keys(CARDS).map((id) => [id, { ...styleOf(id), view: views[id] || 'list' }])),
    set(cards) {
      for (const [id, c] of Object.entries(cards || {})) {
        if (!CARDS[id]) continue;
        const { view, ...st } = c;
        styles[id] = { ...styleOf(id), ...st };
        if (view) views[id] = view;
        apply(id);
      }
      store();
    },
  };
  const closeAll = () => document.querySelectorAll('.card-menu').forEach((m) => {
    if (!m.hidden) { m.hidden = true; document.getElementById(m.dataset.card)?.classList.remove('menu-open'); } });
  document.addEventListener('click', closeAll);
  addEventListener('resize', closeAll);
})();
