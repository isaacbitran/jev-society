"""Emergent issue bundling. python -m jevsociety.bundling --n 10000 --seed 0 [--beta 4] [--control none|axelrod|shuffled]

Every agent holds one side (statement A or B) of each of 16 issues, drawn independently with probability 1/2, so at
tick 0 no two issues are correlated. Every tick, every agent (synchronous update):
  1. Meets a random grid neighbour.
  2. Interacts with probability = share of issues on which the two agree (Axelrod 1997 homophily).
  3. Picks one issue at random where they differ and considers switching to the neighbour's side.
  4. Switches with probability 1 / (1 + exp(-beta * (fit_new - fit_old))), where fit(s) is the mean Jev judgment of
     how statement s fits with each of the agent's other 15 beliefs (data/jev_pairs_<variant>.json, scaled to [-1, 1]).
  5. With probability `noise`, flips one random issue (cultural drift; keeps the system from freezing).

Live mode (--control live): step 4 asks Jev directly instead of using the pairwise table. The question shows the
agent's other 15 beliefs (order shuffled) and both sides of the issue (order shuffled) and asks which fits better;
the agent switches with Jev's probability for the neighbour's side. Answers are cached by (other 15 positions, issue)
in data/jev_live_fit.json, so a rerun replays them without calls. Costs about USD 0.01 per tick at 1,600 agents.

Controls, same code path:
  axelrod   beta = 0: the switch is a coin flip. No meaning anywhere; the standard binary Axelrod model with drift.
  solo      no social contact: each tick an agent reconsiders one random issue on its own, with the same Jev-based
            switch rule. Shows how much bundling individual coherence-seeking produces without copying anyone.
  shuffled  the Jev matrix with its statements relabelled by a random permutation (new one per seed): exactly the
            same distribution of judgments, attached to the wrong sentences.

No left/right label is used by the simulation. The survey data (data/gss2024_corr.json) is read only by `measure`.
Frames store each agent's 16 positions as one uint16 (bit i = 1 means statement B of issue i), base64-encoded.
Pure numpy; no Jev calls (the 1,920 pairwise judgments were bought once by jevsociety.pairs).

Naming: the README and the study page call one tick of this model a round."""
import argparse, base64, json, os, random, time
import numpy as np
from .issues import M, NAMES, SHORT, STATEMENTS
from .pairs import load
from . import jev

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IU = np.triu_indices(M, 1)

def gss():
    G = json.load(open(os.path.join(HERE, "data", "gss2024_corr.json")))
    return np.array([[np.nan if x is None else x for x in r] for r in G["r"]])

def grid(side):
    n = side * side; nb = np.full((n, 4), -1); deg = np.zeros(n, int)
    for u in range(n):
        x, y = divmod(u, side)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if 0 <= x + dx < side and 0 <= y + dy < side: nb[u, deg[u]] = (x + dx) * side + y + dy; deg[u] += 1
    return nb, deg

def corr(S):
    """Issue-issue Pearson (phi) correlation across agents. S: n x M of 0/1 (1 = statement B)."""
    X = 1.0 - S  # 1 = statement A, matching the survey coding
    sd = X.std(0); Xc = (X - X.mean(0)) / np.where(sd > 0, sd, 1)
    with np.errstate(all="ignore"): R = Xc.T @ Xc / len(X)
    R = np.nan_to_num(R); R[:, sd == 0] = 0; R[sd == 0, :] = 0; np.fill_diagonal(R, 1); return R

def direct(K):
    """Issue-issue association implied by the Jev matrix alone, before any dynamics."""
    d = np.zeros((M, M))
    for i in range(M):
        for j in range(M):
            if i != j: d[i, j] = (K[2*i, 2*j] + K[2*i+1, 2*j+1] - K[2*i, 2*j+1] - K[2*i+1, 2*j]) / 4
    return d

def pc1_share(R):
    w = np.linalg.eigvalsh(R); return float(w[-1] / w.sum())

def measure(R, G=None):
    G = gss() if G is None else G; g, x = G[IU], R[IU]; ok = ~np.isnan(g); big = ok & (np.abs(g) > 0.1)
    return {"r_gss": float(np.corrcoef(x[ok], g[ok])[0, 1]) if x[ok].std() > 0 else 0.0,
            "sign_agree": float(np.mean(np.sign(x[big]) == np.sign(g[big]))), "mean_abs_r": float(np.abs(x).mean()), "pc1": pc1_share(R)}

