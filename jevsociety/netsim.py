"""Social-network version of the bundling model. python -m jevsociety.netsim --ranker engagement --seed 0

Same 16 issues and the same Jev belief-fit rule as jevsociety.bundling; the grid is replaced by a follow network and a
feed. Every tick (synchronous update):
  1. Post. Every agent posts one of its 16 positions, chosen uniformly among the issues it is not silent on (step 7).
  2. Feed. A viewer's candidates are this tick's posts from the accounts it follows (20). The feed shows `feed` (6) of
     them, picked by the viewer's ranker:
       chrono      no ranking: a uniformly random 6 of the 20 (all posts in a tick are equally recent).
       engagement  the 6 with the highest predicted like probability for this viewer (below).
       bridging    the 6 whose statement is best liked by BOTH sides of the network's own main division: score = the
                   lower of the two sides' mean like probability (sides = sign on the first principal component of
                   current positions; no survey label). In the spirit of bridging-based ranking (Ovadya and Thorburn 2023).
       outrage     engagement that also counts angry replies: P(like) + 0.5 * P(clash) for posts the viewer disagrees with.
  3. Like. P(like) = P(fit): the probability that the post's statement fits the viewer's other 15 beliefs better than
     its opposite. Pairwise-table mode: 1 / (1 + exp(-beta * (fit(x) - fit(not x)))), fit = mean Jev pairwise judgment,
     exactly the switch rule of jevsociety.bundling. Live mode: Jev is asked that question directly (shuffled options).
  4. Adopt. The viewer picks one shown post it disagrees with, interacts with probability = share of the 16 issues it
     shares with the author (Axelrod homophily, as on the grid), and switches to the post's side with P(fit).
  5. Unfollow. A shown post the viewer disagrees with and does not like is a clash. With probability `unfollow` (0.05)
     the viewer unfollows the author of one random clash and follows someone new: with probability `recommend` (0.8) the
     author of a post one of its followees liked this tick ("liked by people you follow"), otherwise a random account.
     Out-degree stays at 20.
  6. Drift. With probability `noise` (0.002) an agent flips one random issue (as on the grid).
  7. Spiral of silence. Each agent keeps, per issue, a running estimate of the share of feed posts on that issue that
     agree with it (exponential average, weight 0.2 per tick in which it sees such posts). Below `silence` (0.3: it
     perceives 70% or more of its feed against it) it stops posting that position. It still holds it and can still change it.

Controls (same code path): no meaning (beta 0: every P(fit) is 0.5), shuffled meaning (Jev matrix relabelled by a random
permutation), no unfollow, no silence. A per-agent ranker schedule allows a Meta-style field experiment (experiment()).
The survey (data/gss2024_corr.json) is read only by measurement and colouring.

Naming: the README and the study page call the `chrono` ranker the random feed (every post in a tick is equally new, so
newest-first reduces to a random 6) and the `engagement` ranker the ranked feed (ranked by predicted likes). One tick = one
day. Identifiers and CLI flags keep the old names for compatibility with recorded runs."""
import argparse, base64, json, os, time
import numpy as np
from .issues import M, NAMES, SHORT, STATEMENTS
from .pairs import load
from .bundling import corr, measure, capture, gss, gss_axis, direct, live_probs, live_path, BudgetStop, HERE
from . import jev

RANKERS = ["chrono", "engagement", "bridging", "outrage"]
POW = 1 << np.arange(M)

