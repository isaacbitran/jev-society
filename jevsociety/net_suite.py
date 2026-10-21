"""Feed-ranking experiment over many seeds. python -m jevsociety.net_suite [--quick]

Every condition runs on the same seeds, so seed s starts from the same 1,000 agents, the same positions and the same
follow network in every condition; differences between conditions are paired by seed. 300 ticks, snapshot every 5.
Writes data/net_results.json and viewer/runs/net_summary.js. No Jev calls (pairwise table); about 6 minutes.

Naming: the README and the study page call the `chrono` ranker the random feed (every post in a tick is equally new, so
newest-first reduces to a random 6) and the `engagement` ranker the ranked feed (ranked by predicted likes). One tick = one
day. Identifiers and CLI flags keep the old names for compatibility with recorded runs."""
import argparse, copy, json, os, time
import numpy as np
from .netsim import run, Sim, camps, consistency, RANKERS
from .bundling import HERE, gss_axis

GSS_ABS = 0.167
KEYS = ["mean_abs_r", "r_gss", "minority", "diversity", "package_gap", "agree_exposure", "camp_exposure", "cross_ties", "modularity",
        "consistency", "echo_share", "cons_echo", "cons_mixed", "silent", "silent_minority", "silent_majority", "unfollows", "switches",
        "liberal_share", "capture"]
AT = (25, 50, 100, 150, 300)

def summarize(hist):
    out = {}
    for t in AT:
        h = next((h for h in hist if h["tick"] == t), None)
        if h: out[f"t{t}"] = {k: (round(h[k], 4) if isinstance(h[k], float) else h[k]) for k in KEYS}
    m = next((h for h in hist if h["tick"] > 0 and h["mean_abs_r"] >= GSS_ABS and h["minority"] >= 0.05), None)
    out["us_level_tick"] = m["tick"] if m else None; out["r_gss_at_us_level"] = round(m["r_gss"], 4) if m else None
    pk = max(hist[1:], key=lambda h: h["mean_abs_r"]); out["peak_sorting"] = round(pk["mean_abs_r"], 4); out["peak_tick"] = pk["tick"]
    out["consensus_tick"] = next((h["tick"] for h in hist if h["tick"] > 0 and h["diversity"] < 0.05), None)
    return out

def stats(xs):
    xs = np.array([x for x in xs if x is not None], float)
    if not len(xs): return None
    return {"mean": round(float(xs.mean()), 4), "min": round(float(xs.min()), 4), "max": round(float(xs.max()), 4), "n": int(len(xs))}

def agg(rows):
    out = {}
    for when in [f"t{t}" for t in AT]:
        if all(when in r for r in rows): out[when] = {k: stats([r[when][k] for r in rows]) for k in KEYS}
    for k in ("us_level_tick", "r_gss_at_us_level", "peak_sorting", "peak_tick", "consensus_tick"):
        out[k] = stats([r[k] for r in rows]); out[k + "_reached"] = sum(r[k] is not None for r in rows)
    return out

def paired(A, B, when, key):
    """B minus A, seed by seed."""
    d = [b[when][key] - a[when][key] for a, b in zip(A, B) if a[when][key] is not None and b[when][key] is not None]
    s = stats(d); s["b_higher"] = int(sum(x > 0 for x in d)); return s

def meta_experiment(seed, n=1000, warm=200, after=100, share=0.1, beta=4.0):
    """Engagement-ranked society for `warm` ticks, then three continuations from the identical state:
    control (everyone stays on engagement), individual (a random 10% switch to chronological, like the 2023 Meta
    deactivation-style feed experiments), society (everyone switches)."""
    sim = Sim(n=n, seed=seed, ranker="engagement", beta=beta)
    for _ in range(warm): sim.step()
    S0 = sim.S.copy(); camp0 = camps(S0)[0]; cons0 = consistency(S0, camp0)
    treated = np.zeros(n, bool); treated[np.random.default_rng(1000 + seed).choice(n, int(share * n), replace=False)] = True
    out = {}
    for arm in ("control", "individual", "society"):
        s = copy.deepcopy(sim)
        if arm == "individual": s.rank[treated] = 0
        if arm == "society": s.rank[:] = 0
        agree = np.zeros(n); seen = np.zeros(n); sw = np.zeros(n); hist = []
        for t in range(after):
            before = s.S.copy(); s.step(); sw += (s.S != before).sum(1)
            sh, dis = s.last["shown"], s.last["dis"]; agree += (sh & ~dis).sum(1); seen += sh.sum(1)
            if (t + 1) % 10 == 0: hist.append(s.metrics(gss_axis()) | {"tick": warm + t + 1})
        cons1 = consistency(s.S, camp0)                                       # alignment with the package of the camp it was in at the switch
        g = {"treated": treated, "untreated": ~treated}
        out[arm] = {"society": {k: round(hist[-1][k], 4) for k in ("mean_abs_r", "minority", "diversity", "cross_ties", "agree_exposure", "consistency")},
                    "series": [{k: round(h[k], 4) for k in ("tick", "mean_abs_r", "minority", "diversity", "agree_exposure")} for h in hist],
                    "groups": {name: {"agree_exposure": round(float(agree[m].sum() / max(seen[m].sum(), 1)), 4),
                                      "consistency_change": round(float((cons1 - cons0)[m].mean()), 4),
                                      "switches_per_agent": round(float(sw[m].mean()), 3),
                                      "changed_camp": round(float((consistency(s.S, camp0)[m] < 0.5).mean()), 4)} for name, m in g.items()}}
    out["before"] = {"mean_abs_r": round(sim.metrics(gss_axis())["mean_abs_r"], 4), "consistency": round(float(cons0.mean()), 4)}
    return out

