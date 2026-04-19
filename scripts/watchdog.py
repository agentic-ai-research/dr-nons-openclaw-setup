#!/usr/bin/env python3
"""
OpenClaw Watchdog — runs every 5 minutes via cron.

Checks:
  1. Gateway health (port 18789)
  2. relay-bridge process alive
  3. Session file size (auto-resets if > 400KB)

On gateway failure:
  - Force-kills anything on port 8787 (prevents EADDRINUSE)
  - Unloads/reloads the gateway LaunchAgent
  - Sends Telegram alert with diagnosis

Logs to: ~/.openclaw/logs/watchdog.log
"""
import os, sys, json, time, subprocess, urllib.request, urllib.error
from datetime import datetime

# ── config ────────────────────────────────────────────────────────────────────

GATEWAY_HEALTH  = "http://localhost:18789/health"
GATEWAY_PLIST   = os.path.expanduser("~/Library/LaunchAgents/ai.openclaw.gateway.plist")
RELAY_SCRIPT    = os.path.expanduser("~/.openclaw/scripts/relay-bridge.py")
SESSIONS_DIR    = os.path.expanduser("~/.openclaw/agents/main/sessions")
SESSION_MAX_KB  = 400   # auto-reset session above this size
CHAT_ID         = "YOUR_CHAT_ID"
TOKEN_FILE      = os.path.expanduser("~/.openclaw/credentials/telegram-token.txt")
LOG_FILE        = os.path.expanduser("~/.openclaw/logs/watchdog.log")

# ── helpers ───────────────────────────────────────────────────────────────────

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def telegram_token():
    return open(TOKEN_FILE).read().strip()

def send_alert(text):
    try:
        token = telegram_token()
        payload = json.dumps({"chat_id": CHAT_ID, "text": text}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log(f"Alert send failed: {e}")

def gateway_alive():
    try:
        req = urllib.request.Request(GATEWAY_HEALTH)
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            return data.get("ok") is True
    except Exception:
        return False

def relay_alive():
    result = subprocess.run(
        ["pgrep", "-f", "relay-bridge.py"],
        capture_output=True
    )
    return result.returncode == 0

def kill_port(port):
    """Force-kill any process holding the given port."""
    result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
    pids = result.stdout.strip().split()
    for pid in pids:
        try:
            subprocess.run(["kill", "-9", pid], capture_output=True)
            log(f"  Killed PID {pid} on port {port}")
        except Exception:
            pass
    return len(pids) > 0

def restart_gateway():
    log("Restarting gateway...")
    subprocess.run(["launchctl", "unload", GATEWAY_PLIST], capture_output=True)
    time.sleep(4)
    kill_port(8787)  # ensure port is free before reload
    time.sleep(1)
    subprocess.run(["launchctl", "load", GATEWAY_PLIST], capture_output=True)
    time.sleep(10)
    return gateway_alive()

def active_session_files():
    files = []
    for f in os.listdir(SESSIONS_DIR):
        if f.endswith(".jsonl") and ".archived-" not in f:
            files.append(os.path.join(SESSIONS_DIR, f))
    return files

def session_size_kb():
    total = 0
    for f in active_session_files():
        try:
            total += os.path.getsize(f) / 1024
        except Exception:
            pass
    return total

def reset_session():
    """Archive active session files and clear the registry."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    archived = []
    for f in active_session_files():
        dest = f.replace(".jsonl", f".jsonl.archived-{ts}")
        os.rename(f, dest)
        archived.append(os.path.basename(f))

    registry = os.path.join(SESSIONS_DIR, "sessions.json")
    if os.path.exists(registry):
        data = json.load(open(registry))
        for key in data:
            data[key]["sessionId"] = None
            data[key]["status"] = "idle"
            data[key]["abortedLastRun"] = False
        json.dump(data, open(registry, "w"), indent=2)

    return archived

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    issues = []

    # ── 1. Gateway health ──────────────────────────────────────────────────────
    if not gateway_alive():
        log("FAIL: Gateway not responding")
        recovered = restart_gateway()
        if recovered:
            log("OK: Gateway restarted successfully")
            issues.append("Gateway was down — auto-restarted ✅")
        else:
            log("ERROR: Gateway restart failed")
            issues.append("Gateway DOWN — restart failed ❌ Manual intervention needed")
    else:
        log("OK: Gateway alive")

    # ── 2. relay-bridge ────────────────────────────────────────────────────────
    if not relay_alive():
        log("FAIL: relay-bridge not running — restarting via launchctl")
        subprocess.run(["launchctl", "start", "ai.openclaw.relay-bridge"], capture_output=True)
        time.sleep(3)
        if relay_alive():
            log("OK: relay-bridge restarted")
            issues.append("relay-bridge was dead — restarted ✅")
        else:
            log("ERROR: relay-bridge still not running")
            issues.append("relay-bridge DOWN — restart failed ❌")
    else:
        log("OK: relay-bridge alive")

    # ── 3. Session size ────────────────────────────────────────────────────────
    size_kb = session_size_kb()
    log(f"Session size: {size_kb:.0f} KB (limit: {SESSION_MAX_KB} KB)")
    if size_kb > SESSION_MAX_KB:
        log(f"Session too large ({size_kb:.0f} KB) — auto-resetting")
        archived = reset_session()
        log(f"Session reset: archived {len(archived)} file(s)")
        issues.append(f"Session was {size_kb:.0f} KB — auto-reset ✅ Fresh context on next message.")

    # ── 4. Alert if anything was wrong ────────────────────────────────────────
    if issues:
        msg = "⚠️ OpenClaw Watchdog\n\n" + "\n".join(f"• {i}" for i in issues)
        send_alert(msg)
        log(f"Alert sent: {len(issues)} issue(s)")
    else:
        log("All systems nominal")

if __name__ == "__main__":
    main()
