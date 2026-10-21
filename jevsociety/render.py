"""Render a recorded run to PNG panels and a GIF: python -m jevsociety.render viewer/runs/<name>.js"""
import json, sys, os, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib import animation
def load(p):
    s = open(p).read(); return json.loads(s[s.index("=", s.index("]")) + 1:].rstrip().rstrip(";"))
def grid(R, fr):
    pole = R["tags"]["pole"]; lr = [sum(pole[i] for i in R["sets"][s]) / len(R["sets"][s]) for s in fr["agents"]]
    return np.array(lr).reshape(R["side"], R["side"])
def main(p, outdir="img"):
    R = load(p); name = os.path.splitext(os.path.basename(p))[0]; F = R["frames"]
    pick = [F[0], F[len(F) // 5], F[len(F) // 2], F[-1]]
    fig, ax = plt.subplots(1, 4, figsize=(13, 3.6))
    for a, fr in zip(ax, pick):
        a.imshow(grid(R, fr), cmap="coolwarm", vmin=-1, vmax=1, interpolation="nearest"); a.set_title(f"tick {fr['tick']}"); a.axis("off")
    fig.suptitle(f"{name}: blue = progressive-side beliefs, red = traditional-side (tags used for colour only)", fontsize=9)
    fig.tight_layout(); fig.savefig(f"{outdir}/{name}.png", dpi=120); plt.close(fig)
    fig, a = plt.subplots(figsize=(5, 5)); im = a.imshow(grid(R, F[0]), cmap="coolwarm", vmin=-1, vmax=1, interpolation="nearest"); a.axis("off"); t = a.set_title("")
    def upd(i): im.set_data(grid(R, F[i])); t.set_text(f"tick {F[i]['tick']}"); return im,
    animation.FuncAnimation(fig, upd, frames=len(F), interval=200).save(f"{outdir}/{name}.gif", writer="pillow", dpi=80); plt.close(fig)
if __name__ == "__main__": main(*sys.argv[1:])
