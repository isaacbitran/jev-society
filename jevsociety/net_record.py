"""Record the network runs shown in viewer/net.html. python -m jevsociety.net_record

Seed 0, 1,000 agents, 300 ticks, snapshot every 4 ticks, laid out on the exposure graph. No Jev calls; about 5 minutes.
The live runs (400 agents) are recorded separately by `python -m jevsociety.netsim --live --record` (see README).

Naming: the README and the study page call the `chrono` ranker the random feed (every post in a tick is equally new, so
newest-first reduces to a random 6) and the `engagement` ranker the ranked feed (ranked by predicted likes). One tick = one
day. Identifiers and CLI flags keep the old names for compatibility with recorded runs."""
import time
from .netsim import run, save

def switch_at(t0, ranker=0):
    def f(sim, t):
        if t == t0: sim.rank[:] = ranker
    return f

RUNS = {
    "net_chrono": dict(ranker="chrono"), "net_engagement": dict(ranker="engagement"),
    "net_bridging": dict(ranker="bridging"), "net_outrage": dict(ranker="outrage"),
    "net_chrono_beta32": dict(ranker="chrono", beta=32.0), "net_engagement_beta32": dict(ranker="engagement", beta=32.0),
    "net_chrono_axelrod": dict(ranker="chrono", control="axelrod"), "net_engagement_axelrod": dict(ranker="engagement", control="axelrod"),
    "net_switch": dict(ranker="engagement", schedule=switch_at(201)), "net_switch_beta32": dict(ranker="engagement", beta=32.0, schedule=switch_at(201)),
}

if __name__ == "__main__":
    t0 = time.time()
    for name, kw in RUNS.items():
        rec, _ = run(1000, 300, seed=0, snap_every=4, record=True, **kw)
        rec["config"].pop("schedule", None)
        if "schedule" in kw: rec["config"]["switch_to_chrono_at"] = 201
        print("wrote", save(rec, name), f"({time.time() - t0:.0f} s)", flush=True)
