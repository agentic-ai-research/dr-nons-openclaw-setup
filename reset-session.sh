#!/bin/bash
# reset-session.sh — Force a fresh OpenClaw session and restart the gateway.
#
# Run this after:
#   - Installing new skills (they won't load into a live session)
#   - Switching the primary model
#   - Bot behaving erratically
#   - Any openclaw.json config change
#
# Usage: bash reset-session.sh

set -e

SESSIONS_DIR="$HOME/.openclaw/agents/main/sessions"
SESSIONS_JSON="$SESSIONS_DIR/sessions.json"
PLIST="$HOME/Library/LaunchAgents/ai.openclaw.gateway.plist"
LOG="$HOME/.openclaw/logs/reset-session.log"
TS=$(date +%Y%m%d-%H%M%S)

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== Session reset started ==="

# 1. Archive active session JSONL files
for f in "$SESSIONS_DIR"/*.jsonl; do
    [ -f "$f" ] || continue
    [[ "$f" == *".archived-"* ]] && continue
    mv "$f" "${f%.jsonl}.jsonl.archived-$TS"
    log "Archived: $(basename $f)"
done

# 2. Remove stale lock files
find "$SESSIONS_DIR" -name "*.lock" -delete 2>/dev/null
log "Cleared lock files"

# 3. Wipe session registry (including stale skillsSnapshot)
if [ -f "$SESSIONS_JSON" ]; then
    python3 -c "
import json
data = json.load(open('$SESSIONS_JSON'))
for key in data:
    data[key].pop('skillsSnapshot', None)
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
sleep 5

# 5. Force-kill anything still on port 8787
PORT_PID=$(lsof -ti :8787 2>/dev/null)
if [ -n "$PORT_PID" ]; then
    kill -9 $PORT_PID 2>/dev/null
    log "Force-killed stale process on port 8787 (pid: $PORT_PID)"
fi

# 6. Start fresh gateway
log "Starting gateway..."
launchctl load "$PLIST"
sleep 12

# 7. Verify
HEALTH=$(curl -s http://localhost:18789/health 2>/dev/null)
if echo "$HEALTH" | grep -q '"ok":true'; then
    log "Gateway live. Next Telegram message starts a fresh session with all skills."
else
    log "WARNING: Gateway may not be up yet. Check: curl http://localhost:18789/health"
fi
