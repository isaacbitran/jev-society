// Part 2: the party map. 16 independent issues on a grid; Jev's fit judgments sort them into survey-matching camps.
(() => {
const {$, h} = J;
const MODES = {
 jev: {label: 'Jev, stored answers', runs: ['bundle_jev_10000'], names: ['Jev, stored answers'],
  note: '10,000 agents. Every switch looks up 960 stored Jev answers about how well two statements fit together.'},
 live: {label: 'Live Jev', runs: ['bundle_live_1600_s0'], names: ['Live Jev'],
  note: '1,600 agents. Every switch is a fresh Jev question: which side of the issue fits the agent\'s other 15 opinions better.'},
 axelrod: {label: 'Compare: no meaning', runs: ['bundle_jev_10000', 'bundle_axelrod_10000'], names: ['Jev', 'No meaning'],
  note: 'Right: the same grid and copying rule with no judgments at all. Opinions never bundle the way the survey does.'},
 shuffled: {label: 'Compare: shuffled meaning', runs: ['bundle_jev_10000', 'bundle_shuffled_10000'], names: ['Jev', 'Same answers, wrong sentences'],
  note: 'Right: the same Jev answers attached to the wrong sentences. Opinions bundle, but not into the survey\'s pattern.'},
};
const B = window.BUNDLES = window.BUNDLES || {};
const P = J.parts.map = {dirty: true};
let mode = 'jev', panes = [], charts = [], sel = null, hov = null, inspKey = '';
// matrix: amber = positions go together, teal = go apart, paper = unrelated, hairline = never asked together
const POS = [201, 134, 43], NEG = [47, 140, 134], ZERO = [244, 242, 236];
const rRGB = r => r == null ? [232, 230, 220] : J.mix(ZERO, r > 0 ? POS : NEG, Math.pow(Math.min(1, Math.abs(r)), 0.6));

function prep(R, name) {
 if (R._p) return R; R._p = 1; R.name = name; R.n = R.side * R.side; R.maxTick = R.frames[R.frames.length - 1].tick;
 for (const f of R.frames) f.a = J.dec(f.S, Uint16Array);
 J.prepIssues(R); R.fc = {}; return R;
}
function colors(R, fi) {
 if (R.fc[fi]) return R.fc[fi]; const a = R.frames[fi].a, o = new Float32Array(R.n * 3);
 for (let i = 0; i < R.n; i++) { const c = J.sideRGB(R.score[a[i]], J.TOK.gridMid); o[i * 3] = c[0]; o[i * 3 + 1] = c[1]; o[i * 3 + 2] = c[2]; }
 return R.fc[fi] = o;
}
const corrAt = (R, T, i, j) => { const [fi, u] = J.frameAt(R.frames, T), A = R.frames[fi].R, Bm = R.frames[Math.min(fi + 1, R.frames.length - 1)].R; return (A[i][j] + (Bm[i][j] - A[i][j]) * u) * R.sg[i] * R.sg[j]; };

P.init = async () => {
 J.modeSeg($('map-modes'), MODES, m => setMode(m));
 P.tr = new J.Transport($('map-tr'), 25, () => { P.dirty = true; }); P.tr.unit = 'round';
 charts = [J.chartBox($('map-charts'), 'Match to the survey: how well this society\'s pairings line up with US adults\' (1 = perfect)'), J.chartBox($('map-charts'), 'How strongly opinions travel together as packages (0 to 1)')];
 stats();
 await setMode('jev'); P.ready = true;
};
async function setMode(m) {
 mode = m; sel = hov = null; J.closeInspector(true); J.markMode($('map-modes'), m); $('map-note').textContent = MODES[m].note;
 await Promise.all(MODES[m].runs.map(r => J.load(`runs/${r}.js`))); build(); P.dirty = true;
}
function build() {
 const M = MODES[mode], host = $('map-panes'); host.innerHTML = ''; panes = []; const single = M.runs.length === 1;
 M.runs.forEach((name, k) => {
  if (!B[name]) return; const R = prep(B[name], name);
  const el = h('div', 'pane' + (single ? ' split' : ''), J.paneHead(J.SERIES[k], M.names[k], `${J.int(R.n)} agents · ${R.side} × ${R.side} grid`) + `
   <div style="display:flex;flex-direction:column;gap:10px;min-width:0"><div class="cv px"><canvas class="map"></canvas></div></div>
   <div style="min-width:0"><div class="cv"><canvas class="mx"></canvas></div><div class="ps" style="margin-top:8px">Upper right: US adults (2024 survey) · lower left: this society</div></div>`);
  host.appendChild(el);
  const pn = {R, k, el, cv: el.querySelector('canvas.map'), mx: el.querySelector('canvas.mx'), off: document.createElement('canvas')};
  pn.off.width = pn.off.height = R.side; pn.img = pn.off.getContext('2d').createImageData(R.side, R.side);
  const cell = e => { const r = pn.cv.getBoundingClientRect(), row = Math.floor((e.clientY - r.top) / r.height * R.side), col = Math.floor((e.clientX - r.left) / r.width * R.side); return row >= 0 && col >= 0 && row < R.side && col < R.side ? row * R.side + col : -1; };
  pn.cv.onmousemove = e => { const i = cell(e); const nh = i >= 0 ? {k, kind: 'agent', i} : null; if (JSON.stringify(nh) !== JSON.stringify(hov)) P.dirty = true; hov = nh; J.tip(e, i >= 0 ? agentPreview(pn, i) : null); };
  const pair = e => { const r = pn.mx.getBoundingClientRect(), g = geom(pn), d = pn.mx._d, x = (e.clientX - r.left) * d, y = (e.clientY - r.top) * d, c = Math.floor((x - g.l) / g.c), w = Math.floor((y - g.l) / g.c);
   return c >= 0 && w >= 0 && c < R.M && w < R.M && c !== w ? {k, kind: 'pair', i: R.ord[w], j: R.ord[c]} : null; };
  pn.mx.onmousemove = e => { const p = pair(e); if (JSON.stringify(p) !== JSON.stringify(hov)) P.dirty = true; hov = p; J.tip(e, p ? pairHTML(pn, p, true) : null); };
  pn.cv.onmouseleave = pn.mx.onmouseleave = () => { hov = null; J.tip(null, null); P.dirty = true; };
  pn.cv.onclick = e => { const i = cell(e); J.tip(null, null); sel = i >= 0 ? {k, kind: 'agent', i} : null; if (!sel) J.closeInspector(true); inspKey = ''; P.dirty = true; };
  pn.mx.onclick = e => { const p = pair(e); J.tip(null, null); sel = p; if (!sel) J.closeInspector(true); inspKey = ''; P.dirty = true; };
  panes.push(pn);
 });
 P.tr.setMax(Math.min(...panes.map(p => p.R.maxTick)));
 $('map-key').innerHTML = panes.length > 1 ? M.names.map((nm, k) => `<span><i class="sw" style="background:${J.SERIES[k]}"></i>${nm}</span>`).join('') : '';
 P.resize();
}
P.resize = () => {
 const host = $('map-panes'), two = innerWidth > 760, W = host.clientWidth, col = Math.floor(two ? (W - 24) / 2 : W);
 const sz = Math.min(col, 620);
 for (const pn of panes) { J.size(pn.cv, sz, sz); J.size(pn.mx, sz, sz); }
 for (const c of charts) J.size(c.cv, Math.max(100, c.el.clientWidth), 130);
};
function geom(pn) { const W = pn.mx.width, l = Math.round(W * 0.27), c = (W - l - 4) / pn.R.M; return {l, c}; }
function drawMatrix(pn, T) {
 const R = pn.R, g = pn.mx.getContext('2d'), W = pn.mx.width, d = pn.mx._d, {l, c} = geom(pn), s = sel && sel.kind === 'pair' && sel.k === pn.k ? sel : hov && hov.kind === 'pair' && hov.k === pn.k ? hov : null;
 g.clearRect(0, 0, W, W);
 for (let w = 0; w < R.M; w++) for (let q = 0; q < R.M; q++) { if (w === q) continue; const i = R.ord[w], j = R.ord[q];
  const v = q > w ? (R.gss[i][j] == null ? null : R.gss[i][j] * R.sg[i] * R.sg[j]) : corrAt(R, T, i, j);
  g.fillStyle = J.rgb(rRGB(v)); g.fillRect(l + q * c + 0.5 * d, l + w * c + 0.5 * d, c - d, c - d); }
 g.strokeStyle = J.TOK.rule; g.lineWidth = d; g.beginPath(); g.moveTo(l, l); g.lineTo(l + R.M * c, l + R.M * c); g.stroke();
 if (s) { const w = R.ord.indexOf(s.i), q = R.ord.indexOf(s.j); g.strokeStyle = J.TOK.ink; g.lineWidth = 2 * d; for (const [a, b] of [[w, q], [q, w]]) g.strokeRect(l + b * c + d, l + a * c + d, c - 2 * d, c - 2 * d); }
 const fs = Math.max(8.5 * d, Math.min(12 * d, c * 0.6)); g.font = `${fs}px ${getComputedStyle(document.body).fontFamily}`; g.fillStyle = J.TOK.ink2; g.textAlign = 'right'; g.textBaseline = 'middle';
 for (let w = 0; w < R.M; w++) g.fillText(R.issues[R.ord[w]], l - 5 * d, l + (w + 0.5) * c);
 g.textAlign = 'left'; for (let q = 0; q < R.M; q++) { g.save(); g.translate(l + (q + 0.5) * c, l - 5 * d); g.rotate(-Math.PI / 2.6); g.fillText(R.issues[R.ord[q]], 0, 0); g.restore(); }
}
function drawPane(pn, T) {
 const R = pn.R, [fi, u0] = J.frameAt(R.frames, T), u = J.smooth(u0), A = colors(R, fi), Bc = colors(R, Math.min(fi + 1, R.frames.length - 1)), d = pn.img.data;
 const ag = R.frames[u0 < 0.5 ? fi : Math.min(fi + 1, R.frames.length - 1)].a, s = sel && sel.kind === 'agent' && sel.k === pn.k ? sel : null, hs = s ? ag[s.i] : -1;
 // on paper, "dim" fades a cell toward white instead of toward black
 for (let i = 0, j = 0; i < R.n; i++, j += 3) { const dim = hs >= 0 && ag[i] !== hs ? 0.22 : 1, o = i * 4, w = 255 * (1 - dim);
  d[o] = (A[j] + (Bc[j] - A[j]) * u) * dim + w; d[o + 1] = (A[j + 1] + (Bc[j + 1] - A[j + 1]) * u) * dim + w; d[o + 2] = (A[j + 2] + (Bc[j + 2] - A[j + 2]) * u) * dim + w; d[o + 3] = 255; }
 pn.off.getContext('2d').putImageData(pn.img, 0, 0);
 const g = pn.cv.getContext('2d'), W = pn.cv.width, cs = W / R.side; g.imageSmoothingEnabled = false; g.drawImage(pn.off, 0, 0, W, W);
 const mark = (i, col, lw) => { g.strokeStyle = col; g.lineWidth = lw; g.strokeRect(Math.floor(i % R.side) * cs - lw / 2, Math.floor(i / R.side) * cs - lw / 2, cs + lw, cs + lw); };
 if (s) mark(s.i, J.TOK.ink, Math.max(2, cs * 0.25));
 if (hov && hov.kind === 'agent' && hov.k === pn.k && (!s || hov.i !== s.i)) mark(hov.i, 'rgba(20,20,19,.7)', Math.max(1.5, cs * 0.18));
 drawMatrix(pn, T);
}
const frameCodes = (R, T) => { const [fi, u] = J.frameAt(R.frames, T); return R.frames[u < 0.5 ? fi : Math.min(fi + 1, R.frames.length - 1)]; };
function agentPreview(pn, i) { const R = pn.R, f = frameCodes(R, P.tr.T), c = f.a[i], camp = J.campOf(R.score[c]), [l, k] = J.sideCounts(R, c);
 return `<b>Agent at row ${Math.floor(i / R.side) + 1}, column ${i % R.side + 1}</b><br><span style="color:${J.CAMP[camp].c}">${J.CAMP[camp].name}</span> <span class="m">· liberal on ${l}, conservative on ${k} of 14. Click for all 16.</span>`; }
function pairHTML(pn, p, short) {
 const R = pn.R, T = P.tr.T, {i, j} = p, soc = corrAt(R, T, i, j), gs = R.gss[i][j] == null ? null : R.gss[i][j] * R.sg[i] * R.sg[j], dj = R.direct[i][j] * R.sg[i] * R.sg[j];
 const A = q => R.statements[2 * q + (R.sg[q] > 0 ? 0 : 1)], f = v => v == null ? 'never asked together' : J.f2(v);
 if (short) return `<b>${R.issues[i]} × ${R.issues[j]}</b><br><span class="m">This society: </span>${f(soc)} <span class="m">· US adults: </span>${f(gs)}<br><span class="m">Click for details.</span>`;
 return `<h3>${J.esc(R.issues[i])} × ${J.esc(R.issues[j])}</h3><div class="sub">${MODES[mode].names[p.k]} · round ${Math.round(T)}</div>
  <div class="sec"><h4>The two opinions</h4><ul><li style="--c:var(--blue)">${J.esc(A(i))}</li><li style="--c:var(--blue)">${J.esc(A(j))}</li></ul></div>
  <div class="sec"><h4>How strongly holders of one hold the other</h4>
   <div class="row">This society<span class="k">${f(soc)}</span></div><div class="row">US adults, GSS 2024<span class="k">${f(gs)}</span></div><div class="row">Jev's direct pairwise judgment<span class="k">${f(dj)}</span></div>
   <div class="m" style="margin-top:6px">Correlation from −1 (never together) to +1 (always together). The survey is used only for this comparison; agents never see it.</div></div>`;
}
function inspector() {
 if (!sel) return; const pn = panes[sel.k]; if (!pn) return; const R = pn.R, f = frameCodes(R, P.tr.T);
 const key = sel.kind === 'agent' ? `${mode}|a|${sel.k}|${sel.i}|${f.tick}` : `${mode}|p|${sel.k}|${sel.i}|${sel.j}|${Math.round(P.tr.T)}`; if (key === inspKey) return; inspKey = key;
 const close = () => { sel = null; P.dirty = true; };
 if (sel.kind === 'pair') { J.inspect(pairHTML(pn, sel, false), close); return; }
 const c = f.a[sel.i], camp = J.campOf(R.score[c]), [l, k] = J.sideCounts(R, c); let same = 0; for (let q = 0; q < R.n; q++) if (f.a[q] === c) same++;
 J.inspect(`<h3>Agent at row ${Math.floor(sel.i / R.side) + 1}, column ${sel.i % R.side + 1}</h3><div class="sub">${MODES[mode].names[sel.k]} · round ${f.tick}</div>
  <div class="row">${J.chip(camp)}<span class="k">liberal ${l} · conservative ${k} of 14</span></div>
  <div class="bars"><i style="width:${l / 16 * 100}%;background:var(--blue)"></i><i style="width:${(16 - l - k) / 16 * 100}%;background:var(--mixed)"></i><i style="width:${k / 16 * 100}%;background:var(--red)"></i></div>
  <div class="m">${J.int(same)} of ${J.int(R.n)} agents (${(same / R.n * 100).toFixed(1)}%) hold exactly these 16 opinions; they stay in full colour on the map.</div>
  <div class="sec"><h4>Its 16 opinions</h4>${J.positionsHTML(R, c, 0)}</div>`, close);
}
P.render = () => {
 const T = P.tr.T; for (const pn of panes) drawPane(pn, T);
 [['r_gss', v => J.f2(v), null, 1], ['mean_abs_r', v => J.f2(v), {v: (window.BUNDLE_SUMMARY || {}).gss_mean_abs_r || 0.167, label: 'US adults 0.17'}, 1]].forEach(([k, fmt, ref, yMax], j) => {
  const series = panes.map(pn => ({H: pn.R.hist, get: h => h[k], color: J.SERIES[pn.k], at: J.histAt(pn.R.hist, T, k)}));
  J.chart(charts[j].cv, {series, T, maxT: P.tr.maxT, yMax, fmt: v => v.toFixed(1), ref, unit: 'round'});
  const html = series.map(s => `<span style="color:${s.color}">${fmt(s.at)}</span>`).join(''); if (charts[j].val._h !== html) { charts[j].val.innerHTML = html; charts[j].val._h = html; }
 });
 if (sel) inspector();
};
function stats() {
 const S = window.BUNDLE_SUMMARY; if (!S) return; const s = S.summary, r = k => J.f2(s[k].matched_r_gss.mean);
 $('map-stats').innerHTML = [
  {label: 'Match to the 2024 survey (1 = perfect)', vals: [{v: r('jev_10000'), name: `Stored answers, 10,000 agents`}, {v: r('live_1600'), name: `Live Jev, 1,600 agents`}], foot: 'Measured when this society\'s opinions travel together as strongly as US adults\' do. Agents never see the survey.'},
  {label: 'Without meaning, the pattern disappears', vals: [{v: r('axelrod_1600'), name: 'No meaning'}, {v: r('shuffled_1600'), name: 'Shuffled meaning'}], foot: 'Copying neighbours alone does not produce the survey\'s pattern.'},
  {label: 'Jev\'s pairwise answers alone, no society', vals: [{v: J.f2(S.direct.fit.r_gss), name: 'Match to the survey'}], foot: 'The pattern is already in Jev. The society reproduces and strengthens it; it does not discover it.'},
 ].map(J.statCard).join('');
}
})();
