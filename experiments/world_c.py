"""World C: gifts and grudges (control).
Rules (each day, every living agent): eat 1 food, forage +1 with p=0.5; then either keep, give 1 to a neighbour (neighbour gets 2),
or take 1 from a neighbour. Each agent remembers the last 3 things each neighbour did to it, as text. Food 0 = death.
mode=jev: Jev chooses the action from temperament + memory + food words. mode=int: tit-for-tat with a per-temperament take probability."""
import random, json, time, argparse
from collections import Counter, deque
from jevsociety import jev as jevlib
TEMPS = ["generous and trusting", "cautious; repays kindness and avoids trouble", "greedy; takes whenever it can get away with it",
         "vengeful; never forgets a slight", "loyal to friends, hostile to strangers", "fair-minded; gives to those in need"]
PTAKE = [0.0, 0.1, 0.6, 0.2, 0.3, 0.05]; PGIVE = [0.6, 0.2, 0.05, 0.1, 0.3, 0.4]
DIRS = ["north", "south", "west", "east"]
def word(f): return "starving" if f <= 1 else "hungry" if f <= 3 else "well fed" if f <= 7 else "rich"
def gini(x):
    x = sorted(x); n = len(x); s = sum(x)
    return 0 if s == 0 else sum((2 * i - n + 1) * v for i, v in enumerate(x)) / (n * s)
def run(N, days, mode, seed, out):
    rng = random.Random(seed); n = N * N
    temp = [rng.randrange(6) for _ in range(n)]; food = [5] * n; alive = [True] * n
    mem = [dict() for _ in range(n)]
    def nb(u):
        x, y = divmod(u, N); r = {}
        for d, (dx, dy) in zip(DIRS, ((-1, 0), (1, 0), (0, -1), (0, 1))):
            if 0 <= x + dx < N and 0 <= y + dy < N and alive[(x + dx) * N + y + dy]: r[d] = (x + dx) * N + y + dy
        return r
    hist, snaps = [], {}
    gifts = Counter()
    for t in range(1, days + 1):
        live = [u for u in range(n) if alive[u]]
        acts = {}
        if mode == "jev":
            qs = {}
            for u in live:
                ns = nb(u); o = {"keep": "Keep your food and do nothing."}
                for d, v in ns.items():
                    o[f"give_{d}"] = f"Give one food to your {d} neighbour (it becomes two for them)."
                    o[f"take_{d}"] = f"Take one food from your {d} neighbour."
                ks = list(o); rng.shuffle(ks)
                qs[f"q{u}"] = {"type": "choice", "instructions": {"your_temperament": TEMPS[temp[u]], "your_food": word(food[u]),
                    "neighbours": {d: {"their_food": word(food[v]), "what_they_did_to_you_recently": list(mem[u].get(v, [])) or ["nothing yet"]} for d, v in ns.items()},
                    "question": "Today you can keep, give to one neighbour, or take from one neighbour. What do you do?"}, "criteria": {k: o[k] for k in ks}}
            ans = jevlib.ask_many(qs, tag=f"C-jev-N{N}")
            for u in live:
                pr = ans[f"q{u}"]["probabilities"]; ks = list(pr); acts[u] = rng.choices(ks, [pr[k] for k in ks])[0]
        else:
            for u in live:
                ns = nb(u); good = [d for d, v in ns.items() if mem[u].get(v) and mem[u][v][-1].startswith("gave")]
                bad = [d for d, v in ns.items() if mem[u].get(v) and mem[u][v][-1].startswith("took")]
                if bad and rng.random() < 0.7: acts[u] = "take_" + rng.choice(bad)
                elif good and rng.random() < 0.7 and food[u] > 2: acts[u] = "give_" + rng.choice(good)
                elif ns and rng.random() < PTAKE[temp[u]]: acts[u] = "take_" + rng.choice(list(ns))
                elif ns and rng.random() < PGIVE[temp[u]] and food[u] > 2: acts[u] = "give_" + rng.choice(list(ns))
                else: acts[u] = "keep"
        nt = ng = 0
        for u in live:
            a = acts[u]
            if a == "keep": continue
            kind, d = a.split("_"); v = nb(u).get(d)
            if v is None: continue
            if kind == "give" and food[u] > 0:
                food[u] -= 1; food[v] += 2; ng += 1; gifts[(u, v)] += 1; ev = f"day {t}: gave you food"
            elif kind == "take" and food[v] > 0:
                food[v] -= 1; food[u] += 1; nt += 1; ev = f"day {t}: took your food"
            else: continue
            mem[v].setdefault(u, deque(maxlen=3)).append(ev)
        for u in live:
            food[u] += (rng.random() < 0.5) - 1
            if food[u] <= 0: alive[u] = False; food[u] = 0
        lv = [u for u in range(n) if alive[u]]
        mutual = sum(1 for (a, b), c in gifts.items() if a < b and gifts.get((b, a), 0) >= 2 and c >= 2)
        surv = {TEMPS[k][:12]: round(sum(alive[u] for u in range(n) if temp[u] == k) / max(1, sum(temp[u] == k for u in range(n))), 2) for k in range(6)}
        m = {"day": t, "alive": len(lv), "gini": round(gini([food[u] for u in lv]), 3), "gives": ng, "takes": nt, "mutual_pairs": mutual, "survival": surv, "spend": round(jevlib.total_spend(), 4)}
        hist.append(m); snaps[t] = {"food": list(food), "alive": list(alive)}
        if t % 10 == 0: print(json.dumps(m), flush=True)
    json.dump({"N": N, "mode": mode, "temp": temp, "hist": hist, "snaps": snaps}, open(out, "w"))
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--N", type=int, default=15); ap.add_argument("--days", type=int, default=40)
    ap.add_argument("--mode", default="jev"); a = ap.parse_args()
    run(a.N, a.days, a.mode, 0, f"runs/C_{a.mode}_N{a.N}.json")
