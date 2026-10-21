"""Render the README GIFs from the study page (viewer/index.html), served locally over HTTP.

    .venv/bin/python scripts/record_gifs.py [hero|bundles|lean ...]   # default: all three, about 2 minutes

img/hero.gif     Part 1, 10,000 accounts, live Jev: random feed (left) vs ranked feed (right), day 0 to 300
img/bundles.gif  Part 2, 10,000 agents on a grid: which opinions travel together, vs US adults (GSS 2024)
img/lean.gif     Part 3, Jev's lean kept (left) vs removed (right)
Needs: pip install -r requirements.txt && playwright install chromium."""
import asyncio, functools, http.server, io, os, sys, threading
from PIL import Image
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=os.path.join(HERE, "viewer")))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}/"

# name: (part, mode, first element, last element of the crop, seconds, output width)
GIFS = {
    "hero": ("feed", "live10k", "#feed-panes", "#feed-charts", 10, 720),
    "bundles": ("map", "jev", "#map-panes", "#map-charts", 8, 720),
    "lean": ("lean", "neutral", "#lean-panes", "#lean-charts", 6, 720),
}
FPS = 6
HIDE = "header.top, .howto, .legend, .transport, .note, .bar, #feed-robust { display: none !important; } body { background: #faf9f5; }"

async def record(pg, url, name):
    part, mode, top, bottom, sec, width = GIFS[name]
    await pg.goto(url); await pg.wait_for_function("window.__ready", timeout=120000)
    await pg.evaluate(f"J.show('{part}')"); await pg.wait_for_function(f"J.parts.{part}.ready", timeout=120000)
    await pg.evaluate(f"document.querySelector('#{part}-modes button[data-m=\"{mode}\"]').click()"); await pg.wait_for_timeout(500)
    if part == "feed":   # wait until the in-browser layout has positioned every frame
        await pg.wait_for_function("J.parts.feed.panes.length === 2 && J.parts.feed.panes.every(p => { const L = p.R.lay && p.R.lay.reads; return L && L.done >= p.R.frames.length - 1; })", timeout=300000)
    await pg.add_style_tag(content=HIDE); await pg.evaluate(f"J.parts.{part}.resize(); J.parts.{part}.dirty = true"); await pg.wait_for_timeout(300)
    a = await (await pg.query_selector(top)).bounding_box(); sy = await pg.evaluate("scrollY"); a["y"] += sy; b = await (await pg.query_selector(bottom)).bounding_box(); b["y"] += sy
    clip = {"x": min(a["x"], b["x"]), "y": a["y"] - 8, "width": max(a["width"], b["width"]), "height": b["y"] + b["height"] - a["y"] + 16}
    ims, n = [], sec * FPS
    for i in range(n + FPS):   # hold the last frame for one second
        u = min(1, i / (n - 1)); u = u * u * (3 - 2 * u)
        await pg.evaluate(f"(() => {{ const P = J.parts.{part}; P.tr.T = P.tr.maxT * {u}; P.tr.ui(); P.dirty = true; }})()"); await pg.wait_for_timeout(60)
        im = Image.open(io.BytesIO(await pg.screenshot(clip=clip, full_page=True))).convert("RGB")
        ims.append(im.resize((width, int(im.height * width / im.width)), Image.LANCZOS))
    pick = [ims[len(ims) * q // 6] for q in range(6)] + [ims[-1]]; w, h = ims[0].size
    strip = Image.new("RGB", (w, h * len(pick))); [strip.paste(im, (0, h * k)) for k, im in enumerate(pick)]
    pal = strip.quantize(colors=64, method=Image.Quantize.MEDIANCUT)
    q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in ims]
    out = os.path.join(HERE, "img", f"{name}.gif")
    q[0].save(out, save_all=True, append_images=q[1:], duration=int(1000 / FPS), loop=0, optimize=True)
    print("wrote", out, os.path.getsize(out) // 1024, "KB")

async def main():
    names = [a for a in sys.argv[1:] if a in GIFS] or list(GIFS); url = serve()
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        for name in names: await record(pg, url, name)
        await b.close()

asyncio.run(main())
