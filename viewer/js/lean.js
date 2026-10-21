// Part 3: the lean. 5-of-40 belief sentences per agent; Jev's drop judgment leans progressive and the society amplifies it.
(() => {
const {$, h} = J;
const MODES = {
 single: {label: 'Jev as measured', runs: ['jev_10000_open1.5'], names: ['Jev as measured'],
  note: '10,000 agents with 5 political beliefs each. Colour is the share of an agent\'s beliefs on the progressive or traditional side.'},
 neutral: {label: 'Lean kept vs removed', runs: ['jev_10000_open1.5', 'jev_10000_neutral'], names: ['Jev as measured', 'Lean removed'],
  note: 'Same start, same rules. Right: the side leans in Jev\'s judgments are removed, and the society splits much more evenly.'},
 axelrod: {label: 'Compare: counting shared beliefs', runs: ['jev_10000_open1.5', 'axelrod_10000'], names: ['Jev', 'Counting shared beliefs'],
  note: 'Right: a classic copying model with no meaning. Agents copy neighbours who share beliefs, and nobody becomes consistent.'},
 life: {label: 'Compare: everyday life', runs: ['jev_10000_open1.5', 'life_1600'], names: ['Political beliefs', 'Everyday-life beliefs'],
  note: 'Right: the same rules on 40 everyday-life sentences (1,600 agents). Colour shows cultures: neighbours sharing at least 4 of 5 beliefs.'},
};
const RUNS = window.RUNS = window.RUNS || {}, have = new Set(window.RUN_NAMES || []);
const P = J.parts.lean = {dirty: true};
let mode = 'single', panes = [], charts = [], sel = null, hov = null, inspKey = '';
const hsl = (hh, s, l) => { const k = n => (n + hh / 30) % 12, a = s * Math.min(l, 1 - l), f = n => l - a * Math.max(-1, Math.min(k(n) - 3, 9 - k(n), 1)); return [f(0) * 255, f(8) * 255, f(4) * 255]; };
const SHORT = {};

function prep(R, name) {
 if (R._p) return R; R._p = 1; R.name = name; R.n = R.side * R.side; R.maxTick = R.frames[R.frames.length - 1].tick;
 if (R.short) R.pool.forEach((s, i) => SHORT[s] = R.short[i]);
 const S = R.sets, pole = R.tags && R.tags.pole; R.isPol = !!pole;
 R.lr = pole ? Float32Array.from(S, s => s.reduce((a, b) => a + pole[b], 0) / s.length) : null;
 R.lo = new Int32Array(S.length); R.hi = new Int32Array(S.length); R.hue = new Float32Array(S.length);
 S.forEach((s, i) => { let x = 2166136261; for (const b of s) { if (b < 30) R.lo[i] |= 1 << b; else R.hi[i] |= 1 << (b - 30); x = Math.imul(x ^ (b + 1), 16777619); } R.hue[i] = ((x >>> 0) % 3600) / 10; });
 R.fc = {}; R.fl = {}; return R;
}
const shortOf = (R, b) => (R.short && R.short[b]) || SHORT[R.pool[b]] || R.pool[b].slice(0, 26);
function comps(R, fi) {
 if (R.fl[fi]) return R.fl[fi];
 const a = R.frames[fi].agents, side = R.side, n = R.n, Pp = new Int32Array(n).map((_, i) => i), f = x => { while (Pp[x] !== x) x = Pp[x] = Pp[Pp[x]]; return x; };
 const near = (s, t) => s === t || (J.pop(R.lo[s] & R.lo[t]) + J.pop(R.hi[s] & R.hi[t]) >= 4 && (!R.lr || (R.lr[s] > 0) === (R.lr[t] > 0)));
 for (let x = 0; x < side; x++) for (let y = 0; y < side; y++) { const u = x * side + y; if (y + 1 < side && near(a[u], a[u + 1])) Pp[f(u)] = f(u + 1); if (x + 1 < side && near(a[u], a[u + side])) Pp[f(u)] = f(u + side); }
 const g = new Map(); for (let i = 0; i < n; i++) { const r = f(i); if (!g.has(r)) g.set(r, []); g.get(r).push(i); }
 const min = Math.max(8, n * 0.0008), out = [], of = new Int32Array(n).fill(-1);
 for (const m of [...g.values()].filter(m => m.length >= min).sort((p, q) => q.length - p.length)) {
  const fr = new Int32Array(R.pool.length); let cx = 0, cy = 0, lr = 0;
  for (const i of m) { for (const b of R.sets[a[i]]) fr[b]++; cx += Math.floor(i / side); cy += i % side; if (R.lr) lr += R.lr[a[i]]; of[i] = out.length; }
  cx /= m.length; cy /= m.length; let best = m[0], bd = 1e9;
  for (const i of m) { const d = (Math.floor(i / side) - cx) ** 2 + (i % side - cy) ** 2; if (d < bd) { bd = d; best = i; } }
  const top = [...fr.keys()].sort((p, q) => fr[q] - fr[p]).slice(0, 3); let x = 2166136261; for (const b of top) x = Math.imul(x ^ (b + 1), 16777619);
  out.push({key: top.slice().sort((p, q) => p - q).join('-'), size: m.length, row: Math.floor(best / side), col: best % side, top, lr: R.lr ? lr / m.length : null, hue: (x >>> 0) % 360});
 }
 return R.fl[fi] = {list: out, of};
}
function frameColors(R, fi) {
 if (R.fc[fi]) return R.fc[fi]; const a = R.frames[fi].agents, out = new Float32Array(R.n * 3), C = R.isPol ? null : comps(R, fi), lmax = Math.log(Math.max(40, R.n * 0.04));
 for (let i = 0; i < R.n; i++) { const s = a[i]; let c;
  if (R.isPol) c = J.sideRGB(R.lr[s], J.TOK.gridMid);
  else { const k = C.of[i]; if (k < 0) c = hsl(R.hue[s], 0.1, 0.88); else { const r = C.list[k], v = Math.min(1, Math.log(r.size) / lmax); c = hsl(r.hue, 0.3 + 0.18 * v, 0.76 - 0.22 * v); } }
  out[i * 3] = c[0]; out[i * 3 + 1] = c[1]; out[i * 3 + 2] = c[2]; }
 return R.fc[fi] = out;
}

P.init = async () => {
 const avail = Object.fromEntries(Object.entries(MODES).filter(([, M]) => M.runs.every(r => have.has(r))));
 J.modeSeg($('lean-modes'), avail, m => setMode(m));
 P.tr = new J.Transport($('lean-tr'), 4, () => { P.dirty = true; }); P.tr.unit = 'round';
 charts = [J.chartBox($('lean-charts'), 'Agents on the progressive side'), J.chartBox($('lean-charts'), 'How consistently each agent\'s five beliefs sit on one side (everyday life: share in the largest culture, ×5)')];
 sweep(); stats();
 await setMode('single'); P.ready = true;
};
async function setMode(m) {
 mode = m; sel = hov = null; J.closeInspector(true); J.markMode($('lean-modes'), m); $('lean-note').textContent = MODES[m].note;
 await Promise.all(MODES[m].runs.map(r => J.load(`runs/${r}.js`))); build(); P.dirty = true;
}
function build() {
 const M = MODES[mode], host = $('lean-panes'); host.innerHTML = ''; panes = [];
 M.runs.forEach((name, k) => {
  if (!RUNS[name]) return; const R = prep(RUNS[name], name);
  const el = h('div', 'pane', J.paneHead(J.SERIES[k], M.names[k], `${J.int(R.n)} agents`) + `<div class="cv px"><canvas></canvas></div>`);
  host.appendChild(el);
  const pn = {R, k, el, cv: el.querySelector('canvas'), wrap: el.querySelector('.cv'), off: document.createElement('canvas'), labs: new Map()};
  pn.off.width = pn.off.height = R.side; pn.img = pn.off.getContext('2d').createImageData(R.side, R.side);
  const cell = e => { const r = pn.cv.getBoundingClientRect(), row = Math.floor((e.clientY - r.top) / r.height * R.side), col = Math.floor((e.clientX - r.left) / r.width * R.side); return row >= 0 && col >= 0 && row < R.side && col < R.side ? row * R.side + col : -1; };
  pn.cv.onmousemove = e => { const i = cell(e); const nh = i >= 0 ? {k, i} : null; if (JSON.stringify(nh) !== JSON.stringify(hov)) P.dirty = true; hov = nh; J.tip(e, i >= 0 ? preview(pn, i) : null); };
  pn.cv.onmouseleave = () => { hov = null; J.tip(null, null); P.dirty = true; };
  pn.cv.onclick = e => { const i = cell(e); J.tip(null, null); sel = i >= 0 ? {k, i} : null; if (!sel) J.closeInspector(true); inspKey = ''; P.dirty = true; };
  panes.push(pn);
 });
 P.tr.setMax(Math.min(...panes.map(p => p.R.maxTick)));
 $('lean-key').innerHTML = M.names.map((nm, k) => `<span><i class="sw" style="background:${J.SERIES[k]}"></i>${nm}</span>`).join('');
 P.resize();
}
P.resize = () => {
 const host = $('lean-panes'), two = innerWidth > 760 && panes.length > 1, W = host.clientWidth, col = Math.floor(two ? (W - 24) / 2 : W);
 const sz = Math.min(col, panes.length > 1 ? 620 : Math.min(W, Math.max(420, innerHeight - 240)));
 host.style.gridTemplateColumns = panes.length > 1 && innerWidth > 760 ? '' : 'minmax(0,1fr)';
 for (const pn of panes) { J.size(pn.cv, sz, sz); pn.size = sz; pn.wrap.style.width = sz + 'px'; pn.wrap.style.maxWidth = '100%'; pn.el.style.maxWidth = panes.length > 1 ? '' : sz + 'px'; pn.labs.forEach(L => L.el.remove()); pn.labs.clear(); }
 for (const c of charts) J.size(c.cv, Math.max(100, c.el.clientWidth), 130);
};
const curIdx = (R, T) => { const [fi, u] = J.frameAt(R.frames, T); return u < 0.5 ? fi : Math.min(fi + 1, R.frames.length - 1); };
function drawPane(pn, T) {
 const R = pn.R, [fi, u0] = J.frameAt(R.frames, T), u = J.smooth(u0), A = frameColors(R, fi), Bc = frameColors(R, Math.min(fi + 1, R.frames.length - 1)), d = pn.img.data;
 const ci = curIdx(R, T), ag = R.frames[ci].agents, s = sel && sel.k === pn.k ? sel : null, hs = s ? ag[s.i] : -1;
 for (let i = 0, j = 0; i < R.n; i++, j += 3) { const dim = hs >= 0 && ag[i] !== hs ? 0.22 : 1, o = i * 4, w = 255 * (1 - dim);
  d[o] = (A[j] + (Bc[j] - A[j]) * u) * dim + w; d[o + 1] = (A[j + 1] + (Bc[j + 1] - A[j + 1]) * u) * dim + w; d[o + 2] = (A[j + 2] + (Bc[j + 2] - A[j + 2]) * u) * dim + w; d[o + 3] = 255; }
 pn.off.getContext('2d').putImageData(pn.img, 0, 0);
 const g = pn.cv.getContext('2d'), W = pn.cv.width, cs = W / R.side; g.imageSmoothingEnabled = false; g.drawImage(pn.off, 0, 0, W, W);
 if (cs >= 7) { g.strokeStyle = 'rgba(255,255,255,.6)'; g.lineWidth = 1; g.beginPath(); for (let x = 1; x < R.side; x++) { const p = Math.round(x * cs) + 0.5; g.moveTo(p, 0); g.lineTo(p, W); g.moveTo(0, p); g.lineTo(W, p); } g.stroke(); }
 const mark = (i, col, lw) => { g.strokeStyle = col; g.lineWidth = lw; g.strokeRect((i % R.side) * cs - lw / 2, Math.floor(i / R.side) * cs - lw / 2, cs + lw, cs + lw); };
 if (s) mark(s.i, J.TOK.ink, Math.max(2, cs * 0.25));
 if (hov && hov.k === pn.k && (!s || hov.i !== s.i)) mark(hov.i, 'rgba(20,20,19,.7)', Math.max(1.5, cs * 0.18));
 // region labels (hidden while an agent is selected, and on small maps)
 const regs = hs >= 0 || pn.size < 300 ? [] : (() => { const L = comps(R, ci).list; return R.lr ? [...L.filter(r => r.lr < 0).slice(0, 4), ...L.filter(r => r.lr > 0).slice(0, 3)].sort((p, q) => q.size - p.size) : L.slice(0, 7); })();
 const placed = [], seen = new Set(), px = pn.size / R.side, lim = pn.size < 480 ? 4 : 7;
 for (const r of regs) {
  const x = (r.col + 0.5) * px, y = (r.row + 0.5) * px; if (placed.some(p => Math.abs(p[0] - x) < 170 && Math.abs(p[1] - y) < 72) || placed.length >= lim) continue;
  placed.push([x, y]); seen.add(r.key); let L = pn.labs.get(r.key);
  if (!L) { const el = h('div', 'lbl'); pn.wrap.appendChild(el); L = {el, x, y}; pn.labs.set(r.key, L); requestAnimationFrame(() => el.classList.add('on')); }
  L.x += (x - L.x) * 0.2; L.y += (y - L.y) * 0.2; L.x = Math.max(80, Math.min(pn.size - 80, L.x)); L.y = Math.max(34, Math.min(pn.size - 34, L.y));
  const c = r.lr != null ? J.rgb(J.sideRGB(Math.max(-1, Math.min(1, r.lr * 1.4)))) : J.rgb(hsl(r.hue, 0.5, 0.48)), html = `<small>${J.int(r.size)} agents</small>${r.top.map(b => J.esc(shortOf(R, b))).join('<br>')}`;
  if (L.html !== html) { L.el.innerHTML = html; L.html = html; }
  L.el.style.setProperty('--c', c); L.el.style.left = L.x + 'px'; L.el.style.top = L.y + 'px'; L.el.classList.add('on'); L.dead = 0;
 }
 for (const [k, L] of pn.labs) if (!seen.has(k)) { L.el.classList.remove('on'); if (++L.dead > 40) { L.el.remove(); pn.labs.delete(k); } }
}
function preview(pn, i) {
 const R = pn.R, s = R.frames[curIdx(R, P.tr.T)].agents[i], pole = R.tags && R.tags.pole;
 const side = R.isPol ? (R.lr[s] < -0.15 ? ['Progressive-leaning', 'var(--blue)'] : R.lr[s] > 0.15 ? ['Traditional-leaning', 'var(--red)'] : ['Mixed', 'var(--mixed)']) : null;
 return `<b>${side ? `<span style="color:${side[1]}">${side[0]}</span>` : 'Agent'}</b><br><span class="m">${R.sets[s].slice(0, 2).map(b => J.esc(shortOf(R, b))).join(' · ')} … Click for all five beliefs.</span>`;
}
function inspector() {
 if (!sel) return; const pn = panes[sel.k]; if (!pn) return; const R = pn.R, ci = curIdx(R, P.tr.T), f = R.frames[ci], s = f.agents[sel.i], key = `${mode}|${sel.k}|${sel.i}|${f.tick}`;
 if (key === inspKey) return; inspKey = key;
 const pole = R.tags && R.tags.pole, topic = R.topic || (R.tags && R.tags.topic) || []; let same = 0; for (const x of f.agents) if (x === s) same++;
 let chip = ''; if (R.isPol) { const v = R.lr[s]; chip = J.chip(v < -0.15 ? 'lib' : v > 0.15 ? 'con' : 'mix', {lib: 'Progressive-leaning', con: 'Traditional-leaning', mix: 'Mixed'}); }
 const items = R.sets[s].map(b => { const c = pole ? (pole[b] > 0 ? 'var(--red)' : 'var(--blue)') : J.rgb(hsl(R.hue[s], 0.5, 0.48)); return `<li style="--c:${c}">${J.esc(R.pool[b])}${topic[b] ? `<span class="tag">${J.esc(topic[b])}</span>` : ''}</li>`; }).join('');
 const nP = pole ? R.sets[s].filter(b => pole[b] < 0).length : 0;
 J.inspect(`<h3>Agent at row ${Math.floor(sel.i / R.side) + 1}, column ${sel.i % R.side + 1}</h3><div class="sub">${MODES[mode].names[sel.k]} · round ${f.tick}</div>
  ${chip ? `<div class="row">${chip}<span class="k">${nP} progressive · ${5 - nP} traditional</span></div>` : ''}
  <div class="m" style="margin-top:6px">${J.int(same)} of ${J.int(R.n)} agents (${(same / R.n * 100).toFixed(1)}%) hold exactly this set of five; they stay in full colour on the map.</div>
  <div class="sec"><h4>Its five beliefs</h4>${pole ? '<div class="m" style="margin-bottom:4px">Blue: progressive side · red: traditional side</div>' : ''}<ul>${items}</ul></div>`, () => { sel = null; P.dirty = true; });
}
P.render = () => {
 const T = P.tr.T; for (const pn of panes) drawPane(pn, T);
 const defs = [{get: h => h.traditional_share == null ? null : 1 - h.traditional_share, ref: {v: 0.5, label: 'even split'}}, {get: h => h.constraint != null ? h.constraint : h.largest_culture != null ? Math.min(1, h.largest_culture * 5) : null}];
 defs.forEach((c, j) => {
  const series = panes.map(pn => { const H = pn.R.hist, v = H.length ? c.get(H[Math.min(H.length - 1, Math.max(0, H.findIndex(x => x.tick >= Math.round(T))))]) : null; return {H, get: c.get, color: J.SERIES[pn.k], at: T > H[H.length - 1].tick ? null : v}; });
  J.chart(charts[j].cv, {series, T, maxT: P.tr.maxT, yMax: 1, fmt: v => Math.round(v * 100) + '%', ref: c.ref, unit: 'round'});
  const html = series.map(s => `<span style="color:${s.color}">${s.at == null ? '–' : J.pct(s.at)}</span>`).join(''); if (charts[j].val._h !== html) { charts[j].val.innerHTML = html; charts[j].val._h = html; }
 });
 if (sel) inspector();
};
function sweep() {
 const S = window.SWEEP; if (!S) { $('lean-sweep').innerHTML = '<div class="m">No sweep data.</div>'; return; }
 $('lean-sweep-sub').textContent = `Each dot is one setting of the lean, averaged over ${S.points[0].n_seeds} random starts (bars: lowest to highest). ${J.int(S.n)} agents, after ${S.tick} rounds.`;
 const W = 900, H = 340, l = 56, r = 30, t = 24, b = 56, xs = S.points.map(p => p.lean_pts), x0 = Math.min(...xs) - 4, x1 = Math.max(...xs) + 4;
 const X = v => l + (v - x0) / (x1 - x0) * (W - l - r), Y = v => t + (1 - v) * (H - t - b);
 let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Dose-response chart">`;
 const K = J.TOK;
 for (const v of [0, 0.25, 0.5, 0.75, 1]) s += `<line x1="${l}" x2="${W - r}" y1="${Y(v)}" y2="${Y(v)}" stroke="${v === 0.5 ? K.ink4 : K.hairline}" ${v === 0.5 ? 'stroke-dasharray="4 4"' : ''}/><text x="${l - 10}" y="${Y(v) + 4}" text-anchor="end" fill="${K.ink3}" font-size="13">${v * 100}%</text>`;
 s += `<text x="${W - r}" y="${Y(0.5) - 6}" text-anchor="end" fill="${K.ink3}" font-size="12">even split</text>`;
 s += `<line x1="${X(0)}" x2="${X(0)}" y1="${t}" y2="${H - b}" stroke="${K.rule}"/>`;
 const pts = S.points.slice().sort((p, q) => p.lean_pts - q.lean_pts);
 s += `<polyline fill="none" stroke="${K.ink2}" stroke-width="1.8" stroke-linejoin="round" points="${pts.map(p => X(p.lean_pts) + ',' + Y(p.blue)).join(' ')}"/>`;
 for (const p of pts) { const x = X(p.lean_pts); if (p.lo != null) s += `<line x1="${x}" x2="${x}" y1="${Y(p.hi)}" y2="${Y(p.lo)}" stroke="${K.ink4}" stroke-width="1.5"/><line x1="${x - 6}" x2="${x + 6}" y1="${Y(p.hi)}" y2="${Y(p.hi)}" stroke="${K.ink4}" stroke-width="1.5"/><line x1="${x - 6}" x2="${x + 6}" y1="${Y(p.lo)}" y2="${Y(p.lo)}" stroke="${K.ink4}" stroke-width="1.5"/>`;
  s += `<circle cx="${x}" cy="${Y(p.blue)}" r="7.5" fill="${J.rgb(J.sideRGB(Math.max(-1, Math.min(1, (0.5 - p.blue) * 2.2))))}" stroke="${K.surface}" stroke-width="2.5"/>`;
  s += `<text x="${x + 13}" y="${Y(p.blue) + 5}" fill="${K.ink}" font-size="16" font-family="var(--serif)">${Math.round(p.blue * 100)}%</text><text x="${x}" y="${H - b + 22}" text-anchor="middle" fill="${K.ink2}" font-size="13">${({'raw Jev': 'as measured', 'neutralized': 'lean removed'})[p.label] || p.label}</text><text x="${x}" y="${H - b + 38}" text-anchor="middle" fill="${K.ink3}" font-size="12">${p.lean_pts > 0 ? '+' : ''}${p.lean_pts} pts</text>`; }
 s += '</svg>'; $('lean-sweep').innerHTML = s;
}
function stats() {
 const S = window.SWEEP; if (!S) return; const pt = lab => S.points.find(p => p.label === lab), raw = pt('raw Jev'), neu = pt('neutralized'), rev = pt('reversed'), dbl = pt('doubled');
 $('lean-stats').innerHTML = [
  {label: 'Jev\'s lean toward keeping progressive beliefs', vals: [{v: S.raw_gap_pts.toFixed(1) + ' pts', name: 'Measured from Jev\'s own answers'}], foot: 'After adopting a progressive belief Jev drops a traditional one 92% of the time; in the reverse case it drops a progressive one only 78% of the time.'},
  {label: 'Agents ending on the progressive side', vals: [{v: J.pct(raw.blue), name: 'As measured', color: 'var(--blue)', dot: 'var(--blue)'}, {v: J.pct(neu.blue), name: 'Lean removed'}], foot: `${J.int(S.n)} agents, ${raw.n_seeds} random starts each.`},
  {label: 'The dial works both ways', vals: [{v: J.pct(rev.blue), name: 'Lean reversed', color: 'var(--red)', dot: 'var(--red)'}, {v: J.pct(dbl.blue), name: 'Lean doubled', color: 'var(--blue)', dot: 'var(--blue)'}], foot: 'The winner follows the sign of the lean, not anything else in the model.'},
 ].map(J.statCard).join('');
}
})();
