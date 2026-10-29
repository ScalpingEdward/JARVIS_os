// AURON on the LG TV. webOS 5 ships Chromium 68 (2018), and the dashboard uses ?. / ??, color-mix(),
// clamp(), flex gap and the single translate/rotate/scale properties -- that browser would show a blank
// page. This gate sits between the TV and the dashboard (127.0.0.1:8080) and hands the TV a version it
// understands; the dashboard itself stays as it is. What CSS cannot carry over statically, shim.js does
// at runtime on the TV, from the lists /__tv/config hands it.
//
// It is also the lock: the API behind the dashboard has no login, so only the TV's address (TV_IPS) and
// this laptop get in -- everyone else on the Wi-Fi gets 403.
//   node tools/tv_gate/gate.mjs          TV_IPS, TV_GATE_PORT, AURON_UI override the defaults
import http from 'node:http';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { transform } from 'esbuild';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.TV_GATE_PORT || 8090);
const UPSTREAM = (process.env.AURON_UI || 'http://127.0.0.1:8080').replace(/\/$/, '');
const TV_IPS = (process.env.TV_IPS || '192.168.0.175').split(',').map((s) => s.trim()).filter(Boolean);
const ALLOWED = new Set(['127.0.0.1', '::1', ...TV_IPS]);
const TARGET = 'chrome68';
const VW = 1920, VH = 1080, REM = 16;  // a webOS app lays out at 1920x1080 CSS px
const CDN = 'https://cdn.jsdelivr.net/npm/';

const log = (...a) => console.log(new Date().toISOString().slice(0, 19), ...a);

// what shim.js needs to finish the CSS on the TV; filled while stylesheets pass through
const config = { gaps: new Set(), autoMargins: new Map(), aspects: new Map(), zooms: new Map(), whiteMix: new Set(),
  keyframes: new Map(), transforms: [], animated: new Set() };

// --- CSS --------------------------------------------------------------------------------------------

const hexRgb = (hex) => {
  let h = hex.replace('#', '');
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
};
const mixKey = (p) => String(p).replace('.', '_');

