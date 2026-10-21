"""Convert recorded 10,000-account run files in viewer/runs/ from live10k-1 to the smaller live10k-2 format, in place.

    .venv/bin/python scripts/compact_runs.py            # every net_live10k_*.js still in the old format

New recordings are written in live10k-2 already (jevsociety.live10k.save); this is for files recorded before that change."""
import glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jevsociety.live10k import compact, HERE

for path in sorted(glob.glob(os.path.join(HERE, "viewer", "runs", "net_live10k_*.js"))):
    s = open(path).read(); head, body = s.split("]=", 1); rec = json.loads(body.rstrip().rstrip(";"))
    if rec.get("fmt") != "live10k-1": continue
    before = len(s); s = head + "]=" + json.dumps(compact(rec), separators=(",", ":")) + ";\n"
    open(path, "w").write(s); print(f"{os.path.basename(path)}: {before / 1e6:.1f} MB -> {len(s) / 1e6:.1f} MB")