def network(n, k, kind, rng):
    """Out-neighbour table F (n x k), no self-follows, no duplicates. random: uniform; smallworld: directed ring lattice
    (k nearest on a ring) with 10% of follows rewired at random (Watts and Strogatz 1998)."""
    F = np.empty((n, k), np.int64)
    for v in range(n):
        if kind == "smallworld":
            off = np.r_[np.arange(1, k // 2 + 1), -np.arange(1, k - k // 2 + 1)]; row = (v + off) % n
            for j in range(k):
                if rng.random() < 0.1:
                    while True:
                        c = rng.integers(n)
                        if c != v and c not in row: row[j] = c; break
        else:
            row = rng.choice(n - 1, k, replace=False); row[row >= v] += 1
        F[v] = row
    return F

def camps(S):
    """The society's own two sides, with no survey label: start from the sign on the first principal component of current
    positions, then 3 rounds of 2-means on Hamming distance to each side's majority package. If the two packages differ on
    fewer than 4 of the 16 issues there is only one side (camp all 0). Returns (camp, issues the packages differ on, PC1 share)."""
    with np.errstate(all="ignore"):
        X = 1.0 - S; Xc = X - X.mean(0); C = Xc.T @ Xc / len(X); w, V = np.linalg.eigh(C)
        camp = (Xc @ V[:, -1] > 0).astype(np.int8); pc = float(w[-1] / max(w.sum(), 1e-12))
    for _ in range(3):
        if camp.all() or not camp.any(): break
        P0 = S[camp == 0].mean(0) > 0.5; P1 = S[camp == 1].mean(0) > 0.5
        camp = ((S != P1).sum(1) < (S != P0).sum(1)).astype(np.int8)
    if camp.all() or not camp.any(): return np.zeros(len(S), np.int8), 0, pc
    nd = int(((S[camp == 0].mean(0) > 0.5) != (S[camp == 1].mean(0) > 0.5)).sum())
    if nd < 4: return np.zeros(len(S), np.int8), nd, pc
    if camp.mean() > 0.5: camp = 1 - camp                                     # camp 1 = the smaller side
    return camp, nd, pc

def consistency(S, camp):
    """Per agent: share of the 16 issues on which it holds its own camp's majority side (1.0 = the full package)."""
    out = np.zeros(len(S))
    for c in (0, 1):
        m = camp == c
        if m.any(): maj = (S[m].mean(0) > 0.5).astype(np.int8); out[m] = (S[m] == maj).mean(1)
    return out

def modularity(F, camp):
    """Newman modularity of the directed follow graph for the 2-group partition `camp`."""
    n, k = F.shape; m = n * k; same = (camp[:, None] == camp[F]).mean()
    kin = np.bincount(F.ravel(), minlength=n); exp = sum((k * (camp == c).sum()) * kin[camp == c].sum() for c in (0, 1)) / m ** 2
    return float(same - exp)

def fair_measures(S, camp, cons, S0, axis):
    """Polarization and consensus measures that do not depend on correlations (which fall toward 0 under consensus).
    pkg_dist: mean over issues of |share on side B in camp 0 - in camp 1| (0 = same views, 1 = opposite packages; 0 with one camp).
    full_pkg / pkg14: share of accounts holding their camp's whole package / at least 14 of its 16 positions.
    consensus: mean over issues of the share on the majority side (0.5 = even split, 1 = everyone agrees).
    bimodality: Sarle's bimodality coefficient of the accounts' scores on the first principal component (above 0.555 suggests two
    peaks). kept: share of positions equal to tick 0. init_*: does the final camp follow from tick-0 positions? Each account is
    assigned to the final camp whose package is nearer its tick-0 positions; agreement with its actual final camp, the agreement
    expected by chance from the camp sizes alone, and Cohen's kappa. cons_side: share on the survey's conservative side, all issues."""
    n = len(S); out = {}
    one = camp.all() or not camp.any()
    out["pkg_dist"] = 0.0 if one else float(np.abs(S[camp == 0].mean(0) - S[camp == 1].mean(0)).mean())
    out["full_pkg"] = float((cons == 1).mean()); out["pkg14"] = float((cons >= 14 / 16 - 1e-9).mean())
    sh = S.mean(0); out["consensus"] = float(np.maximum(sh, 1 - sh).mean())
    X = S - sh; w, V = np.linalg.eigh(X.T @ X / n); z = X @ V[:, -1]; z = z - z.mean(); sd = z.std()
    if sd > 0:
        g = (z ** 3).mean() / sd ** 3; k = (z ** 4).mean() / sd ** 4 - 3
        out["bimodality"] = float((g * g + 1) / (k + 3 * (n - 1) ** 2 / ((n - 2) * (n - 3))))
    else: out["bimodality"] = None
    out["kept"] = float((S == S0).mean())
    out["cons_side"] = float((S == (axis > 0)).mean())                     # side B (1) is conservative where axis > 0
    if one: out["init_agree"] = out["init_chance"] = out["init_kappa"] = None
    else:
        P0 = S[camp == 0].mean(0) > 0.5; P1 = S[camp == 1].mean(0) > 0.5
        pred = ((S0 != P1).sum(1) < (S0 != P0).sum(1)).astype(np.int8)
        a = float((pred == camp).mean()); c = float(camp.mean() * pred.mean() + (1 - camp.mean()) * (1 - pred.mean()))
        out["init_agree"] = a; out["init_chance"] = c; out["init_kappa"] = (a - c) / (1 - c) if c < 1 else None
    return out

_PAIRS = {}
def rng_pairs(n):
    if n not in _PAIRS: r = np.random.default_rng(12345); _PAIRS[n] = (r.integers(0, n, 20000), r.integers(0, n, 20000))
    return _PAIRS[n]

class Sim:
    def __init__(self, n=1000, k=20, feed=6, beta=4.0, noise=0.002, unfollow=0.05, recommend=0.8, silence=0.3,
                 net="random", control="none", variant="fit", seed=0, live=False, budget=None, ranker="chrono",
                 stubborn=0.0, sym=False, init_liberal=None):
        """Fair-test options (jevsociety/fair.py). stubborn: each tick, with this probability, an agent that has moved off
        any of its tick-0 positions moves one of them (chosen at random) back (Friedkin and Johnsen 1990 style anchoring).
        sym: live mode only; P_sym(x | S) = (P(x | S) + P(not x | not S)) / 2, where not S flips the other 15 positions;
        this makes the judge treat a position set and its mirror image identically, removing any lean to one side.
        init_liberal: if set, each tick-0 position is on the survey's liberal side with this probability (default: fair coin)."""
        self.rng = rng = np.random.default_rng(seed); self.n, self.k, self.fd = n, k, feed
        self.beta = 0.0 if control == "axelrod" else beta; self.noise, self.unf, self.rec, self.sil_t = noise, unfollow, recommend, silence
        K = np.array(load(variant))
        if control == "shuffled":
            p = rng.permutation(2 * M); K = K[np.ix_(p, p)]
            for i in range(M): K[2*i, 2*i+1] = K[2*i+1, 2*i] = 0.0
        self.K = K; self.live = live; self.budget = budget; self.tok0 = jev.STATS["tokens"]
        if init_liberal is None: self.S = rng.integers(0, 2, (n, M)).astype(np.int8)
        else: lib = rng.random((n, M)) < init_liberal; self.S = np.where(gss_axis() > 0, ~lib, lib).astype(np.int8)  # side A (0) is liberal where axis > 0
        self.F = network(n, k, net, rng)
        self.S0 = self.S.copy(); self.stub = stubborn; self.sym = sym
        self.A = np.full((n, M), 0.5); self.t = 0; self.ar = np.arange(n)
        self.rank = np.full(n, RANKERS.index(ranker)); self.cache = {}
        if live and os.path.exists(live_path()): self.cache = {int(a): b for a, b in json.load(open(live_path())).items()}
        self.tab = np.full(1 << 20, np.nan)                                 # dense copy of the cache, indexed by key
        if self.cache: kk = np.fromiter(self.cache.keys(), np.int64); self.tab[kk] = np.fromiter(self.cache.values(), float)
        self.unfollows = 0; self.last = {}; self._saved = len(self.cache)

    # P(fit) of statement x for viewer v, for an (n x c) array of statements, one row per viewer
    def pfit(self, X, mask=None):
        """mask (live mode only): ask Jev only for these cells; the rest are left at 0.5 and never used."""
        idx = 2 * np.arange(M) + self.S                                     # n x M statements held
        if not self.live:
            K = self.K; d = K[X[:, :, None], idx[:, None, :]].sum(-1) - K[(X ^ 1)[:, :, None], idx[:, None, :]].sum(-1)
            return 1 / (1 + np.exp(-self.beta * d / (M - 1)))
        code = self.S.astype(np.int64) @ POW; I = X // 2
        keys = (code[:, None] & ~(1 << I)) * 16 + I
        mir = ((~code[:, None]) & 0xFFFF & ~(1 << I)) * 16 + I if self.sym else None   # the mirror question: other 15 flipped
        need = keys if mask is None else keys[mask]
        if self.sym: need = np.concatenate([need.ravel(), (mir if mask is None else mir[mask]).ravel()])
        need = np.unique(need); miss = need[np.isnan(self.tab[need])]
        if len(miss):
            left = None if self.budget is None else self.budget - (jev.STATS["tokens"] - self.tok0) * jev.PRICE
            live_probs(miss.tolist(), self.cache, left); self.tab[miss] = [self.cache[int(q)] for q in miss]
        pA = np.nan_to_num(self.tab[keys], nan=0.5)                        # cells outside the mask are never used
        if self.sym: pA = (pA + 1 - np.nan_to_num(self.tab[mir], nan=0.5)) / 2
        return np.where(X % 2 == 0, pA, 1 - pA)

    def step(self):
        rng, n, k, S, F, ar = self.rng, self.n, self.k, self.S, self.F, self.ar
        self.t += 1
        # 1. post
        w = (self.A >= self.sil_t) * rng.random((n, M)); pi = np.argmax(w, 1); posted = w[ar, pi] > 0
        px = 2 * pi + S[ar, pi]
        # 2. candidates and feed
        Xc = px[F]; Ic = pi[F]; valid = posted[F]
        Fc = F.copy()                                                        # authors of the candidates, before any unfollow
        dis = S[ar[:, None], Ic] != (Xc % 2)                                  # viewer holds the other side
        rk = self.rank
        # live mode asks Jev only for cells it needs: every candidate of a ranked feed, only the shown posts of a chronological one
        P = self.pfit(Xc, valid & (rk != 0)[:, None]) if self.live else self.pfit(Xc)
        score = rng.random((n, k)) * 1e-6
        ch = rk == 0; score[ch] += rng.random((ch.sum(), k))
        e = rk == 1; score[e] += P[e]
        o = rk == 3; score[o] += P[o] + 0.5 * (1 - P[o]) * dis[o]
        b = rk == 2
        if b.any():
            camp = camps(S)[0]
            allx = np.tile(np.arange(2 * M), (n, 1)); Pall = self.pfit(allx) if not self.live else None
            if Pall is None: raise ValueError("bridging ranker is not available in live mode")
            B = np.minimum(Pall[camp == 0].mean(0) if (camp == 0).any() else 0.5, Pall[camp == 1].mean(0) if (camp == 1).any() else 0.5)
            score[b] += B[Xc[b]]
        score[~valid] = -1.0
        top = np.argpartition(-score, self.fd - 1, 1)[:, :self.fd]
        shown = np.zeros((n, k), bool); shown[ar[:, None], top] = True; shown &= valid
        if self.live and (rk == 0).any():
            m = shown & (rk == 0)[:, None]; P2 = self.pfit(Xc, m); P = np.where(m, P2, P)
        # 3. like
        L = shown & (rng.random((n, k)) < P)
        # 4. adopt
        cand = shown & dis
        pick = np.argmax(cand * rng.random((n, k)), 1); has = cand[ar, pick]
        au = F[ar, pick]; agree = (S == S[au]).mean(1)
        go = has & (rng.random(n) < agree) & (rng.random(n) < P[ar, pick])
        newS = S.copy(); ii = Ic[ar, pick]; newS[ar[go], ii[go]] = 1 - S[ar[go], ii[go]]
        # 5. unfollow + recommendation
        clash = shown & dis & ~L; nunf = 0
        if self.unf > 0:
            cp = np.argmax(clash * rng.random((n, k)), 1); hc = clash[ar, cp] & (rng.random(n) < self.unf)
            liked = [F[f][L[f]] for f in range(n)] if hc.any() else None
            for v in np.nonzero(hc)[0]:
                fol = set(F[v].tolist()); new = -1
                if rng.random() < self.rec:
                    pool = np.concatenate([liked[f] for f in F[v]]) if len(F[v]) else np.array([], int)
                    pool = [c for c in pool.tolist() if c != v and c not in fol]
                    if pool: new = pool[rng.integers(len(pool))]
                while new < 0:
                    c = int(rng.integers(n))
                    if c != v and c not in fol: new = c
                F[v, cp[v]] = new; nunf += 1
        self.unfollows += nunf
        # 7. silence: running estimate of agreement among seen posts, per issue
        cnt = np.zeros((n, M)); agr = np.zeros((n, M))
        vv = np.broadcast_to(ar[:, None], (n, k))[shown]; np.add.at(cnt, (vv, Ic[shown]), 1); np.add.at(agr, (vv, Ic[shown]), (~dis)[shown])
        seen = cnt > 0; self.A[seen] = 0.8 * self.A[seen] + 0.2 * agr[seen] / cnt[seen]
        # 6. drift
        fl = rng.random(n) < self.noise; j = rng.integers(0, M, n); newS[ar[fl], j[fl]] ^= 1
        self.last = dict(shown=shown, dis=dis, F=F.copy(), likes=int(L.sum()), unf=nunf, switches=int(go.sum()), posted=posted,
                         Xc=Xc, Fc=Fc, L=L, go=go, ii=ii)
        self.S[:] = newS
        if self.stub > 0:                                                    # anchoring: one position back toward tick 0
            off = self.S != self.S0; back = (rng.random(n) < self.stub) & off.any(1)
            j = np.argmax(off * rng.random((n, M)), 1); self.S[ar[back], j[back]] = self.S0[ar[back], j[back]]
        if self.live and self.t % 5 == 0: self.save_cache()

    def save_cache(self):
        """Merge with the file on disk (another run may have added answers) and replace it atomically."""
        if not self.live or len(self.cache) == getattr(self, "_saved", -1): return   # nothing new since the last save
        p = live_path()
        if os.path.exists(p):
            for a, b in json.load(open(p)).items(): self.cache.setdefault(int(a), b)
        tmp = f"{p}.{os.getpid()}.tmp"; json.dump({str(a): b for a, b in self.cache.items()}, open(tmp, "w")); os.replace(tmp, p)
        self._saved = len(self.cache)

    def metrics(self, axis):
      with np.errstate(all="ignore"):
        S, F, n = self.S, self.F, self.n; R = corr(S); m = measure(R); camp, nd, pc = camps(S); m['package_gap'] = nd
        L = self.last; shown = L.get("shown")
        if shown is not None:
            Fp = L["F"]; tot = max(shown.sum(), 1)
            m["agree_exposure"] = float((shown & ~L["dis"]).sum() / tot)       # share of feed posts that agree with the viewer
            m["camp_exposure"] = float((shown & (camp[:, None] == camp[Fp])).sum() / tot)
        else: m["agree_exposure"] = m["camp_exposure"] = 0.5
        same = (camp[:, None] == camp[F]).mean(1)
        m["cross_ties"] = float(1 - same.mean()); m["modularity"] = modularity(F, camp)
        cons = consistency(S, camp); m["consistency"] = float(cons.mean())
        ec = same >= 0.9; m["echo_share"] = float(ec.mean())                  # agents whose follows are 90%+ own side
        m["cons_echo"] = float(cons[ec].mean()) if ec.any() else None; m["cons_mixed"] = float(cons[same < 0.6].mean()) if (same < 0.6).any() else None
        sil = self.A < self.sil_t; maj = S.mean(0) > 0.5; minor = S != maj
        m["silent"] = float(sil.mean()); m["silent_minority"] = float(sil[minor].mean()) if minor.any() else 0.0; m["silent_majority"] = float(sil[~minor].mean())
        m["liberal_share"] = float(((0.5 - S) @ axis > 0).mean()); m["capture"] = capture(R); m["pc1_self"] = pc
        m["unfollows"] = self.unfollows; m["switches"] = L.get("switches", 0); m["likes"] = L.get("likes", 0)
        m["minority"] = float(min(camp.mean(), 1 - camp.mean()))           # share of agents on the smaller side
        i, j = rng_pairs(n); m["diversity"] = float((S[i] != S[j]).mean())  # mean share of issues two random agents disagree on
        m.update(fair_measures(S, camp, cons, self.S0, np.asarray(axis))); m["tick"] = self.t; return m

def layout_step(P, W, iters, step=0.02):
    """Spring-electrical layout in numpy: all-pairs repulsion, springs weighted by W (n x n, symmetric), weak gravity.
    Warm-started from the previous frame so the picture moves continuously."""
    u, v = np.nonzero(np.triu(W, 1)); w = W[u, v]; w = w / (w.mean() or 1)
    for _ in range(iters):
        D = P[:, None, :] - P[None, :, :]; d2 = (D ** 2).sum(-1) + 1e-4
        f = (D / d2[..., None]).sum(1) * 0.0009 - P * 0.03
        dv = (P[v] - P[u]) * w[:, None] * 0.012; np.add.at(f, u, dv); np.add.at(f, v, -dv)
        L = np.clip(np.linalg.norm(f, axis=1, keepdims=True), 1e-9, None); P += f / L * np.minimum(L, step)
    return P

def b64(a, dt): return base64.b64encode(np.ascontiguousarray(a).astype(dt).tobytes()).decode()

def run(n=1000, ticks=300, ranker="chrono", seed=0, snap_every=5, record=False, log=None, schedule=None, **kw):
    """record: also store per-frame positions for the viewer, laid out on the EXPOSURE graph (who saw whose posts over the
    last ~10 ticks, exponentially weighted), plus each viewer's feed this tick and its silent issues.
    schedule: optional function (sim, t) -> None called before each tick (used to change rankers mid-run)."""
    sim = Sim(n=n, seed=seed, ranker=ranker, **kw); axis = gss_axis(); hist, frames = [], []
    P = np.random.default_rng(seed + 99).normal(0, 0.3, (n, 2)) if record else None
    E = np.zeros((n, n), np.float32) if record else None
    def snap():
        nonlocal P
        m = sim.metrics(axis); hist.append(m)
        if log: log(json.dumps({a: (round(b, 4) if isinstance(b, float) else b) for a, b in m.items()}))
        if record:
            W = E + E.T
            if sim.t == 0: W = np.zeros((n, n), np.float32); W[np.repeat(np.arange(n), sim.k), sim.F.ravel()] = 1; W = W + W.T
            P = layout_step(P, W, 60 if sim.t == 0 else 4 * snap_every)
            c = P - P.mean(0); sc = np.abs(c).max() or 1
            sh = sim.last.get("shown"); feed = np.full((n, 2), 65535, np.int64)   # 2 of each viewer's feed posts, for drawing
            if sh is not None:
                Fp = sim.last["F"]; r = np.random.default_rng(sim.t)
                for v in range(n):
                    f = Fp[v][sh[v]]
                    if len(f): f = r.permutation(f)[:2]; feed[v, :len(f)] = f
            frames.append({"tick": sim.t, "S": b64(sim.S.astype(np.int64) @ POW, "<u2"), "xy": b64(np.round(c / sc * 32000), "<i2"),
                           "feed": b64(feed, "<u2"), "sil": b64((sim.A < sim.sil_t).astype(np.int64) @ POW, "<u2")})
    stopped = None
    snap()
    for t in range(1, ticks + 1):
        if schedule: schedule(sim, t)
        try: sim.step()
        except (BudgetStop, RuntimeError) as e:
            stopped = f"tick {t - 1}: {type(e).__name__} {str(e)[:120]}"; sim.t = t - 1
            if log: log("stopping at " + stopped)
            break
        if record:
            E *= 0.9; sh = sim.last["shown"]; vv, jj = np.nonzero(sh); np.add.at(E, (vv, sim.last["F"][vv, jj]), 1.0)
        if t % snap_every == 0 or t == ticks: snap()
    sim.save_cache()
    if stopped and hist[-1]["tick"] != sim.t: snap()
    cfg = dict(n=n, ticks=ticks, ranker=ranker, seed=seed, k=sim.k, **{a: b for a, b in kw.items() if a != "budget"}); cfg["feed"] = sim.fd
    return {"config": cfg, "cost_usd": round((jev.STATS["tokens"] - sim.tok0) * jev.PRICE, 4), "stopped": stopped,
            "issues": NAMES, "short": SHORT, "statements": STATEMENTS, "hist": hist, "frames": frames,
            "axis": np.round(gss_axis(), 4).tolist()}, sim

def save(rec, name):
    out = os.path.join(HERE, "viewer", "runs", f"{name}.js")
    open(out, "w").write(f"window.NETS=window.NETS||{{}};window.NETS[{json.dumps(name)}]=" + json.dumps(rec, separators=(",", ":")) + ";\n")
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="python -m jevsociety.netsim")
    ap.add_argument("--n", type=int, default=1000); ap.add_argument("--ticks", type=int, default=300)
    ap.add_argument("--ranker", choices=RANKERS, default="chrono"); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--control", choices=["none", "axelrod", "shuffled"], default="none")
    ap.add_argument("--unfollow", type=float, default=0.05); ap.add_argument("--silence", type=float, default=0.3)
    ap.add_argument("--net", choices=["random", "smallworld"], default="random")
    ap.add_argument("--live", action="store_true", help="every like/switch probability is a live Jev call (cached)")
    ap.add_argument("--budget", type=float, default=None, help="USD cap for live mode"); ap.add_argument("--record", action="store_true")
    ap.add_argument("--snap-every", type=int, default=5); ap.add_argument("--name", default=None)
    a = ap.parse_args(); t0 = time.time()
    rec, _ = run(a.n, a.ticks, a.ranker, a.seed, a.snap_every, record=a.record, log=print, control=a.control, unfollow=a.unfollow,
                 silence=a.silence, net=a.net, live=a.live, budget=a.budget)
    name = a.name or f"net_{a.ranker}_{a.control}_{a.n}_s{a.seed}{'_live' if a.live else ''}"
    print("cost USD", rec["cost_usd"]); print("wrote", save(rec, name), f"in {time.time() - t0:.1f} s")
