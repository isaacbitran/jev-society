"""Run the bundling experiment and its controls over many seeds. python -m jevsociety.bundle_suite

Conditions (all on the same grid code, beta 4, noise 0.002, 400 ticks):
  jev       Jev "fit" judgments                 jev_reasons  Jev "reasons" judgments (logic-only wording)
  axelrod   no meaning (switch is a coin flip)  shuffled     Jev "fit" judgments attached to the wrong sentences
Each run is measured at two points: (a) the first snapshot where the society is as sorted as US adults (mean |r|
between issues >= the GSS 2024 value, 0.167), and (b) tick 400. Runs that never get that sorted are reported at their
most sorted snapshot instead. Writes data/bundle_results.json and viewer/runs/bundle_summary.js, plus full recordings
of the 10,000-agent seed-0 runs for the viewer. Takes about a minute; no Jev calls."""
import json, os
import numpy as np
from .bundling import simulate, save, gss, gss_axis, IU, direct, HERE
from .issues import M
from .pairs import load

GSS_ABS = float(np.nanmean(np.abs(gss()[IU])))
CONDS = {"jev": dict(control="none", variant="fit"), "jev_reasons": dict(control="none", variant="reasons"),
         "axelrod": dict(control="axelrod", variant="fit"), "shuffled": dict(control="shuffled", variant="fit"),
         "solo": dict(control="solo", variant="fit")}

def summarize(rec):
    H = rec["hist"]; m = next((h for h in H if h["tick"] > 0 and h["mean_abs_r"] >= GSS_ABS), None)
    matched = m is not None; m = m or max(H[1:], key=lambda h: h["mean_abs_r"]); e = H[-1]
    pick = lambda h: {k: round(h[k], 4) for k in ("tick", "r_gss", "sign_agree", "mean_abs_r", "pc1", "liberal_share", "capture", "cultures")}
    return {"matched_reached": matched, "matched": pick(m), "end": pick(e), "peak_r_gss": round(max(h["r_gss"] for h in H[1:]), 4)}

def stats(xs):
    xs = np.array(xs, float); return {"mean": round(float(xs.mean()), 4), "sd": round(float(xs.std(ddof=1)), 4) if len(xs) > 1 else 0.0,
                                      "min": round(float(xs.min()), 4), "max": round(float(xs.max()), 4), "n": len(xs)}

