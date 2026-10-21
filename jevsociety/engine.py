"""Semantic culture: Axelrod's (1997) dissemination-of-culture model where every trait is a real belief sentence.

The four rules, applied to every agent each tick:
  1. Meet a random neighbour.
  2. Jev scores how much the two of you agree overall (0 to 4).
  3. With probability openness * agreement / 4, adopt one of their beliefs you don't hold.
  4. Jev picks which of your current beliefs conflicts most with the new one; you drop it.

rule="axelrod" swaps Jev for the classic integer version: agreement = shared sentences / k, drop a random unshared belief.


Naming: the README and the study page call one tick of this model a round."""
import json, os, pickle, random, time
from collections import Counter
from . import jev
from .beliefs import POOL as DEFAULT_POOL, POLE, TOPIC, POOLS

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache"); os.makedirs(CACHE_DIR, exist_ok=True)

class ScoreCache:
    """Raw Jev answers persisted across runs (keyed by pool name + sorted belief tuples). The bias knob is applied
    after lookup, so every sweep setting reuses the same answers and only pays for pairs it has not seen."""
    def __init__(self, name="politics"):
        self.path = os.path.join(CACHE_DIR, f"jev_mock_{name}.pkl" if jev.MOCK else f"jev_{name}.pkl")
        self.d = pickle.load(open(self.path, "rb")) if os.path.exists(self.path) else {"score": {}, "choice": {}}
    def get(self, u, v): return self.d["score"].get((u, v))
    def put(self, u, v, s): self.d["score"][(u, v)] = s
    def save(self):
        if os.path.exists(self.path):  # merge with entries written by runs in parallel processes
            old = pickle.load(open(self.path, "rb"))
            for k in ("score", "choice"): old[k].update(self.d[k]); self.d[k].update(old[k])
        tmp = f"{self.path}.{os.getpid()}.tmp"; pickle.dump(self.d, open(tmp, "wb")); os.replace(tmp, self.path)

def drop_rates():
    p = os.path.join(CACHE_DIR, "calib_drop.json")
    return json.load(open(p))["rates"] if os.path.exists(p) else {}

def calib_e():
    p = os.path.join(CACHE_DIR, "calib.json")
    return json.load(open(p))["e"] if os.path.exists(p) else 0.0

LEVELS = ["They disagree on almost everything", "They mostly disagree", "Mixed: they agree on some things and disagree on others", "They mostly agree", "They agree on almost everything"]

def agree_q(a, b, pool):
    return {"type": "score", "instructions": {"person_a_believes": [pool[i] for i in a], "person_b_believes": [pool[i] for i in b],
            "question": "Taking all their beliefs into account, how much would person A and person B agree with each other overall about how society should be?"}, "criteria": LEVELS}

def conflict_q(a, new, pool, rng=None):
    order = list(a); random.Random(hash((tuple(sorted(a)), new))).shuffle(order)  # shuffle: Jev leans toward the first option
    return order, {"type": "choice", "instructions": {"current_beliefs": [pool[i] for i in order], "new_belief": pool[new],
        "question": "This person is adopting `new_belief`. Which one of their current beliefs conflicts most with `new_belief`? If none conflicts, pick the one least related to it."},
        "criteria": {str(j): pool[i] for j, i in enumerate(order)}}

def build_network(n, rewire, rng):
    """2-D grid (square, no wrap) with Watts-Strogatz rewiring: each edge is moved to a random agent with prob `rewire`."""
    side = int(round(n ** 0.5)); assert side * side == n, "population must be a square number"
    nb = [set() for _ in range(n)]
    for u in range(n):
        x, y = divmod(u, side)
        for dx, dy in ((1, 0), (0, 1)):
            if x + dx < side and y + dy < side:
                v = (x + dx) * side + y + dy
                if rng.random() < rewire: v = rng.randrange(n)
                if v != u: nb[u].add(v); nb[v].add(u)
    return side, [sorted(s) for s in nb]