NONPARTISAN = [NAMES.index("space"), NAMES.index("roads")]
def capture(R):
    """Mean |correlation| between the two issues with no partisan content in the survey (space, roads) and the other 14."""
    others = [j for j in range(M) if j not in NONPARTISAN]
    return float(np.abs(R[np.ix_(NONPARTISAN, others)]).mean())

def gss_axis():
    """First principal component of the survey correlation matrix (missing pair filled with 0), oriented so that the
    'abortion for any reason' answer is positive. Used ONLY to colour agents in the viewer."""
    G = np.nan_to_num(gss()); np.fill_diagonal(G, 1); w, V = np.linalg.eigh(G); v = V[:, -1]
    return v * np.sign(v[NAMES.index("abortion")])

LIVE_Q = "This person holds all of `other_beliefs`. Which of the two options fits better with the rest of their beliefs?"
def live_path(): return os.path.join(HERE, "data", f"jev_live{'_mock' if jev.MOCK else ''}_fit.json")

def live_probs(keys, cache, budget_left):
    """keys: ints (other-15 code with issue bit cleared) * 16 + issue. Returns nothing; fills cache[key] = P(statement A)."""
    need = {}
    for key in set(keys) - cache.keys():
        code, i = divmod(key, 16); r = random.Random(key)
        others = [STATEMENTS[2 * j + ((code >> j) & 1)] for j in range(M) if j != i]; r.shuffle(others)
        flip = r.random() < 0.5  # option order shuffled: Jev leans toward the first option
        opts = [STATEMENTS[2 * i + 1], STATEMENTS[2 * i]] if flip else [STATEMENTS[2 * i], STATEMENTS[2 * i + 1]]
        need[key] = (flip, {"type": "choice", "instructions": {"other_beliefs": others, "question": LIVE_Q}, "criteria": {"0": opts[0], "1": opts[1]}})
    if not need: return 0
    if budget_left is not None and len(need) * TOK_PER_Q * jev.PRICE > budget_left: raise BudgetStop(len(need))
    ids = sorted(need)
    for c0 in range(0, len(ids), CHUNK):                                  # chunks: answers already paid for are kept if a later call fails
        part = ids[c0:c0 + CHUNK]; ans = jev.ask_many({f"k{j}": need[k][1] for j, k in enumerate(part)}, tag="bundle-live")
        for j, k in enumerate(part):
            pr = ans[f"k{j}"].get("probabilities") or {ans[f"k{j}"]["choice"]: 1.0}
            p_first = float(pr.get("0", 0.0)); cache[k] = round(1 - p_first if need[k][0] else p_first, 4)
    return len(need)

TOK_PER_Q = 400   # budget pre-check, input tokens per live question (measured mean 344 over 976 full calls of 120)
CHUNK = 12000     # questions per ask_many round

class BudgetStop(Exception): pass

