"""10,000-account live-Jev network runs. python -m jevsociety.live10k --ranker engagement --budget 6 [--seed 0] [--net smallworld] [--switch-at 50]
Fair-test recordings: add --sym (Jev's lean removed) and/or --stubborn 0.26, with --label "Lean removed" (see jevsociety/fair.py).

Same model as jevsociety.netsim (Sim, live mode: every like/adopt probability is a direct Jev Choice question, cached by
(other-15 positions, issue) in data/jev_live_fit.json). 1 tick = 1 day; metrics for all accounts every tick.

The viewer cannot draw 10,000 accounts or lay them out with all-pairs forces, so the recorder draws a fixed random sample
(`--draw`, default 2,500, the same accounts for every run with the same seed and n) laid out on the exposure graph among
drawn accounts (who saw whose posts, weight decays 0.9 per tick). Field layout: viewer/runs/SCHEMA-live10k.md.
Writes viewer/runs/<name>.js, merges the run's metrics into data/net_live10k.json and rewrites viewer/runs/live10k_manifest.js.

Naming: the README and the study page call the `chrono` ranker the random feed (every post in a tick is equally new, so
newest-first reduces to a random 6) and the `engagement` ranker the ranked feed (ranked by predicted likes). One tick = one
day. Identifiers and CLI flags keep the old names for compatibility with recorded runs."""
import argparse, json, os, time
import numpy as np
from .netsim import Sim, camps, layout_step, b64, POW, RANKERS
from .net_suite import KEYS, GSS_ABS
from .bundling import BudgetStop, gss_axis, HERE
from .issues import NAMES, SHORT, STATEMENTS
from . import jev

AT = (1, 10, 25, 50, 75, 100, 150, 200, 300)
DATA = os.path.join(HERE, "data", "net_live10k.json")
MANIFEST = os.path.join(HERE, "viewer", "runs", "live10k_manifest.js")

def summarize(hist):
    out = {}
    for t in AT:
        h = next((h for h in hist if h["tick"] == t), None)
        if h: out[f"t{t}"] = {k: h.get(k) for k in KEYS}
    m = next((h for h in hist if h["tick"] > 0 and h["mean_abs_r"] >= GSS_ABS and h["minority"] >= 0.05), None)
    out["us_level_tick"] = m["tick"] if m else None; out["r_gss_at_us_level"] = round(m["r_gss"], 4) if m else None
    pk = max(hist[1:], key=lambda h: h["mean_abs_r"]) if len(hist) > 1 else hist[0]
    out["peak_sorting"] = round(pk["mean_abs_r"], 4); out["peak_tick"] = pk["tick"]
    out["consensus_tick"] = next((h["tick"] for h in hist if h["tick"] > 0 and h["diversity"] < 0.05), None)
    return out

