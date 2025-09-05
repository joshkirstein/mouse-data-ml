import json
import re
import threading
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


INDEX_HTML = (ROOT / "index.html").read_text(encoding="utf-8") if (ROOT / "index.html").exists() else """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Mouse Trajectory Capture (Web)</title>
  <style>
    html, body { height: 100%; margin: 0; }
    body { background: #fff; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; display: flex; align-items: start; justify-content: center; padding-top: 16px; }
    #wrap { position: relative; }
    #hud { position: absolute; top: 8px; left: 8px; background: rgba(255,255,255,0.85); padding: 6px 8px; border-radius: 6px; font-size: 12px; }
    #canvas { display: block; width: 750px; height: 550px; box-shadow: 0 0 0 1px #ddd inset; }
  </style>
</head>
<body>
  <div id="wrap">
    <div id="hud">Trials: <span id="trial">0</span> · Session: <span id="session"></span> · Click the red dot. Press R to reset.</div>
    <canvas id="canvas"></canvas>
  </div>
  <script>
    const session = (crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(36).slice(2);
    document.getElementById('session').textContent = session.slice(0, 8);

    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');
    const CANVAS_W = 750, CANVAS_H = 550;
    let trial = 0;
    let target = null; // {x, y, r}
    const radius = 12;
    let path = [];
    let t0 = 0;
    let prevTarget = null;

    function resizeCanvas() {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.floor(CANVAS_W * dpr);
      canvas.height = Math.floor(CANVAS_H * dpr);
      canvas.style.width = CANVAS_W + 'px';
      canvas.style.height = CANVAS_H + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw();
    }

    function randInt(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; }

    function newTarget() {
      const margin = radius + 10;
      const W = CANVAS_W, H = CANVAS_H;
      let x, y; let tries = 0;
      do {
        x = randInt(margin, W - margin);
        y = randInt(margin, H - margin);
        tries++;
      } while (prevTarget && ((x - prevTarget.x) ** 2 + (y - prevTarget.y) ** 2) < (5 * radius) ** 2 && tries < 100);
      prevTarget = target = { x, y, r: radius };
    }

    function newTrial() {
      trial += 1;
      document.getElementById('trial').textContent = trial;
      path = [];
      t0 = performance.now();
      newTarget();
      draw();
    }

    function draw() {
      if (!target) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      // draw dot
      ctx.fillStyle = 'red';
      ctx.beginPath();
      ctx.arc(target.x, target.y, target.r, 0, Math.PI * 2);
      ctx.fill();
    }

    function onMove(ev) {
      if (!t0) return;
      const rect = canvas.getBoundingClientRect();
      const x = ev.clientX - rect.left;
      const y = ev.clientY - rect.top;
      const t = (performance.now() - t0) / 1000;
      path.push({ t, x, y });
    }

    function onDown(ev) {
      if (!target) return;
      const rect = canvas.getBoundingClientRect();
      const x = ev.clientX - rect.left;
      const y = ev.clientY - rect.top;
      const t = (performance.now() - t0) / 1000;
      path.push({ t, x, y, click: true });
      const inside = ((x - target.x) ** 2 + (y - target.y) ** 2) <= (target.r ** 2);
      if (inside) {
        finishTrial().then(() => {
          newTrial();
        }).catch(() => {
          // still continue new trial even if logging failed
          newTrial();
        });
      }
    }

    async function finishTrial() {
      const payload = {
        session,
        trial,
        timestamp: new Date().toISOString(),
        window: { width: CANVAS_W, height: CANVAS_H },
        target: { x: target.x, y: target.y, radius: target.r },
        path,
      };
      await fetch('/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        keepalive: true,
      });
    }

    window.addEventListener('resize', resizeCanvas);
    canvas.addEventListener('pointermove', onMove);
    canvas.addEventListener('pointerdown', onDown);
    window.addEventListener('keydown', (e) => {
      if (e.key === 'r' || e.key === 'R') {
        trial = 0; prevTarget = null; newTrial();
      }
    });

    resizeCanvas();
    newTrial();
  </script>
</body>
</html>
"""


SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")
VIS_HTML = (ROOT / "visualize.html").read_text(encoding="utf-8") if (ROOT / "visualize.html").exists() else """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Mouse Trajectory Visualizer</title>
  <style>
    html, body { height: 100%; margin: 0; }
    body { background: #f8f9fa; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
    header { padding: 10px 12px; background: #fff; border-bottom: 1px solid #e5e7eb; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    #status { margin-left: auto; font-size: 12px; color: #555; }
    main { display: flex; justify-content: center; padding: 16px; }
    #wrap { position: relative; }
    #canvas { display: block; background: #fff; box-shadow: 0 0 0 1px #ddd inset; }
    #hud { position: absolute; top: 8px; left: 8px; background: rgba(255,255,255,0.85); padding: 6px 8px; border-radius: 6px; font-size: 12px; }
    button, select { padding: 6px 10px; border: 1px solid #cbd5e1; border-radius: 6px; background: #fff; }
    button:hover { background: #f3f4f6; }
  </style>
</head>
<body>
  <header>
    <strong>Visualizer</strong>
    <select id="sessionSel"></select>
    <button id="reload">Reload Sessions</button>
    <div style="width:12px"></div>
    <button id="prev">Prev</button>
    <button id="play">Play</button>
    <button id="next">Next</button>
    <label>Speed <select id="speed"><option>0.5</option><option selected>1</option><option>2</option><option>4</option></select>x</label>
    <span id="status"></span>
  </header>
  <main>
    <div id="wrap">
      <div id="hud">Trial <span id="trial">0</span>/<span id="total">0</span></div>
      <canvas id="canvas" width="750" height="550"></canvas>
    </div>
  </main>
  <script>
    const $ = (q) => document.querySelector(q);
    const sessionSel = $('#sessionSel');
    const reloadBtn = $('#reload');
    const prevBtn = $('#prev');
    const playBtn = $('#play');
    const nextBtn = $('#next');
    const speedSel = $('#speed');
    const status = $('#status');
    const trialLbl = $('#trial');
    const totalLbl = $('#total');
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');
    let records = [];
    let idx = 0; // current trial idx
    let playing = false;
    let startMs = 0;
    let pointer = 0; // path index cursor

    function setCanvasSize(w, h) {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = w + 'px';
      canvas.style.height = h + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function drawFrame(sampleIndex = null) {
      if (!records.length) return;
      const rec = records[idx];
      const { width, height } = rec.window || { width: 750, height: 550 };
      setCanvasSize(width, height);
      ctx.clearRect(0, 0, width, height);
      // target
      ctx.fillStyle = 'red';
      ctx.beginPath();
      ctx.arc(rec.target.x, rec.target.y, rec.target.radius, 0, Math.PI * 2);
      ctx.fill();
      // path up to sampleIndex
      const path = rec.path || [];
      const n = (sampleIndex == null) ? path.length : Math.max(0, Math.min(path.length, sampleIndex));
      if (n > 0) {
        ctx.strokeStyle = '#2563eb';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(path[0].x, path[0].y);
        for (let i = 1; i < n; i++) ctx.lineTo(path[i].x, path[i].y);
        ctx.stroke();
        // pointer
        const p = path[n - 1];
        ctx.fillStyle = '#1d4ed8';
        ctx.beginPath();
        ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    function updateHUD() {
      trialLbl.textContent = (idx + 1);
      totalLbl.textContent = records.length;
      status.textContent = records.length ? (records[idx].timestamp || '') : '';
    }

    async function loadSessions() {
      sessionSel.innerHTML = '';
      const res = await fetch('/sessions');
      const data = await res.json();
      const list = data.sessions || [];
      list.sort();
      for (const name of list) {
        const opt = document.createElement('option');
        opt.value = name; opt.textContent = name;
        sessionSel.appendChild(opt);
      }
      return list;
    }

    async function loadData(name) {
      const res = await fetch('/data/' + encodeURIComponent(name));
      const text = await res.text();
      records = text.split('\n').filter(Boolean).map(line => {
        try { return JSON.parse(line); } catch { return null; }
      }).filter(Boolean);
      idx = 0; pointer = 0; playing = false; playBtn.textContent = 'Play';
      updateHUD();
      drawFrame(0);
    }

    function playCurrent() {
      if (!records.length) return;
      const rec = records[idx];
      const path = rec.path || [];
      if (path.length === 0) { drawFrame(0); return; }
      playing = true; playBtn.textContent = 'Pause';
      pointer = 0; startMs = performance.now();
      const speed = parseFloat(speedSel.value) || 1;
      function step(now) {
        if (!playing) return; // paused
        const elapsed = (now - startMs) / 1000 * speed;
        while (pointer < path.length && path[pointer].t <= elapsed) pointer++;
        drawFrame(pointer);
        if (pointer >= path.length) { playing = false; playBtn.textContent = 'Play'; return; }
        requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    }

    function togglePlay() {
      if (!playing) playCurrent(); else { playing = false; playBtn.textContent = 'Play'; }
    }

    function next() { idx = Math.min(records.length - 1, idx + 1); playing = false; playBtn.textContent = 'Play'; pointer = 0; updateHUD(); drawFrame(0); }
    function prev() { idx = Math.max(0, idx - 1); playing = false; playBtn.textContent = 'Play'; pointer = 0; updateHUD(); drawFrame(0); }

    // wire up
    reloadBtn.addEventListener('click', async () => { const list = await loadSessions(); if (list.length) await loadData(sessionSel.value); });
    sessionSel.addEventListener('change', () => loadData(sessionSel.value));
    playBtn.addEventListener('click', togglePlay);
    nextBtn.addEventListener('click', next);
    prevBtn.addEventListener('click', prev);
    speedSel.addEventListener('change', () => { if (playing) { playing = false; playBtn.textContent = 'Play'; playCurrent(); } });

    // init
    (async function(){
      const list = await loadSessions();
      if (list.length) await loadData(list[list.length - 1]);
    })();
  </script>
</body>
</html>
"""


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(INDEX_HTML.encode("utf-8"))
            return
        if self.path == "/visualize" or self.path == "/visualize.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(VIS_HTML.encode("utf-8"))
            return
        if self.path == "/sessions":
            # List available session files in data dir
            sessions = sorted(p.name for p in DATA_DIR.glob("session_*.jsonl"))
            payload = json.dumps({"sessions": sessions})
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload.encode("utf-8"))
            return
        if self.path.startswith("/data/"):
            name = self.path[len("/data/"):]
            name = SAFE_NAME.sub("_", name)
            if not name.startswith("session_"):
                self.send_error(400, "Invalid session name")
                return
            path = DATA_DIR / name
            if not path.exists():
                self.send_error(404, "Session not found")
                return
            try:
                data = path.read_bytes()
            except Exception as e:
                self.send_error(500, f"Failed to read: {e}")
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        return super().do_GET()

    def do_POST(self):
        if self.path != "/log":
            self.send_error(404, "Not Found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        try:
            record = json.loads(body.decode("utf-8"))
        except Exception as e:
            self.send_error(400, f"Invalid JSON: {e}")
            return

        session = str(record.get("session", "unknown"))
        session = SAFE_NAME.sub("_", session)[:64]
        if not session:
            session = "unknown"

        out_path = DATA_DIR / f"session_{session}.jsonl"
        try:
            with out_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False))
                f.write("\n")
        except Exception as e:
            self.send_error(500, f"Failed to write: {e}")
            return

        self.send_response(204)
        self.end_headers()


def run(host: str = "127.0.0.1", port: int = 8000):
    httpd = HTTPServer((host, port), Handler)
    print(f"Serving on http://{host}:{port}  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run()
