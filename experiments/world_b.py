"""World B: telephone myths.
Rules:
 1. Every tick, each agent that knows the story tells it to one random neighbour.
 2. When retelling, the teller may leave out one sentence or swap one for a sentence from its own worldview (Jev picks which sentence, then what to do with it; sampled from Jev's probabilities).
 3. A listener who already knows a version keeps whichever version it believes more (Jev choice). Otherwise it takes the new one.
mode=random: same rules, but code picks uniformly at random (mutation rate matched to Jev's).
"""
import random, json, time, argparse
from collections import Counter
from jevsociety import jev as jevlib

WORLDVIEWS = {
 "devout": ["Everything happens by the will of the gods.", "Pride is always punished.", "Prayer at the temple brings rain.", "Strangers may be spirits in disguise.", "The dead watch over the living."],
 "merchant": ["Every gift expects a gift in return.", "Gold is worth more than promises.", "A clever bargain beats a strong arm.", "The sea rewards the bold.", "Never trust a deal you did not sign."],
 "warrior": ["Only the strong are remembered.", "An insult must be answered with a blade.", "The king's word is law.", "Cowards die many times before their death.", "Blood ties come before everything."],
 "farmer": ["The land feeds those who work it.", "Most wonders have a plain explanation.", "Rich men cheat the poor.", "Patience grows more than ambition.", "Water is more precious than gold."],
}
REGION_NAMES = ["devout", "merchant", "warrior", "farmer"]  # NW, NE, SW, SE quadrants
STORY = ["A fisherman pulled a golden fish from the river.", "The fish spoke and offered him three wishes.", "He wished first for a new boat.",
         "His wife made him wish for a palace.", "The river turned black when he asked to rule the sky.", "The next morning he was back in his old hut."]
ALL = STORY + [s for w in WORLDVIEWS.values() for s in w]
SID = {s: i for i, s in enumerate(ALL)}  # sentence id

