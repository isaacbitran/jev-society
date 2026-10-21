// Part 1: the social network. Two societies, same people and follows at tick 0, different feed ranking.
// Two run-file formats: the 1,000-account files (every account drawn, 2 of 6 feed posts, no follow list) and
// `fmt: "live10k-1"` (10,000 accounts, a drawn subset with its follow list, all 6 feed posts and what was posted;
// see runs/SCHEMA-live10k.md). The inspector shows whatever the file has.
(() => {
const {$, h} = J;
// Robustness checks: the 1,000-account table runs and the first 400-account live runs. Shown in a disclosure below
// the main row once the 10,000-account live runs exist; otherwise they are the main row.
const ROBUST = {
 loose: {label: 'Soft judgments, 1,000 accounts', runs: ['net_chrono', 'net_engagement'], names: ['Random feed', 'Ranked feed'],
  desc: 'The first version: 1,000 accounts, stored Jev answers, likes only slightly favour posts that fit. Random feed drifts to one view; ranked keeps two camps.',
  note: '1,000 accounts using 960 stored Jev answers. Judgments are soft: a post that fits a little better is liked only a little more often.'},
 strict: {label: 'Decisive judgments, 1,000 accounts', runs: ['net_chrono_beta32', 'net_engagement_beta32'], names: ['Random feed', 'Ranked feed'],
  desc: 'Small differences in fit become near-certain likes, closer to how live Jev answers. Here the random-feed society unfollows the other side.',
  note: '1,000 accounts, decisive judgments: small differences in fit become near-certain likes and switches, closer to live Jev.'},
 live: {label: 'Live Jev, 400 accounts', runs: ['net_live_chrono_400', 'net_live_engagement_400'], names: ['Random feed', 'Ranked feed'],
  desc: 'The first live runs: 400 accounts, 120 days, a fresh Jev question for every like and switch.',
  note: '400 accounts, 120 days. Every like and switch is a fresh Jev question.'},
 rankers: {label: 'Bridging vs angry replies', runs: ['net_bridging', 'net_outrage'], names: ['Bridging feed', 'Ranked + angry replies'],
  desc: 'Two other feeds: one shows posts both sides like; one also rewards angry replies. Neither is a clean fix.',
  note: 'Left: shows posts liked by both sides. Right: the ranked feed plus a bonus for posts likely to start a clash. 1,000 accounts.'},
 switch: {label: 'Switch on day 200', runs: ['net_engagement', 'net_switch'], names: ['Stays on ranked feed', 'Everyone switches to chronological on day 200'],
  desc: '1,000 accounts, soft judgments: switching everyone to the random feed on day 200 dissolves the camps.',
  note: 'Both run the ranked feed for 200 days; then the right-hand society moves everyone to a random feed. Soft judgments.'},
 switch32: {label: 'Switch on day 200, decisive', runs: ['net_engagement_beta32', 'net_switch_beta32'], names: ['Stays on ranked feed', 'Everyone switches to chronological on day 200'],
  desc: 'The same switch with decisive judgments: opinions bundle slightly more after it, not less.',
  note: 'The same switch with decisive judgments. Here switching to the random feed makes opinions bundle slightly more, not less.'},
 control: {label: 'Control: no meaning', runs: ['net_chrono_axelrod', 'net_engagement_axelrod'], names: ['Random feed', 'Ranked feed'],
  desc: 'Every post fits every reader equally, so Jev plays no role. The two feeds become indistinguishable.',
  note: 'Every post fits every reader equally (50%), so Jev plays no role. The two feeds become indistinguishable.'},
};
const MODES = {};   // what the selector shows: main row first, then robustness checks
let MAIN = {};
const N = window.NETS = window.NETS || {};
const P = J.parts.feed = {dirty: true};
let mode = '', panes = [], charts = [], sel = null, hov = null, inspKey = '', lay = 'reads';
const EMPTY = 65535;

const CH = [
 {k: 'agree_exposure', t: 'Posts people see that agree with them', y: 1, f: J.pct},
 {k: 'mean_abs_r', t: 'How strongly opinions travel together as packages (0 to 1)', y: 1, f: J.f2, ref: {v: 0.167, label: 'US adults 0.17'}},
 {k: 'cross_ties', t: 'Follows that cross camps (blank while there is one camp)', y: 0.6, f: J.pct, ref: {v: 0.5, label: 'random 50%'}, get: h => h.minority < 0.02 ? null : h.cross_ties},
 {k: 'unfollows', t: 'Unfollows so far', y: null, f: v => v >= 1000 ? (v / 1000).toFixed(1) + 'k' : J.int(v)},
];

// Decode a run once. Drawn index d ↔ account id: R.acc(d), R.idx(id) (identity for the old format). Positions are
// laid out client-side (js/layout.js); the recorded xy is kept as f.p0 and used only until the first frame arrives.
function prep(R, name) {
 if (R._p) return R; R._p = 1; R.name = name; R.n = R.config.n; R.k = R.config.k || 20; R.maxTick = R.frames[R.frames.length - 1].tick;
 R.unit = 'day'; R.units = 'days';
 R.live = /^live10k-/.test(R.fmt || '') || typeof R.drawn === 'string';
 if (R.live) { R.dr = J.dec(R.drawn, Uint16Array); R.D = R.dr.length; const di = new Int32Array(R.n).fill(-1); for (let d = 0; d < R.D; d++) di[R.dr[d]] = d; R.acc = d => R.dr[d]; R.idx = i => di[i]; }
 else { R.D = R.n; R.acc = d => d; R.idx = i => i < R.n ? i : -1; }
 const u8 = k => k ? J.dec(k, Uint8Array) : null;
 // live10k-2 stores S and fol in full on frame 0 and as (index, value) changes afterwards
 const full = (prev, whole, delta) => { if (whole) return J.dec(whole, Uint16Array); if (!delta || !prev) return prev; const a = prev.slice(), d = J.dec(delta, Uint32Array); for (let j = 0; j < d.length; j += 2) a[d[j]] = d[j + 1]; return a; };
 let ps = null, pf = null;
 for (const f of R.frames) {
  f.s = ps = full(ps, f.S, f.dS); f.fo = pf = full(pf, f.fol, f.dfol);
  f.fd = J.dec(f.feed, Uint16Array); f.si = J.dec(f.sil, Uint16Array); f.po = u8(f.post); f.li = u8(f.like); f.ad = u8(f.adopt);
  delete f.S; delete f.dS; delete f.fol; delete f.dfol; delete f.xy; delete f.feed;
 }
 R.fw = Math.round(R.frames[0].fd.length / R.D) || R.config.feed || 6; R.hasFollows = !!R.frames[0].fo; R.hasPosts = !!R.frames[0].po;
 J.prepIssues(R); return R;
}

// The main row comes from runs/live10k_manifest.js (window.LIVE10K_MANIFEST): the 10,000-account live runs that have a
// viewer file. At most four: the headline pair (seed 0), a different random start, Jev's lean removed, and the day-50
// switch. Fair-test runs (lean removed: e.sym; stubborn agents: e.stubborn > 0) are kept out of the as-measured modes.
const plain = e => !e.sym && !(e.stubborn > 0);
const NAMES = ['Random feed', 'Ranked feed'];
function discoverModes() {
 const L = Array.isArray(window.LIVE10K_MANIFEST) ? window.LIVE10K_MANIFEST.filter(e => e && e.name && e.file && e.ticks_done > 0) : [];
 const find = (ranker, seed, sw = null) => L.find(e => plain(e) && e.ranker === ranker && (e.seed || 0) === seed && (e.net || 'random') === 'random' && (e.switch_to_chrono_at || null) === sw);
 const main = {}, c0 = find('chrono', 0), g0 = find('engagement', 0);
 if (c0 && g0) {
  main.live10k = {runs: [c0.name, g0.name], names: NAMES, label: `Live Jev, ${J.int(g0.n)} accounts`,
   note: `${J.int(g0.n)} accounts over ${g0.ticks_done} days; every like and every change of mind is a fresh Jev question.`};
  const seeds = [...new Set(L.filter(e => plain(e) && !e.switch_to_chrono_at).map(e => e.seed || 0))].filter(s => s !== 0).sort((a, b) => a - b);
  for (const sd of seeds) { const c = find('chrono', sd), g = find('engagement', sd); if (!c || !g) continue;
   main.seed = {runs: [c.name, g.name], names: NAMES, label: 'Different random start',
    note: `The same experiment from a different random draw of opinions and follows. The results repeat.`}; break; }
  const c = L.find(e => e.ranker === 'chrono' && e.sym && !(e.stubborn > 0)), g = L.find(e => e.ranker === 'engagement' && e.sym && !(e.stubborn > 0));
  if (c && g) main.leanremoved = {runs: [c.name, g.name], names: NAMES, label: 'Lean removed',
   note: `Jev's conservative lean removed, so it favours neither side. Both feeds now end about 50/50, and the random-feed society bundles opinions more tightly than the ranked one.`};
  const sw = L.filter(e => e.switch_to_chrono_at && (e.seed || 0) === 0).sort((a, b) => a.switch_to_chrono_at - b.switch_to_chrono_at)[0];
  if (sw) main.switchday = {runs: [g0.name, sw.name], names: ['Stays on ranked feed', `Switches to the random feed on day ${sw.switch_to_chrono_at}`], label: `Switch feeds on day ${sw.switch_to_chrono_at}`,
   note: `Both run the ranked feed for ${sw.switch_to_chrono_at} days; then the right-hand society moves everyone to a random feed. The camps are already formed, so switching does not undo them.`};
 }
 MAIN = Object.keys(main).length ? main : ROBUST;
 Object.assign(MODES, MAIN); if (MAIN !== ROBUST) Object.assign(MODES, ROBUST);
 return MAIN !== ROBUST;
}

P.init = async () => {
 const hasMain = discoverModes();
 J.modeSeg($('feed-modes'), MAIN, m => setMode(m));
 const det = $('feed-robust');
 if (hasMain) { det.hidden = false; $('feed-rlist').innerHTML = Object.entries(ROBUST).map(([k, M]) => `<button data-m="${k}"><b>${M.label}</b><span>${M.desc}</span></button>`).join(''); $('feed-rlist').onclick = e => { const b = e.target.closest('button'); if (b) setMode(b.dataset.m); }; }
 $('feed-lay').onclick = e => { const b = e.target.closest('button[data-l]'); if (!b || b.dataset.l === lay) return; lay = b.dataset.l; layoutUI(); startLayouts(); P.dirty = true; };
 P.tr = new J.Transport($('feed-tr'), 16, () => { P.dirty = true; });
 charts = CH.map(c => J.chartBox($('feed-charts'), c.t));
 stats();
 await setMode(Object.keys(MAIN)[0]);
 P.ready = true;
};

async function setMode(m) {
 mode = m; sel = hov = null; J.closeInspector(true); J.markMode($('feed-modes'), m); J.markMode($('feed-rlist'), m); $('feed-note').textContent = MODES[m].note;
 await Promise.all(MODES[m].runs.map(r => J.load(`runs/${r}.js`)));
 // keep at most the current pair of large live runs in memory
 for (const k of Object.keys(N)) if (!MODES[m].runs.includes(k) && N[k] && /^live10k-/.test(N[k].fmt || '')) { for (const L of Object.values(N[k].lay || {})) if (L.worker) L.worker.terminate(); delete N[k]; J.unload(`runs/${k}.js`); }
 build(); P.dirty = true;
}

// layout: 'reads' (who saw whose posts) or 'follows' (follow lists), the latter only when every pane's file has them
const canFollow = () => panes.length && panes.every(pn => pn.R.hasFollows);
const layOf = () => lay === 'follows' && canFollow() ? 'follows' : 'reads';
function layoutUI() {
 const can = canFollow(), L = layOf(); $('feed-lay').hidden = !can; $('feed-laynote').hidden = !can;
 $('feed-lay').querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.l === L));
 $('feed-pos').textContent = L === 'follows' ? 'Position is who follows whom: accounts are pulled together when one follows the other. Directions mean nothing.'
  : 'Position is who reads whom: accounts are pulled together when one saw the other\'s posts in the last few days. Directions mean nothing.';
}
function startLayouts() { const L = layOf(); for (const pn of panes) J.layoutRun(pn.R, L, () => { P.dirty = true; }); }

