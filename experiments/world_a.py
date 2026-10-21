"""World A: semantic culture (Axelrod 1997 with real beliefs).
Rules (each tick, every agent):
 1. Meet a random grid neighbour.
 2. Jev scores how much you agree overall (0..4).  [mode=overlap: shared sentences / 5]
 3. With probability f(agreement) you adopt one of their beliefs you don't hold.
 4. Jev chooses which of your beliefs conflicts most with it; that one is dropped. [overlap: random one]
"""
import random, json, sys, time, argparse, os
from collections import Counter
from jevsociety.beliefs import POOL, TOPIC, POLE
from jevsociety import jev as jevlib

LEVELS = ["They disagree on almost everything", "They mostly disagree", "Mixed: they agree on some things and disagree on others", "They mostly agree", "They agree on almost everything"]
K = 5

def agree_q(a, b):
    return {"type": "score", "instructions": {"person_a_believes": [POOL[i] for i in a], "person_b_believes": [POOL[i] for i in b],
            "question": "Taking all their beliefs into account, how much would person A and person B agree with each other overall about how society should be?"}, "criteria": LEVELS}

def conflict_q(a, new, rng):
    order = list(a); rng.shuffle(order)
    return order, {"type": "choice", "instructions": {"current_beliefs": [POOL[i] for i in order], "new_belief": POOL[new],
        "question": "This person is adopting `new_belief`. Which one of their current beliefs conflicts most with `new_belief`? If none conflicts, pick the one least related to it."},
        "criteria": {str(j): POOL[i] for j, i in enumerate(order)}}

def metrics(B, N):
    sets = [frozenset(b) for b in B]
    c = Counter(sets)
    # connected regions of identical sets
    seen = [False] * len(B); regions = 0
    for s in range(len(B)):
        if seen[s]: continue
        regions += 1; stack = [s]; seen[s] = True
        while stack:
            u = stack.pop(); x, y = divmod(u, N)
            for v in nbrs(u, N):
                if not seen[v] and sets[v] == sets[u]: seen[v] = True; stack.append(v)
    lr = [sum(POLE[i] for i in b) / K for b in B]
    same = tot = contra = 0
    for b in B:
        bl = list(b)
        for i in range(K):
            for j in range(i + 1, K):
                tot += 1; same += POLE[bl[i]] == POLE[bl[j]]
                if TOPIC[bl[i]] == TOPIC[bl[j]] and POLE[bl[i]] != POLE[bl[j]]: contra += 1
    return {"distinct_sets": len(c), "largest_culture": c.most_common(1)[0][1] / len(B), "regions": regions,
            "mean_lr": sum(lr) / len(lr), "polarization": sum(abs(x) for x in lr) / len(lr),
            "constraint": same / tot, "contradictions_per_agent": contra / len(B)}

def nbrs(u, N):
    x, y = divmod(u, N); out = []
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if 0 <= x + dx < N and 0 <= y + dy < N: out.append((x + dx) * N + y + dy)
    return out

def run(N, ticks, mode, seed, prob, out, snap_every=5):
    rng = random.Random(seed)
    B = [rng.sample(range(len(POOL)), K) for _ in range(N * N)]
    score_cache, choice_cache = {}, {}
    hist, snaps = [], {0: [list(b) for b in B]}
    hist.append({"tick": 0, **metrics(B, N)})
    t0 = time.time()
    for t in range(1, ticks + 1):
        pairs = []
        for u in range(N * N):
            v = rng.choice(nbrs(u, N))
            if set(B[u]) != set(B[v]): pairs.append((u, v))
        # step 2: agreement
        if mode == "jev":
            need = {}
            for u, v in pairs:
                key = (frozenset(B[u]), frozenset(B[v]))
                if key not in score_cache and key not in need: need[key] = agree_q(sorted(B[u]), sorted(B[v]))
            ids = list(need); qs = {f"s{i}": need[k] for i, k in enumerate(ids)}
            if qs:
                ans = jevlib.ask_many(qs, tag=f"A-{mode}-N{N}")
                for i, k in enumerate(ids): score_cache[k] = ans[f"s{i}"]["score"] / 4
            agr = [score_cache[(frozenset(B[u]), frozenset(B[v]))] for u, v in pairs]
        else:
            agr = [len(set(B[u]) & set(B[v])) / K for u, v in pairs]
        # step 3: adopt?
        adopt = []
        for (u, v), a in zip(pairs, agr):
            p = a if prob == "linear" else max(0.0, (a - 0.25) / 0.75)
            if rng.random() < p:
                cand = [s for s in B[v] if s not in B[u]]
                adopt.append((u, rng.choice(cand), v))
        # step 4: drop
        if mode == "jev":
            need = {}; meta = {}
            for idx, (u, new, v) in enumerate(adopt):
                key = (frozenset(B[u]), new)
                if key not in choice_cache:
                    order, q = conflict_q(B[u], new, rng); need[f"c{idx}"] = q; meta[f"c{idx}"] = (key, order)
            if need:
                ans = jevlib.ask_many(need, tag=f"A-{mode}-N{N}")
                for qid, (key, order) in meta.items(): choice_cache[key] = order[int(ans[qid]["choice"])]
            drops = [choice_cache[(frozenset(B[u]), new)] for u, new, v in adopt]
        elif mode == "tagged":  # hand-labelled baseline: drop same-topic opposite if present, else random
            drops = []
            for u, new, v in adopt:
                opp = [s for s in B[u] if TOPIC[s] == TOPIC[new] and s not in B[v]]
                drops.append(opp[0] if opp else rng.choice([s for s in B[u] if s not in B[v]]))
        else:
            drops = [rng.choice([s for s in B[u] if s not in B[v]]) for u, new, v in adopt]  # Axelrod: keep shared traits
        for (u, new, v), d in zip(adopt, drops):
            if new in B[u]: continue
            B[u] = [new if s == d else s for s in B[u]]
        m = metrics(B, N); m.update({"tick": t, "pairs": len(pairs), "adoptions": len(adopt), "spend": round(jevlib.total_spend(), 4), "sec": round(time.time() - t0, 1)})
        hist.append(m)
        if t % snap_every == 0 or t == ticks: snaps[t] = [list(b) for b in B]
        if t % 5 == 0: print(json.dumps({k: (round(x, 3) if isinstance(x, float) else x) for k, x in m.items()}), flush=True)
        if not pairs: break
    json.dump({"N": N, "mode": mode, "seed": seed, "prob": prob, "hist": hist, "snaps": snaps, "pool": POOL,
               "score_cache_size": len(score_cache)}, open(out, "w"))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--N", type=int, default=20); ap.add_argument("--ticks", type=int, default=60)
    ap.add_argument("--mode", default="jev"); ap.add_argument("--seed", type=int, default=0); ap.add_argument("--prob", default="linear")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = a.out or f"runs/A_{a.mode}_N{a.N}_s{a.seed}_{a.prob}.json"
    run(a.N, a.ticks, a.mode, a.seed, a.prob, out)
    print("spend total", round(jevlib.total_spend(), 4))
