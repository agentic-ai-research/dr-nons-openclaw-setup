#!/usr/bin/env python3
"""
Polls the Fly.io relay for Telegram updates and forwards them
to the local OpenClaw webhook listener.

Resilience features:
- Pending queue: messages that fail to forward are retried until gateway is ready
- Startup wait: on launch, waits up to 60s for gateway to become available
- Survives gateway restarts, sleep/wake cycles, and cold boots
"""
import time, json, urllib.request, urllib.error, sys, collections

RELAY_URL     = "https://dnoc-tg-relay.fly.dev/"
LOCAL_WEBHOOK = "http://127.0.0.1:8787/telegram-webhook"
LOCAL_HEALTH  = "http://127.0.0.1:18789/health"
SECRET        = "a4963b87d7d67c93a00517b5117dd4f45902e11a548d2e5ecdf339926b4c241c"
POLL_INTERVAL = 2   # seconds between relay polls
MAX_PENDING   = 500 # safety cap on undelivered message queue

# Messages that failed to forward — retried on every loop before polling for new ones
pending = collections.deque()


def gateway_ready():
    try:
        req = urllib.request.Request(LOCAL_HEALTH)
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def wait_for_gateway(timeout=120):
    """Block until gateway is up, or timeout. Called once at startup."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if gateway_ready():
            return True
        time.sleep(2)
    return False


def poll():
    req = urllib.request.Request(RELAY_URL)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def forward(update_str):
    data = update_str.encode()
    req = urllib.request.Request(LOCAL_WEBHOOK, data=data, method="POST", headers={
        "Content-Type": "application/json",
        "X-Telegram-Bot-Api-Secret-Token": SECRET,
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status


# ── startup: wait for gateway before processing anything ─────────────────────

print("Bridge starting — waiting for gateway...", flush=True)
if wait_for_gateway(timeout=120):
    print("Gateway ready. Bridge running — polling relay every 2s", flush=True)
else:
    print("Gateway did not come up within 120s — continuing anyway (will retry per-message)", flush=True)

# ── main loop ─────────────────────────────────────────────────────────────────

while True:
    # 1. Retry any messages that previously failed to forward
    if pending:
        if gateway_ready():
            retry_count = len(pending)
            delivered = 0
            for _ in range(retry_count):
                msg_str = pending.popleft()
                try:
                    status = forward(msg_str)
                    msg_preview = json.loads(msg_str).get("message", {}).get("text", "")[:40]
                    print(f"retry delivered: {msg_preview!r} -> {status}", flush=True)
                    delivered += 1
                except Exception as e:
                    pending.append(msg_str)  # back in queue
                    print(f"retry failed: {e}", flush=True)
                    break  # gateway still not taking — stop retrying this cycle
            if delivered:
                print(f"Flushed {delivered}/{retry_count} queued message(s)", flush=True)
        else:
            print(f"Gateway down — {len(pending)} message(s) queued", flush=True)

    # 2. Poll relay for new messages
    try:
        updates = poll()
        for u in updates:
            try:
                status = forward(u)
                msg = json.loads(u).get("message", {}).get("text", "")[:40]
                print(f"forwarded: {msg!r} -> {status}", flush=True)
            except Exception as e:
                # Gateway not ready — queue for retry
                print(f"forward failed (queued): {e}", flush=True)
                if len(pending) < MAX_PENDING:
                    pending.append(u)
                else:
                    print("WARNING: pending queue full — oldest message dropped", flush=True)
    except Exception as e:
        err_str = str(e)
        # Connection reset / timeout from Fly.io is expected on idle connections — suppress log spam
        if any(s in err_str for s in ("Connection reset by peer", "timed out", "UND_ERR")):
            pass  # silent — will retry in 2s
        else:
            print(f"poll error: {e}", flush=True)

    time.sleep(POLL_INTERVAL)