function build() {
 const M = MODES[mode], host = $('feed-panes'); host.innerHTML = ''; panes = [];
 M.runs.forEach((name, k) => {
  if (!N[name]) return; const R = prep(N[name], name);
  const el = h('div', 'pane', J.paneHead(J.SERIES[k], M.names[k], `${J.int(R.n)} accounts${R.live ? `, ${J.int(R.D)} drawn` : ''} · each reads ${R.config.feed} of ${R.k} posts a ${R.unit}`) + `<div class="cv"><canvas></canvas></div>`);
  host.appendChild(el);
  const pn = {R, k, el, cv: el.querySelector('canvas'), xy: new Float32Array(R.D * 2)};
  const pick = e => { const r = pn.cv.getBoundingClientRect(), d = pn.cv._d, x = (e.clientX - r.left) * d, y = (e.clientY - r.top) * d; let best = -1, bd = (12 * d) ** 2;
   for (let i = 0; i < R.D; i++) { const dx = pn.xy[2 * i] - x, dy = pn.xy[2 * i + 1] - y, q = dx * dx + dy * dy; if (q < bd) { bd = q; best = i; } } return best; };
  pn.cv.onmousemove = e => { const i = pick(e); const nh = i >= 0 ? {k, i} : null; if ((nh && nh.i) !== (hov && hov.i) || (nh && nh.k) !== (hov && hov.k)) P.dirty = true; hov = nh; J.tip(e, i >= 0 ? preview(pn, i) : null); };
  pn.cv.onmouseleave = () => { hov = null; J.tip(null, null); P.dirty = true; };
  pn.cv.onclick = e => { const i = pick(e); J.tip(null, null); if (i < 0) { sel = null; J.closeInspector(true); } else { sel = {k, i}; inspKey = ''; } P.dirty = true; };
  panes.push(pn);
 });
 const missing = M.runs.filter(r => !N[r]);
 if (missing.length) $('feed-note').textContent = MODES[mode].note + ` (run file${missing.length > 1 ? 's' : ''} ${missing.map(r => r + '.js').join(', ')} not found in viewer/runs/.)`;
 const R0 = panes.length ? panes[0].R : null;
 $('feed-dots').textContent = !R0 ? '' : R0.D < R0.n ? `Each dot is one account: ${J.int(R0.D)} of the ${J.int(R0.n)}, drawn at random.` : `Each dot is one of the ${J.int(R0.n)} accounts.`;
 M.names.forEach((nm, k) => { $('feed-k' + k).textContent = nm; });
 layoutUI(); startLayouts();
 P.tr.setMax(panes.length ? Math.max(...panes.map(p => p.R.maxTick)) : 1); P.tr.unit = R0 ? R0.unit : 'day'; P.tr.ui();
 P.resize(); P.panes = panes; P.built = (P.built || 0) + 1;
}

