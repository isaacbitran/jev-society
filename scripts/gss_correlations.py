"""Issue-issue correlations among US adults from the General Social Survey 2024 (NORC; gss.norc.org, Stata release R3a).

    pip install pandas && python scripts/gss_correlations.py path/to/GSS2024.dta

Each item is recoded to 1 (statement A) / 0 (statement B) as listed in jevsociety/issues.py; middle answers and
missing values are dropped. For every pair of issues it computes the weighted Pearson (phi) correlation over
respondents who answered both (weight WTSSPS), keeping pairs with at least 150 joint respondents. GSS asks many items
on split ballots, so some pairs are never asked together and are left out. Writes data/gss2024_corr.json."""
import json, os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
from jevsociety.issues import ISSUES, NAMES, M

def main(path):
    d = pd.read_stata(path, convert_categoricals=False)
    w = d["wtssps"].fillna(0).to_numpy()
    X = np.full((len(d), M), np.nan)
    for j, (name, var, a, b, *_) in enumerate(ISSUES):
        v = d[var].to_numpy(); X[np.isin(v, a), j] = 1; X[np.isin(v, b), j] = 0
    R = np.full((M, M), np.nan); N = np.zeros((M, M), int); share = []
    for i in range(M):
        ok = ~np.isnan(X[:, i]) & (w > 0); share.append(float(np.average(X[ok, i], weights=w[ok])))
        for j in range(M):
            ok = ~np.isnan(X[:, i]) & ~np.isnan(X[:, j]) & (w > 0); N[i, j] = ok.sum()
            if i != j and N[i, j] >= 150:
                x, y, ww = X[ok, i], X[ok, j], w[ok]
                mx, my = np.average(x, weights=ww), np.average(y, weights=ww)
                c = np.average((x - mx) * (y - my), weights=ww)
                R[i, j] = c / np.sqrt(np.average((x - mx) ** 2, weights=ww) * np.average((y - my) ** 2, weights=ww))
    out = {"source": "General Social Survey 2024 (NORC at the University of Chicago), GSS2024.dta release R3a, weight WTSSPS",
           "issues": NAMES, "r": [[None if np.isnan(x) else round(float(x), 4) for x in row] for row in R], "n": N.tolist(),
           "share_A": [round(s, 4) for s in share]}
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, "data", "gss2024_corr.json"), "w"), indent=1)
    k = ~np.isnan(R[np.triu_indices(M, 1)])
    print(f"{k.sum()} of {k.size} issue pairs have >=150 joint respondents; mean |r| = {np.nanmean(np.abs(R[np.triu_indices(M, 1)])):.3f}")
    for i in range(M): print(f"{NAMES[i]:<20} share A {share[i]:.2f}  " + " ".join("  .  " if np.isnan(x) else f"{x:+.2f}" for x in R[i]))

if __name__ == "__main__": main(sys.argv[1])