def run(n=10000, ticks=100, ranker="engagement", seed=0, draw=2500, budget=None, net="random", switch_at=None, frame_every=1, log=print,
        stubborn=0.0, sym=False, label=None):
    t0 = time.time(); sim = Sim(n=n, seed=seed, ranker=ranker, live=True, budget=budget, net=net, stubborn=stubborn, sym=sym); axis = gss_axis()
    k, fd = sim.k, sim.fd
    ids = np.sort(np.random.default_rng(seed + 7).choice(n, draw, replace=False)); D = len(ids)
    pos = np.full(n, -1); pos[ids] = np.arange(D)
    E = np.zeros((D, D), np.float32); P = np.random.default_rng(seed + 99).normal(0, 0.3, (D, 2)).astype(np.float32)
    hist, frames = [], []; cache0 = len(sim.cache)

    def frame():
        nonlocal P
        camp = camps(sim.S)[0]
        if sim.t == 0:
            W = np.zeros((D, D), np.float32); fo = pos[sim.F[ids]]; r, c = np.nonzero(fo >= 0); W[r, fo[r, c]] = 1
        else: W = E
        P = layout_step(P, W + W.T, 60 if sim.t == 0 else 4 * frame_every).astype(np.float32)
        cxy = P - P.mean(0); sc = float(np.abs(cxy).max()) or 1.0
        feed = np.full((D, fd), 65535, np.int64); post = np.full((D, fd), 255, np.int64); like = np.zeros(D, np.int64); adopt = np.full(D, 255, np.int64)
        L = sim.last
        if "shown" in L:
            sh = L["shown"][ids]; order = np.argsort(~sh, axis=1, kind="stable")[:, :fd]; rr = np.arange(D)[:, None]
            ok = sh[rr, order]
            feed[ok] = L["Fc"][ids][rr, order][ok]; post[ok] = L["Xc"][ids][rr, order][ok]
            lk = L["L"][ids][rr, order] & ok; like = (lk * (1 << np.arange(fd))).sum(1)
            g = L["go"][ids]; adopt[g] = L["ii"][ids][g]
        own = (camp[sim.F[ids]] == camp[ids][:, None]).sum(1)
        frames.append({"tick": sim.t, "S": b64(sim.S.astype(np.int64) @ POW, "<u2"), "camp": b64(np.packbits(camp.astype(np.uint8), bitorder="little"), "u1"),
                       "xy": b64(np.round(cxy / sc * 32000), "<i2"), "fol": b64(sim.F[ids], "<u2"), "fown": b64(own, "u1"),
                       "feed": b64(feed, "<u2"), "post": b64(post, "u1"), "like": b64(like, "u1"), "adopt": b64(adopt, "u1"),
                       "sil": b64((sim.A[ids] < sim.sil_t).astype(np.int64) @ POW, "<u2")})

    def snap(force=False):
        m = sim.metrics(axis); m["cost_usd"] = round((jev.STATS["tokens"] - sim.tok0) * jev.PRICE, 4)
        m["cache"] = len(sim.cache); m["wall_s"] = round(time.time() - t0, 1)
        m["chrono_share"] = float((sim.rank == 0).mean())
        m = {a: (round(b, 4) if isinstance(b, float) else b) for a, b in m.items()}; hist.append(m)
        if sim.t % frame_every == 0 or force: frame()
        log(json.dumps({a: m[a] for a in ("tick", "mean_abs_r", "minority", "agree_exposure", "cross_ties", "silent", "unfollows", "cost_usd", "cache", "wall_s")}), flush=True)

    stopped = None; snap()
    for t in range(1, ticks + 1):
        if switch_at and t == switch_at: sim.rank[:] = 0
        try: sim.step()
        except (BudgetStop, RuntimeError) as e:
            stopped = f"tick {t - 1}: {type(e).__name__} {str(e)[:160]}"; sim.t = t - 1; log("stopping at " + stopped, flush=True); break
        E *= 0.9; sh = sim.last["shown"][ids]; vv, jj = np.nonzero(sh); aa = pos[sim.last["Fc"][ids][vv, jj]]; ok = aa >= 0
        np.add.at(E, (vv[ok], aa[ok]), 1.0)
        snap()
        if t % 2 == 0: sim.save_cache()
    if stopped and frames[-1]["tick"] != sim.t: frame()
    sim.save_cache()
    cfg = dict(n=n, ticks=ticks, ticks_done=sim.t, ranker=ranker, seed=seed, k=k, feed=fd, beta="live", noise=sim.noise, unfollow=sim.unf,
               recommend=sim.rec, silence=sim.sil_t, net=net, drawn=D, switch_to_chrono_at=switch_at, day_per_tick=1, frame_every=frame_every,
               stubborn=stubborn, sym=sym, label=label)
    rec = {"fmt": "live10k-1", "config": cfg, "cost_usd": round((jev.STATS["tokens"] - sim.tok0) * jev.PRICE, 4), "stopped": stopped,
           "new_answers": len(sim.cache) - cache0, "issues": NAMES, "short": SHORT, "statements": STATEMENTS,
           "axis": np.round(axis, 4).tolist(), "drawn": b64(ids, "<u2"), "hist": hist, "frames": frames}
    return rec