P.resize = () => {
 const host = $('feed-panes'), two = innerWidth > 760, W = host.clientWidth, col = two ? (W - 24) / 2 : W;
 const sz = Math.floor(Math.min(col, two ? Math.max(360, innerHeight - 250) : col, 680));
 for (const pn of panes) { J.size(pn.cv, sz, sz); pn.cv.parentElement.style.width = sz + 'px'; pn.cv.parentElement.style.maxWidth = '100%'; }
 for (const c of charts) { const w = c.el.clientWidth; J.size(c.cv, Math.max(100, w), 120); }
};

const curFrame = (R, T) => { const [fi, u] = J.frameAt(R.frames, T); return R.frames[u < 0.5 ? fi : Math.min(fi + 1, R.frames.length - 1)]; };
const campOfAcc = (R, f, id) => J.campOf(R.score[f.s[id]]);   // by account id

function drawPane(pn, T) {
 const R = pn.R, F = R.frames, [fi, u0] = J.frameAt(F, T), cv = pn.cv, W = cv.width, d = cv._d, D = R.D, xy = pn.xy;
 const g = cv.getContext('2d'); g.clearRect(0, 0, W, W);
 const LY = R.lay && R.lay[layOf()], lim = LY ? LY.done : -1; if (lim < 0) return;   // positions not ready yet (worker still on frame 0)
 const A = LY.pos[Math.min(fi, lim)], B = LY.pos[Math.min(fi + 1, lim)], u = fi + 1 > lim ? 0 : J.smooth(u0);
 const sc = (W / 2 - W * 0.05) / 32000, c0 = W / 2;
 for (let i = 0; i < D; i++) { xy[2 * i] = c0 + (A[2 * i] + (B[2 * i] - A[2 * i]) * u) * sc; xy[2 * i + 1] = c0 + (A[2 * i + 1] + (B[2 * i + 1] - A[2 * i + 1]) * u) * sc; }
 const cur = F[u0 < 0.5 ? fi : Math.min(fi + 1, F.length - 1)], side = new Int8Array(D), col = new Array(D);
 for (let i = 0; i < D; i++) { const s = R.score[cur.s[R.acc(i)]]; side[i] = s > 0.15 ? 1 : s < -0.15 ? -1 : 0; col[i] = J.rgb(J.sideRGB(s)); }
 const si = sel ? sel.i : -1, focus = si >= 0 && si < D;
 // feed edges: who saw whose post this tick (authors outside the drawn set are not drawn)
 g.lineWidth = Math.max(0.6, 0.55 * d);
 for (const cross of [false, true]) {
  g.beginPath();
  for (let v = 0; v < D; v++) for (let j = 0; j < R.fw; j++) { const id = cur.fd[v * R.fw + j]; if (id === EMPTY) continue; const a = R.idx(id); if (a < 0) continue; if ((side[v] * side[a] < 0) !== cross) continue; g.moveTo(xy[2 * v], xy[2 * v + 1]); g.lineTo(xy[2 * a], xy[2 * a + 1]); }
  g.strokeStyle = cross ? `rgba(123,94,167,${focus ? 0.08 : 0.34})` : `rgba(20,20,19,${focus ? 0.02 : 0.07})`; g.stroke();
 }
 const r = Math.max(1.9, W / d / (D > 1500 ? 300 : 250)) * d, auth = new Set(), K = J.TOK;
 if (focus) for (let j = 0; j < R.fw; j++) { const id = cur.fd[si * R.fw + j]; if (id !== EMPTY) { const a = R.idx(id); if (a >= 0) auth.add(a); } }
 g.globalAlpha = focus ? 0.22 : 1;
 for (let i = 0; i < D; i++) {
  const q = cur.si[i] !== 0;
  g.beginPath(); g.arc(xy[2 * i], xy[2 * i + 1], r, 0, 6.2832);
  if (q) { g.strokeStyle = col[i]; g.lineWidth = 1.1 * d; g.stroke(); } else { g.fillStyle = col[i]; g.fill(); }
 }
 g.globalAlpha = 1;
 if (focus) {
  g.strokeStyle = 'rgba(20,20,19,.8)'; g.lineWidth = 1.4 * d; g.beginPath();
  for (const a of auth) { g.moveTo(xy[2 * si], xy[2 * si + 1]); g.lineTo(xy[2 * a], xy[2 * a + 1]); } g.stroke();
  for (const a of auth) { g.beginPath(); g.arc(xy[2 * a], xy[2 * a + 1], r * 1.6, 0, 6.2832); g.fillStyle = col[a]; g.fill(); g.strokeStyle = K.ink; g.lineWidth = 1.2 * d; g.stroke(); }
  g.beginPath(); g.arc(xy[2 * si], xy[2 * si + 1], r * 1.8, 0, 6.2832); g.fillStyle = col[si]; g.fill(); g.strokeStyle = K.surface; g.lineWidth = 1.2 * d; g.stroke();
  g.beginPath(); g.arc(xy[2 * si], xy[2 * si + 1], r * 3.6, 0, 6.2832); g.strokeStyle = sel.k === pn.k ? K.ink : 'rgba(20,20,19,.5)'; g.lineWidth = 1.6 * d; if (sel.k !== pn.k) g.setLineDash([3 * d, 3 * d]); g.stroke(); g.setLineDash([]);
 }
 if (hov && hov.k === pn.k && hov.i !== si) { g.beginPath(); g.arc(xy[2 * hov.i], xy[2 * hov.i + 1], r * 2.6, 0, 6.2832); g.strokeStyle = 'rgba(20,20,19,.7)'; g.lineWidth = 1.2 * d; g.stroke(); }
}

