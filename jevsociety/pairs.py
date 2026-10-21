"""Ask Jev how every pair of statements from different issues relates. python -m jevsociety.pairs [--variant fit|reasons]

Two question wordings, both on the same 0-4 scale with "unrelated" in the middle:
  fit      "How well do these two beliefs fit together in one coherent view of how society should be?"
  reasons  "Setting aside which kinds of people usually hold them, does one belief give a reason for or against the other?"
Each unordered pair is asked in both orders (belief_1/belief_2 swapped) and the two answers are averaged, so the
position of a sentence in the question cannot tilt the result. Pairs from the same issue are never asked (an agent
holds exactly one side of each issue). Answers are stored in data/jev_pairs_<variant>.json, which is committed, so
the bundling simulation runs offline. Re-running skips pairs already stored."""
import argparse, json, os
from . import jev
from .issues import STATEMENTS, M

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Q = {
 "fit": ("How well do `belief_1` and `belief_2` fit together in one coherent view of how society should be?",
         ["They clash: holding both makes little sense", "They mostly clash", "They are unrelated: neither fits nor clashes",
          "They fit together somewhat", "They fit together naturally"]),
 "reasons": ("Setting aside which kinds of people usually hold these beliefs, does accepting `belief_1` give a person a reason to accept or to reject `belief_2`?",
             ["A strong reason to reject belief_2", "A weak reason to reject belief_2", "No reason either way: they are unrelated",
              "A weak reason to accept belief_2", "A strong reason to accept belief_2"]),
}

def path(variant): return os.path.join(HERE, "data", f"jev_pairs{'_mock' if jev.MOCK else ''}_{variant}.json")

def load(variant):
    """Returns a 2M x 2M matrix K in [-1, 1]: (mean Jev score over both orders - 2) / 2. Same-issue entries are 0."""
    real = os.path.join(HERE, "data", f"jev_pairs_{variant}.json")  # committed real answers; reading them makes no call
    d = json.load(open(real if os.path.exists(real) else path(variant)))["scores"]; n = 2 * M
    K = [[0.0] * n for _ in range(n)]
    for a in range(n):
        for b in range(n):
            if a // 2 != b // 2: K[a][b] = ((d[f"{a},{b}"] + d[f"{b},{a}"]) / 2 - 2) / 2
    return K

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--variant", choices=list(Q), default="fit"); a = ap.parse_args()
    p = path(a.variant); os.makedirs(os.path.dirname(p), exist_ok=True)
    store = json.load(open(p)) if os.path.exists(p) else {"variant": a.variant, "question": Q[a.variant][0], "levels": Q[a.variant][1], "scores": {}}
    question, levels = Q[a.variant]
    need = {}
    for x in range(2 * M):
        for y in range(2 * M):
            if x // 2 != y // 2 and f"{x},{y}" not in store["scores"]:
                need[f"{x},{y}"] = {"type": "score", "instructions": {"belief_1": STATEMENTS[x], "belief_2": STATEMENTS[y], "question": question}, "criteria": levels}
    print(f"{len(need)} questions to ask; spend so far USD {jev.total_spend():.4f}")
    if need:
        ids = list(need); ans = jev.ask_many({f"q{i}": need[k] for i, k in enumerate(ids)}, tag=f"pairs-{a.variant}")
        for i, k in enumerate(ids): store["scores"][k] = ans[f"q{i}"]["score"]
    json.dump(store, open(p, "w"), indent=0)
    print(f"stored {len(store['scores'])} answers in {p}; spend now USD {jev.total_spend():.4f}")

if __name__ == "__main__": main()
