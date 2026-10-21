"""Is it the algorithm? Fair tests for the 10,000-account live-Jev network. python -m jevsociety.fair <experiment> [--workers 6]

Same model and code path as jevsociety.live10k (netsim.Sim, live mode: every like/adopt probability is a cached Jev answer),
metrics only (no viewer frames), every 5 ticks plus the last. Options added for these tests (see netsim.Sim):
  stubborn s     each tick, with probability s, an agent moves one position it has changed back to its tick-0 side
  sym            Jev's lean removed: P_sym(x | S) = (P(x | S) + P(not x | not S)) / 2
  init_liberal q tick-0 positions are on the survey's liberal side with probability q (default 0.5)
Experiments:
  calib   both feeds, seed 0, raw and lean-removed Jev, s in STUB_GRID
  fine    both feeds, seeds 0-2, raw Jev, s in FINE_GRID: the smallest s that keeps a chronological society diverse
  main    chronological vs engagement, seeds 0-2, for {baseline, stubborn, lean removed, stubborn + lean removed}
  tilt    chronological vs engagement, seeds 0-2, tick-0 liberal majority: q = 0.6 (raw and lean-removed Jev), 0.52 and 0.55 (raw)
  seeds   chronological vs engagement, seeds 3-9, baseline and lean removed (who wins, over 10 seeds)
  summary writes viewer/runs/fair_summary.js (day-300 mean/min/max per condition) for the viewer
Results merge into data/fair_results.json (one entry per run name).

Naming: the README and the study page call the `chrono` ranker the random feed (every post in a tick is equally new, so
newest-first reduces to a random 6) and the `engagement` ranker the ranked feed (ranked by predicted likes). One tick = one
day. Identifiers and CLI flags keep the old names for compatibility with recorded runs."""
import argparse, json, os, time
from multiprocessing import Pool
import numpy as np
from .netsim import Sim
from .bundling import gss_axis, HERE
from . import jev

OUT = os.path.join(HERE, "data", "fair_results.json")
STUB_GRID = (0.0, 0.005, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0)
FINE_GRID = (0.2, 0.22, 0.24, 0.26, 0.28, 0.3)
S_STAR = 0.26   # from `fine`: smallest s on the grid at which the chronological society stays diverse in all 3 seeds

def one(job):
    name, kw = job; t0 = time.time(); ticks = kw.pop("ticks", 300)
    sim = Sim(n=10000, live=True, budget=0.05, **kw); axis = gss_axis(); hist = []
    sim.save_cache = lambda: None                                          # cache is complete; parallel runs must not race on it
    def snap():
        m = sim.metrics(axis); m["wall_s"] = round(time.time() - t0, 1)
        hist.append({a: (round(b, 4) if isinstance(b, float) else b) for a, b in m.items()})
    snap()
    for t in range(1, ticks + 1):
        sim.step()
        if t % 5 == 0 or t == ticks: snap()
    cost = round((jev.STATS["tokens"] - sim.tok0) * jev.PRICE, 4)
    return name, {"config": dict(kw, ticks=ticks, n=10000), "cost_usd": cost, "hist": hist}

def jobs(exp):
    J = []
    if exp == "calib":
        for sym in (False, True):
            for r in ("chrono", "engagement"):
                for s in STUB_GRID: J.append((f"calib{'sym' if sym else ''}_{r}_s{s}", dict(ranker=r, seed=0, stubborn=s, sym=sym)))
    if exp == "fine":
        for s in FINE_GRID:
            for seed in (0, 1, 2):
                for r in ("chrono", "engagement"): J.append((f"fine_{r}_s{s}_seed{seed}", dict(ranker=r, seed=seed, stubborn=s)))
    conds = {"main": [("base", {}), ("stub", {"stubborn": S_STAR}), ("sym", {"sym": True}), ("stubsym", {"stubborn": S_STAR, "sym": True})],
             "tilt": [("tilt", {"init_liberal": 0.6}), ("tiltsym", {"init_liberal": 0.6, "sym": True}),
                      ("tilt52", {"init_liberal": 0.52}), ("tilt55", {"init_liberal": 0.55})]}.get(exp, [])
    seeds = (0, 1, 2)
    if exp == "seeds": conds, seeds = [("base", {}), ("sym", {"sym": True})], range(3, 10)
    for tag, kw in conds:
        for seed in seeds:
            for r in ("chrono", "engagement"): J.append((f"{tag}_{r}_s{seed}", dict(ranker=r, seed=seed, **kw)))
    return J

def merge(res):
    d = json.load(open(OUT)) if os.path.exists(OUT) else {"note": "jevsociety/fair.py: fair tests, 10,000 accounts, live Jev (cached), metrics every 5 ticks", "runs": {}}
    d["runs"].update(res); json.dump(d, open(OUT, "w"), indent=0)

SUMMARY_KEYS = ("minority", "liberal_share", "consensus", "diversity", "pkg_dist", "pkg14", "full_pkg", "bimodality", "mean_abs_r",
                "agree_exposure", "cross_ties", "echo_share", "silent_minority", "unfollows", "kept", "init_agree", "init_chance", "init_kappa")
CONDS = {"base": "Jev as measured", "sym": "Lean removed", "stub": f"Stubborn agents (s = {S_STAR})", "stubsym": f"Stubborn agents, lean removed",
         "tilt52": "52% liberal start", "tilt55": "55% liberal start", "tilt": "60% liberal start", "tiltsym": "60% liberal start, lean removed"}

def summary():
    """Day-300 mean, min and max over seeds for every condition and feed -> viewer/runs/fair_summary.js."""
    R = json.load(open(OUT))["runs"]; out = {"s_star": S_STAR, "conds": {}}
    for tag, label in CONDS.items():
        for r in ("chrono", "engagement"):
            rows = [R[k]["hist"][-1] for k in sorted(R) if k.startswith(f"{tag}_{r}_s")]
            if not rows: continue
            st = {}
            for k in SUMMARY_KEYS:
                v = [h[k] for h in rows if h.get(k) is not None]
                if v: st[k] = {"mean": round(float(np.mean(v)), 4), "min": round(min(v), 4), "max": round(max(v), 4), "n": len(v)}
            out["conds"].setdefault(tag, {"label": label})[r] = st
    calib = {k: R[k]["hist"][-1] for k in R if k.startswith(("calib_", "fine_"))}
    out["calib"] = {k: {a: h.get(a) for a in ("minority", "consensus", "diversity", "mean_abs_r", "pkg14")} for k, h in calib.items()}
    p = os.path.join(HERE, "viewer", "runs", "fair_summary.js")
    open(p, "w").write("window.FAIR_SUMMARY=" + json.dumps(out, separators=(",", ":")) + ";\n"); return p

if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="python -m jevsociety.fair"); ap.add_argument("exp", choices=["calib", "fine", "main", "tilt", "seeds", "summary"])
    ap.add_argument("--workers", type=int, default=6); ap.add_argument("--only", default=None, help="comma-separated run names")
    a = ap.parse_args()
    if a.exp == "summary": print("wrote", summary()); raise SystemExit
    J = jobs(a.exp)
    if a.only: J = [j for j in J if j[0] in a.only.split(",")]
    with Pool(a.workers) as p:
        for name, rec in p.imap_unordered(one, J):
            merge({name: rec}); h = rec["hist"][-1]
            print(name, "cost", rec["cost_usd"], {k: h.get(k) for k in ("tick", "minority", "diversity", "consensus", "pkg_dist", "cons_side", "wall_s")}, flush=True)
