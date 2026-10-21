"""Headless check of the study page (viewer/index.html): every mode of all three parts at 1440x900 and 390x844, served over
HTTP from viewer/ as the site root (the same layout as the Vercel deploy). Reports console errors, failed requests,
horizontal overflow, missing run files and blank panes; saves a screenshot per mode.

    .venv/bin/python scripts/check_viewer.py OUT_DIR [URL]     # URL defaults to a local server on viewer/"""
import asyncio, functools, http.server, os, sys, threading
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
URL = sys.argv[2] if len(sys.argv) > 2 else None

def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=os.path.join(HERE, "viewer")))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}/"

# per part: the mode buttons to click (selector) and a JS expression that is true once the mode has drawn
READY = {
    "feed": "(() => { const P = J.parts.feed; return P.built > window.__b && P.panes.length === 2 && P.panes.every(p => p.R.lay && Object.values(p.R.lay).some(L => L.done >= 0)); })()",
    "map": "(() => { const P = J.parts.map; return P.ready && document.querySelectorAll('#map-panes canvas').length > 0; })()",
    "lean": "(() => { const P = J.parts.lean; return P.ready && document.querySelectorAll('#lean-panes canvas').length > 0; })()",
}
BUTTONS = {"feed": "#feed-modes button, #feed-rlist button", "map": "#map-modes button", "lean": "#lean-modes button"}

async def main():
    os.makedirs(OUT, exist_ok=True); url = URL or serve(); errs = []; shots = 0
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for w, h in ((1440, 900), (390, 844)):
            pg = await b.new_page(viewport={"width": w, "height": h})
            pg.on("console", lambda m, w=w: m.type in ("error", "warning") and errs.append(f"{w}: console {m.type}: {m.text}"))
            pg.on("pageerror", lambda e, w=w: errs.append(f"{w}: page error: {e}"))
            pg.on("requestfailed", lambda r, w=w: errs.append(f"{w}: request failed: {r.url}"))
            pg.on("response", lambda r, w=w: r.status >= 400 and errs.append(f"{w}: HTTP {r.status}: {r.url}"))
            await pg.goto(url); await pg.wait_for_function("window.__ready", timeout=120000)
            for part in ("feed", "map", "lean"):
                await pg.evaluate(f"J.show('{part}')"); await pg.wait_for_function(f"J.parts.{part}.ready", timeout=120000)
                n = await pg.eval_on_selector_all(BUTTONS[part], "bs => bs.length")
                for i in range(n):
                    label = await pg.evaluate(f"(() => {{ window.__b = J.parts.feed.built || 0; const b = document.querySelectorAll('{BUTTONS[part]}')[{i}]; if (b.closest('details')) b.closest('details').open = true; b.click(); return b.dataset.m; }})()")
                    try: await pg.wait_for_timeout(300); await pg.wait_for_function(READY[part], timeout=120000)
                    except Exception: errs.append(f"{w}: {part}/{label} never finished drawing")
                    await pg.evaluate(f"(() => {{ const P = J.parts.{part}; P.tr.T = P.tr.maxT * 0.7; P.tr.ui(); P.dirty = true; }})()"); await pg.wait_for_timeout(600)
                    note = await pg.evaluate(f"(document.getElementById('{part}-note') || {{}}).textContent || ''")
                    if "not found" in note: errs.append(f"{w}: {part}/{label}: {note}")
                    blank = await pg.evaluate(f"""[...document.querySelectorAll('#{part}-panes canvas')].filter(c => {{
                        const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; for (let k = 3; k < d.length; k += 4000) if (d[k]) return false; return true; }}).length""")
                    if blank: errs.append(f"{w}: {part}/{label}: {blank} blank pane(s)")
                    sw = await pg.evaluate("document.documentElement.scrollWidth")
                    if sw > w: errs.append(f"{w}: {part}/{label}: horizontal overflow {sw}px")
                    el = await pg.query_selector(f"#part-{part} figure")
                    await el.screenshot(path=os.path.join(OUT, f"{part}_{label}_{w}.png")); shots += 1
            await pg.close()
        await b.close()
    print(f"{shots} screenshots in {OUT}"); print("\n".join(errs) or "no console errors, failed requests, blank panes or horizontal overflow")
    sys.exit(1 if errs else 0)

asyncio.run(main())
