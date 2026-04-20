#!/bin/bash
# =============================================================================
# OpenClaw Install Script
# Run this from the cloned repo directory on a fresh machine.
# Usage: bash install.sh
#
# What it does automatically:
#   - Installs prerequisites (Homebrew, Node, Python, Tesseract, pip packages)
#   - Creates all directories
#   - Fills in all templates with your credentials
#   - Copies scripts and skills to the right places
#   - Loads LaunchAgents (gateway + relay-bridge)
#   - Sets up crontab
#   - Runs watchdog to verify everything is working
#
# What you must do manually (prompted at the end):
#   - Run google-auth.py and complete the browser OAuth flow
#   - Send a message to @userinfobot in Telegram to get your chat ID
# =============================================================================

set -e

# ── colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; RESET='\033[0m'

ok()   { echo -e "${GREEN}  ✓${RESET} $*"; }
info() { echo -e "${BLUE}  →${RESET} $*"; }
warn() { echo -e "${YELLOW}  ⚠${RESET} $*"; }
fail() { echo -e "${RED}  ✗${RESET} $*"; exit 1; }
step() { echo -e "\n${BOLD}${BLUE}[$1]${RESET} ${BOLD}$2${RESET}"; }
ask()  {
    local var="$1" prompt="$2" default="$3" secret="$4"
    if [ -n "$default" ]; then
        prompt="$prompt [${default}]"
    fi
    if [ "$secret" = "secret" ]; then
        read -r -s -p "  $prompt: " "$var"
        echo
    else
        read -r -p "  $prompt: " "$var"
    fi
    # Use default if empty
    if [ -z "${!var}" ] && [ -n "$default" ]; then
        eval "$var='$default'"
    fi
}

USERNAME=$(whoami)
HOME_DIR="/Users/$USERNAME"
OPENCLAW_DIR="$HOME_DIR/.openclaw"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo -e "\n${BOLD}OpenClaw Setup${RESET}"
echo "─────────────────────────────────────────────"
echo "Repo:     $REPO_DIR"
echo "User:     $USERNAME"
echo "Install:  $OPENCLAW_DIR"
echo "─────────────────────────────────────────────"

# ── Step 1: Prerequisites ─────────────────────────────────────────────────────
step "1/9" "Prerequisites"

if ! command -v brew &>/dev/null; then
    info "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
ok "Homebrew"

for pkg in node python3 tesseract; do
    if ! brew list "$pkg" &>/dev/null; then
        info "Installing $pkg..."
        brew install "$pkg" -q
    fi
    ok "$pkg"
done

info "Installing Python packages..."
pip3 install -q google-auth google-auth-oauthlib google-api-python-client \
    pillow pytesseract youtube-transcript-api yt-dlp 2>/dev/null
ok "Python packages"

# ── Step 2: Find OpenClaw installation ───────────────────────────────────────
step "2/9" "Locate OpenClaw"

OPENCLAW_NODE=""
OPENCLAW_DIST=""

# Try common install paths
for candidate in \
    "$HOME_DIR/.gemini/antigravity/scratch/openclaw/dist/index.js" \
    "/usr/local/lib/node_modules/openclaw/dist/index.js" \
    "$HOME_DIR/.npm-global/lib/node_modules/openclaw/dist/index.js" \
    "$(npm root -g 2>/dev/null)/openclaw/dist/index.js"; do
    if [ -f "$candidate" ]; then
        OPENCLAW_DIST="$candidate"
        break
    fi
done

# Try finding the binary directly
if command -v openclaw-gateway &>/dev/null; then
    OPENCLAW_NODE=$(which node)
    ok "Found openclaw-gateway binary"
elif [ -n "$OPENCLAW_DIST" ]; then
    OPENCLAW_NODE=$(which node)
    ok "Found OpenClaw dist: $OPENCLAW_DIST"
