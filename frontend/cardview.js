// A gear on every card (shows on hover): how the card lays out its list -- rows or small tiles --
// and how its text looks: size (A− / A+), the numbers' size on their own, and one of six typefaces,
// for this card or all of them. Kept per card in this browser.
// The card itself never grows with its text (Brano, 2026-10-19): it keeps the height it has at 100 %,
// larger text pushes the last list rows out, and the size stops at the step where something no
// longer fits -- a figure or a number column running over its neighbour.
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
  const NUM_SEL = '.tile-figure b, .kpis b, .tile-list .row > span:last-child, .tile-list .row.grp > span:nth-child(3), .mono';
  const DEFAULT = { size: 1.12, font: 'std', num: 1 };   // a little larger than before (Brano, 2026-10-19)
  const load = (k) => { try { return JSON.parse(localStorage.getItem(k) || '{}'); } catch { return {}; } };
  let views = load(KEY), styles = load(STYLE_KEY);
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(views)); localStorage.setItem(STYLE_KEY, JSON.stringify(styles)); } catch { /* private window */ } };
  const styleOf = (id) => ({ ...DEFAULT, ...(styles[id] || {}) });

  // Only the letters grow -- paddings, gaps and the card stay as they are, so the text takes the
  // room the card already has. Nothing is dropped from the card (Brano, 2026-10-19: "alles bleibt
  // auf der Karte"): the size stops at the step where the content would reach the card's bottom
  // edge (half its padding stays free) or a number would run over its cell.
  const textEls = (card) => [...card.querySelectorAll('*')].filter((el) => !(el instanceof SVGElement) && !el.closest('.card-gear, .corner'));
  const flowKids = (card) => [...card.children].filter((el) => el instanceof HTMLElement && !el.matches('.corner, .card-gear') && getComputedStyle(el).position !== 'absolute');
  const spillCount = (card) => [...card.querySelectorAll(NUM_SEL), ...card.querySelectorAll('.tile-list .row, .kpis > div, .tile-head, .tile-figure')]
    .filter((el) => el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 1).length
    // neighbours in a row that run into each other (a badge wider than its column)
    + [...card.querySelectorAll('.tile-list .row')].reduce((t, row) => {
      const c = [...row.children].filter((el) => el.offsetWidth);
      return t + c.slice(1).filter((el, k) => Math.abs(el.offsetTop - c[k].offsetTop) < 8 && c[k].offsetLeft + c[k].scrollWidth > el.offsetLeft + 1).length;
    }, 0);

  // 1. every card back to 100 % and its natural height, sizes read
  function prepare(id) {
    const card = document.getElementById(id);
    if (!card) return null;
    const els = textEls(card);
    els.forEach((el) => { el.style.fontSize = ''; if (el.dataset.deskHidden) { el.style.display = ''; delete el.dataset.deskHidden; } });
    card.style.height = '';
    return { id, card, els };
  }
  // 2. the card gets its box: its natural height plus its share of the free room in its column
  //    (top bar and status bar stay clear) -- or, on the wallpaper, one height for the whole row
  // 3. the largest text that fits in that box
  function finish({ id, card, els, nat, box }, forced) {
    const st = styleOf(id), desk = document.documentElement.classList.contains('desk');
    const base = els.map((el) => parseFloat(getComputedStyle(el).fontSize) || 0), num = els.map((el) => el.matches(NUM_SEL));
    card.style.height = `${box}px`;
    const pad = parseFloat(getComputedStyle(card).paddingBottom) || 0;
    const set = (z, n) => els.forEach((el, k) => { el.style.fontSize = z === 1 && n === 1 ? '' : `${(base[k] * z * (num[k] ? n : 1)).toFixed(2)}px`; });
    const bottom = () => Math.max(0, ...flowKids(card).map((el) => el.offsetTop + el.offsetHeight));
    const spill0 = spillCount(card);        // what already runs over at 100 % does not hold the size back
    const fits = () => bottom() <= box - pad / 2 + 1 && spillCount(card) <= spill0;
    // from the chosen sizes downwards (never below 100 % unless chosen): the pair that gives up the
    // fewest steps; on a tie the numbers keep theirs -- they are what is read from across the room
    const one = SIZES.indexOf(1), oneN = NUMS.indexOf(1), ai = SIZES.indexOf(st.size), bi = NUMS.indexOf(st.num);
    const aLow = Math.min(one, ai), bLow = Math.min(oneN, bi);
    let used = SIZES[aLow], usedNum = NUMS[bLow], ok = false;
    // a data refresh keeps the size it had while it still fits -- trying larger ones on every refresh
    // made a card jump between two sizes as its numbers changed width (Brano, 2026-10-19)
    const key = `${st.size}|${st.num}|${box}`, prev = card._fit;
    if (!forced && prev && prev.key === key) {
      set(prev.a, prev.b);
      if (fits()) { used = prev.a; usedNum = prev.b; ok = true; }
    }
    for (let d = 0; d <= (ai - aLow) + (bi - bLow) && !ok; d++) {
      for (let db = 0; db <= d && !ok; db++) {
        const a = ai - (d - db), b = bi - db;
        if (a < aLow || b < bLow) continue;
        set(SIZES[a], NUMS[b]);
        if (fits()) { used = SIZES[a]; usedNum = NUMS[b]; ok = true; }
      }
    }
    if (!ok) set(used, usedNum);
    card._fit = { key, a: used, b: usedNum };
    // the wallpaper's row has one height for all: what doesn't fit there steps out whole, never half
    const topIn = (el) => { let t = 0; for (let e = el; e && e !== card; e = e.offsetParent) t += e.offsetTop; return t; };
    if (desk) [...card.querySelectorAll('.tile-list > *')].forEach((el) => {
      if (topIn(el) + el.offsetHeight > box - pad / 2) { el.style.display = 'none'; el.dataset.deskHidden = '1'; } });
    card.dataset.fit = String(used); card.dataset.fitNum = String(usedNum);
  }

  const TOP_CLEAR = 90, BOTTOM_CLEAR = 120;   // the column is centred a little above the middle
  let force = true;   // a new size, a new window size: look for the largest again
  function fitAll() {
    const desk = document.documentElement.classList.contains('desk');
    const all = Object.keys(CARDS).map(prepare).filter(Boolean);
    all.forEach((p) => { p.nat = p.card.offsetHeight; p.box = p.nat; });
    const shown = all.filter((p) => p.nat);   // parked or hidden cards are measured when they show
    // wallpaper: at least a third of the screen (room for the text to grow), a tall card up to 46 %
    if (desk) shown.forEach((p) => { p.box = Math.round(Math.min(Math.max(p.nat, innerHeight * 0.34), innerHeight * 0.46)); });
    else if (innerWidth > 1000) {
      for (const col of document.querySelectorAll('#colLeft, #colRight')) {
        const mine = shown.filter((p) => p.card.parentElement === col);
        const spare = Math.max(0, innerHeight - TOP_CLEAR - BOTTOM_CLEAR - col.offsetHeight);
        const sum = mine.reduce((t, p) => t + p.nat, 0) || 1;
        mine.forEach((p) => { p.box = p.nat + Math.floor(spare * p.nat / sum); });
      }
    }
    shown.forEach((p) => finish(p, force));
    force = false;
  }

  function apply(id) {
    document.querySelector(CARDS[id])?.classList.toggle('as-tiles', views[id] === 'tiles');
    const card = document.getElementById(id);
    if (!card) return;
    const st = styleOf(id);
    card.style.zoom = '';
    card.style.fontFamily = st.font === 'std' ? '' : FONTS[st.font][1];
    card.dataset.font = st.font;
    force = true; refit();
  }
  // the lists are re-rendered with every refresh: fit again once the new rows are in
  let pending = 0;
  const refit = () => { clearTimeout(pending); pending = setTimeout(fitAll, 30); };
  let queued = false;
  const refitNow = () => { if (queued) return; queued = true; queueMicrotask(() => { queued = false; fitAll(); }); };   // not rAF: it sleeps in a hidden window

  for (const id of Object.keys(CARDS)) {
    const card = document.getElementById(id);
    if (!card) continue;
    const gear = document.createElement('span');
    gear.className = 'card-gear'; gear.setAttribute('role', 'button'); gear.title = 'Ansicht der Karte'; gear.textContent = '⚙';
    const menu = document.createElement('span');
    menu.className = 'card-menu'; menu.hidden = true;
    const paint = () => {
      const st = styleOf(id), i = SIZES.indexOf(st.size), j = NUMS.indexOf(st.num), f = Number(card.dataset.fit || st.size), fn = Number(card.dataset.fitNum || st.num);
      menu.innerHTML = `<b class="cm-h">Ansicht</b>`
        + [['list', '☰ Liste'], ['tiles', '▦ Kacheln']].map(([v, t]) =>
          `<span role="button" data-v="${v}" class="${(views[id] || 'list') === v ? 'on' : ''}">${t}</span>`).join('')
        + `<b class="cm-h">Schriftgröße</b><span class="cm-size"><i role="button" data-size="-1" class="${i <= 0 ? 'off' : ''}">A−</i>`
        + `<em>${Math.round(st.size * 100)} %</em><i role="button" data-size="1" class="${i >= SIZES.length - 1 ? 'off' : ''}">A+</i></span>`
        + (f < st.size ? `<small class="cm-note">passt bis ${Math.round(f * 100)} %</small>` : '')
        + `<b class="cm-h">Zahlen</b><span class="cm-size"><i role="button" data-num="-1" class="${j <= 0 ? 'off' : ''}">A−</i>`
        + `<em>${Math.round(st.num * 100)} %</em><i role="button" data-num="1" class="${j >= NUMS.length - 1 ? 'off' : ''}">A+</i></span>`
        + (fn < st.num ? `<small class="cm-note">passt bis ${Math.round(fn * 100)} %</small>` : '')
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
      if (!b) return;
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
  addEventListener('resize', () => { force = true; refit(); });
  document.fonts?.ready.then(refit);
  const closeAll = () => document.querySelectorAll('.card-menu').forEach((m) => {
    if (!m.hidden) { m.hidden = true; document.getElementById(m.dataset.card)?.classList.remove('menu-open'); } });
  document.addEventListener('click', closeAll);
  addEventListener('resize', closeAll);
})();
