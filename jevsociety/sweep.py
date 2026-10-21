"""Collect the bias-sweep runs (data/bias_sweep/, 1,600 agents, 4 seeds per lean setting) into viewer/runs/sweep.js and print
the table. python -m jevsociety.sweep. New sweep runs are written to viewer/runs/ by python -m jevsociety; move them to
data/bias_sweep/ to include them."""
import glob, json, os
from .render import load
from .beliefs import SHORT, TOPICS
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); RUNS = os.path.join(HERE, "viewer", "runs"); SWEEP_DIR = os.path.join(HERE, "data", "bias_sweep")
TICK = 24  # every sweep run reached this tick before its budget cap; compare all at the same tick
LABELS = {-1.0: "reversed", 0.0: "neutralized", 0.5: "half", 1.0: "raw Jev", 2.0: "doubled"}

def main():
    rates = json.load(open(os.path.join(HERE, "cache", "calib_drop.json")))["rates"]
    raw_gap = sum(rates[f"-1,{k}"] - rates[f"1,{k}"] for k in range(1, 5)) / 4 * 100  # points of drop coherence, progressive minus traditional
    pts = []
    for p in sorted(glob.glob(os.path.join(SWEEP_DIR, "sweep_1600_gap*.js"))):
        R = load(p); c = R["config"]; h = next(x for x in R["hist"] if x["tick"] == TICK)
        row = dict(name=os.path.basename(p)[:-3], gap=c.get("drop_gap", 1.0), lean_fix=c.get("lean_fix", 0.0), tick=h["tick"],
                   blue=round(1 - h["traditional_share"], 4), consistency=h["constraint"], cultures=h["cultures"], usd=R["cost_usd"], seed=c.get("seed", 0))
        row["lean_pts"] = round(row["gap"] * raw_gap, 1); row["label"] = LABELS.get(row["gap"], str(row["gap"])) + (" + score fix" if row["lean_fix"] else "")
        pts.append(row)
    runs = [r for r in pts if not r["lean_fix"]]
    main_pts = []  # one point per setting: mean over seeds, with min, max and SD
    for g in sorted({r["gap"] for r in runs}):
        rs = [r for r in runs if r["gap"] == g]; bl = [r["blue"] for r in rs]; m = sum(bl) / len(bl)
        sd = (sum((x - m) ** 2 for x in bl) / (len(bl) - 1)) ** 0.5 if len(bl) > 1 else 0.0
        main_pts.append(dict(gap=g, label=rs[0]["label"], lean_pts=rs[0]["lean_pts"], tick=TICK, n_seeds=len(rs), blue=round(m, 4),
                             lo=min(bl), hi=max(bl), sd=round(sd, 4), consistency=round(sum(r["consistency"] for r in rs) / len(rs), 4),
                             runs=[dict(name=r["name"], seed=r["seed"], blue=r["blue"]) for r in rs]))
        print(f'{main_pts[-1]["label"]:<12} n={len(rs)} mean {m*100:.1f}% range {min(bl)*100:.1f}-{max(bl)*100:.1f}% sd {sd*100:.1f} consistency {main_pts[-1]["consistency"]*100:.0f}%  seeds {[r["seed"] for r in rs]}')
    out = dict(points=main_pts, extra=[r for r in pts if r["lean_fix"]], raw_gap_pts=raw_gap, rates=rates, n=1600, tick=TICK)
    open(os.path.join(RUNS, "sweep.js"), "w").write("window.SWEEP=" + json.dumps(out) + ";\n")
if __name__ == "__main__": main()
