// Shared helpers for the three-part viewer: loading, decoding, colours, issue positions, transport, charts,
// inspector card and hover tooltip. Everything works from file:// (run data arrives as <script> files).
(() => {
const J = window.J = {parts: {}};
const $ = J.$ = id => document.getElementById(id);
J.h = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const loaded = {};
J.load = src => loaded[src] || (loaded[src] = new Promise(ok => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = () => { console.warn('missing ' + src); ok(); }; document.head.appendChild(s); }));
// forget a loaded run file so its memory can be freed (the 10,000-account files are ~25 MB each)
J.unload = src => { delete loaded[src]; document.querySelectorAll(`script[src="${src}"]`).forEach(e => e.remove()); };
J.dec = (s, T) => { const b = atob(s), u = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return new T(u.buffer); };
J.dpr = () => Math.min(2, window.devicePixelRatio || 1);
J.pct = v => v == null || isNaN(v) ? '–' : Math.round(v * 100) + '%';
J.f2 = v => v == null || isNaN(v) ? '–' : (v < 0 ? '−' : '') + Math.abs(v).toFixed(2);
J.int = v => Math.round(v).toLocaleString('en-US');
J.esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
J.pop = x => { x -= (x >>> 1) & 0x55555555; x = (x & 0x33333333) + ((x >>> 2) & 0x33333333); return (((x + (x >>> 4)) & 0x0F0F0F0F) * 0x01010101) >>> 24; };

// frame / history lookup by tick
J.frameAt = (F, T) => { const last = F[F.length - 1].tick; T = Math.min(T, last); let i = 0; while (i < F.length - 2 && F[i + 1].tick <= T) i++;
 if (!F[i + 1]) return [i, 0]; const sp = F[i + 1].tick - F[i].tick || 1; return [i, Math.min(1, Math.max(0, (T - F[i].tick) / sp))]; };
J.histAt = (H, T, k) => { const last = H[H.length - 1].tick; T = Math.min(T, last); let i = 0; while (i < H.length - 2 && H[i + 1].tick <= T) i++;
 const j = Math.min(H.length - 1, i + 1), a = H[i][k], b = H[j][k]; if (a == null) return null; if (b == null) return a; const sp = (H[j].tick - H[i].tick) || 1, u = Math.min(1, Math.max(0, (T - H[i].tick) / sp)); return a + (b - a) * u; };
J.smooth = u => u * u * (3 - 2 * u);

// colours (score > 0 = conservative / traditional, < 0 = liberal / progressive)
// Palette for canvas work, matched to the CSS tokens in css/study.css (light paper). Mixed agents are a warm grey; camps saturate.
const BL = [63, 110, 166], RD = [181, 67, 47], MID = [168, 164, 152];
J.TOK = {ink: '#141413', ink2: '#3d3d3a', ink3: '#73726c', ink4: '#a19e95', paper: '#faf9f5', surface: '#ffffff', hairline: '#e8e6dc', rule: '#d8d4c8', accent: '#c96442', cross: [123, 94, 167], gridMid: [222, 218, 208]};
J.mix = (a, b, e) => [a[0] + (b[0] - a[0]) * e, a[1] + (b[1] - a[1]) * e, a[2] + (b[2] - a[2]) * e];
J.sideRGB = (x, mid = MID) => J.mix(mid, x < 0 ? BL : RD, Math.pow(Math.min(1, Math.abs(x)), 0.75));
J.rgb = c => `rgb(${c[0] | 0},${c[1] | 0},${c[2] | 0})`;
J.campOf = x => x > 0.15 ? 'con' : x < -0.15 ? 'lib' : 'mix';
J.CAMP = {lib: {name: 'Leans liberal', c: 'var(--blue)'}, con: {name: 'Leans conservative', c: 'var(--red)'}, mix: {name: 'Mixed', c: 'var(--mixed)'}};
// pane header: title line + subtitle line, fixed height so side-by-side panes align
J.paneHead = (color, title, sub) => `<div class="ph"><div class="pt"><i class="sw" style="background:${color}"></i><b>${title}</b></div><div class="ps">${sub}</div></div>`;
J.chip = (camp, names) => `<span class="chip" style="--c:${J.CAMP[camp].c}">${(names || {})[camp] || J.CAMP[camp].name}</span>`;

// 16-issue model shared by parts 1 and 2. Bit i of a position code = 0 means statement 2i, 1 means statement 2i+1.
J.prepIssues = R => {
 if (R._iss) return R; R._iss = 1; R.M = R.issues.length;
 R.sg = R.axis.map(v => Math.abs(v) < 0.1 || v >= 0 ? 1 : -1);
 R.ord = [...R.axis.keys()].sort((i, j) => Math.abs(R.axis[j]) - Math.abs(R.axis[i]));
 const tot = R.axis.reduce((s, v) => s + Math.abs(v), 0) / 2; R.score = new Float32Array(1 << R.M);
 for (let c = 0; c < 1 << R.M; c++) { let s = 0; for (let i = 0; i < R.M; i++) s += R.axis[i] * (((c >> i) & 1) ? -0.5 : 0.5); R.score[c] = -s / tot; }
 return R;
};
J.sideOf = (R, i, b) => Math.abs(R.axis[i]) < 0.1 ? 'mix' : ((b === 0) === (R.sg[i] > 0) ? 'lib' : 'con');
J.positionsHTML = (R, code, sil = 0) => {
 const g = {lib: [], con: [], mix: []};
 for (const i of R.ord) { const b = (code >> i) & 1, q = (sil >> i) & 1; g[J.sideOf(R, i, b)].push(`<li class="${q ? 'quiet' : ''}">${J.esc(R.statements[2 * i + b])}${q ? '<span class="tag">silent</span>' : ''}</li>`); }
 const H = {lib: 'Liberal side', con: 'Conservative side', mix: 'No party lean'}, C = {lib: 'var(--blue)', con: 'var(--red)', mix: 'var(--mixed)'};
 return ['lib', 'con', 'mix'].filter(k => g[k].length).map(k => `<div class="grp" style="--c:${C[k]}"><h5><i class="dot" style="background:${C[k]}"></i>${H[k]} · ${g[k].length}</h5><ul>${g[k].join('')}</ul></div>`).join('');
};
J.sideCounts = (R, code) => { let l = 0, c = 0; for (let i = 0; i < R.M; i++) { const s = J.sideOf(R, i, (code >> i) & 1); if (s === 'lib') l++; else if (s === 'con') c++; } return [l, c]; };

// inspector + tooltip
let owner = null;
J.inspect = (html, onClose) => { $('insp-body').innerHTML = html; owner = onClose || null; $('insp').classList.add('on'); };
J.closeInspector = (silent) => { $('insp').classList.remove('on'); const o = owner; owner = null; if (o && !silent) o(); };
const tip = () => $('tip');
J.tip = (e, html) => { const t = tip(); if (!html) { t.classList.remove('on'); return; } if (t._h !== html) { t.innerHTML = html; t._h = html; }
 const w = t.offsetWidth, hh = t.offsetHeight; let x = e.clientX + 14, y = e.clientY + 14; if (x + w > innerWidth - 8) x = e.clientX - w - 14; if (y + hh > innerHeight - 8) y = e.clientY - hh - 14;
 t.style.left = Math.max(8, x) + 'px'; t.style.top = Math.max(8, y) + 'px'; t.classList.add('on'); };

// transport: play/pause, speed, scrubber; synced for every panel of one part
const PLAY = '<svg viewBox="0 0 14 14"><path d="M3 1.5v11l9.5-5.5z" fill="currentColor"/></svg>', PAUSE = '<svg viewBox="0 0 14 14"><rect x="2.5" y="1.5" width="3.2" height="11" rx="1" fill="currentColor"/><rect x="8.3" y="1.5" width="3.2" height="11" rx="1" fill="currentColor"/></svg>';
J.Transport = class {
 constructor(host, rate, onchange) {
  this.T = 0; this.maxT = 1; this.playing = false; this.speed = 1; this.rate = rate; this.onchange = onchange; this.unit = 'round';
  host.innerHTML = `<button class="play" aria-label="Play">${PLAY}</button><div class="seg"><button data-s="0.5">0.5×</button><button data-s="1" class="on">1×</button><button data-s="2">2×</button><button data-s="4">4×</button></div><input type="range" min="0" max="1" step="0.01" value="0" aria-label="Time"><span class="t">0</span>`;
  this.btn = host.querySelector('.play'); this.rng = host.querySelector('input'); this.lab = host.querySelector('.t');
  this.btn.onclick = () => this.toggle();
  host.querySelector('.seg').onclick = e => { const s = e.target.dataset.s; if (!s) return; this.speed = +s; host.querySelectorAll('.seg button').forEach(b => b.classList.toggle('on', b === e.target)); };
  this.rng.oninput = () => { this.T = +this.rng.value; this.ui(); this.onchange(); };
 }
 toggle(on) { if (on === undefined) on = !this.playing; if (on && this.T >= this.maxT) this.T = 0; this.playing = on; this.btn.innerHTML = on ? PAUSE : PLAY; this.btn.setAttribute('aria-label', on ? 'Pause' : 'Play'); }
 setMax(m) { this.maxT = m; this.rng.max = m; if (this.T > m) this.T = m; this.ui(); }
 step(dt) { if (!this.playing) return false; this.T = Math.min(this.maxT, this.T + dt * this.speed * this.rate); if (this.T >= this.maxT) this.toggle(false); this.ui(); return true; }
 ui() { this.rng.value = this.T; this.lab.textContent = this.unit + ' ' + Math.round(this.T); }
};

// canvas sizing and line charts
J.size = (cv, w, h) => { const d = J.dpr(); cv.width = Math.round(w * d); cv.height = Math.round(h * d); cv.style.width = w + 'px'; cv.style.height = h + 'px'; cv._d = d; };
J.SERIES = ['#2f2f2c', '#c96442'];   // first society: ink; second society: clay
// o = {series:[{H, get(h)->v|null, color}], T, maxT, yMax, fmt, ref:{v,label}}
J.chart = (cv, o) => {
 const d = cv._d || 1, W = cv.width, H = cv.height, g = cv.getContext('2d'), K = J.TOK; g.clearRect(0, 0, W, H);
 const l = 34 * d, r = 8 * d, t = 8 * d, b = 18 * d, X = v => l + Math.min(1, v / o.maxT) * (W - l - r), Y = v => H - b - Math.min(1, Math.max(0, v / o.yMax)) * (H - t - b);
 g.font = `${10 * d}px ${getComputedStyle(document.body).fontFamily}`; g.textBaseline = 'middle';
 for (const v of [0, o.yMax / 2, o.yMax]) { g.strokeStyle = K.hairline; g.lineWidth = d; g.beginPath(); g.moveTo(l, Y(v)); g.lineTo(W - r, Y(v)); g.stroke(); g.fillStyle = K.ink3; g.textAlign = 'right'; g.fillText(o.fmt(v), l - 6 * d, Y(v)); }
 g.textAlign = 'left'; g.textBaseline = 'alphabetic'; g.fillText('0', l, H - 4 * d); g.textAlign = 'right'; g.fillText((o.unit || 'round') + ' ' + o.maxT, W - r, H - 4 * d);
 if (o.ref) { g.setLineDash([3 * d, 3 * d]); g.strokeStyle = K.ink4; g.beginPath(); g.moveTo(l, Y(o.ref.v)); g.lineTo(W - r, Y(o.ref.v)); g.stroke(); g.setLineDash([]); g.fillStyle = K.ink3; g.textAlign = 'right'; g.fillText(o.ref.label, W - r - 2 * d, Y(o.ref.v) - 4 * d); }
 for (const s of o.series) for (const pass of [0, 1]) {
  g.strokeStyle = s.color; g.globalAlpha = pass ? 1 : 0.18; g.lineWidth = (pass ? 1.8 : 1.2) * d; g.lineJoin = 'round'; g.beginPath(); let pen = false;
  for (const h of s.H) { if (pass && h.tick > o.T) break; const v = s.get(h); if (v == null) { pen = false; continue; } const x = X(h.tick), y = Y(v); pen ? g.lineTo(x, y) : g.moveTo(x, y); pen = true; }
  g.stroke();
 }
 g.globalAlpha = 1; const cx = X(Math.min(o.T, o.maxT)); g.strokeStyle = 'rgba(20,20,19,.28)'; g.lineWidth = d; g.beginPath(); g.moveTo(cx, t); g.lineTo(cx, H - b); g.stroke();
 for (const s of o.series) { const v = s.at; if (v == null || o.T > s.H[s.H.length - 1].tick) continue; g.fillStyle = s.color; g.beginPath(); g.arc(cx, Y(v), 3.2 * d, 0, 6.2832); g.fill(); g.strokeStyle = K.surface; g.lineWidth = 1.5 * d; g.stroke(); }
};
J.chartBox = (host, title) => { const el = J.h('div', 'chart', `<div class="ct">${title}</div><div class="cv2"></div><canvas></canvas>`); host.appendChild(el); return {el, cv: el.querySelector('canvas'), val: el.querySelector('.cv2')}; };
J.statCard = c => `<div class="stat${c.wide ? ' wide' : ''}"><div class="lab">${c.label}</div>${c.vals ? `<div class="vals">${c.vals.map(v => `<div class="v"><b style="color:${v.color || 'var(--ink)'}">${v.v}</b><span>${v.dot ? `<i class="dot" style="background:${v.dot}"></i>` : ''}${v.name}</span></div>`).join('')}</div>` : ''}${c.html || ''}${c.foot ? `<div class="foot">${c.foot}</div>` : ''}</div>`;
J.modeSeg = (host, modes, onpick) => { host.innerHTML = Object.entries(modes).map(([k, M]) => `<button data-m="${k}">${M.label}</button>`).join(''); host.onclick = e => { const m = e.target.closest('button'); if (m) onpick(m.dataset.m); }; };
J.markMode = (host, m) => host.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.m === m));

