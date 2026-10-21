"""Measure Jev's side lean in the agreement score. python -m jevsociety.calibrate [--pairs 4000]

Samples pairs of 5-belief agents with controlled side mixes, asks Jev the same agreement question the
simulation asks, and fits  score/4 = a + b*p_u*p_v + c*|p_u-p_v| + d*shared/5 + e*m,
where p = mean pole of an agent's beliefs (+1 traditional, -1 progressive) and m = (p_u+p_v)/2.
`e` is the side lean: how much agreement changes as a pair moves toward the traditional side with
alignment and overlap held fixed. Writes cache/calib.json; answers also seed the shared score cache."""
import argparse, json, os, random, numpy as np
from . import jev
from .beliefs import POOL, POLE
from .engine import agree_q, ScoreCache, CACHE_DIR

TRAD = [i for i, p in enumerate(POLE) if p > 0]; PROG = [i for i, p in enumerate(POLE) if p < 0]
def agent(rng, ntrad): return rng.sample(TRAD, ntrad) + rng.sample(PROG, 5 - ntrad)
def pole(b): return sum(POLE[i] for i in b) / len(b)

def features(bu, bv):
    pu, pv = pole(bu), pole(bv)
    return [1.0, pu * pv, abs(pu - pv), len(set(bu) & set(bv)) / 5, (pu + pv) / 2]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--pairs", type=int, default=4000); ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args(); rng = random.Random(a.seed)
    pairs = []
    for _ in range(a.pairs):
        bu = agent(rng, rng.randint(0, 5))
        if rng.random() < 0.3:  # neighbour-like: 1-3 beliefs swapped
            bv = list(bu)
            for _ in range(rng.randint(1, 3)):
                j = rng.randrange(5); bv[j] = rng.choice([x for x in range(len(POOL)) if x not in bv])
        else: bv = agent(rng, rng.randint(0, 5))
        pairs.append((tuple(sorted(bu)), tuple(sorted(bv))))
    sc = ScoreCache(); need = {f"s{i}": agree_q(u, v, POOL) for i, (u, v) in enumerate(pairs) if sc.get(u, v) is None}
    ans = jev.ask_many(need, tag="calibrate") if need else {}
    for i, (u, v) in enumerate(pairs):
        if f"s{i}" in ans: sc.put(u, v, ans[f"s{i}"]["score"])
    sc.save()
    X = np.array([features(u, v) for u, v in pairs]); y = np.array([sc.get(u, v) / 4 for u, v in pairs])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef; cov = np.linalg.inv(X.T @ X) * resid.var(); se = np.sqrt(np.diag(cov))
    names = ["intercept", "alignment p_u*p_v", "distance |p_u-p_v|", "shared/5", "side lean m"]
    # matched check: same-side pairs, all-progressive vs all-traditional
    m = X[:, 4]; same = np.abs(X[:, 2]) < 1e-9
    out = {"coef": dict(zip(names, coef.round(4).tolist())), "se": dict(zip(names, se.round(4).tolist())), "e": float(coef[4]),
           "n": len(pairs), "r2": float(1 - resid.var() / y.var()),
           "matched_score_0to4": {"both_all_progressive": float(y[same & (m < -0.99)].mean() * 4), "both_all_traditional": float(y[same & (m > 0.99)].mean() * 4)},
           "lean_points_0to4": float(-coef[4] * 2 * 4)}
    json.dump(out, open(os.path.join(CACHE_DIR, "calib.json"), "w"), indent=1); print(json.dumps(out, indent=1)); print("USD", round(jev.total_spend(), 4))
if __name__ == "__main__": main()

def drop_rates(save=True):
    """Drop-rule coherence by side, from cached Jev Choice answers: P(Jev drops an opposite-side belief | new belief's
    side, number of opposite-side beliefs held). Free: no new Jev calls."""
    import pickle, collections
    C = pickle.load(open(os.path.join(CACHE_DIR, "jev_politics.pkl"), "rb"))["choice"]
    st = collections.defaultdict(lambda: [0, 0])
    for (bs, new), drop in C.items():
        nopp = sum(POLE[b] != POLE[new] for b in bs)
        if 0 < nopp < len(bs): r = st[f"{POLE[new]},{nopp}"]; r[0] += 1; r[1] += POLE[drop] != POLE[new]
    rates = {k: round(o / n, 4) for k, (n, o) in st.items()}
    out = {"rates": rates, "n": {k: v[0] for k, v in st.items()}}
    if save: json.dump(out, open(os.path.join(CACHE_DIR, "calib_drop.json"), "w"), indent=1)
    return out