function preview(pn, i) {
 const R = pn.R, f = curFrame(R, P.tr.T), id = R.acc(i), c = f.s[id], camp = campOfAcc(R, f, id), [l, k] = J.sideCounts(R, c), q = J.pop(f.si[i]);
 return `<b>Account ${id}</b> · <span style="color:${J.CAMP[camp].c}">${J.CAMP[camp].name}</span><br><span class="m">Liberal on ${l}, conservative on ${k} of 14 partisan issues${q ? ` · quiet on ${q}` : ''}. Click for details.</span>`;
}

function inspector() {
 if (!sel) return; const pn = panes[sel.k]; if (!pn) return; const R = pn.R, f = curFrame(R, P.tr.T), i = sel.i, id = R.acc(i), key = `${mode}|${sel.k}|${i}|${f.tick}`;
 if (key === inspKey) return; inspKey = key;
 const c = f.s[id], camp = campOfAcc(R, f, id), [l, k] = J.sideCounts(R, c), sil = f.si[i];
 // the feed: every stored slot, with the posted statement and the like when the file has them
 const slots = []; for (let j = 0; j < R.fw; j++) { const a = f.fd[i * R.fw + j]; if (a !== EMPTY) slots.push({a, j}); }
 const full = R.fw >= (R.config.feed || 6), liked = j => f.li ? (f.li[i] >> j) & 1 : 0;
 const slotHTML = ({a, j}) => {
  const ca = campOfAcc(R, f, a), ag = 16 - J.pop(c ^ f.s[a]), p = f.po ? f.po[i * R.fw + j] : 255;
  const who = `<div class="who"><i class="dot" style="background:${J.CAMP[ca].c}"></i>Account ${a} · ${J.CAMP[ca].name.toLowerCase()}${R.idx(a) < 0 ? ' (not drawn)' : ''}<span class="k">agrees on ${ag} of 16</span></div>`;
  if (p === 255 || p >= 2 * R.M) return `<div class="post">${who}</div>`;
  const q = p >> 1, b = p & 1, same = ((c >> q) & 1) === b, sideC = J.CAMP[J.sideOf(R, q, b)].c;
  return `<div class="post">${who}<div class="what"><span style="color:${sideC}">●</span> ${J.esc(R.statements[p])}<span class="tag">${same ? 'agrees' : 'disagrees'}</span>${liked(j) ? '<span class="tag">liked</span>' : ''}</div></div>`;
 };
 const feedHTML = slots.length ? slots.map(slotHTML).join('') + `<div class="m" style="margin-top:8px">${full ? `All ${slots.length} posts its feed showed this day${R.hasPosts ? ', with what each author posted' : ''}.` : `The run file keeps ${R.fw} of the ${R.config.feed} posts each account saw per recorded day.`} Highlighted on the graph.</div>`
  : `<div class="m">No feed yet on day 0.</div>`;
 const adopt = f.ad && f.ad[i] !== 255 && f.ad[i] < R.M ? `<div class="m" style="margin-top:6px">This day it switched sides on <b style="color:var(--ink)">${J.esc(R.issues[f.ad[i]])}</b> after reading a post.</div>` : '';
 const quiet = R.ord.filter(q => (sil >> q) & 1);
 const silHTML = quiet.length ? `<div class="m">Still holds these positions but no longer posts them, because less than 30% of its feed agreed:</div><ul>${quiet.map(q => `<li style="--c:${J.CAMP[J.sideOf(R, q, (c >> q) & 1)].c}">${J.esc(R.issues[q])}</li>`).join('')}</ul>` : '<div class="m">Posts on every issue.</div>';
 const mi = J.histAt(R.hist, f.tick, 'minority'), xt = J.histAt(R.hist, f.tick, 'cross_ties'), net = mi < 0.02 ? 'everyone is in one camp, so no follow crosses camps.' : `<b style="color:var(--ink)">${J.pct(xt)}</b> of follows cross camps (a random network would be 50%).`;
 let folHTML;
 if (f.fo && f.fo.length >= R.D * R.k) {
  const cnt = {lib: 0, con: 0, mix: 0}; let cross = 0, tot = 0;
  for (let j = 0; j < R.k; j++) { const a = f.fo[i * R.k + j]; if (a === EMPTY || a >= R.n) continue; const ca = campOfAcc(R, f, a); cnt[ca]++; tot++; if (camp !== 'mix' && ca !== 'mix' && ca !== camp) cross++; }
  const w = x => (tot ? x / tot * 100 : 0) + '%';
  folHTML = `<div class="row"><i class="dot" style="background:var(--blue)"></i>Lean liberal<span class="k">${cnt.lib}</span></div><div class="row"><i class="dot" style="background:var(--red)"></i>Lean conservative<span class="k">${cnt.con}</span></div><div class="row"><i class="dot" style="background:var(--mixed)"></i>Mixed<span class="k">${cnt.mix}</span></div>
   <div class="bars"><i style="width:${w(cnt.lib)};background:var(--blue)"></i><i style="width:${w(cnt.mix)};background:var(--mixed)"></i><i style="width:${w(cnt.con)};background:var(--red)"></i></div>
   <div class="m">${camp === 'mix' ? `Follows ${tot} accounts.` : `${cross} of its ${tot} follows are on the other side.`} Network-wide at ${R.unit} ${f.tick}: ${net}</div>`;
 } else folHTML = `<div class="m">Follows ${R.k} accounts. This run file stores feeds, not each account's follow list, so a per-account split isn't available. Across the whole network at ${R.unit} ${f.tick}: ${net}</div>`;
 const other = panes[1 - sel.k]; let otherHTML = '';
 if (other && id < other.R.n) { const fo = curFrame(other.R, P.tr.T), co = fo.s[id], ca = campOfAcc(other.R, fo, id), drawn = other.R.idx(id) >= 0;
  otherHTML = `<div class="sec"><h4>Same account in the other feed</h4><div class="row">${J.chip(ca)}<span class="k">same opinion on ${16 - J.pop(c ^ co)} of 16</span></div><div class="m">Both societies start from the same ${J.int(R.n)} people and follows, so account ${id} is the same person in both. ${drawn ? 'Dashed ring on the other graph.' : 'It is not among the accounts drawn on the other graph.'}</div></div>`; }
 J.inspect(`<h3>Account ${id}</h3><div class="sub">${MODES[mode].names[sel.k]} · ${R.unit} ${f.tick}</div>
  <div class="row">${J.chip(camp)}<span class="k">liberal ${l} · conservative ${k} of 14</span></div>
  <div class="bars"><i style="width:${l / 16 * 100}%;background:var(--blue)"></i><i style="width:${(16 - l - k) / 16 * 100}%;background:var(--mixed)"></i><i style="width:${k / 16 * 100}%;background:var(--red)"></i></div>
  ${adopt}
  <div class="sec"><h4>What its feed showed this day</h4>${feedHTML}</div>
  <div class="sec"><h4>Stopped posting</h4>${silHTML}</div>
  <div class="sec"><h4>Who it follows${f.fo ? ', by camp' : ''}</h4>${folHTML}</div>
  ${otherHTML}
  <div class="sec"><h4>Its 16 opinions</h4>${J.positionsHTML(R, c, sil)}</div>`, () => { sel = null; P.dirty = true; });
}

