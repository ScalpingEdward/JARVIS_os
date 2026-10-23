// The dashboard in AURON's language (Brano, 2026-10-23): when AURON speaks Czech, the cards, views and menus
// read Czech too. The page is written in German; every German text it shows -- numbers taken out, "+# weitere" --
// is looked up in a table AURON's server keeps per language (backend/app/dashboard_layout/i18n.py) and, if new,
// translated there once. Changing text (live numbers, re-rendered lists) is caught as it appears.
// Left as they are: the chat, mails, notes, group names and anything typed -- his own data, never sent away.
(() => {
  const API_BASE = typeof API !== 'undefined' ? API : '/api';
  const SKIP = '#chatLog, .msg, #mList, .mail-list, .ac-notes, .ac-note-row, .gname, .ps-mem, .tk-legs, script, style, textarea, input, select, option, [data-no-i18n]';
  const ATTRS = ['placeholder', 'title', 'aria-label'];
  const NUM = /[-+−]?\d[\d.,:'’%]*/g;
  const LETTERS = /[A-Za-zÄÖÜäöüß]{2}/;
  let lang = 'de', table = {}, pending = new Set(), timer = 0, shown = new WeakMap();

  const key = (t) => t.replace(NUM, '#');
  function render(text) {                               // the German text in this language, or null
    const core = text.trim();
    if (!core || core.length > 300 || !LETTERS.test(core) || /^[A-Z0-9._#\-/ ]+$/.test(core)) return null;
    const k = key(core), tr = table[k];
    if (tr === undefined) { pending.add(k); return null; }
    const nums = core.match(NUM) || [];
    let i = 0;
    const out = tr.replace(/#/g, () => nums[i++] ?? '#');
    return text.replace(core, out);
  }
  const skipped = (el) => el?.closest?.(SKIP);

  function doNode(n) {
    const seen = shown.get(n);
    // the app wrote new text since our translation: that is the German original now
    const orig = seen && n.nodeValue === seen.out ? seen.orig : n.nodeValue;
    const out = render(orig);
    if (out != null && out !== n.nodeValue) { shown.set(n, { orig, out }); n.nodeValue = out; }
  }
  function doEl(el) {
    for (const a of ATTRS) {
      const v = el.getAttribute(a);
      if (!v) continue;
      const k = `__i18n_${a}`, seen = el[k];
      const orig = seen && v === seen.out ? seen.orig : v;
      const out = render(orig);
      if (out != null && out !== v) { el[k] = { orig, out }; el.setAttribute(a, out); }
    }
  }
  function scan(root) {
    if (lang === 'de' || !root) return;
    if (root.nodeType === 3) { if (!skipped(root.parentElement)) doNode(root); return; }
    if (root.nodeType !== 1 || skipped(root)) return;
    doEl(root);
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, {
      acceptNode: (x) => (x.nodeType === 1 && skipped(x) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT) });
    for (let x = w.nextNode(); x; x = w.nextNode()) (x.nodeType === 3 ? doNode : doEl)(x);
    if (pending.size) { clearTimeout(timer); timer = setTimeout(ask, 700); }
  }

  async function ask() {                                // the new texts, translated once on the server
    const texts = [...pending].slice(0, 400);
    texts.forEach((t) => pending.delete(t));
    try {
      const r = await fetch(`${API_BASE}/v1/dashboard/i18n`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ texts }) });
      if (!r.ok) return;
      const d = await r.json();
      if (d.lang !== lang) return;
      Object.assign(table, d.table);
      texts.forEach((t) => { if (!(t in table)) table[t] = t; });   // untranslatable: left as is, not asked again
      scan(document.body);
    } catch { /* AURON away: next change tries again */ }
  }

  const changed = new Set();
  new MutationObserver((ms) => {
    if (lang === 'de') return;
    for (const m of ms) {
      if (m.type === 'characterData') changed.add(m.target);
      else if (m.type === 'attributes') changed.add(m.target);
      else m.addedNodes.forEach((n) => changed.add(n));
    }
    requestAnimationFrame(() => { const list = [...changed]; changed.clear(); list.forEach((n) => n.isConnected && scan(n)); });
  }).observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });

  async function check() {
    let d;
    try { d = await (await fetch(`${API_BASE}/v1/dashboard/i18n`)).json(); } catch { return; }
    if (d.lang === lang) return;
    if (lang !== 'de' || d.lang === 'de') { location.reload(); return; }   // back to German, or another language: fresh
    lang = d.lang; table = d.table || {};
    document.documentElement.lang = lang;
    scan(document.body);
  }
  check();
  setInterval(check, 10000);
})();
