#!/bin/bash
SESSIONS_DIR="$HOME/.openclaw/agents/main/sessions"
LOG="$HOME/.openclaw/logs/startup-cleanup.log"

log() { echo "[$(date '+%Y-%m-%dT%H:%M:%S')] $*" | tee -a "$LOG"; }
log "=== Gateway start ==="

find "$SESSIONS_DIR" -name "*.lock" -delete 2>/dev/null && log "Cleared locks"
find "$SESSIONS_DIR" -name "*.jsonl" -size 0 -delete 2>/dev/null && log "Cleared empty sessions"

# Force-kill anything holding port 8787 (prevents EADDRINUSE on restart)
PORT_PID=$(lsof -ti :8787 2>/dev/null)
if [ -n "$PORT_PID" ]; then
    kill -9 $PORT_PID 2>/dev/null
    log "Killed stale process on port 8787 (pid: $PORT_PID)"
    sleep 1
fi

log "Starting gateway..."
exec /opt/homebrew/opt/node/bin/node \
    /Users/axiom/.gemini/antigravity/scratch/openclaw/dist/index.js \
    gateway --port 18789