def compact(rec):
    """live10k-1 -> live10k-2, the format the viewer ships (about 7 MB instead of 25 MB per run). Drops the per-frame fields the
    viewer recomputes or never reads (`xy`: the browser lays the graph out itself; `camp`, `fown`), and stores `S` and `fol`
    in full only on frame 0; later frames hold just the entries that changed since the previous frame (`dS`, `dfol`: base64
    `<u4` pairs, index then new value). See viewer/runs/SCHEMA-live10k.md."""
    if rec.get("fmt") != "live10k-1": return rec
    import base64
    dec = lambda s, dt: np.frombuffer(base64.b64decode(s), dt)
    out, prev = [], {}
    for i, f in enumerate(rec["frames"]):
        g = {k: v for k, v in f.items() if k not in ("xy", "camp", "fown", "S", "fol")}
        for k, dk in (("S", "dS"), ("fol", "dfol")):
            a = dec(f[k], "<u2")
            if i == 0: g[k] = f[k]
            else: ch = np.flatnonzero(a != prev[k]); g[dk] = b64(np.stack([ch, a[ch]], 1).ravel(), "<u4")
            prev[k] = a
        out.append(g)
    return {**rec, "fmt": "live10k-2", "frames": out}

def save(rec, name, frames=True):
    out = os.path.join(HERE, "viewer", "runs", f"{name}.js")
    if frames: open(out, "w").write(f"window.NETS=window.NETS||{{}};window.NETS[{json.dumps(name)}]=" + json.dumps(compact(rec), separators=(",", ":")) + ";\n")
    d = json.load(open(DATA)) if os.path.exists(DATA) else {"note": "10,000-account live-Jev network runs (jevsociety/live10k.py). hist = every tick, all accounts.", "runs": {}}
    d["runs"][name] = {"config": rec["config"], "cost_usd": rec["cost_usd"], "new_answers": rec["new_answers"], "stopped": rec["stopped"],
                       "summary": summarize(rec["hist"]), "hist": rec["hist"]}
    json.dump(d, open(DATA, "w"), indent=1)
    man = [{"name": k, "file": f"runs/{k}.js" if os.path.exists(os.path.join(HERE, "viewer", "runs", f"{k}.js")) else None, **{a: v["config"][a] for a in ("ranker", "n", "ticks_done", "seed", "net", "drawn", "switch_to_chrono_at")},
            **{a: v["config"].get(a, d) for a, d in (("stubborn", 0.0), ("sym", False), ("label", None))},
            "cost_usd": v["cost_usd"], "stopped": v["stopped"], "summary": {a: v["summary"][a] for a in ("us_level_tick", "r_gss_at_us_level", "peak_sorting", "consensus_tick")},
            "final": v["hist"][-1]} for k, v in d["runs"].items()]
    open(MANIFEST, "w").write("window.LIVE10K_MANIFEST=" + json.dumps(man, separators=(",", ":")) + ";\n")
    return out, os.path.getsize(out) if os.path.exists(out) else 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="python -m jevsociety.live10k")
    ap.add_argument("--n", type=int, default=10000); ap.add_argument("--ticks", type=int, default=100)
    ap.add_argument("--ranker", choices=RANKERS[:2], default="engagement"); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--draw", type=int, default=2500); ap.add_argument("--budget", type=float, required=True, help="USD cap for this run")
    ap.add_argument("--net", choices=["random", "smallworld"], default="random"); ap.add_argument("--switch-at", type=int, default=None)
    ap.add_argument("--frame-every", type=int, default=1, help="record a viewer frame every this many ticks (metrics: every tick)")
    ap.add_argument("--stubborn", type=float, default=0.0, help="anchoring: per-tick chance of moving one changed position back (netsim.Sim)")
    ap.add_argument("--sym", action="store_true", help="remove Jev's lean: P_sym(x | S) = (P(x | S) + P(not x | not S)) / 2")
    ap.add_argument("--label", default=None, help="short label for the viewer")
    ap.add_argument("--name", default=None); ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--metrics-only", action="store_true", help="write metrics to data/net_live10k.json but no viewer file")
    a = ap.parse_args()
    rec = run(a.n, a.ticks, a.ranker, a.seed, a.draw, a.budget, a.net, a.switch_at, a.frame_every, stubborn=a.stubborn, sym=a.sym, label=a.label)
    print("cost USD", rec["cost_usd"], "new answers", rec["new_answers"], "stopped", rec["stopped"], flush=True)
    if not a.no_save:
        name = a.name or f"net_live10k_{a.ranker}"; out, size = save(rec, name, not a.metrics_only); print("wrote", out, size // 1024, "KB", flush=True)