// color-mix() with the accent: 65 times against transparent (= the accent at an alpha), once against white
function colorMix(css) {
  css = css.replace(/color-mix\(in srgb,\s*var\(--accent\)\s*([\d.]+)%,\s*transparent\)/g,
    (_, p) => `rgba(var(--accent-rgb), ${+p / 100})`);
  return css.replace(/color-mix\(in srgb,\s*var\(--accent\)\s*([\d.]+)%,\s*#fff(?:fff)?\)/gi,
    (_, p) => { config.whiteMix.add(+p); return `var(--accent-w${mixKey(p)})`; });
}

// clamp()/min()/max() arrived in Chrome 79. On a fixed 1920x1080 screen most of them can simply be worked
// out; a % term cannot -- it is dropped, i.e. min(1640px, 100%) becomes 1640px (the box is wider than that).
function lengthPx(expr) {
  const s = expr.trim().replace(/calc\(/g, '(').replace(/(-?[\d.]+)(px|vw|vh|rem)?\b/g, (m, n, u) =>
    String(+n * (u === 'vw' ? VW / 100 : u === 'vh' ? VH / 100 : u === 'rem' ? REM : 1)));
  if (!/^[\d.\s+\-*/()]+$/.test(s)) return null;  // %, em, var(), fr ... -- unknown here
  try { const v = Function(`return (${s})`)(); return Number.isFinite(v) ? v : null; } catch { return null; }
}
function splitArgs(s) {
  const out = []; let depth = 0, cur = '';
  for (const ch of s) {
    if (ch === '(') depth++;
    if (ch === ')') depth--;
    if (ch === ',' && depth === 0) { out.push(cur); cur = ''; } else cur += ch;
  }
  out.push(cur);
  return out;
}
function resolveSizes(css) {
  const re = /(?<![\w.$-])(clamp|min|max)\(((?:[^()]|\([^()]*\))*)\)/g;
  for (let i = 0; i < 5; i++) {
    const next = css.replace(re, (m, fn, args) => {
      const v = splitArgs(args).map(lengthPx);
      let r = null;
      if (fn === 'clamp') r = v[1] != null && v[0] != null && v[2] != null ? Math.max(v[0], Math.min(v[1], v[2])) : v[0];
      else { const k = v.filter((x) => x != null); if (k.length) r = fn === 'min' ? Math.min(...k) : Math.max(...k); }
      return r == null ? m : `${Math.round(r * 100) / 100}px`;
    });
    if (next === css) break;
    css = next;
  }
  return css;
}

// translate:/rotate:/scale: (Chrome 104) -> one transform, in the order the browser applies them.
// Returns the rewritten body, the single transforms as one string, and the rule's own transform.
function singleTransforms(body) {
  const take = (prop) => {
    const m = body.match(new RegExp(`(^|[;\\s])${prop}\\s*:\\s*([^;]+);?`));
    if (!m) return null;
    body = body.replace(m[0], m[1]);
    return m[2].trim();
  };
  const t = take('translate'), r = take('rotate'), s = take('scale');
  const own = body.match(/(^|[;\s])transform\s*:\s*([^;]+)/);
  const transform = own ? own[2].trim() : null;
  if (t == null && r == null && s == null) return { body, single: null, transform };
  const parts = [];
  if (t != null) parts.push(`translate(${t.split(/\s+/).join(', ')})`);
  if (r != null) parts.push(`rotate(${r})`);
  if (s != null) parts.push(`scale(${s.split(/\s+/).join(', ')})`);
  const single = parts.join(' ');
  if (own) return { body: body.replace(own[0], `${own[1]}transform: ${single} ${transform}`), single, transform };
  return { body: `${body.replace(/\s*$/, '')}; transform: ${single};`, single, transform };
}

// The catch with folding translate: into transform: an animation that sets transform then wipes the
// position out (the orbit rings lost their centre), and one that sets translate: wipes the element's own
// transform (the turned tiles went flat while floating). shim.js rebuilds such keyframes per element with
// both parts in -- from these lists: each keyframes' frames, and each rule's single/own transform.
function collectKeyframes(css) {
  const re = /@keyframes\s+([\w-]+)\s*\{((?:[^{}]*\{[^{}]*\})*[^{}]*)\}/g;
  for (const [, name, inner] of css.matchAll(re)) {
    const frames = [];
    for (const [, sel, body] of inner.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      const { single, transform } = singleTransforms(body);
      const rest = body.replace(/(^|[;\s])(transform|translate|rotate|scale)\s*:[^;]*;?/g, '$1').trim();
      frames.push([sel.trim(), transform, single, rest]);
    }
    if (frames.some((f) => f[1] != null || f[2] != null)) config.keyframes.set(name, frames);
  }
}

function perRule(css) {
  return css.replace(/([^{}]*)\{([^{}]*)\}/g, (m, sel, body) => {
    const selector = sel.trim();
    const isRule = selector && !/^(from|to|\d)/.test(selector) && !selector.startsWith('@');
    const plain = isRule ? selector.split(',').map((s) => s.trim()).filter((s) => s && !/::|:(before|after)\b/.test(s)) : [];
    if (isRule) {
      if (/(^|[;\s])(gap|column-gap|row-gap)\s*:/.test(body)) plain.forEach((s) => config.gaps.add(s));
      for (const side of ['left', 'right']) if (new RegExp(`margin-${side}\\s*:\\s*auto`).test(body)) plain.forEach((s) => config.autoMargins.set(`${s}|${side}`, { sel: s, side }));
      const ar = body.match(/aspect-ratio\s*:\s*([\d.]+)\s*(?:\/\s*([\d.]+))?/);
      if (ar) plain.forEach((s) => config.aspects.set(s, +ar[1] / (ar[2] ? +ar[2] : 1)));
      const zoom = body.match(/(^|[;\s])zoom\s*:\s*([\d.]+)/);
      if (zoom && +zoom[2] !== 1) plain.forEach((s) => config.zooms.set(s, +zoom[2]));
    }
    const st = singleTransforms(body);
    body = st.body;
    if (isRule && (st.single || st.transform)) plain.forEach((s) => config.transforms.push([s, st.single, st.transform]));
    if (isRule && /(^|[;\s])animation(-name)?\s*:/.test(body)) plain.forEach((s) => config.animated.add(s));
    // inset (Chrome 87) -- esbuild lowers most, not all
    body = body.replace(/(^|[;\s])inset\s*:\s*([^;!]+)(!important)?/g, (m, pre, v, imp = '') => {
      const [t, r = t, b = t, l = r] = v.trim().split(/\s+/);
      return `${pre}top: ${t}${imp}; right: ${r}${imp}; bottom: ${b}${imp}; left: ${l}${imp}`;
    });
    // a rule that sets the accent itself (.core.degraded) gets its rgb triple and white mixes too
    const acc = body.match(/--accent\s*:\s*(#[0-9a-f]{3,6})\b/i);
    if (acc) {
      const c = hexRgb(acc[1]);
      body += ` --accent-rgb: ${c.join(', ')};`;
      for (const p of config.whiteMix) body += ` --accent-w${mixKey(p)}: rgb(${c.map((v) => Math.round(v * p / 100 + 255 * (1 - p / 100))).join(', ')});`;
    }
    return `${sel}{${body}}`;
  });
}

async function cssForTv(css, name) {
  css = (await transform(css, { loader: 'css', target: TARGET })).code;  // inset, nesting ...
  css = colorMix(css);
  css = resolveSizes(css);
  // :focus-visible (Chrome 86) as :focus -- but only while the arrows are in use (shim.js sets tv-keys):
  // a plain :focus left a blue edge on every card clicked with the pointer (Brano, 2026-10-29)
  css = css.replace(/([^{}]+)\{/g, (m, sel) => (!/:focus-visible/.test(sel) ? m
    : `${sel.split(',').map((s) => (/:focus-visible/.test(s) ? `html.tv-keys ${s.trim().replace(/:focus-visible/g, ':focus')}` : s)).join(',')}{`));
  collectKeyframes(css);
  css = perRule(css);
  const left = (css.match(/color-mix\(|(?<![\w.$-])clamp\(/g) || []).length;
  if (left) log(`${name}: ${left} color-mix/clamp the TV cannot read -- extend gate.mjs`);
  return css;
}

// --- JS / HTML ----------------------------------------------------------------------------------------

async function jsForTv(code, name) {
  try { return (await transform(code, { loader: 'js', target: TARGET, charset: 'utf8' })).code; } catch (e) {
    log(`${name}: esbuild failed, sent unchanged --`, e.message.split('\n')[0]);
    return code;
  }
}

async function htmlForTv(html) {
  const blocks = [];
  html = html.replace(/<script(\s[^>]*)?>([\s\S]*?)<\/script>/gi, (m, attrs = '', body) => { blocks.push({ attrs, body }); return `\u0000${blocks.length - 1}\u0000`; });
  html = html.replace(/<style([^>]*)>([\s\S]*?)<\/style>/gi, (m, a, b) => { blocks.push({ style: a, body: b }); return `\u0000${blocks.length - 1}\u0000`; });
  html = resolveSizes(colorMix(html));  // style="" attributes
  const done = await Promise.all(blocks.map(async (b) => {
    if (b.style !== undefined) return `<style${b.style}>${await cssForTv(b.body, 'inline style')}</style>`;
    const attrs = b.attrs.replace(`src="${CDN}`, 'src="/__tv/cdn/');
    return `<script${attrs}>${b.body.trim() ? await jsForTv(b.body, 'inline script') : b.body}</script>`;
  }));
  html = html.replace(/\u0000(\d+)\u0000/g, (_, i) => done[+i]);
  return html.replace(/<head[^>]*>/i, (m) => `${m}\n<script src="/__tv/shim.js"></script>`);
}

const cache = new Map();
async function converted(kind, text, name) {
  const key = kind + crypto.createHash('sha1').update(text).digest('hex');
  if (!cache.has(key)) cache.set(key, kind === 'css' ? cssForTv(text, name) : kind === 'js' ? jsForTv(text, name) : htmlForTv(text));
  return cache.get(key);
}

// --- server -------------------------------------------------------------------------------------------

const refused = new Set();
const clientIp = (req) => (req.socket.remoteAddress || '').replace(/^::ffff:/, '');

function pipe(req, res) {  // the API and everything not GET: passed through untouched, streaming
  const up = http.request(UPSTREAM + req.url, { method: req.method, headers: { ...req.headers, host: new URL(UPSTREAM).host } }, (r) => {
    res.writeHead(r.statusCode, r.headers);
    r.pipe(res);
  });
  up.on('error', (e) => { if (!res.headersSent) res.writeHead(502); res.end(`AURON nicht erreichbar: ${e.message}`); });
  req.pipe(up);
}

function kindOf(type, url) {
  if (/text\/html/.test(type)) return 'html';
  if (/text\/css/.test(type) || /\.css(\?|$)/.test(url)) return 'css';
  if (/javascript/.test(type) || /\.m?js(\?|$)/.test(url)) return 'js';
  return null;
}

async function serveConverted(req, res, source) {
  const headers = { ...req.headers }; delete headers.host; delete headers['accept-encoding'];
  const r = await fetch(source, { headers, redirect: 'manual' });
  const type = r.headers.get('content-type') || '';
  const kind = r.ok ? kindOf(type, source) : null;
  const out = {};
  for (const h of ['content-type', 'cache-control', 'location', 'last-modified']) if (r.headers.has(h)) out[h] = r.headers.get(h);
  let body = Buffer.from(await r.arrayBuffer());
  if (kind) {
    body = Buffer.from(await converted(kind, body.toString('utf8'), new URL(source).pathname), 'utf8');
    out['cache-control'] = 'no-store';  // a dashboard update reaches the TV with the next start
  }
  res.writeHead(r.status, { ...out, 'content-length': body.length });
  res.end(body);
}

const server = http.createServer(async (req, res) => {
  const ip = clientIp(req);
  if (!ALLOWED.has(ip)) {
    if (!refused.has(ip)) { refused.add(ip); log(`refused ${ip} -- only ${[...ALLOWED].join(', ')} may in`); }
    res.writeHead(403); res.end('AURON: dieses Geraet ist nicht freigegeben.'); return;
  }
  try {
    if (req.url === '/__tv/shim.js') {
      res.writeHead(200, { 'content-type': 'text/javascript; charset=utf-8', 'cache-control': 'no-store' });
      res.end(fs.readFileSync(path.join(HERE, 'shim.js')));
    } else if (req.url === '/__tv/config') {
      // the lists fill while stylesheets pass through: right after a restart the TV can ask before that
      await Promise.all(cache.values());
      if (!config.keyframes.size) await converted('css', await (await fetch(`${UPSTREAM}/styles.css`)).text(), '/styles.css');
      res.writeHead(200, { 'content-type': 'application/json', 'cache-control': 'no-store' });
      res.end(JSON.stringify({ gaps: [...config.gaps], autoMargins: [...config.autoMargins.values()], aspects: [...config.aspects], zooms: [...config.zooms], keyframes: [...config.keyframes], transforms: config.transforms, animated: [...config.animated], whiteMix: [...config.whiteMix] }));
    } else if (req.url === '/__tv/ping') {
      res.writeHead(200, { 'content-type': 'text/plain', 'access-control-allow-origin': '*' }); res.end('ok');
    } else if (req.method === 'GET' && req.url.startsWith('/__tv/cdn/')) {
      await serveConverted(req, res, CDN + req.url.slice('/__tv/cdn/'.length));
    } else if (req.method === 'GET' && !req.url.startsWith('/api/')) {
      await serveConverted(req, res, UPSTREAM + req.url);
    } else pipe(req, res);
  } catch (e) {
    log(`${req.method} ${req.url}:`, e.message);
    if (!res.headersSent) res.writeHead(502);
    res.end(`AURON nicht erreichbar: ${e.message}`);
  }
});

server.listen(PORT, '0.0.0.0', () => log(`tv gate on :${PORT} -> ${UPSTREAM}, open for ${[...ALLOWED].join(', ')}`));