else
    warn "OpenClaw dist not found automatically."
    echo "  Please install OpenClaw from https://openclaw.ai first, then re-run this script."
    echo "  Or enter the path to dist/index.js manually:"
    ask OPENCLAW_DIST "Path to openclaw dist/index.js"
    OPENCLAW_NODE=$(which node)
    [ -f "$OPENCLAW_DIST" ] || fail "Path does not exist: $OPENCLAW_DIST"
fi

NODE_BIN=$(which node)
ok "Node: $NODE_BIN"

# ── Step 3: Collect credentials ───────────────────────────────────────────────
step "3/9" "Credentials"
echo "  These are stored in ~/.openclaw/credentials/ and never leave your machine."
echo "  Press Enter to skip optional ones (you can add them later)."
echo ""

ask OPENAI_KEY    "OpenAI API key (sk-...)" "" secret
ask TAVILY_KEY    "Tavily API key (tvly-...)" "" secret
ask TG_TOKEN      "Telegram bot token (from BotFather)" "" secret
ask TG_CHAT_ID    "Your Telegram chat ID (from @userinfobot — skip if unknown)" ""
ask GH_TOKEN      "GitHub personal access token (for morning briefing)" "" secret
ask GEMINI_KEY    "Google Gemini API key (from aistudio.google.com/apikey — FREE)" "" secret
 ask THAILLM_KEY   "ThaiLLM API key (free — skip if not needed)" "" secret
ask RELAY_URL     "Fly.io relay URL" "https://dnoc-tg-relay.fly.dev/"
ask WEBHOOK_SECRET "Relay webhook secret" "$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
ask GATEWAY_TOKEN  "Gateway auth token" "$(python3 -c 'import secrets; print(secrets.token_hex(24))')"

# ── Step 4: Create directories ────────────────────────────────────────────────
step "4/9" "Directories"

for d in \
    "$OPENCLAW_DIR/credentials" \
    "$OPENCLAW_DIR/logs" \
    "$OPENCLAW_DIR/scripts" \
    "$OPENCLAW_DIR/agents/main/sessions" \
    "$OPENCLAW_DIR/workspace/skills" \
    "$OPENCLAW_DIR/workspace/state" \
    "$HOME_DIR/self-improving/domains" \
    "$HOME_DIR/self-improving/projects"; do
    mkdir -p "$d"
done
ok "Directory structure created"

# ── Step 5: Credentials files ─────────────────────────────────────────────────
step "5/9" "Writing credentials"

[ -n "$GEMINI_KEY" ]  && echo "$GEMINI_KEY"  > "$OPENCLAW_DIR/credentials/gemini-key.txt"
[ -n "$TG_TOKEN" ]    && echo "$TG_TOKEN"    > "$OPENCLAW_DIR/credentials/telegram-token.txt"
[ -n "$GH_TOKEN" ]    && echo "$GH_TOKEN"    > "$OPENCLAW_DIR/credentials/github-token.txt"
chmod 600 "$OPENCLAW_DIR/credentials/"* 2>/dev/null || true

if [ -n "$THAILLM_KEY" ]; then
    python3 -c "
import json
data = {'url': 'http://thaillm.or.th/api/openthaigpt/v1/chat/completions', 'apiKey': '$THAILLM_KEY'}
json.dump(data, open('$OPENCLAW_DIR/credentials/thaillm.json', 'w'), indent=2)
"
    ok "ThaiLLM credentials saved"
fi
ok "Credentials written"

# ── Step 6: openclaw.json ─────────────────────────────────────────────────────
step "6/9" "openclaw.json"