def main(quick=False):
    seeds = 3 if quick else 10; t0 = time.time()
    conds = {f"{r}": dict(ranker=r) for r in RANKERS}
    for r in ("chrono", "engagement"):
        conds[f"{r}_axelrod"] = dict(ranker=r, control="axelrod"); conds[f"{r}_shuffled"] = dict(ranker=r, control="shuffled")
        conds[f"{r}_nounfollow"] = dict(ranker=r, unfollow=0.0); conds[f"{r}_nosilence"] = dict(ranker=r, silence=0.0)
        conds[f"{r}_smallworld"] = dict(ranker=r, net="smallworld"); conds[f"{r}_unfollow0.2"] = dict(ranker=r, unfollow=0.2)
        conds[f"{r}_beta11"] = dict(ranker=r, beta=11.0); conds[f"{r}_beta32"] = dict(ranker=r, beta=32.0)
    dose = {}
    for fd in (3, 12, 20):
        for r in ("chrono", "engagement"): dose[f"{r}_feed{fd}"] = dict(ranker=r, feed=fd)
    out = {"config": {"n": 1000, "ticks": 300, "k": 20, "feed": 6, "beta": 4.0, "noise": 0.002, "unfollow": 0.05, "recommend": 0.8,
                      "silence": 0.3, "seeds": seeds}, "runs": {}, "summary": {}, "paired": {}}
    def go(name, kw, ns, n=1000):
        rows = []
        for s in range(ns):
            rec, _ = run(n, 300, seed=s, snap_every=5, **kw); r = summarize(rec["hist"]); r["seed"] = s; rows.append(r)
        out["runs"][name] = rows; out["summary"][name] = agg(rows)
        e = out["summary"][name]["t300"]; print(f"{name:<24} sort {e['mean_abs_r']['mean']:.2f} minority {e['minority']['mean']:.2f} diversity {e['diversity']['mean']:.2f}"
              f" agree {e['agree_exposure']['mean']:.2f} cross {e['cross_ties']['mean']:.2f} silent {e['silent']['mean']:.2f} unf {e['unfollows']['mean']:.0f}  ({time.time() - t0:.0f} s)", flush=True)
    for name, kw in conds.items(): go(name, kw, seeds)
    for name, kw in dose.items(): go(name, kw, 3 if quick else 5)
    for r in ("chrono", "engagement"): go(f"{r}_n4000", dict(ranker=r), 2 if quick else 3, n=4000)
    for base in ("", "_axelrod", "_shuffled", "_nounfollow", "_nosilence", "_smallworld", "_unfollow0.2", "_beta11", "_beta32"):
        A, B = out["runs"]["chrono" + base], out["runs"]["engagement" + base]
        out["paired"]["engagement_minus_chrono" + base] = {w: {k: paired(A, B, w, k) for k in ("mean_abs_r", "minority", "diversity", "agree_exposure", "cross_ties", "modularity", "consistency", "silent", "unfollows")} for w in ("t50", "t300")}
    for r in ("bridging", "outrage"):
        A, B = out["runs"]["chrono"], out["runs"][r]
        out["paired"][f"{r}_minus_chrono"] = {w: {k: paired(A, B, w, k) for k in ("mean_abs_r", "minority", "diversity", "agree_exposure", "cross_ties", "silent")} for w in ("t50", "t300")}
    out["meta"] = {f"beta{b:g}": [meta_experiment(s, beta=b) | {"seed": s} for s in range(seeds)] for b in (4.0, 32.0)}
    print(f"meta experiment done ({time.time() - t0:.0f} s)")
    json.dump(out, open(os.path.join(HERE, "data", "net_results.json"), "w"), indent=1)
    open(os.path.join(HERE, "viewer", "runs", "net_summary.js"), "w").write("window.NET_SUMMARY=" + json.dumps(out) + ";\n")
    print("wrote data/net_results.json")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--quick", action="store_true"); main(ap.parse_args().quick)
