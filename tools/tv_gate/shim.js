// AURON TV shim -- loaded first, and only through tools/tv_gate/gate.mjs (never by the dashboard itself).
// Chromium 68 (webOS 5) lacks a few built-ins the dashboard uses, flex gap, aspect-ratio, and an accent
// colour with alpha. gate.mjs rewrote the CSS as far as it could; this does the rest at runtime from
// /__tv/config. And the remote: the arrows move between controls, OK clicks, Back acts like Escape.
// Written for that old browser on purpose: no ?., no ??.
(function () {
  'use strict';
  var def = function (obj, name, value) { if (!(name in obj)) Object.defineProperty(obj, name, { configurable: true, writable: true, value: value }); };

  // --- built-ins from Chrome 69..85 ---------------------------------------------------------------------
  def(Array.prototype, 'flat', function flat(depth) {
    var out = [];
    (function walk(a, d) { for (var i = 0; i < a.length; i++) { if (!(i in a)) continue; if (Array.isArray(a[i]) && d > 0) walk(a[i], d - 1); else out.push(a[i]); } })(this, depth === undefined ? 1 : Number(depth));
    return out;
  });
  def(Array.prototype, 'flatMap', function flatMap(fn, self) { return Array.prototype.map.call(this, fn, self).flat(1); });
  def(Object, 'fromEntries', function fromEntries(entries) { var o = {}; for (var e of entries) o[e[0]] = e[1]; return o; });
  def(String.prototype, 'matchAll', function* matchAll(re) {
    var r = typeof re === 'string' ? new RegExp(re.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g') : new RegExp(re.source, re.flags.indexOf('g') < 0 ? re.flags + 'g' : re.flags);
    var s = String(this), m;
    while ((m = r.exec(s)) !== null) { yield m; if (m[0] === '') r.lastIndex++; }
  });
  def(String.prototype, 'replaceAll', function replaceAll(a, b) { return typeof a === 'string' ? this.split(a).join(b) : this.replace(a, b); });
  def(Array.prototype, 'at', function at(i) { i = Math.trunc(i) || 0; return this[i < 0 ? this.length + i : i]; });
  def(Promise, 'allSettled', function allSettled(ps) {
    return Promise.all(Array.from(ps, function (p) { return Promise.resolve(p).then(function (v) { return { status: 'fulfilled', value: v }; }, function (e) { return { status: 'rejected', reason: e }; }); }));
  });
  def(window, 'globalThis', window);
  def(window, 'queueMicrotask', function (fn) { Promise.resolve().then(fn).catch(function (e) { setTimeout(function () { throw e; }); }); });
  // MediaQueryList became an EventTarget in Chrome 80
  if (window.MediaQueryList && !MediaQueryList.prototype.addEventListener) {
    MediaQueryList.prototype.addEventListener = function (t, fn) { if (t === 'change') this.addListener(fn); };
    MediaQueryList.prototype.removeEventListener = function (t, fn) { if (t === 'change') this.removeListener(fn); };
  }
  // Animation.finished (Chrome 84) -- the detail panel's open/close morph awaits it
  try {
    var probe = document.createElement('div').animate([], 0), AP = Object.getPrototypeOf(probe);
    probe.cancel();
    if (!('finished' in AP)) {
      Object.defineProperty(AP, 'finished', { configurable: true, get: function () {
        var a = this;
        if (!a.__tvFinished) {
          a.__tvFinished = new Promise(function (resolve, reject) {
            if (a.playState === 'finished') { resolve(a); return; }
            var done = a.onfinish, gone = a.oncancel;
            a.onfinish = function (e) { if (done) done.call(a, e); resolve(a); };
            a.oncancel = function (e) { if (gone) gone.call(a, e); reject(new DOMException('The animation was cancelled', 'AbortError')); };
          });
        }
        return a.__tvFinished;
      } });
    }
  } catch (e) { /* no Web Animations at all: nothing to fill in */ }
  // keyframes must all name the same properties before Chrome 84 ("Partial keyframes are not supported");
  // the detail morph sets borderRadius only on its first frame -- fill the gaps with the current value
  var animate = Element.prototype.animate;
  if (animate) Element.prototype.animate = function (frames, opts) {
    if (Array.isArray(frames) && frames.length) {
      var props = {}, cs = null, el = this;
      frames.forEach(function (f) { Object.keys(f).forEach(function (k) { if (k !== 'offset' && k !== 'easing' && k !== 'composite') props[k] = 1; }); });
      cs = getComputedStyle(el);
      // a value the browser cannot read back (a shorthand) is left out of every frame instead
      var now = {};
      Object.keys(props).forEach(function (k) { var v = cs[k]; if (v) now[k] = v; });
      if (frames.length === 1) frames = [Object.assign({}, now), frames[0]];
      frames = frames.map(function (f) {
        var g = Object.assign({}, f);
        Object.keys(props).forEach(function (k) { if (!(k in g)) { if (k in now) g[k] = now[k]; } });
        Object.keys(props).forEach(function (k) { if (!(k in now) && frames.some(function (h) { return !(k in h); })) delete g[k]; });
        return g;
      });
    }
    return animate.call(this, frames, opts);
  };

  // the scripts see reduced motion: the particle field is an O(n^2) canvas loop the TV's chip cannot
  // carry. The CSS animations (rings, floating tiles) stay -- Brano wants the movement, ~0.45 s per frame.
  var matchMedia = window.matchMedia.bind(window);
  window.matchMedia = function (q) {
    var m = matchMedia(q);
    if (!/prefers-reduced-motion:\s*reduce/.test(q)) return m;
    return { matches: true, media: q, onchange: null, addListener: function () {}, removeListener: function () {}, addEventListener: function () {}, removeEventListener: function () {}, dispatchEvent: function () { return false; } };
  };

  // the live prices every 3 s instead of every second: with trades open each refresh rebuilds the
  // trading tile, ~150 ms on this chip -- Brano saw it as a freeze every second (2026-10-29)
  var setInterval0 = window.setInterval;
  window.setInterval = function (fn, ms) {
    if (typeof fn === 'function' && fn.name === 'refreshLive' && ms === 1000) arguments[1] = 3000;
    return setInterval0.apply(window, arguments);
  };

  // confirm() answers "no" at once inside a webOS app, without a dialog -- Freigeben, Senden etc. could
  // never go through. It has to stay synchronous for the dashboard, so: the first press shows the
  // question and says no, the same press again within 5 s says yes.
  var asked = null, note = null;
  window.confirm = function (msg) {
    var key = String(msg) + '|' + (document.activeElement && document.activeElement.id || '');
    if (asked && asked.key === key && Date.now() - asked.at < 5000) { asked = null; if (note) note.style.display = 'none'; return true; }
    asked = { key: key, at: Date.now() };
    if (!note) {
      note = document.createElement('div');
      note.style.cssText = 'position:fixed;left:50%;bottom:120px;transform:translateX(-50%);z-index:2147483647;max-width:1100px;padding:22px 34px;border-radius:16px;background:rgba(6,10,18,.96);border:2px solid rgb(var(--accent-rgb));color:#fff;font:600 28px/1.35 sans-serif;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.6)';
      document.body.appendChild(note);
    }
    note.textContent = msg + ' – zum Bestätigen noch einmal drücken';
    note.style.display = 'block';
    clearTimeout(note.timer);
    note.timer = setTimeout(function () { note.style.display = 'none'; }, 5000);
    return false;
  };

  var root = document.documentElement;
  root.classList.add('tv');

  // --- the accent with alpha: gate.mjs wrote rgba(var(--accent-rgb), a); the Look panel sets --accent inline
  var whiteMix = [], seenAccent = null;
  function rgbOf(colour) {
    var m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(colour.trim());
    if (m) { var h = m[1].length === 3 ? m[1].replace(/./g, '$&$&') : m[1]; return [0, 2, 4].map(function (i) { return parseInt(h.slice(i, i + 2), 16); }); }
    var n = colour.match(/[\d.]+/g);
    return n && n.length >= 3 ? n.slice(0, 3).map(Number) : null;
  }
  function syncAccent() {
    var a = root.style.getPropertyValue('--accent').trim();
    if (!a || a === seenAccent) return;
    var c = rgbOf(a);
    if (!c) return;
    seenAccent = a;
    root.style.setProperty('--accent-rgb', c.join(', '));
    whiteMix.forEach(function (p) {
      root.style.setProperty('--accent-w' + String(p).replace('.', '_'), 'rgb(' + c.map(function (v) { return Math.round(v * p / 100 + 255 * (1 - p / 100)); }).join(', ') + ')');
    });
  }
  new MutationObserver(syncAccent).observe(root, { attributes: true, attributeFilter: ['style'] });

  // --- flex gap (Chrome 84) as margins, aspect-ratio (Chrome 88) as a height ---------------------------
  var cfg = { gaps: [], autoMargins: [], aspects: [], zooms: [], keyframes: [], transforms: [], animated: [] }, gapSheet = document.createElement('style'), gapCss = '';
  function firstMatch(sel) { try { return document.querySelector(sel); } catch (e) { return null; } }
  // full: the gap rules (per selector, so they hold for re-rendered rows by themselves) and the rings'
  // centre -- at load, on resize and every 5 s. After a re-render (every second: the trading tile) only
  // the cheap part runs; the whole pass cost ~35 ms a second on the TV (2026-10-29).
  var gapRules = [];
  function fixLayout(full) {
    if (full) gapRules = gapPass();
    var rules = gapRules.slice();
    if (full) fixAnimations(rules); else Array.prototype.push.apply(rules, madeCss);
    var css = rules.join('\n');
    if (css !== gapCss) { gapCss = css; gapSheet.textContent = css; }
    cfg.aspects.forEach(function (a) {
      var els; try { els = document.querySelectorAll(a[0]); } catch (e) { return; }
      for (var i = 0; i < els.length; i++) { var w = els[i].offsetWidth; if (w && els[i].__tvW !== w) { els[i].__tvW = w; els[i].style.height = (w / a[1]) + 'px'; } }
    });
    if (full) centreOrbits();
  }
  function gapPass() {
    var rules = [];
    cfg.gaps.forEach(function (sel) {
      var el = firstMatch(sel);
      if (!el) return;
      var cs = getComputedStyle(el);
      if (cs.display !== 'flex' && cs.display !== 'inline-flex') return;
      var col = parseFloat(cs.columnGap) || 0, row = parseFloat(cs.rowGap) || 0;
      var dir = cs.flexDirection, wrap = cs.flexWrap !== 'nowrap';
      if (dir.indexOf('column') === 0) { if (row) rules.push(sel + ' > * + * { margin-top: ' + row + 'px; }'); }
      else if (wrap) { if (col || row) rules.push(sel + ' > * { margin-' + (dir === 'row-reverse' ? 'left' : 'right') + ': ' + col + 'px; margin-bottom: ' + row + 'px; }'); }
      else if (col) rules.push(sel + ' > * + * { margin-' + (dir === 'row-reverse' ? 'right' : 'left') + ': ' + col + 'px; }');
    });
    // a child pushed to the side with margin-left:auto must stay pushed
    cfg.autoMargins.forEach(function (m) { rules.push(m.sel + ' { margin-' + m.side + ': auto !important; }'); });
    return rules;
  }
  // gate.mjs folded translate:/rotate:/scale: into transform. An animation of transform would then wipe
  // an element's position (the orbit rings slid off the planet), an animation of translate: its own
  // transform (the turned tiles went flat while floating). Give such an element a copy of its keyframes
  // with both parts in each frame -- composed the way the browser would: single transforms first.
  var madeFrames = {}, madeCss = [];
  // Off on the TV, measured in frames per second with one animation running at a time (2026-10-29;
  // all paused: 56, rings alone: 34-42, floating holo alone: 49): the floating tiles take it to 5 fps,
  // whatever the keyframes -- plain translateY, will-change, no shadows, no glass made no difference:
  // six big cards re-rastered at 4K (devicePixelRatio 2) each frame is more than this chip has.
  // Brano chose them floating anyway (2026-10-29: "Schwebend") -- they pause while the remote is in use
  // (busy()), so a press still answers fast; only the idle float is choppy.
  // Off: the filter/blur ones (sun pulse, energy, beam).
  var TV_OFF = ['energy', 'beam', 'sunpulse'];
  function ownTransforms(el) {
    var t = { single: null, own: null };
    cfg.transforms.forEach(function (r) { try { if (el.matches(r[0])) { if (r[1] != null) t.single = r[1]; if (r[2] != null) t.own = r[2]; } } catch (e) { /* bad selector */ } });
    return t;
  }
  var animEls = [];  // what busy() pauses
  function fixAnimations(rules) {
    var frames = {};
    cfg.keyframes.forEach(function (k) { frames[k[0]] = k[1]; });
    animEls = [];
    cfg.animated.forEach(function (sel) {
      var els; try { els = document.querySelectorAll(sel); } catch (e) { return; }
      for (var i = 0; i < els.length; i++) {
        var el = els[i];
        animEls.push(el);
        if (el.__tvClass === el.className) continue;  // done, and its classes have not changed since
        el.__tvClass = el.className;
        el.style.animationName = '';
        var names = getComputedStyle(el).animationName.split(',').map(function (n) { return n.trim(); });
        var t = ownTransforms(el), changed = false;
        var mapped = names.map(function (n) {
          if (TV_OFF.indexOf(n) >= 0) { changed = true; return 'none'; }
          var f = frames[n];
          if (!f) return n;
          var keepPos = t.single && f.some(function (x) { return x[1] != null; });   // frames set transform
          var keepOwn = t.own && f.some(function (x) { return x[2] != null; });      // frames set translate etc.
          if (!keepPos && !keepOwn) return n;
          var key = n + '|' + (keepPos ? t.single : '') + '|' + (keepOwn ? t.own : '');
          if (!madeFrames[key]) {
            madeFrames[key] = n + '__tv' + madeCss.length;
            madeCss.push('@keyframes ' + madeFrames[key] + ' { ' + f.map(function (x) {
              var parts = [];
              if (x[1] != null || x[2] != null) {
                parts.push(x[2] != null ? x[2] : keepPos ? t.single : '');
                parts.push(x[1] != null ? x[1] : keepOwn ? t.own : '');
              }
              var tf = parts.join(' ').trim();
              return x[0] + ' { ' + x[3] + (tf ? (x[3] && !/;\s*$/.test(x[3]) ? '; ' : ' ') + 'transform: ' + tf + ';' : '') + ' }';
            }).join(' ') + ' }');
          }
          changed = true;
          return madeFrames[key];
        });
        if (changed) el.style.animationName = mapped.join(', ');
      }
    });
    Array.prototype.push.apply(rules, madeCss);
  }
  // The rings sit a little below the planet by design; in the laptop's 3D perspective that reads as
  // "around" it, in the flat TV scene as off-centre (Brano, 2026-10-29: "Ringe zentrieren zum Planet").
  function centreOrbits() {
    var planet = document.querySelector('.globe-map');
    if (!planet || !planet.offsetWidth) return;
    var p = planet.getBoundingClientRect(), py = p.top + p.height / 2;
    Array.prototype.forEach.call(document.querySelectorAll('.orbit'), function (o) {
      var r = o.getBoundingClientRect(), dy = py - (r.top + r.height / 2);
      if (Math.abs(dy) > 1) o.style.top = (parseFloat(getComputedStyle(o).top) + dy) + 'px';
    });
  }
  var layoutTimer = 0;
  function soon() { clearTimeout(layoutTimer); layoutTimer = setTimeout(function () { fixLayout(false); }, 300); }
  function full() { fixLayout(true); }
  setInterval(full, 5000);

  function start() {
    document.head.appendChild(gapSheet);
    var tv = document.createElement('style');
    tv.textContent = [
      'html.tv-keys :focus { outline: 3px solid rgb(var(--accent-rgb)) !important; outline-offset: 3px; }',
      // a shared 3D space confuses this Chromium: the open panel showed the tiles through it and clicks
      // landed on the wrong element. Flat scene; each tile still carries its own perspective, so it stays turned.
      'html.tv .stage { perspective: none !important; }',
      'html.tv .stage, html.tv .stage * { transform-style: flat !important; }',
      // no backdrop blur here (Chrome 76): the see-through glass of the full views needs more body to read
      '@supports not (backdrop-filter: blur(1px)) {',
      '  html.tv .detail { background: rgba(4, 6, 10, .78); }',
      '  html.tv .detail-panel { background: rgb(6 10 18 / calc(.86 + var(--solid) * .14)); }',
      '}'
    ].join('\n');
    document.head.appendChild(tv);
    (function load(tries) {
      fetch('/__tv/config').then(function (r) { return r.json(); }).then(function (c) {
        cfg = c; whiteMix = c.whiteMix || []; seenAccent = null; syncAccent(); full();
        if (!c.keyframes.length && tries < 5) setTimeout(function () { load(tries + 1); }, 2000);
      }).catch(function () { if (tries < 5) setTimeout(function () { load(tries + 1); }, 2000); });
    })(0);
    new MutationObserver(soon).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
    window.addEventListener('resize', full);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  window.addEventListener('load', full);

  // --- the remote ---------------------------------------------------------------------------------------
  // Magic Remote pointer = a mouse, nothing to do. Arrows: move to the nearest control in that direction,
  // within whatever is on top (an open panel covers the tiles, so they fail the hit test). OK clicks.
  var KEY = { 37: 'left', 38: 'up', 39: 'right', 40: 'down' }, BACK = 461;
  var CONTROLS = 'a[href], button, input, select, textarea, summary, [tabindex], [onclick], .tile';
  var typing = function (el) { return el && (el.tagName === 'TEXTAREA' || (el.tagName === 'INPUT' && !/^(button|checkbox|radio|range|submit)$/.test(el.type))); };

  // Inside an element with CSS zoom (.detail .view: 1.1) this Chromium paints and hit-tests zoomed, but
  // getBoundingClientRect answers unzoomed -- the arrows aimed ~10 % off and found nothing. Scale it back.
  var OLD_ZOOM = +((/Chrome\/(\d+)/.exec(navigator.userAgent) || [0, 999])[1]) < 128;  // Chrome 128 fixed it
  function rectOf(el) {
    var r = el.getBoundingClientRect(), z = 1;
    if (!OLD_ZOOM) return r;
    cfg.zooms.forEach(function (s) { try { if (el.closest(s[0])) z *= s[1]; } catch (e) { /* bad selector */ } });
    if (z === 1) return r;
    return { left: r.left * z, top: r.top * z, right: r.right * z, bottom: r.bottom * z, width: r.width * z, height: r.height * z };
  }
  function usable(el) {
    if (el.disabled || el.tabIndex === -1 && !el.matches('.tile, [onclick]')) return false;
    var r = el.getBoundingClientRect();
    if (!r.width || !r.height) return false;
    var cs = getComputedStyle(el);
    return cs.visibility !== 'hidden' && cs.pointerEvents !== 'none' && !el.closest('[hidden], [aria-hidden="true"]');
  }
  function onTop(el, r) {
    var x = r.left + r.width / 2, y = r.top + r.height / 2;
    if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) return null;  // off screen: cannot tell
    var hit = document.elementFromPoint(x, y);
    return !!hit && (hit === el || el.contains(hit) || hit.contains(el));
  }
  // the dashboard re-renders tiles every second (countdowns), which drops the focus to <body>: remember
  // where it was, and carry on from there
  var last = { id: '', rect: null };
  function current() {
    var el = document.activeElement;
    if (el && el !== document.body && usable(el)) return el;
    var again = last.id && document.getElementById(last.id);
    return again && usable(again) ? again : null;
  }
  function step(dir) {
    var cur = current();
    var all = Array.prototype.filter.call(document.querySelectorAll(CONTROLS), usable);
    var visible = all.filter(function (el) { return onTop(el, rectOf(el)) === true; });
    var c = cur ? rectOf(cur) : last.rect;
    if (!c) {  // nothing chosen yet: start top left
      visible.sort(function (a, b) { var p = rectOf(a), q = rectOf(b); return (p.left + p.top) - (q.left + q.top); });
      return visible[0] || null;
    }
    var cx = c.left + c.width / 2, cy = c.top + c.height / 2;
    var best = null, bestScore = Infinity;
    function consider(list) {
      list.forEach(function (el) {
        if (cur && (el === cur || el.contains(cur) || cur.contains(el))) return;
        var r = rectOf(el), x = r.left + r.width / 2, y = r.top + r.height / 2, main, side;
        if (dir === 'right') { if (x <= cx + 1 || r.right <= c.right) return; main = Math.max(0, r.left - c.right); side = Math.max(0, r.top - c.bottom, c.top - r.bottom); }
        if (dir === 'left') { if (x >= cx - 1 || r.left >= c.left) return; main = Math.max(0, c.left - r.right); side = Math.max(0, r.top - c.bottom, c.top - r.bottom); }
        if (dir === 'down') { if (y <= cy + 1 || r.bottom <= c.bottom) return; main = Math.max(0, r.top - c.bottom); side = Math.max(0, r.left - c.right, c.left - r.right); }
        if (dir === 'up') { if (y >= cy - 1 || r.top >= c.top) return; main = Math.max(0, c.top - r.bottom); side = Math.max(0, r.left - c.right, c.left - r.right); }
        var score = main + side * 3 + Math.abs(dir === 'left' || dir === 'right' ? y - cy : x - cx) * 0.1;
        if (score < bestScore) { bestScore = score; best = el; }
      });
    }
    consider(visible);
    // nothing on screen that way: something scrolled out of view (but not under an open panel)
    if (!best) consider(all.filter(function (el) { return onTop(el, rectOf(el)) === null; }));
    return best;
  }
  window.__tvStep = step;  // for timing over the TV's web inspector (ares-inspect)
  function scrollFrom(el, dir) {
    var dy = dir === 'down' ? 240 : dir === 'up' ? -240 : 0, dx = dir === 'right' ? 240 : dir === 'left' ? -240 : 0;
    for (var n = el; n && n !== document.body; n = n.parentElement) {
      var cs = getComputedStyle(n);
      if ((dy && /auto|scroll/.test(cs.overflowY) && n.scrollHeight > n.clientHeight) || (dx && /auto|scroll/.test(cs.overflowX) && n.scrollWidth > n.clientWidth)) { n.scrollBy(dx, dy); return; }
    }
    window.scrollBy(dx, dy);
  }

  // A text field reached with the arrows is only chosen, not opened: it is parked read-only, so the TV's
  // keyboard stays away and the arrows can move on. OK opens it for typing, Back parks it again.
  function choose(el) {
    if (typing(el) && !el.readOnly) { el.readOnly = true; el.dataset.tvParked = '1'; }
    if (el.tabIndex < 0 && !el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1');
    el.focus({ preventScroll: true });
  }
  var editing = function (el) { return typing(el) && !el.dataset.tvParked; };
  document.addEventListener('focusout', function (e) {
    var el = e.target;
    if (el.dataset && el.dataset.tvParked) { el.readOnly = false; delete el.dataset.tvParked; }
  }, true);

  document.addEventListener('keydown', function (e) {
    var el = document.activeElement;
    if (e.keyCode === BACK) {
      e.preventDefault();
      if (editing(el)) { el.blur(); choose(el); return; }  // stop typing, the field stays chosen
      (el || document.body).dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true, cancelable: true }));
      return;
    }
    var dir = KEY[e.keyCode];
    if (dir) {
      if (editing(el) && (dir === 'left' || dir === 'right' || el.tagName === 'TEXTAREA')) return;
      if (el && el.tagName === 'SELECT') return;
      e.preventDefault();
      root.classList.add('tv-keys');
      var next = step(dir);
      if (next) {
        choose(next);
        next.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        last = { id: next.id, rect: rectOf(next) };
      } else scrollFrom(current() || document.body, dir);
      return;
    }
    if (e.keyCode !== 13 || editing(el) || (el && el.tagName === 'SELECT')) return;
    e.preventDefault();
    if (el && el.dataset.tvParked) {  // open the chosen field: now the keyboard may come
      el.blur(); el.readOnly = false; delete el.dataset.tvParked; el.focus();
      return;
    }
    // OK clicks whatever is chosen -- also buttons, so it does not hang on the browser's own Enter handling
    var target = el && el !== document.body ? el : current();
    if (target) target.click();
  }, true);
  // put the focus back after a re-render took it away
  new MutationObserver(function () {
    if (!root.classList.contains('tv-keys') || (document.activeElement && document.activeElement !== document.body)) return;
    var again = last.id && document.getElementById(last.id);
    if (again) choose(again);
  }).observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener('mousemove', function () { root.classList.remove('tv-keys'); busy(); }, { passive: true });
  // the animations pause while the remote is in use and run again 2 s after the last press or move
  // -- element by element: a class on <html> with "html.tv-busy *" made the chip restyle the whole page,
  // 0.8 s for the first press (2026-10-29)
  var busyTimer = 0, paused = false;
  function pauseAll(on) {
    paused = on;
    animEls.forEach(function (el) { el.style.animationPlayState = on ? 'paused' : ''; });
  }
  function busy() {
    if (!paused) pauseAll(true);
    clearTimeout(busyTimer);
    busyTimer = setTimeout(function () { pauseAll(false); }, 2000);
  }
  ['keydown', 'mousedown', 'wheel'].forEach(function (t) { document.addEventListener(t, busy, { capture: true, passive: true }); });
})();
