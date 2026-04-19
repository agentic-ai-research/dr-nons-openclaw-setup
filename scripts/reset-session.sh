#!/bin/bash
# reset-session.sh — Force a fresh OpenClaw session and restart the gateway.
#
# Run this after:
#   - Installing new skills (they won't load into a live session)
#   - Switching the primary model
#   - Bot behaving erratically (context near-full, wrong behavior)
#   - Any openclaw.json config change
#
# Usage: bash ~/.openclaw/scripts/reset-session.sh

set -e

SESSIONS_DIR="$HOME/.openclaw/agents/main/sessions"
SESSIONS_JSON="$SESSIONS_DIR/sessions.json"
PLIST="$HOME/Library/LaunchAgents/ai.openclaw.gateway.plist"
LOG="$HOME/.openclaw/logs/reset-session.log"
TS=$(date +%Y%m%d-%H%M%S)

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== Session reset started ==="

# 0. Validate openclaw.json before touching anything
VALIDATION=$(/opt/homebrew/opt/node/bin/node \
    /Users/axiom/.gemini/antigravity/scratch/openclaw/dist/index.js \
    gateway --port 18799 2>&1 | head -5 || true)
if echo "$VALIDATION" | grep -q "Config invalid"; then
    log "ERROR: openclaw.json is invalid. Aborting reset."
    echo ""
    echo "$VALIDATION"
    echo ""
    echo "Fix the config first, then re-run this script."
    exit 1
fi
log "Config valid"

# 1. Archive any active session JSONL files
for f in "$SESSIONS_DIR"/*.jsonl; do
    [ -f "$f" ] || continue
    [[ "$f" == *".archived-"* ]] && continue
    mv "$f" "${f%.jsonl}.jsonl.archived-$TS"
    log "Archived: $(basename $f)"
done

# 2. Remove stale lock files
find "$SESSIONS_DIR" -name "*.lock" -delete 2>/dev/null
log "Cleared lock files"

# 3. Clear session registry
if [ -f "$SESSIONS_JSON" ]; then
    python3 -c "
import json, sys
data = json.load(open('$SESSIONS_JSON'))
for key in data:
    data[key]['sessionId'] = None
    data[key]['status'] = 'idle'
    data[key]['abortedLastRun'] = False
with open('$SESSIONS_JSON', 'w') as f:
    json.dump(data, f, indent=2)
print('Session registry cleared')
"
fi

# 4. Stop old gateway FIRST (it holds port 8787)
log "Stopping gateway..."
launchctl unload "$PLIST" 2>/dev/null || true
sleep 5  # wait for port 8787 to be released

# 4b. Force-kill anything still on port 8787
PORT_PID=$(lsof -ti :8787 2>/dev/null)
if [ -n "$PORT_PID" ]; then
    kill -9 $PORT_PID 2>/dev/null
    log "Force-killed stale process on port 8787 (pid: $PORT_PID)"
fi

# 5. Start fresh gateway
log "Starting gateway..."
launchctl load "$PLIST"
sleep 12

# 6. Verify
HEALTH=$(curl -s http://localhost:18789/health 2>/dev/null || true)
if echo "$HEALTH" | grep -q '"ok":true'; then
    log "Gateway live. Fresh session will start on your next Telegram/Discord message."
else
    log "WARNING: Gateway may not be up yet. Check: curl http://localhost:18789/health"
fi
