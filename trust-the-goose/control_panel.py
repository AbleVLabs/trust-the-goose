"""
PARANOID PENGUIN — control panel (by AbleV Labs).
"Paranoid so you don't have to be."

Double-click Start-ParanoidPenguin.bat (or run this) and a local website opens
with big buttons. No commands. Each button runs one security check and shows
your results. Runs entirely on your own machine (127.0.0.1).

Scanners run IN-PROCESS (imported as modules), so this also works when packaged
as a standalone .exe with PyInstaller — see build_exe.bat.
"""
import contextlib
import http.server
import io
import json
import os
import sys
import threading
import webbrowser
from urllib.parse import urlparse, parse_qs

PORT = 8765
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# import each scanner as a module (bundled automatically when frozen to .exe)
_MOD = {}
for _name in ("real_feeds", "scan_pc", "audit_python", "harden_audit",
              "scan_startup", "scan_logins", "scan_network",
              "scan_connections", "scan_wifi", "grade"):
    try:
        _MOD[_name] = __import__(_name)
    except Exception as _e:                       # keep the panel usable if one dep is missing
        _MOD[_name] = None
        print(f"  (note: could not load {_name}: {_e})")

# task key -> module that has .main()
TASKS = {
    "feeds":   "real_feeds",
    "pc":      "scan_pc",
    "apps":    "audit_python",
    "harden":  "harden_audit",
    "startup": "scan_startup",
    "logins":  "scan_logins",
    "network": "scan_network",
    "connections": "scan_connections",
    "wifi":    "scan_wifi",
}
_RUN_LOCK = threading.Lock()

PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Paranoid Penguin · AbleV Labs</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Rajdhani:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#04050a; --accent:#00d4ff; --accent2:#6c3fff; --gold:#e8960a; --ember:#c23b22; --green:#00ff88;
  --text:#e8edf5; --muted:#5a6480; --dim:#2a3050; --border:rgba(0,212,255,.14); --card:rgba(8,14,26,.72);
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:'Rajdhani',sans-serif;min-height:100vh;overflow-x:hidden;position:relative}
#stars{position:fixed;inset:0;z-index:0;pointer-events:none}
.grid-bg{position:fixed;inset:0;z-index:0;pointer-events:none;
  background-image:linear-gradient(rgba(0,212,255,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(0,212,255,.045) 1px,transparent 1px);
  background-size:64px 64px;-webkit-mask-image:radial-gradient(ellipse at 50% 0%,#000 30%,transparent 80%);
  mask-image:radial-gradient(ellipse at 50% 0%,#000 30%,transparent 80%)}
.wrap{position:relative;z-index:2;max-width:1020px;margin:0 auto;padding:46px 22px 60px}
header{margin:0 auto 34px;display:flex;flex-direction:column;align-items:center;text-align:center;
  animation:rise .9s cubic-bezier(.2,.85,.25,1) both}
.logo-badge{display:inline-block;background:#fff;border-radius:24px;padding:10px;line-height:0;
  box-shadow:0 18px 55px -14px rgba(108,63,255,.65),0 0 0 1px rgba(0,212,255,.2)}
#logo{max-height:138px;display:block;border-radius:15px}
.brand{font-family:'Bebas Neue',sans-serif;font-size:4.2rem;line-height:.86;letter-spacing:.015em;color:#fff;
  text-shadow:0 0 34px rgba(0,212,255,.28)}
.brand .c{color:var(--accent);text-shadow:0 0 22px rgba(0,212,255,.75)}
.tag{font-family:'Space Mono',monospace;font-size:.64rem;letter-spacing:.26em;text-transform:uppercase;
  color:var(--muted);margin-top:16px}
.tag b{color:#bfe9f6}
@keyframes rise{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:none}}
.hero{background:linear-gradient(120deg,rgba(0,212,255,.06),rgba(108,63,255,.05));border:1px solid var(--border);
  border-radius:16px;padding:22px 24px;margin-bottom:24px;display:flex;gap:26px;align-items:stretch;flex-wrap:wrap;position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;inset:0;background:radial-gradient(620px 140px at 15% 0%,rgba(0,212,255,.10),transparent 70%);pointer-events:none}
.badge{position:relative;z-index:1;border:2px solid var(--dim);border-radius:16px;min-width:160px;padding:16px 28px;
  display:flex;flex-direction:column;align-items:center;justify-content:center}
.badge .ltr{font-family:'Bebas Neue',sans-serif;font-size:5rem;line-height:.85}
.badge .scr{font-family:'Space Mono',monospace;font-size:.62rem;letter-spacing:.14em;color:var(--muted);margin-top:8px}
.badge .lbl{font-family:'Space Mono',monospace;font-size:.5rem;letter-spacing:.24em;text-transform:uppercase;color:var(--dim);margin-top:9px}
.fixes{position:relative;z-index:1;flex:1;min-width:280px}
.fh{font-family:'Space Mono',monospace;font-size:.6rem;letter-spacing:.22em;text-transform:uppercase;color:var(--accent);margin-bottom:13px}
.fix{display:flex;gap:12px;padding:9px 0;border-bottom:1px solid rgba(0,212,255,.08)}
.fix .sev{font-family:'Space Mono',monospace;font-size:.54rem;font-weight:700;letter-spacing:.06em;min-width:44px;padding-top:3px}
.fix b{color:var(--text);font-size:.98rem;font-weight:600}
.fix .why{color:var(--muted);font-size:.82rem;margin:2px 0;line-height:1.45}
.fix .cmd{color:var(--green);font-size:.8rem;font-family:'Space Mono',monospace;word-break:break-all}
.hint{color:var(--muted);font-size:.9rem;line-height:1.6}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(232px,1fr));gap:15px}
.card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:20px;display:flex;flex-direction:column;
  position:relative;backdrop-filter:blur(6px);transition:transform .18s,border-color .18s,box-shadow .18s}
.card:hover{transform:translateY(-4px);border-color:rgba(0,212,255,.4);box-shadow:0 14px 40px -18px rgba(0,212,255,.5)}
.kick{font-family:'Space Mono',monospace;font-size:.56rem;letter-spacing:.22em;text-transform:uppercase;color:var(--dim);margin-bottom:9px}
.card h2{font-family:'Rajdhani',sans-serif;font-weight:700;font-size:1.12rem;letter-spacing:.02em;color:#fff;margin-bottom:7px}
.card p{color:var(--muted);font-size:.88rem;line-height:1.5;flex:1;margin-bottom:16px}
.btn{font-family:'Space Mono',monospace;font-size:.62rem;letter-spacing:.14em;text-transform:uppercase;border-radius:9px;
  padding:12px 15px;width:100%;cursor:pointer;transition:.16s;background:transparent;color:#bfe9f6;border:1px solid rgba(0,212,255,.32)}
.btn:hover{border-color:var(--accent);color:#fff;box-shadow:0 0 22px -6px rgba(0,212,255,.6);background:rgba(0,212,255,.06)}
.btn:disabled{border-color:var(--dim);color:var(--muted);cursor:wait;box-shadow:none;background:transparent}
.status{margin-top:12px;font-family:'Space Mono',monospace;font-size:.64rem;color:var(--muted);min-height:15px}
.status.run{color:var(--gold)}.status.ok{color:var(--green)}.status.err{color:var(--ember)}
.spin{display:inline-block;width:11px;height:11px;border:2px solid var(--dim);border-top-color:var(--accent);
  border-radius:50%;animation:sp .8s linear infinite;vertical-align:-1px;margin-right:7px}
@keyframes sp{to{transform:rotate(360deg)}}
.open{display:none;margin-top:11px}
.open a{font-family:'Space Mono',monospace;font-size:.66rem;letter-spacing:.06em;color:var(--accent);text-decoration:none;
  border-bottom:1px solid rgba(0,212,255,.35);padding-bottom:2px}
.open a:hover{color:#fff;border-color:#fff}
pre{background:#04070e;border:1px solid var(--dim);border-radius:9px;padding:11px;margin-top:11px;font-size:.64rem;line-height:1.5;
  color:#7e8da3;max-height:150px;overflow:auto;white-space:pre-wrap;display:none;font-family:'Space Mono',monospace}
.foot{color:var(--muted);font-size:.82rem;line-height:1.85;margin-top:34px;border-top:1px solid var(--border);padding-top:18px}
.foot b{color:#bfe9f6;font-family:'Space Mono',monospace;font-size:.6rem;letter-spacing:.1em;text-transform:uppercase}
</style></head><body>
<canvas id="stars"></canvas><div class="grid-bg"></div>
<div class="wrap">

<header>
  <!-- Drop a logo.png in this folder and it appears here automatically. -->
  <span class="logo-badge" id="logo-badge">
    <img id="logo" src="/logo.png" alt="Paranoid Penguin"
         onerror="document.getElementById('logo-badge').remove();document.getElementById('wordmark').style.display='block';">
  </span>
  <div id="wordmark" class="brand" style="display:none">PARANOID <span class="c">PENGUIN</span></div>
  <div class="tag">by <b>Able<span class="c">V</span>Labs</b> · paranoid so you don't have to be</div>
</header>

<div class="hero" id="hero">
  <div class="badge" id="badge">
    <div class="ltr" id="grade-ltr" style="color:var(--dim)">—</div>
    <div class="scr" id="grade-scr"></div>
    <div class="lbl">Security grade</div>
  </div>
  <div class="fixes">
    <div class="fh">Top things to fix</div>
    <div id="fix-list"><div class="hint">Run any check below and your security grade and priority
      fixes appear here — the fastest read on where you stand.</div></div>
  </div>
</div>

<div class="grid">
  <div class="card"><div class="kick">01 — World threats</div><h2>Threat Intelligence</h2>
    <p>Today's list of vulnerabilities attackers are actively exploiting worldwide (CISA + EPSS).</p>
    <button class="btn" data-task="feeds" data-open="real_dashboard.html">Update &amp; view threats</button>
    <div class="status" id="st-feeds"></div><div class="open" id="op-feeds"></div><pre id="lg-feeds"></pre></div>

  <div class="card"><div class="kick">02 — Endpoint</div><h2>Computer Scan</h2>
    <p>Installed programs, open ports, antivirus &amp; firewall — cross-referenced against the threat list.</p>
    <button class="btn" data-task="pc" data-open="my_dashboard.html">Scan this PC</button>
    <div class="status" id="st-pc"></div><div class="open" id="op-pc"></div><pre id="lg-pc"></pre></div>

  <div class="card"><div class="kick">03 — Software</div><h2>App Vulnerability Audit</h2>
    <p>Checks your packages against real vulnerability databases and says exactly which to update.</p>
    <button class="btn" data-task="apps" data-open="my_dashboard.html">Audit my apps</button>
    <div class="status" id="st-apps"></div><div class="open" id="op-apps"></div><pre id="lg-apps"></pre></div>

  <div class="card"><div class="kick">04 — Configuration</div><h2>Hardening Audit</h2>
    <p>Mini CIS benchmark mapped to MITRE ATT&amp;CK: encryption, UAC, RDP, SMBv1, guest account, updates.</p>
    <button class="btn" data-task="harden" data-open="my_dashboard.html">Audit my settings</button>
    <div class="status" id="st-harden"></div><div class="open" id="op-harden"></div><pre id="lg-harden"></pre></div>

  <div class="card"><div class="kick">05 — Persistence</div><h2>Startup Review</h2>
    <p>Everything that auto-runs at boot — where malware hides to survive reboots. Flags suspicious entries.</p>
    <button class="btn" data-task="startup" data-open="my_dashboard.html">Review startup items</button>
    <div class="status" id="st-startup"></div><div class="open" id="op-startup"></div><pre id="lg-startup"></pre></div>

  <div class="card"><div class="kick">06 — Intrusion</div><h2>Login Monitor</h2>
    <p>Reads the Windows log for bursts of failed sign-ins — the fingerprint of a brute-force attack. (Admin.)</p>
    <button class="btn" data-task="logins" data-open="my_dashboard.html">Check for break-in attempts</button>
    <div class="status" id="st-logins"></div><div class="open" id="op-logins"></div><pre id="lg-logins"></pre></div>

  <div class="card"><div class="kick">07 — Network</div><h2>Network Map + Alerts</h2>
    <p>Lists every device on your own network and flags anything new that joined. (Needs <b style="font-family:inherit;color:var(--muted)">nmap</b>.)</p>
    <button class="btn" data-task="network" data-open="my_dashboard.html">Map my network</button>
    <div class="status" id="st-network"></div><div class="open" id="op-network"></div><pre id="lg-network"></pre></div>

  <div class="card"><div class="kick">08 — Live traffic</div><h2>Connection Monitor</h2>
    <p>Who is your PC talking to right now? Live outbound connections, the program, and the server it's reaching — how analysts spot malware phoning home.</p>
    <button class="btn" data-task="connections" data-open="my_dashboard.html">See live connections</button>
    <div class="status" id="st-connections"></div><div class="open" id="op-connections"></div><pre id="lg-connections"></pre></div>

  <div class="card"><div class="kick">09 — Wireless</div><h2>Wi-Fi Security Audit</h2>
    <p>Is your network encrypted (WPA3/WPA2) or open? Also flags saved open networks that let "evil twin" hotspots auto-connect you.</p>
    <button class="btn" data-task="wifi" data-open="my_dashboard.html">Audit my Wi-Fi</button>
    <div class="status" id="st-wifi"></div><div class="open" id="op-wifi"></div><pre id="lg-wifi"></pre></div>
</div>

<div class="foot">
  <b>What is this?</b> &nbsp;A personal security scanner — it shows what's on your computer and network,
  what's risky, and what to fix first, with a plain-English A–F grade.<br>
  <b>Privacy</b> &nbsp;Every check runs locally; results stay on your machine. Nothing is uploaded.<br>
  <b>Tip</b> &nbsp;Right-click the launcher → Run as administrator to unlock disk-encryption and login checks.<br>
  <b>To stop</b> &nbsp;Close the black command window that opened alongside this page.
</div>
</div>

<script>
(function(){var c=document.getElementById('stars'),x=c.getContext('2d'),st=[];
function sz(){c.width=innerWidth;c.height=innerHeight;}sz();addEventListener('resize',sz);
for(var i=0;i<140;i++)st.push({x:Math.random(),y:Math.random(),r:Math.random()*1.3+.2,a:Math.random()*.5+.1,t:Math.random()*6.28,s:Math.random()*.9+.2});
(function loop(){x.clearRect(0,0,c.width,c.height);for(var i=0;i<st.length;i++){var d=st[i];d.t+=.02*d.s;var tw=d.a*(.6+.4*Math.sin(d.t));
x.beginPath();x.arc(d.x*c.width,d.y*c.height,d.r,0,7);x.fillStyle='rgba(150,210,255,'+tw.toFixed(3)+')';x.fill();}requestAnimationFrame(loop);})();})();
addEventListener('mousemove',function(e){var gx=(e.clientX/innerWidth-.5)*14,gy=(e.clientY/innerHeight-.5)*14;
document.querySelector('.grid-bg').style.transform='translate('+gx+'px,'+gy+'px)';});

var GC={A:'#00ff88',B:'#00d4ff',C:'#e8960a',D:'#e0a35a',F:'#c23b22'};
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function loadGrade(retry){
  fetch('/status?t='+Date.now(),{cache:'no-store'}).then(function(r){return r.json();}).then(function(g){
    if(!g||!g.has_data){ if(!retry) setTimeout(function(){loadGrade(true);},500); return; }
    var col=GC[g.letter]||'#5a6480';var lt=document.getElementById('grade-ltr');
    lt.textContent=g.letter;lt.style.color=col;document.getElementById('badge').style.borderColor=col;
    document.getElementById('grade-scr').textContent=g.score+' / 100';
    var host=document.getElementById('fix-list');
    if(!g.top_fixes||!g.top_fixes.length){host.innerHTML='<div class="hint">No priority issues in what you\'ve scanned. Nice.</div>';return;}
    var sev={high:'#c23b22',med:'#e8960a',low:'#00d4ff'};
    host.innerHTML=g.top_fixes.map(function(f){return '<div class="fix"><span class="sev" style="color:'+(sev[f.sev]||'#5a6480')+'">'+
      f.sev.toUpperCase()+'</span><div><b>'+esc(f.title)+'</b><div class="why">'+esc(f.why)+'</div><div class="cmd">'+esc(f.fix)+'</div></div></div>';}).join('');
  }).catch(function(){});
}
function run(btn){
  var task=btn.getAttribute('data-task'),dash=btn.getAttribute('data-open');
  var st=document.getElementById('st-'+task),op=document.getElementById('op-'+task),lg=document.getElementById('lg-'+task);
  btn.disabled=true;st.className='status run';st.innerHTML='<span class="spin"></span>Working… keep this tab open.';
  if(op)op.style.display='none';if(lg)lg.style.display='none';
  fetch('/run?task='+task).then(function(r){return r.json();}).then(function(res){
    btn.disabled=false;
    if(res.ok){st.className='status ok';st.textContent='✓ Done.';}else{st.className='status err';st.textContent='⚠ Finished with a problem — see details.';}
    if(op&&dash){op.style.display='block';op.innerHTML='<a href="/'+dash+'?t='+Date.now()+'" target="_blank">Open my results →</a>';}
    if(lg&&res.output){lg.style.display='block';lg.textContent=res.output;}
    loadGrade();
  }).catch(function(e){btn.disabled=false;st.className='status err';st.textContent='⚠ Could not run: '+e;});
}
var b=document.querySelectorAll('button[data-task]');for(var i=0;i<b.length;i++)b[i].addEventListener('click',function(){run(this);});
loadGrade();
</script>
</body></html>"""


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=HERE, **k)

    def do_GET(self):
        # Host-header guard: a malicious webpage can make YOUR browser fire
        # requests at 127.0.0.1 (CSRF), and DNS-rebinding tricks can even read
        # responses — which here would mean your private scan results. Only
        # answer requests actually addressed to this panel.
        host = (self.headers.get("Host") or "").split(":")[0].strip().lower()
        if host not in ("127.0.0.1", "localhost"):
            self.send_error(403, "Forbidden")
            return
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self._html(PAGE)
        if parsed.path == "/run":
            return self._run(parse_qs(parsed.query).get("task", [""])[0])
        if parsed.path == "/status":
            return self._status()
        return super().do_GET()

    def _html(self, html):
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _run(self, task):
        mod_name = TASKS.get(task)
        mod = _MOD.get(mod_name) if mod_name else None
        if mod is None:
            return self._json({"ok": False, "output": "That check isn't available."})
        buf = io.StringIO()
        ok = True
        with _RUN_LOCK:
            try:
                with contextlib.redirect_stdout(buf):
                    mod.main()
            except Exception as e:
                ok = False
                buf.write(f"\nError: {e}")
        self._json({"ok": ok, "output": buf.getvalue()[-4000:].strip()})

    def _status(self):
        try:
            g = _MOD.get("grade")
            self._json(g.compute() if g else {"has_data": False})
        except Exception:
            self._json({"has_data": False})

    def _json(self, obj):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def main():
    os.chdir(HERE)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}/"
    print("=" * 54)
    print("   PARANOID PENGUIN  ·  by AbleV Labs")
    print("=" * 54)
    print(f"   Open in your browser:  {url}")
    print("   (a browser tab should open automatically)")
    print("   Keep THIS window open while you use it.")
    print("   Close this window to stop.")
    print("=" * 54)
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