P.render = () => {
 const T = P.tr.T; for (const pn of panes) drawPane(pn, T);
 CH.forEach((c, j) => {
  const get = c.get || (h => h[c.k]), series = panes.map(pn => ({H: pn.R.hist, get, color: J.SERIES[pn.k], at: (() => { const H = pn.R.hist; if (T > H[H.length - 1].tick) return null; const v = J.histAt(H, T, c.k); return c.get && J.histAt(H, T, 'minority') < 0.02 ? null : v; })()}));
  const yMax = c.y || Math.max(1, ...panes.flatMap(pn => pn.R.hist.map(h => h[c.k]))) * 1.05;
  J.chart(charts[j].cv, {series, T, maxT: P.tr.maxT, yMax, fmt: c.y ? c.f : v => v >= 1000 ? Math.round(v / 1000) + 'k' : Math.round(v) + '', ref: c.ref, unit: P.tr.unit});
  const html = series.map((s, k) => `<span style="color:${s.color}">${s.at == null ? (c.get ? 'one camp' : '–') : c.f(s.at)}</span>`).join('');
  if (charts[j].val._h !== html) { charts[j].val.innerHTML = html; charts[j].val._h = html; }
 });
 if (sel) inspector();
};

// Key numbers and the Details tables. All from runs/fair_summary.js (data/fair_results.json): 10,000 accounts, live Jev,
// day 300, means over seeds. The four fair conditions: as measured, lean removed, stubborn agents, both.
function stats() {
 const FS = window.FAIR_SUMMARY, A = J.SERIES[0], B = J.SERIES[1]; if (!FS || !FS.conds) return;
 const C = FS.conds, m = (t, r, k) => C[t][r][k].mean, four = ['base', 'sym', 'stub', 'stubsym'].filter(t => C[t]);
 const rng = (r, k) => { const v = four.map(t => m(t, r, k)); return [Math.min(...v), Math.max(...v)]; };
 const p1 = v => { const x = v * 100; return (Math.abs(x - Math.round(x)) < 0.05 || x < 99 ? Math.round(x) : x.toFixed(1)) + '%'; };
 const ag = rng('engagement', 'agree_exposure'), ac = rng('chrono', 'agree_exposure'), ratio = four.map(t => m(t, 'chrono', 'unfollows') / m(t, 'engagement', 'unfollows'));
 const rk = v => ({v, name: 'Ranked', dot: B, color: B}), ch = v => ({v, name: 'Chronological', dot: A, color: A});
 const cards = [
  {label: 'Posts people see that agree with them', vals: [rk(`${p1(ag[0])}–${p1(ag[1])}`), ch(`${p1(ac[0])}–${p1(ac[1])}`)], foot: 'Ranges over four settings: as measured, lean removed, stubborn agents, and both. The ranked feed hides disagreement every time.'},
  {label: 'Unfollows', vals: [{v: `${Math.floor(Math.min(...ratio))}–${Math.round(Math.max(...ratio))}×`, name: 'fewer under the ranked feed'}], foot: 'People rarely see the posts that would make them unfollow, so they keep following across camps.'},
  {label: 'How strongly opinions travel together as packages (0 to 1, US adults 0.17)', vals: [{v: `${J.f2(m('sym', 'chrono', 'mean_abs_r'))} vs ${J.f2(m('sym', 'engagement', 'mean_abs_r'))}`, name: 'Lean removed: random vs ranked'}, {v: `${J.f2(m('stub', 'engagement', 'mean_abs_r'))} vs ${J.f2(m('stub', 'chrono', 'mean_abs_r'))}`, name: 'Stubborn agents: ranked vs random'}], foot: 'Which feed polarizes opinions more flips with the assumptions, so there is no reliable answer.'},
  {label: 'Why the conservative side wins', vals: [{v: '60.5%', name: 'Jev picks the conservative side', color: 'var(--red)', dot: 'var(--red)'}, {v: `${J.pct(m('sym', 'chrono', 'liberal_share'))} / ${J.pct(m('sym', 'engagement', 'liberal_share'))}`, name: 'Liberal with the lean removed'}], foot: `As measured, ${J.pct(m('base', 'chrono', 'liberal_share'))} (random) and ${J.pct(m('base', 'engagement', 'liberal_share'))} (ranked) end liberal. With Jev's lean removed both feeds end 50/50.`},
 ];
 $('feed-stats').innerHTML = cards.map(J.statCard).join('');
 // Details: the fair-test table and the Meta-style experiment
 const rows = [['base', 'Jev as measured'], ['sym', 'Lean removed'], ['stub', 'Stubborn agents'], ['stubsym', 'Stubborn agents, lean removed'], ['tilt', '60% liberal start']].filter(([t]) => C[t] && C[t].chrono && C[t].engagement);
 const pair = (t, k, f) => `<span style="color:${A}">${f(C[t].chrono[k].mean)}</span> / <span style="color:${B}">${f(C[t].engagement[k].mean)}</span>`;
 let html = `<h4>The fair tests, day 300 (<span style="color:${A}">random</span> / <span style="color:${B}">ranked</span>)</h4><div class="tw"><table class="t"><tr><th></th><th>Leaning liberal</th><th>Package strength</th><th>Posts seen that agree</th><th>Follows across camps</th><th>Unfollows</th></tr>
  ${rows.map(([t, lab]) => `<tr><td>${lab} <span class="n">${C[t].chrono.minority.n} runs</span></td><td>${pair(t, 'liberal_share', J.pct)}</td><td>${pair(t, 'mean_abs_r', J.f2)}</td><td>${pair(t, 'agree_exposure', p1)}</td><td>${pair(t, 'cross_ties', J.pct)}</td><td>${pair(t, 'unfollows', v => v >= 1000 ? Math.round(v / 1000) + 'k' : J.int(v))}</td></tr>`).join('')}</table></div>
  <p class="m">Package strength: how strongly opinions travel together, from 0 (knowing one opinion tells you nothing about the others) to 1 (it tells you all of them). Means over random starts; 10,000 accounts, live Jev.</p>`;
 const S = window.NET_SUMMARY, mt = S && S.meta && S.meta.beta4, m32 = S && S.meta && S.meta.beta32;
 if (mt && m32) {
  const av = (M, arm, grp, k) => M.reduce((a, r) => a + r[arm].groups[grp][k], 0) / M.length, sg = v => (v < 0 ? '−' : '+') + Math.abs(v).toFixed(1);
  const row = (lab, arm, grp) => `<tr><td>${lab}</td><td>${J.pct(av(mt, arm, grp, 'agree_exposure'))}</td><td>${sg(av(mt, arm, grp, 'consistency_change') * 100)} pts</td><td>${sg(av(m32, arm, grp, 'consistency_change') * 100)} pts</td></tr>`;
  html += `<h4>Like Meta's 2023 feed experiments: 200 days on the ranked feed, then 100 more three ways</h4><div class="tw"><table class="t"><tr><th></th><th>Posts seen that agree</th><th>Move into own camp's package, soft judgments</th><th>Same, decisive judgments</th></tr>
   ${row('Stay on ranked', 'control', 'untreated')}${row('10% switched to the random feed', 'individual', 'treated')}${row('Everyone switched to the random feed', 'society', 'untreated')}</table></div>
   <p class="m">1,000 accounts, ${mt.length} random starts. Switching to the random feed cuts agreeing posts, as in the real studies, but whether opinions then move toward or away from their camp's package depends on how decisive the agents' judgments are.</p>`;
 }
 $('feed-tables').innerHTML = html;
}
})();
