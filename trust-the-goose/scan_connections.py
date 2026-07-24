"""
CONNECTION MONITOR — who is your PC talking to, right now?

Lists every live outbound internet connection: the program, the remote server's
IP, and (via reverse-DNS) who owns it. This is exactly how a security analyst
spots malware "phoning home" to a command server, or data being quietly
exfiltrated. Nothing else in the app shows live network traffic.

Maps to MITRE ATT&CK T1071 (Command & Control) and T1041 (Exfiltration).
Read-only.

    python scan_connections.py

Output: connections_audit.json + refreshes my_dashboard.html
"""
import ipaddress
import json
import os
import socket
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

PS = (
    "Get-NetTCPConnection -State Established -EA SilentlyContinue | ForEach-Object { "
    "$p = Get-Process -Id $_.OwningProcess -EA SilentlyContinue; "
    "[PSCustomObject]@{ Process=$p.ProcessName; PID=$_.OwningProcess; "
    "Remote=$_.RemoteAddress; Port=$_.RemotePort } } | ConvertTo-Json -Compress"
)


def is_external(ip):
    """True only for public internet addresses (skip LAN/loopback/link-local)."""
    try:
        a = ipaddress.ip_address(ip)
        return a.is_global and not a.is_multicast
    except ValueError:
        return False


def main():
    if not sys.platform.startswith("win"):
        print("scan_connections.py targets Windows. Skipping.")
        return

    print("[conn 1/3] Reading live network connections (read-only)...")
    try:
        raw = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", PS],
            capture_output=True, text=True, timeout=90).stdout.strip()
        rows = json.loads(raw) if raw else []
        if isinstance(rows, dict):
            rows = [rows]
    except Exception as e:
        print(f"      Could not read connections: {e}")
        rows = []

    # keep only outbound-to-internet, de-duplicated
    seen, ext = set(), []
    for r in rows:
        ip = str(r.get("Remote", ""))
        if not is_external(ip):
            continue
        key = (r.get("Process"), ip, r.get("Port"))
        if key in seen:
            continue
        seen.add(key)
        ext.append({"process": r.get("Process") or "?", "pid": r.get("PID"),
                    "remote": ip, "port": r.get("Port")})

    print(f"[conn 2/3] Resolving {len(set(c['remote'] for c in ext))} unique servers...")
    # setdefaulttimeout is PROCESS-WIDE — if we don't restore it, every
    # socket the control panel opens afterwards (threat-feed downloads etc.)
    # inherits this 1.2s limit and starts failing on slow links.
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(1.2)
    cache = {}
    try:
        for c in ext:
            ip = c["remote"]
            if ip not in cache:
                try:
                    cache[ip] = socket.gethostbyaddr(ip)[0]
                except Exception:
                    cache[ip] = ""
            c["host"] = cache[ip]
    finally:
        socket.setdefaulttimeout(old_timeout)

    # group by process for the dashboard
    procs = {}
    for c in ext:
        p = procs.setdefault(c["process"], {"name": c["process"], "count": 0, "hosts": set()})
        p["count"] += 1
        p["hosts"].add(c["host"] or c["remote"])
    proc_list = sorted(
        ({"name": p["name"], "count": p["count"], "hosts": sorted(p["hosts"])[:6]}
         for p in procs.values()),
        key=lambda x: x["count"], reverse=True)

    unresolved = sum(1 for c in ext if not c["host"])
    result = {"connections": ext, "processes": proc_list,
              "total_external": len(ext), "unresolved": unresolved}

    with open(os.path.join(HERE, "connections_audit.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"[conn 3/3] {len(ext)} live internet connections across {len(proc_list)} programs "
          f"({unresolved} to unnamed servers) -> connections_audit.json")
    for p in proc_list[:6]:
        print(f"          {p['name']}: {p['count']} → {', '.join(p['hosts'][:3])}")

    try:
        import build_my_dashboard
        build_my_dashboard.main()
    except Exception as e:
        print(f"      (dashboard step: {e})")


if __name__ == "__main__":
    main()