cat > "$OPENCLAW_DIR/openclaw.json" << EOFJSON
{
  "gateway": {
    "mode": "local",
    "auth": {
      "mode": "token",
      "token": "$GATEWAY_TOKEN"
    }
  },
  "plugins": {
    "entries": {
      "ollama": { "enabled": false },
      "active-memory": { "enabled": false },
      "openai": { "enabled": true }
    }
  },
  "agents": {
    "defaults": {
      "model": { "primary": "openai/gpt-4o-mini" },
      "llm": { "idleTimeoutSeconds": 0 },
      "compaction": { "reserveTokensFloor": 8000 },
      "models": { "openai/gpt-4o-mini": {} }
    }
  },
  "models": {
    "providers": {
      "openai": {
        "baseUrl": "https://api.openai.com/v1",
        "api": "openai-responses",
        "apiKey": "$OPENAI_KEY",
        "models": [
          {
            "id": "gpt-4o-mini",
            "name": "GPT-4o Mini",
            "reasoning": false,
            "input": ["text", "image"],
            "cost": { "input": 0.15, "output": 0.6, "cacheRead": 0.075, "cacheWrite": 0 },
            "contextWindow": 128000,
            "maxTokens": 16384
          }
        ]
      }
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "botToken": "$TG_TOKEN",
      "webhookUrl": "$RELAY_URL",
      "webhookSecret": "$WEBHOOK_SECRET"
    },
    "discord": { "enabled": false }
  },
  "update": { "auto": { "enabled": true } }
}
EOFJSON
ok "openclaw.json written"

# ── Step 7: Scripts + Skills ──────────────────────────────────────────────────
step "7/9" "Scripts and skills"

# Copy scripts, replacing placeholder paths
for script in "$REPO_DIR/scripts/"*; do
    fname=$(basename "$script")
    sed "s|/Users/YOUR_USERNAME|$HOME_DIR|g; \
         s|YOUR_USERNAME|$USERNAME|g; \
         s|YOUR_CHAT_ID|$TG_CHAT_ID|g" \
        "$script" > "$OPENCLAW_DIR/scripts/$fname"
    chmod +x "$OPENCLAW_DIR/scripts/$fname"
done
ok "Scripts installed"

# Update start-gateway.sh with actual openclaw path
if [ -n "$OPENCLAW_DIST" ]; then
    # Replace the hardcoded node+dist path with detected one
    sed -i '' "s|exec.*dist/index.js.*gateway|exec $NODE_BIN $OPENCLAW_DIST gateway|g" \
        "$OPENCLAW_DIR/scripts/start-gateway.sh" 2>/dev/null || true
elif command -v openclaw-gateway &>/dev/null; then
    # Replace with binary call
    sed -i '' "s|exec.*dist/index.js.*gateway.*|exec openclaw-gateway|g" \
        "$OPENCLAW_DIR/scripts/start-gateway.sh" 2>/dev/null || true
fi
ok "start-gateway.sh updated with openclaw path"

# Copy workspace files
mkdir -p "$OPENCLAW_DIR/workspace"
cp -n "$REPO_DIR/workspace/SOUL.md" "$OPENCLAW_DIR/workspace/SOUL.md" 2>/dev/null || \
    warn "SOUL.md already exists — not overwriting"

# Replace placeholder paths in SOUL.md
sed -i '' "s|/Users/YOUR_USERNAME|$HOME_DIR|g; s|YOUR_USERNAME|$USERNAME|g" \
    "$OPENCLAW_DIR/workspace/SOUL.md"
ok "SOUL.md installed"

# Copy skills
for skill_dir in "$REPO_DIR/workspace/skills/"*/; do
    skill_name=$(basename "$skill_dir")
    mkdir -p "$OPENCLAW_DIR/workspace/skills/$skill_name/scripts"
    cp -r "$skill_dir"scripts/. "$OPENCLAW_DIR/workspace/skills/$skill_name/scripts/" 2>/dev/null || true
    ok "  Skill: $skill_name"
done

# ── Step 8: LaunchAgents ──────────────────────────────────────────────────────
step "8/9" "LaunchAgents"

LAUNCHD="$HOME_DIR/Library/LaunchAgents"
mkdir -p "$LAUNCHD"