class Society:
    def __init__(self, n=400, k=5, openness=1.0, rewire=0.0, rule="jev", seed=0, pool="politics", budget_usd=None, lean_fix=0.0, drop_gap=1.0):
        self.rng = random.Random(seed); self.pool_name = pool; self.pool = POOLS[pool]; self.k = k
        # lean_fix: 0 = raw Jev, 1 = measured side lean subtracted (neutralized), 2 = lean reversed, -1 = lean doubled
        self.lean_fix, self.e = lean_fix, (calib_e() if pool == "politics" else 0.0)
        self.cache = ScoreCache(pool)
        # drop_gap scales the measured side gap in drop-rule coherence: 1 = raw Jev, 0 = both sides equally coherent,
        # -1 = gap reversed, 2 = gap doubled. Applied as a post-hoc random override of Jev's pick (rng2, so the main RNG is untouched).
        self.drop_gap, self.rates, self.rng2 = drop_gap, (drop_rates() if pool == "politics" and drop_gap != 1.0 else {}), random.Random(seed + 99)
        self.openness, self.rule, self.budget = openness, rule, budget_usd
        self.side, self.nb = build_network(n, rewire, self.rng)
        self.n = n; self.tick = 0
        self.B = [self.rng.sample(range(len(self.pool)), k) for _ in range(n)]
        self.choice_cache = self.cache.d["choice"]
        self.cfg = dict(n=n, k=k, openness=openness, rewire=rewire, rule=rule, seed=seed, pool=pool, lean_fix=lean_fix, drop_gap=drop_gap,
                        injected_lean_points=round(-(1 - lean_fix) * self.e * 8, 4) if pool == "politics" else None)

    def adjust_drop(self, bu, new, drop):
        if not self.rates: return drop
        opp = [b for b in bu if POLE[b] != POLE[new]]; same = [b for b in bu if POLE[b] == POLE[new]]
        key = f"{POLE[new]},{len(opp)}"; other = f"{-POLE[new]},{len(opp)}"
        if not opp or not same or key not in self.rates or other not in self.rates: return drop
        r, mean = self.rates[key], (self.rates[key] + self.rates[other]) / 2
        t = min(1.0, max(0.0, mean + self.drop_gap * (r - mean)))
        if t > r and POLE[drop] == POLE[new] and self.rng2.random() < (t - r) / (1 - r): return self.rng2.choice(opp)
        if t < r and POLE[drop] != POLE[new] and self.rng2.random() < (r - t) / r: return self.rng2.choice(same)
        return drop

    def agreement(self, bu, bv):
        a = self.cache.get(bu, bv) / 4
        if self.lean_fix and self.e:
            m = (sum(POLE[i] for i in bu) + sum(POLE[i] for i in bv)) / (2 * self.k)
            a -= self.lean_fix * self.e * m
        return min(1.0, max(0.0, a))

    def step(self):
        rng, B, pool = self.rng, self.B, self.pool
        pairs = []
        for u in range(self.n):
            if not self.nb[u]: continue
            v = rng.choice(self.nb[u])
            if set(B[u]) != set(B[v]): pairs.append((u, v))
        if self.rule == "jev":
            need = {}
            keys = [(tuple(sorted(B[u])), tuple(sorted(B[v]))) for u, v in pairs]
            for key in keys:
                if self.cache.get(*key) is None and key not in need: need[key] = agree_q(key[0], key[1], pool)
            ids = list(need)
            if ids:
                ans = jev.ask_many({f"s{i}": need[key] for i, key in enumerate(ids)}, tag=f"society-{self.n}")
                for i, key in enumerate(ids): self.cache.put(*key, ans[f"s{i}"]["score"])
            agr = [self.agreement(*key) for key in keys]
        else:
            agr = [len(set(B[u]) & set(B[v])) / self.k for u, v in pairs]
        adopt = []
        for (u, v), a in zip(pairs, agr):
            if rng.random() < min(1.0, self.openness * a):
                adopt.append((u, rng.choice([s for s in B[v] if s not in B[u]]), v))
        if self.rule == "jev":
            need, meta = {}, {}
            for idx, (u, new, v) in enumerate(adopt):
                key = (frozenset(B[u]), new)
                if key not in self.choice_cache and key not in meta.values():
                    order, q = conflict_q(B[u], new, pool, rng); need[f"c{idx}"] = q; meta[f"c{idx}"] = (key, order)
            if need:
                ans = jev.ask_many(need, tag=f"society-{self.n}")
                for qid, (key, order) in meta.items(): self.choice_cache[key] = order[int(ans[qid]["choice"])]
            drops = [self.adjust_drop(B[u], new, self.choice_cache[(frozenset(B[u]), new)]) for u, new, v in adopt]
        else:
            drops = [rng.choice([s for s in B[u] if s not in B[v]]) for u, new, v in adopt]
        for (u, new, v), d in zip(adopt, drops):
            if new not in B[u]: B[u] = [new if s == d else s for s in B[u]]
        self.tick += 1
        return len(pairs), len(adopt)

    def metrics(self):
        B, k = self.B, self.k
        sets = Counter(frozenset(b) for b in B)
        lr = [sum(POLE[i] for i in b) / k for b in B] if self.pool_name == "politics" else None
        m = {"tick": self.tick, "cultures": len(sets), "largest_culture": round(sets.most_common(1)[0][1] / self.n, 4)}
        if lr:
            same = tot = 0
            for b in B:
                for i in range(k):
                    for j in range(i + 1, k): tot += 1; same += POLE[b[i]] == POLE[b[j]]
            m.update(mean_lr=round(sum(lr) / len(lr), 4), polarization=round(sum(map(abs, lr)) / len(lr), 4), constraint=round(same / tot, 4),
                     traditional_share=round(sum(x > 0 for x in lr) / len(lr), 4))
        return m