def region(u, N):
    x, y = divmod(u, N); return REGION_NAMES[(x >= N // 2) * 2 + (y >= N // 2)]

def nbrs(u, N):
    x, y = divmod(u, N); return [(x + dx) * N + y + dy for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) if 0 <= x + dx < N and 0 <= y + dy < N]

def persona(r): return {"worldview": WORLDVIEWS[r]}

def run(N, ticks, mode, seed, out):
    rng = random.Random(seed); n = N * N
    S = [None] * n
    c = (N // 2) * N + N // 2
    for u in (c, c - 1, c - N, c - N - 1): S[u] = tuple(SID[s] for s in STORY)
    hist, snaps = [], {0: list(S)}
    t0 = time.time()
    for t in range(1, ticks + 1):
        tellers = [u for u in range(n) if S[u] is not None]
        # rule 2: mutation (stage 1: which sentence; stage 2: what to do with it)
        tq = {}
        for u in tellers:
            st = S[u]
            tq[f"t{u}"] = {"type": "choice", "instructions": {"teller_worldview": WORLDVIEWS[region(u, N)], "story": [ALL[i] for i in st],
                "question": "When this person retells `story`, which sentence are they most likely to change or forget, given their worldview?"},
                "criteria": {str(j): ALL[i] for j, i in enumerate(st)}}
        targ = {}
        if mode == "jev":
            ans = jevlib.ask_many(tq, tag=f"B-jev-N{N}")
            for u in tellers: targ[u] = int(ans[f"t{u}"]["choice"])
        else:
            for u in tellers: targ[u] = rng.randrange(len(S[u]))
        aq, opts = {}, {}
        for u in tellers:
            st = S[u]; tgt = ALL[st[targ[u]]]; wv = [s for s in WORLDVIEWS[region(u, N)] if SID[s] not in st]
            o = {"keep": "Tell it exactly as heard."}
            if len(st) > 3: o["drop"] = "Leave this sentence out of the story."
            for j, s in enumerate(wv): o[f"swap{j}"] = f"Replace it with: {s}"
            keys = list(o); rng.shuffle(keys); opts[u] = (keys, wv)
            aq[f"a{u}"] = {"type": "choice", "instructions": {"teller_worldview": WORLDVIEWS[region(u, N)], "story": [ALL[i] for i in st], "sentence": tgt,
                "question": "Retelling `story` to a neighbour, what does this person do with `sentence`? People usually retell faithfully unless the sentence clashes with their worldview."},
                "criteria": {k: o[k] for k in keys}}
        act = {}
        if mode == "jev":
            ans = jevlib.ask_many(aq, tag=f"B-jev-N{N}")
            for u in tellers:
                pr = ans[f"a{u}"]["probabilities"]; ks = list(pr); act[u] = rng.choices(ks, [pr[k] for k in ks])[0]
        else:
            for u in tellers:
                keys = opts[u][0]; act[u] = "keep" if rng.random() < KEEP_RATE else rng.choice([k for k in keys if k != "keep"] or ["keep"])
        told = {}
        for u in tellers:
            st = list(S[u]); a = act[u]; i = targ[u]
            if a == "drop": st.pop(i)
            elif a.startswith("swap"): st[i] = SID[opts[u][1][int(a[4:])]]
            told[u] = (rng.choice(nbrs(u, N)), tuple(st))
        # rule 3: listeners
        cq, pend = {}, []
        for u, (v, st) in told.items():
            if S[v] is None: S[v] = st
            elif S[v] != st: pend.append((v, st))
        if mode == "jev" and pend:
            for k, (v, st) in enumerate(pend):
                flip = rng.random() < 0.5; A, Bv = (S[v], st) if not flip else (st, S[v])
                cq[f"c{k}"] = {"type": "choice", "instructions": {"listener_worldview": WORLDVIEWS[region(v, N)], "version_1": [ALL[i] for i in A], "version_2": [ALL[i] for i in Bv],
                    "question": "This person has heard two versions of the same story. Which version do they believe and prefer to retell, given their worldview?"},
                    "criteria": {"1": "version_1", "2": "version_2"}}
                pend[k] = (v, A, Bv)
            ans = jevlib.ask_many(cq, tag=f"B-jev-N{N}")
            for k, (v, A, Bv) in enumerate(pend): S[v] = A if ans[f"c{k}"]["choice"] == "1" else Bv
        elif pend:
            for v, st in pend:
                if rng.random() < 0.5: S[v] = st
        known = [s for s in S if s is not None]
        vc = Counter(known)
        orig = sum(1 for s in known for i in s if i < 6) / max(1, sum(len(s) for s in known))
        local = sum(1 for u in range(n) if S[u] for i in S[u] if i >= 6 and ALL[i] in WORLDVIEWS[region(u, N)])
        foreign = sum(1 for u in range(n) if S[u] for i in S[u] if i >= 6 and ALL[i] not in WORLDVIEWS[region(u, N)])
        m = {"tick": t, "knowers": len(known), "versions": len(vc), "top_version_share": vc.most_common(1)[0][1] / len(known),
             "mean_len": sum(map(len, known)) / len(known), "original_fraction": orig, "local_inserts": local, "foreign_inserts": foreign,
             "keep_rate": sum(1 for u in tellers if act[u] == "keep") / len(tellers), "spend": round(jevlib.total_spend(), 4), "sec": round(time.time() - t0, 1)}
        hist.append(m); snaps[t] = list(S)
        if t % 5 == 0: print(json.dumps({k: (round(x, 3) if isinstance(x, float) else x) for k, x in m.items()}), flush=True)
    json.dump({"N": N, "mode": mode, "hist": hist, "snaps": snaps, "sentences": ALL, "regions": REGION_NAMES}, open(out, "w"))

KEEP_RATE = 0.5
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--N", type=int, default=20); ap.add_argument("--ticks", type=int, default=50)
    ap.add_argument("--mode", default="jev"); ap.add_argument("--seed", type=int, default=0); ap.add_argument("--keep", type=float, default=0.5)
    a = ap.parse_args(); KEEP_RATE = a.keep
    run(a.N, a.ticks, a.mode, a.seed, f"runs/B_{a.mode}_N{a.N}_s{a.seed}.json"); print("spend", round(jevlib.total_spend(), 4))