// navigation + main loop
J.show = async name => {
 if (!J.parts[name]) name = 'feed';
 document.querySelectorAll('#tabs button').forEach(b => b.classList.toggle('on', b.dataset.p === name));
 document.querySelectorAll('.part').forEach(s => s.classList.toggle('on', s.id === 'part-' + name));
 J.closeInspector(); J.tip(null, null);
 const prev = J.parts[J.active]; if (prev && prev.tr) prev.tr.toggle(false);
 J.active = name; if (location.hash.slice(1) !== name) history.replaceState(null, '', '#' + name);
 const P = J.parts[name]; if (!P.started) { P.started = true; await P.init(); } else P.resize();
 P.dirty = true;
};
J.start = () => {
 $('tabs').onclick = e => { const b = e.target.closest('button'); if (b) { J.show(b.dataset.p); scrollTo({top: 0}); } };
 // masthead contents and brand link: same navigation, scroll to the part's heading
 document.querySelectorAll('.contents a[data-p], .brand[data-p]').forEach(a => a.onclick = e => { e.preventDefault(); J.show(a.dataset.p).then(() => { const s = $('part-' + a.dataset.p); if (a.classList.contains('brand')) scrollTo({top: 0}); else if (s) scrollTo({top: s.getBoundingClientRect().top + scrollY - 56}); }); });
 $('insp-x').onclick = () => J.closeInspector();
 addEventListener('keydown', e => { if (e.key === 'Escape') J.closeInspector(); if (e.code === 'Space' && !/INPUT|BUTTON|SUMMARY/.test(e.target.tagName)) { e.preventDefault(); const P = J.parts[J.active]; if (P && P.tr) P.tr.toggle(); } });
 let rz; addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => { const P = J.parts[J.active]; if (P && P.ready) { P.resize(); P.dirty = true; } }, 120); });
 let last = performance.now();
 const loop = now => { const dt = Math.min(0.1, (now - last) / 1000); last = now; const P = J.parts[J.active];
  if (P && P.ready) { if (P.tr.step(dt)) P.dirty = true; if (P.dirty) { P.dirty = false; P.render(); } }
  requestAnimationFrame(loop); };
 J.show(location.hash.slice(1) || 'feed').then(() => { window.__ready = true; });
 requestAnimationFrame(loop);
};
})();