def run(n=400, ticks=60, k=5, openness=1.0, rewire=0.0, rule="jev", seed=0, snap_every=2, out=None, budget_usd=None, log=print, pool="politics", lean_fix=0.0, drop_gap=1.0):
    s = Society(n, k, openness, rewire, rule, seed, pool, lean_fix=lean_fix, drop_gap=drop_gap)
    sets, set_id, frames, hist = [], {}, [], []
    def snap():
        ids = []
        for b in s.B:
            key = tuple(sorted(b))
            if key not in set_id: set_id[key] = len(sets); sets.append(list(key))
            ids.append(set_id[key])
        frames.append({"tick": s.tick, "agents": ids})
    snap(); hist.append(s.metrics()); t0 = time.time(); tok0 = jev.STATS["tokens"]
    spent = lambda: (jev.STATS["tokens"] - tok0) * jev.PRICE
    for t in range(ticks):
        pairs, adopts = s.step()
        m = s.metrics(); m.update(pairs=pairs, adoptions=adopts, run_usd=round(spent(), 4), sec=round(time.time() - t0, 1))
        hist.append(m)
        if s.tick % snap_every == 0 or t == ticks - 1: snap()
        log(json.dumps(m))
        if s.rule == "jev" and s.tick % 5 == 0: s.cache.save()
        if budget_usd and spent() > budget_usd: log("budget reached, stopping"); snap(); break
        if pairs == 0: break
    if s.rule == "jev": s.cache.save()
    from .beliefs import SHORT, TOPICS
    rec = {"config": s.cfg, "pool": s.pool, "short": SHORT[pool], "topic": TOPICS[pool], "tags": {"topic": TOPIC, "pole": POLE} if pool == "politics" else None,
           "side": s.side, "sets": sets, "frames": frames, "hist": hist,
           "cost_usd": round(spent(), 4), "calls": jev.STATS["calls"], "tokens": jev.STATS["tokens"]}
    if out:
        name = os.path.splitext(os.path.basename(out))[0]
        with open(out, "w") as f:
            if out.endswith(".js"): f.write(f"window.RUNS=window.RUNS||{{}};window.RUNS[{json.dumps(name)}]=" + json.dumps(rec, separators=(",", ":")) + ";\n")
            else: json.dump(rec, f, separators=(",", ":"))
    return rec