def main(seeds=10, big_seeds=3):
    G = gss(); g = G[IU]; ok = ~np.isnan(g)
    out = {"gss_mean_abs_r": round(GSS_ABS, 4), "gss_pc1": None, "direct": {}, "runs": {}, "summary": {}}
    Gf = np.nan_to_num(G); np.fill_diagonal(Gf, 1); out["gss_pc1"] = round(float(np.linalg.eigvalsh(Gf)[-1] / len(Gf)), 4)
    for v in ("fit", "reasons"):
        d = direct(np.array(load(v)))[IU]
        out["direct"][v] = {"r_gss": round(float(np.corrcoef(d[ok], g[ok])[0, 1]), 4), "mean_abs": round(float(np.abs(d).mean()), 4)}
    for n, ns in ((1600, seeds), (10000, big_seeds)):
        for c, kw in CONDS.items():
            if n == 10000 and c in ("jev_reasons", "solo"): continue
            rows = []
            for s in range(ns):
                rec = simulate(n, 400, seed=s, snap_every=5, **kw); row = summarize(rec); row["seed"] = s; rows.append(row)
                if n == 10000 and s == 0: save(rec, f"bundle_{c}_10000")
                print(n, c, s, json.dumps(row))
            out["runs"][f"{c}_{n}"] = rows
            out["summary"][f"{c}_{n}"] = {f"{when}_{k}": stats([r[when][k] for r in rows]) for when in ("matched", "end")
                                          for k in ("tick", "r_gss", "sign_agree", "mean_abs_r", "pc1", "liberal_share", "capture")}
            out["summary"][f"{c}_{n}"]["matched_reached"] = sum(r["matched_reached"] for r in rows)
    # sensitivity: switch sharpness beta and drift rate, Jev "fit" condition, 5 seeds each
    out["sensitivity"] = []
    for b in (1, 2, 4, 8, 16):
        for nz in (0.0005, 0.002, 0.008):
            rows = [summarize(simulate(1600, 400, beta=b, noise=nz, seed=s, snap_every=5)) for s in range(5)]
            out["sensitivity"].append({"beta": b, "noise": nz, "reached": sum(r["matched_reached"] for r in rows),
                                       "matched_r_gss": stats([r["matched"]["r_gss"] for r in rows]), "matched_tick": stats([r["matched"]["tick"] for r in rows]),
                                       "end_liberal_share": stats([r["end"]["liberal_share"] for r in rows]), "end_capture": stats([r["end"]["capture"] for r in rows])})
    # side coherence of the judgments: mean fit among statements on the same side of the survey axis (colour/measurement only)
    ax = gss_axis(); lib = np.array([2 * i if ax[i] > 0 else 2 * i + 1 for i in range(M)]); core = [i for i in range(M) if abs(ax[i]) > 0.1]
    out["side_fit"] = {}
    for v in ("fit", "reasons"):
        K = np.array(load(v)); L, C = lib[core], lib[core] ^ 1; mean = lambda A: float(A[A != 0].mean())
        out["side_fit"][v] = {"liberal": round(mean(K[np.ix_(L, L)]), 4), "conservative": round(mean(K[np.ix_(C, C)]), 4), "across": round(mean(K[np.ix_(L, C)]), 4)}
    # live Jev runs (jevsociety.bundling --control live), if recorded
    live = {}
    for f in sorted(os.listdir(os.path.join(HERE, "viewer", "runs"))):
        if f.startswith("bundle_live_"):
            src = open(os.path.join(HERE, "viewer", "runs", f)).read(); rec = json.loads(src[src.index("=", src.index("]")) + 1:].rstrip().rstrip(";"))
            row = summarize(rec); row.update(seed=rec["config"]["seed"], cost_usd=rec["cost_usd"], ticks=rec["hist"][-1]["tick"])
            live.setdefault(f"live_{rec['config']['n']}", []).append(row)
    for key, rows in live.items():
        out["runs"][key] = rows
        out["summary"][key] = {f"{when}_{k}": stats([r[when][k] for r in rows]) for when in ("matched", "end")
                               for k in ("tick", "r_gss", "sign_agree", "mean_abs_r", "pc1", "liberal_share", "capture")}
        out["summary"][key]["matched_reached"] = sum(r["matched_reached"] for r in rows)
    json.dump(out, open(os.path.join(HERE, "data", "bundle_results.json"), "w"), indent=1)
    open(os.path.join(HERE, "viewer", "runs", "bundle_summary.js"), "w").write("window.BUNDLE_SUMMARY=" + json.dumps(out) + ";\n")
    for k, v in out["summary"].items():
        print(f"{k:<20} reached US sorting {v['matched_reached']}  r_gss@match {v['matched_r_gss']['mean']:+.3f} ({v['matched_r_gss']['min']:+.2f}..{v['matched_r_gss']['max']:+.2f})"
              f"  tick {v['matched_tick']['mean']:.0f}  | end: r_gss {v['end_r_gss']['mean']:+.3f} |r| {v['end_mean_abs_r']['mean']:.3f} pc1 {v['end_pc1']['mean']:.2f}"
              f" liberal {v['end_liberal_share']['mean']:.2f} ({v['end_liberal_share']['min']:.2f}..{v['end_liberal_share']['max']:.2f}) capture {v['end_capture']['mean']:.2f}")
    for r in out["sensitivity"]: print(f"beta {r['beta']:>4} noise {r['noise']:<6} reached {r['reached']}/5  r_gss@match {r['matched_r_gss']['mean']:.3f}  liberal end {r['end_liberal_share']['mean']:.2f}")
    print("side fit:", out["side_fit"])
    print("direct (no dynamics):", out["direct"], "GSS mean|r|", out["gss_mean_abs_r"], "GSS pc1", out["gss_pc1"])

if __name__ == "__main__": main()