for template in "$REPO_DIR/config/launchagents/"*.template; do
    plist_name=$(basename "$template" .template)
    dest="$LAUNCHD/$plist_name"

    sed "s|YOUR_USERNAME|$USERNAME|g; \
         s|YOUR_TAVILY_KEY|$TAVILY_KEY|g; \
         s|YOUR_OPENCLAW_DIST_PATH|$OPENCLAW_DIST|g" \
        "$template" > "$dest"

    # Update gateway plist with actual openclaw path and node binary
    if [[ "$plist_name" == *"gateway"* ]] && [ -n "$OPENCLAW_DIST" ]; then
        # The plist calls start-gateway.sh which we already updated above
        :
    fi

    launchctl unload "$dest" 2>/dev/null || true
    launchctl load "$dest"
    ok "$plist_name loaded"
done

# ── Step 9: Crontab ───────────────────────────────────────────────────────────
step "9/9" "Crontab"

CRON_CONTENT=$(sed \
    "s|YOUR_USERNAME|$USERNAME|g; \
     s|YOUR_CHAT_ID|$TG_CHAT_ID|g" \
    "$REPO_DIR/config/crontab.template")

# Merge with existing crontab (avoid duplicates)
EXISTING=$(crontab -l 2>/dev/null | grep -v "openclaw\|morning-briefing\|watchdog\|organize-downloads" || true)
echo "$EXISTING" > /tmp/openclaw-crontab.tmp
echo "$CRON_CONTENT" >> /tmp/openclaw-crontab.tmp
crontab /tmp/openclaw-crontab.tmp
rm /tmp/openclaw-crontab.tmp
ok "Crontab updated"

# ── Verification ──────────────────────────────────────────────────────────────
echo -e "\n${BOLD}${BLUE}[✓]${RESET} ${BOLD}Verifying${RESET}"
sleep 8  # give gateway time to start

HEALTH=$(curl -s http://localhost:18789/health 2>/dev/null || echo "")
if echo "$HEALTH" | grep -q '"ok":true'; then
    ok "Gateway: live"
else
    warn "Gateway not responding yet — may still be starting. Run: curl http://localhost:18789/health"
fi

BRIDGE=$(pgrep -f relay-bridge.py &>/dev/null && echo "running" || echo "not found")
if [ "$BRIDGE" = "running" ]; then
    ok "relay-bridge: running"
else
    warn "relay-bridge not found — check: launchctl list | grep openclaw"
fi

python3 "$OPENCLAW_DIR/scripts/watchdog.py" 2>/dev/null && ok "Watchdog: clean" || \
    warn "Watchdog reported issues — check ~/.openclaw/logs/watchdog.log"

# ── Manual steps ──────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}─────────────────────────────────────────────${RESET}"
echo -e "${BOLD}Setup complete. Two manual steps remain:${RESET}"
echo ""
echo -e "${YELLOW}1. Google OAuth${RESET} (required for Gmail, Calendar, Contacts, YouTube)"
echo "   a. Download your OAuth client secret from Google Cloud Console"
echo "   b. Save it to: $OPENCLAW_DIR/credentials/google-oauth.json"
echo "   c. Run:  python3 $OPENCLAW_DIR/scripts/google-auth.py"
echo "   d. Complete the browser flow — approve all scopes"
echo ""
if [ -z "$TG_CHAT_ID" ]; then
    echo -e "${YELLOW}2. Telegram Chat ID${RESET}"
    echo "   a. Open Telegram and message @userinfobot"
    echo "   b. It replies with your chat ID"
    echo "   c. Run:  crontab -e"
    echo "      Replace YOUR_CHAT_ID with your actual chat ID in the briefing line"
    echo "   d. Also update: $OPENCLAW_DIR/scripts/watchdog.py (CHAT_ID line)"
    echo ""
fi
echo -e "${YELLOW}3. Test it${RESET}"
echo "   Send 'hello' in Telegram — bot should reply within 10 seconds."
echo ""
echo -e "${GREEN}${BOLD}Done.${RESET}"
