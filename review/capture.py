import json, urllib.request, asyncio, base64, os, hashlib, datetime
import websockets

OUT = "/root/.hermes/work/zus-review"
os.makedirs(OUT, exist_ok=True)
URL = "https://vizitka-preview-production.up.railway.app/zus-kanikuly/instrukcja.html"

class Tab:
    def __init__(self, ws): self.ws = ws; self.i = 0
    async def call(self, method, **params):
        self.i += 1; mid = self.i
        await self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg: raise RuntimeError(msg["error"])
                return msg.get("result", {})
    async def js(self, expr):
        r = await self.call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

async def shot(tab, name, full=True):
    m = await tab.call("Page.getLayoutMetrics")
    css = m.get("cssContentSize") or m["contentSize"]
    w, h = int(css["width"]), int(css["height"])
    if full:
        params = dict(format="jpeg", quality=88, captureBeyondViewport=True,
                      clip={"x": 0, "y": 0, "width": w, "height": h, "scale": 1})
        path = f"{OUT}/{name}.jpg"
    else:
        params = dict(format="png")
        path = f"{OUT}/{name}.png"
    r = await tab.call("Page.captureScreenshot", **params)
    data = base64.b64decode(r["data"])
    open(path, "wb").write(data)
    return path, w, h, len(data)

async def run():
    t = json.load(urllib.request.urlopen(urllib.request.Request(
        "http://127.0.0.1:9444/json/new?about:blank", method="PUT")))
    ws = await websockets.connect(t["webSocketDebuggerUrl"], max_size=200*1024*1024)
    tab = Tab(ws)
    await tab.call("Page.enable"); await tab.call("Runtime.enable")
    manifest = []
    ts = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

    async def setup(width, height, mobile):
        await tab.call("Emulation.setDeviceMetricsOverride", width=width, height=height,
                       deviceScaleFactor=2 if mobile else 1, mobile=mobile)
        if mobile:
            await tab.call("Emulation.setUserAgentOverride",
                           userAgent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

    async def load():
        await tab.call("Page.navigate", url=URL)
        await asyncio.sleep(3.5)

    # --- desktop full page
    await setup(1440, 900, False); await load()
    p, w, h, sz = await shot(tab, "01-desktop-full", True)
    manifest.append(dict(file=os.path.basename(p), scenario="desktop full page, initial state (route selection visible)",
                         viewport="1440x900 @1x", page_height=h, bytes=sz, captured_at=ts()))

    # --- initial route selection (viewport, desktop)
    p, w, h, sz = await shot(tab, "02-route-selection", False)
    manifest.append(dict(file=os.path.basename(p), scenario="initial route-selection screen (viewport, top of page)",
                         viewport="1440x900", bytes=sz, captured_at=ts()))

    # --- first-time route
    await tab.js("setRoute('first'); window.scrollTo(0,0);")
    await asyncio.sleep(1.2)
    p, w, h, sz = await shot(tab, "03-route-first", False)
    manifest.append(dict(file=os.path.basename(p), scenario="after selecting first-time application route (setRoute('first'))",
                         viewport="1440x900", bytes=sz, captured_at=ts()))

    # --- repeat route
    await tab.js("setRoute('repeat'); window.scrollTo(0,0);")
    await asyncio.sleep(1.2)
    p, w, h, sz = await shot(tab, "04-route-repeat", False)
    manifest.append(dict(file=os.path.basename(p), scenario="after selecting repeat-application route (setRoute('repeat'))",
                         viewport="1440x900", bytes=sz, captured_at=ts()))

    # --- change route control
    await tab.js("document.getElementById('rb-change').click(); window.scrollTo(0,0);")
    await asyncio.sleep(1.2)
    p, w, h, sz = await shot(tab, "05-route-change-clicked", False)
    rb_state = await tab.js("JSON.stringify({label:document.getElementById('rb-label').textContent, hidden:document.getElementById('routebar').offsetHeight===0, forkVisible: document.querySelector('[data-r=\"first\"]') ? getComputedStyle(document.querySelector('[data-r=\"first\"]').closest('div')).display : 'n/a'})")
    manifest.append(dict(file=os.path.basename(p), scenario="after activating \"Изменить маршрут\" (#rb-change)", viewport="1440x900",
                         bytes=sz, state=rb_state, captured_at=ts()))

    # --- instructional step (deep link / scroll to a step)
    await tab.js("setRoute('first'); const el=document.getElementById('login-ezus'); if(el) el.scrollIntoView({block:'start'});")
    await asyncio.sleep(1.2)
    p, w, h, sz = await shot(tab, "06-step-login-ezus", False)
    manifest.append(dict(file=os.path.basename(p), scenario="instructional step anchored on #login-ezus (first-time route)",
                         viewport="1440x900", bytes=sz, captured_at=ts()))

    # --- nav bar / TOC state
    p, w, h, sz = await shot(tab, "07-nav-jump-bar", False)
    manifest.append(dict(file=os.path.basename(p), scenario="navigation: route bar + section jump controls after step scroll",
                         viewport="1440x900", bytes=sz, captured_at=ts()))

    # --- mobile
    await setup(390, 844, True); await load()
    p, w, h, sz = await shot(tab, "08-mobile-full", True)
    manifest.append(dict(file=os.path.basename(p), scenario="mobile full page, initial state", viewport="390x844 @2x", page_height=h, bytes=sz, captured_at=ts()))
    await tab.js("setRoute('repeat'); window.scrollTo(0,0);")
    await asyncio.sleep(1.2)
    p, w, h, sz = await shot(tab, "09-mobile-repeat", False)
    manifest.append(dict(file=os.path.basename(p), scenario="mobile after selecting repeat route", viewport="390x844 @2x", bytes=sz, captured_at=ts()))

    # --- JS disabled test (server-side content presence)
    await setup(1440, 900, False)
    await tab.call("Emulation.setScriptExecutionDisabled", value=True)
    await load()
    text = await tab.js("document.body.innerText.length") or 0
    steps = await tab.js("document.querySelectorAll('figure').length") or 0
    imgs = await tab.js("document.querySelectorAll('img').length") or 0
    menu = await tab.js("(()=>{const f=document.getElementById('fork')||document.querySelector('[data-r=\"first\"]'); return f? 'present':'missing'})()")
    p, w, h, sz = await shot(tab, "10-nojs-desktop", True)
    manifest.append(dict(file=os.path.basename(p), scenario="JavaScript disabled: server HTML alone (content presence test)",
                         viewport="1440x900", bytes=sz, innerText_len=text, figures=steps, images=imgs, route_fork=menu, captured_at=ts()))
    await tab.call("Emulation.setScriptExecutionDisabled", value=False)

    doc = dict(url=URL, deployed_commit="c13dba9", deployed_commit_sha256="8ec894b0b784d2a424bcc4f2bd1be9fdf1c0f262fa75a4a82ab6c1c3b23724ba",
               captured_at=ts(), browser="Chromium headless (CDP), /usr/bin/chromium",
               note="Every file is a real browser capture of the live page; no source-code rendering substituted.",
               shots=manifest)
    open(f"{OUT}/manifest.json", "w").write(json.dumps(doc, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in doc.items() if k != 'shots'}, ensure_ascii=False))
    for m in manifest: print(m["file"], m.get("bytes"), m.get("scenario")[:60])
    await ws.close()

asyncio.run(run())
