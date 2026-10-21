// Client-side layout of the feed part's network, replacing the recorded positions. ForceAtlas2-style forces:
// repulsion k/d between every pair (Barnes-Hut), linear attraction along exposure edges (who saw whose post, decaying
// over frames), weak linear gravity. With no or random edges this settles to an evenly filled disc (2-D Coulomb
// repulsion under harmonic confinement is uniform), and camps pull apart into lobes as the feed sorts them. Frame 0
// starts from a jittered phyllotaxis disc indexed by drawn order, so the same account starts at the same point in
// both panes. Runs in a Web Worker (built from a blob so file:// works); frames arrive as they are computed.
(() => {
const J = window.J;

// Barnes-Hut quadtree over n points, array-based, rebuilt each iteration.
class Tree {
 constructor(cap) { this.ch = new Int32Array(cap * 4); this.mx = new Float32Array(cap); this.my = new Float32Array(cap); this.m = new Float32Array(cap); this.pt = new Int32Array(cap); this.cx = new Float32Array(cap); this.cy = new Float32Array(cap); this.hw = new Float32Array(cap); this.cap = cap; this.stack = new Int32Array(8192); }
 build(x, y, n) {
  let lo = Infinity, hi = -Infinity; for (let i = 0; i < n; i++) { const a = Math.min(x[i], y[i]), b = Math.max(x[i], y[i]); if (a < lo) lo = a; if (b > hi) hi = b; }
  const c = (lo + hi) / 2, h = (hi - lo) / 2 + 1e-6; this.k = 0; this.node(c, c, h);
  for (let i = 0; i < n; i++) this.insert(0, i, x, y);
  for (let q = this.k - 1; q >= 0; q--) { if (this.pt[q] >= 0) continue; let m = 0, sx = 0, sy = 0; for (let j = 0; j < 4; j++) { const r = this.ch[q * 4 + j]; if (r >= 0) { m += this.m[r]; sx += this.mx[r] * this.m[r]; sy += this.my[r] * this.m[r]; } } this.m[q] = m; this.mx[q] = m ? sx / m : this.cx[q]; this.my[q] = m ? sy / m : this.cy[q]; }
 }
 node(cx, cy, hw) { const q = this.k++; if (q >= this.cap) throw new Error('quadtree full'); this.cx[q] = cx; this.cy[q] = cy; this.hw[q] = hw; this.pt[q] = -1; this.m[q] = 0; this.ch[q * 4] = this.ch[q * 4 + 1] = this.ch[q * 4 + 2] = this.ch[q * 4 + 3] = -1; return q; }
 insert(q, i, x, y) {
  let depth = 0;
  for (;;) {
   if (this.m[q] === 0 && this.pt[q] < 0 && this.ch[q * 4] < 0 && this.ch[q * 4 + 1] < 0 && this.ch[q * 4 + 2] < 0 && this.ch[q * 4 + 3] < 0) { this.pt[q] = i; this.m[q] = 1; this.mx[q] = x[i]; this.my[q] = y[i]; return; }
   if (this.pt[q] >= 0) {
    const j = this.pt[q]; if (depth > 24 || (x[j] === x[i] && y[j] === y[i])) { this.m[q]++; this.mx[q] = (this.mx[q] * (this.m[q] - 1) + x[i]) / this.m[q]; this.my[q] = (this.my[q] * (this.m[q] - 1) + y[i]) / this.m[q]; return; }
    this.pt[q] = -1; this.m[q] = 0; this.place(q, j, x, y);
   }
   const s = this.quad(q, x[i], y[i]); let r = this.ch[q * 4 + s];
   if (r < 0) { const h = this.hw[q] / 2; r = this.node(this.cx[q] + (s & 1 ? h : -h), this.cy[q] + (s & 2 ? h : -h), h); this.ch[q * 4 + s] = r; }
   q = r; depth++;
  }
 }
 place(q, j, x, y) { const s = this.quad(q, x[j], y[j]); const h = this.hw[q] / 2; const r = this.node(this.cx[q] + (s & 1 ? h : -h), this.cy[q] + (s & 2 ? h : -h), h); this.ch[q * 4 + s] = r; this.pt[r] = j; this.m[r] = 1; this.mx[r] = x[j]; this.my[r] = y[j]; }
 quad(q, px, py) { return (px >= this.cx[q] ? 1 : 0) | (py >= this.cy[q] ? 2 : 0); }
 force(i, x, y, k, theta, out) {
  const px = x[i], py = y[i]; let fx = 0, fy = 0; const st = this.stack; let sp = 0; st[sp++] = 0;
  while (sp) { const q = st[--sp]; const m = this.m[q]; if (m === 0) continue;
   const dx = px - this.mx[q], dy = py - this.my[q], d2 = dx * dx + dy * dy;
   if (this.pt[q] >= 0 || this.hw[q] * this.hw[q] * 4 < theta * theta * d2) { if (this.pt[q] === i && m === 1) continue; const f = k * (this.pt[q] === i ? m - 1 : m) / (d2 + 1e-4); fx += dx * f; fy += dy * f; }
   else for (let j = 0; j < 4; j++) { const r = this.ch[q * 4 + j]; if (r >= 0) st[sp++] = r; }
  }
  out[0] = fx; out[1] = fy;
 }
}

// The layout proper. feeds: array of Uint16Array (D*fw feed authors per frame, 65535 empty); idx: Int32Array account id -> drawn index.
// emit(fi, Int16Array positions ±32000) is called once per frame in order.
function core(D, fw, feeds, idx, emit, inc) {
 inc = inc || 1;
 const x = new Float32Array(D), y = new Float32Array(D), vx = new Float32Array(D), vy = new Float32Array(D);
 let seed = 12345; const rnd = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
 for (let d = 0; d < D; d++) { const r = Math.sqrt((d + 0.5) / D) * (1 + (rnd() - 0.5) * 0.06), t = d * 2.399963 + (rnd() - 0.5) * 0.5; x[d] = r * Math.cos(t); y[d] = r * Math.sin(t); }
 const tree = new Tree(D * 8), out = [0, 0], kr = 1 / D, kg = 2.0, decay = 0.85, wmin = 0.08, ka = 0.9;
 const W = new Map();
 let src = new Int32Array(0), dst = new Int32Array(0), wt = new Float32Array(0), scale = 1;
 for (let fi = 0; fi < feeds.length; fi++) {
  for (const [k, w] of W) { const nw = w * decay; if (nw < wmin) W.delete(k); else W.set(k, nw); }
  const fd = feeds[fi]; for (let v = 0; v < D; v++) for (let j = 0; j < fw; j++) { const id = fd[v * fw + j]; if (id === 65535) continue; const a = idx[id]; if (a < 0 || a === v) continue; const key = v < a ? v * D + a : a * D + v; W.set(key, (W.get(key) || 0) + inc); }
  if (src.length !== W.size) { src = new Int32Array(W.size); dst = new Int32Array(W.size); wt = new Float32Array(W.size); }
  let e = 0; for (const [k, w] of W) { src[e] = (k / D) | 0; dst[e] = k % D; wt[e] = w; e++; }
  const iters = fi === 0 ? 70 : 20, E = src.length;
  for (let it = 0; it < iters; it++) {
   tree.build(x, y, D);
   const temp = fi === 0 ? 0.06 * (1 - it / iters) + 0.005 : 0.03 * (1 - it / iters) + 0.004;
   for (let i = 0; i < D; i++) { tree.force(i, x, y, kr, 1.0, out); vx[i] = out[0] - kg * x[i]; vy[i] = out[1] - kg * y[i]; }
   for (let q = 0; q < E; q++) { const a = src[q], b = dst[q], dx = x[b] - x[a], dy = y[b] - y[a], f = ka * wt[q]; vx[a] += dx * f; vy[a] += dy * f; vx[b] -= dx * f; vy[b] -= dy * f; }
   for (let i = 0; i < D; i++) { let dx = vx[i] * temp, dy = vy[i] * temp; const l = Math.sqrt(dx * dx + dy * dy); if (l > temp * 3) { dx *= temp * 3 / l; dy *= temp * 3 / l; } x[i] += dx; y[i] += dy; }
  }
  let mx = 0, my = 0; for (let i = 0; i < D; i++) { mx += x[i]; my += y[i]; } mx /= D; my /= D;
  const rs = new Float32Array(D); for (let i = 0; i < D; i++) rs[i] = Math.hypot(x[i] - mx, y[i] - my); rs.sort(); const r95 = rs[Math.floor(D * 0.95)] || 1;
  const want = 0.92 / r95; scale = fi === 0 ? want : scale + (want - scale) * 0.35;
  const p = new Int16Array(D * 2); for (let i = 0; i < D; i++) { p[2 * i] = Math.max(-32000, Math.min(32000, (x[i] - mx) * scale * 32000)); p[2 * i + 1] = Math.max(-32000, Math.min(32000, (y[i] - my) * scale * 32000)); }
  emit(fi, p);
 }
}

const WORKER_SRC = Tree.toString() + '\n' + core.toString() + '\nself.onmessage = e => { const {D, fw, feeds, idx, inc} = e.data; core(D, fw, feeds, idx, (fi, p) => self.postMessage({fi, p}, [p.buffer]), inc); self.postMessage({done: true}); };';
let workerURL = null;

// R: prepared run (R.D drawn nodes, R.frames with fd and optionally fo, R.fw, R.idx). kind = 'reads' (exposure
// edges: who saw whose posts) or 'follows' (follow edges, when the run file stores follow lists). Results go to
// R.lay[kind] = {pos: [Int16Array per frame], done: index of the last laid-out frame (-1 until the first)}.
// Follow edges are stable, so each frame adds a smaller weight (0.3) to keep the pull comparable to the reads layout.
J.layoutRun = (R, kind, onFrame) => {
 R.lay = R.lay || {}; if (R.lay[kind]) return; const L = R.lay[kind] = {pos: new Array(R.frames.length), done: -1};
 const D = R.D, idx = new Int32Array(R.n); for (let i = 0; i < R.n; i++) idx[i] = R.idx(i);
 const fol = kind === 'follows', feeds = R.frames.map(f => fol ? f.fo : f.fd), fw = fol ? R.k : R.fw, inc = fol ? 0.3 : 1;
 const take = (fi, p) => { L.pos[fi] = p; L.done = fi; if (onFrame) onFrame(fi); };
 try {
  if (!workerURL) workerURL = URL.createObjectURL(new Blob([WORKER_SRC], {type: 'text/javascript'}));
  const w = new Worker(workerURL);
  w.onmessage = e => { if (e.data.done) { w.terminate(); return; } take(e.data.fi, e.data.p); };
  w.onerror = err => { console.warn('layout worker failed, computing inline', err.message || err); w.terminate(); core(D, fw, feeds, idx, take, inc); };
  L.worker = w; w.postMessage({D, fw, feeds, idx, inc});
 } catch (err) { console.warn('no worker, computing inline', err.message || err); core(D, fw, feeds, idx, take, inc); }
};
})();