def simulate(n=1600, ticks=300, beta=4.0, noise=0.002, seed=0, control="none", variant="fit", snap_every=5, log=None, budget=None):
    rng = np.random.default_rng(seed); side = int(round(n ** 0.5)); assert side * side == n
    K = np.array(load(variant))
    if control == "shuffled":
        p = rng.permutation(2 * M); K = K[np.ix_(p, p)]
        for i in range(M): K[2*i, 2*i+1] = K[2*i+1, 2*i] = 0.0  # same-issue entries are never used
    b = 0.0 if control == "axelrod" else beta
    nb, deg = grid(side); S = rng.integers(0, 2, (n, M)); base = 2 * np.arange(M); ar = np.arange(n)
    frames, hist = [], []; AXIS = gss_axis()
    def snap(t):
        R = corr(S); m = measure(R); m.update(tick=t, cultures=int(len(np.unique(S @ (1 << np.arange(M))))),
                                             liberal_share=float(((0.5 - S) @ AXIS > 0).mean()), capture=capture(R))
        hist.append(m); frames.append({"tick": t, "S": base64.b64encode((S @ (1 << np.arange(M))).astype("<u2").tobytes()).decode(), "R": np.round(R, 3).tolist()})
        if log: log(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items()}))
    live = {int(k): v for k, v in json.load(open(live_path())).items()} if control == "live" and os.path.exists(live_path()) else {}
    tok0 = jev.STATS["tokens"]; stopped = False
    snap(0)
    for t in range(1, ticks + 1):
        v = nb[ar, rng.integers(0, deg)]
        if control == "solo":  # no neighbours: reconsider one random issue alone
            i = rng.integers(0, M, n); act = rng.random(n) < 0.5; v = ar
        else:
            diff = S != S[v]; nd = diff.sum(1)
            act = (nd > 0) & (rng.random(n) < 1 - nd / M)
            i = np.argmax(diff * rng.random((n, M)), 1)                   # random differing issue
        idx = base + S                                                     # statements currently held
        old = idx[ar, i]; new = old ^ 1
        fit_new = K[new[:, None], idx].sum(1) / (M - 1); fit_old = K[old[:, None], idx].sum(1) / (M - 1)
        if control == "live":
            code = S @ (1 << np.arange(M)); keys = (code & ~(1 << i)) * 16 + i
            try: live_probs(keys[act].tolist(), live, None if budget is None else budget - (jev.STATS["tokens"] - tok0) * jev.PRICE)
            except (BudgetStop, RuntimeError) as e:
                if log: log(f"stopping at tick {t - 1}: {type(e).__name__} {str(e)[:120]}")
                stopped = True; break
            pA = np.array([live.get(int(k), 0.5) for k in keys]); p = np.where(new % 2 == 0, pA, 1 - pA)
        else: p = 1 / (1 + np.exp(-b * (fit_new - fit_old)))
        go = act & (rng.random(n) < p)
        S[ar[go], i[go]] = 1 - S[ar[go], i[go]]                          # take the other side (the neighbour's, except in solo)
        fl = rng.random(n) < noise; j = rng.integers(0, M, n); S[ar[fl], j[fl]] ^= 1
        if t % snap_every == 0 or t == ticks: snap(t)
        if control == "live" and t % 5 == 0: json.dump({str(k): v for k, v in live.items()}, open(live_path(), "w"))
    if control == "live":
        json.dump({str(k): v for k, v in live.items()}, open(live_path(), "w"))
        if stopped and hist[-1]["tick"] != t - 1: snap(t - 1)
    return {"cost_usd": round((jev.STATS["tokens"] - tok0) * jev.PRICE, 4), "live_answers": len(live),"config": dict(n=n, ticks=ticks, beta=beta, noise=noise, seed=seed, control=control, variant=variant),
            "side": side, "issues": NAMES, "short": SHORT, "statements": STATEMENTS, "frames": frames, "hist": hist,
            "direct": np.round(direct(K), 4).tolist(), "gss": [[None if np.isnan(x) else x for x in r] for r in gss()],
            "axis": np.round(gss_axis(), 4).tolist(), "final": hist[-1]}

def save(rec, name):
    out = os.path.join(HERE, "viewer", "runs", f"{name}.js")
    open(out, "w").write(f"window.BUNDLES=window.BUNDLES||{{}};window.BUNDLES[{json.dumps(name)}]=" + json.dumps(rec, separators=(",", ":")) + ";\n")
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="python -m jevsociety.bundling")
    ap.add_argument("--n", type=int, default=1600); ap.add_argument("--ticks", type=int, default=300)
    ap.add_argument("--beta", type=float, default=4.0); ap.add_argument("--noise", type=float, default=0.002)
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--control", choices=["none", "axelrod", "shuffled", "solo", "live"], default="none")
    ap.add_argument("--variant", choices=["fit", "reasons"], default="fit"); ap.add_argument("--snap-every", type=int, default=5)
    ap.add_argument("--name", default=None); ap.add_argument("--budget", type=float, default=None, help="USD cap for live mode")
    a = ap.parse_args(); t0 = time.time()
    rec = simulate(a.n, a.ticks, a.beta, a.noise, a.seed, a.control, a.variant, a.snap_every, log=print, budget=a.budget)
    name = a.name or f"bundle_{a.variant}_{a.control}_{a.n}_s{a.seed}"
    print("wrote", save(rec, name), f"in {time.time() - t0:.1f} s")
