# OpenClaw Setup Bible

> Built from hours of trial and error. Every mistake documented. Every fix included.
> Use this to set up on a new machine without repeating any of it.

---

## What You Need (Hardware)

OpenClaw runs on **any Mac** — including a 10-year-old MacBook — as long as you use cloud models (OpenAI). The only thing that requires a powerful machine is local models (Ollama). Disable Ollama in the config and you're fine on old hardware.

**Minimum:** macOS 12+, 4GB RAM, internet connection.  
**Not required:** GPU, Apple Silicon, Ollama, local models.

---

## Prerequisites

```bash
# Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Node.js 20+
brew install node

# Python 3
brew install python3

# Tesseract (for OCR / business card scanning)
brew install tesseract

# Python packages
pip3 install google-auth google-auth-oauthlib google-api-python-client \
             pillow pytesseract youtube-transcript-api yt-dlp
```

---

## Step 1: Install OpenClaw

Follow the official install at [openclaw.ai](https://openclaw.ai). After install:

```bash
# Verify
openclaw-gateway --version
curl http://localhost:18789/health   # should return {"ok":true,"status":"live"}
```

---

## Step 2: Directory Structure

Everything lives under `~/.openclaw/`. Create the layout:

```bash
mkdir -p ~/.openclaw/{credentials,logs,workspace/skills,agents/main/sessions,state,scripts}
```

---

## Step 3: openclaw.json

Copy `config/openclaw.json.template` from this repo to `~/.openclaw/openclaw.json`.  
Fill in your API keys. **Never commit the live file** — it contains secrets.

**Critical settings:**
- `channels.discord.enabled`: **false** — Discord causes gateway crash loops. Leave it off unless you specifically need it and have debugged your Discord bot.
- `agents.defaults.model.primary`: `"openai/gpt-4o-mini"` — fastest, cheapest, works on all hardware.
- Remove Ollama model entries if not on a powerful machine — they'll fail silently otherwise.

---

## Step 4: Credentials Directory

All secrets live in `~/.openclaw/credentials/`. **This directory is never committed to git.**

| File | What it is | How to get it |
|------|-----------|---------------|
| `telegram-token.txt` | Telegram bot token | BotFather → `/newbot` |
| `google-token.pkl` | Google OAuth pickle | Run `python3 scripts/google-auth.py` |
| `google-oauth.json` | Google OAuth client secret | Google Cloud Console → OAuth credentials |
| `thaillm.json` | ThaiLLM API config | `{"url":"http://thaillm.or.th/api/openthaigpt/v1/chat/completions","apiKey":"YOUR_KEY"}` |
| `github-token.txt` | GitHub personal access token | github.com → Settings → Developer settings → PAT |

```bash
chmod 600 ~/.openclaw/credentials/*
```

---

## Step 5: Google OAuth

You must run this once per machine — the token is machine-specific.

```bash
# Put your client_secret_*.json from Google Cloud Console in credentials/
cp ~/Downloads/client_secret_*.json ~/.openclaw/credentials/google-oauth.json

# Run the auth flow (opens browser)
python3 ~/.openclaw/scripts/google-auth.py
```

Required scopes (already in the script):
- Gmail read/send
- Calendar read/write
- Contacts read/write
- Sheets, Drive, YouTube

---

## Step 6: Telegram Bot + Relay

OpenClaw uses a Fly.io relay to receive Telegram messages when the machine is asleep or behind NAT. The relay is already deployed at `https://dnoc-tg-relay.fly.dev/`.

1. Create bot via BotFather if you don't have one
2. Set webhook to point at the Fly.io relay:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://dnoc-tg-relay.fly.dev/telegram"
   ```
3. Store token: `echo "YOUR_TOKEN" > ~/.openclaw/credentials/telegram-token.txt && chmod 600 ~/.openclaw/credentials/telegram-token.txt`
4. Update `openclaw.json` → `channels.telegram.botToken` with your token

---

## Step 7: LaunchAgents (Auto-Start on Boot)

Copy plist templates from `config/launchagents/` and update paths for your username.

```bash
# Replace USERNAME with your actual username in both files
sed 's/YOUR_USERNAME/$(whoami)/g' config/launchagents/ai.openclaw.gateway.plist.template \
  > ~/Library/LaunchAgents/ai.openclaw.gateway.plist

sed 's/YOUR_USERNAME/$(whoami)/g' config/launchagents/ai.openclaw.relay-bridge.plist.template \
  > ~/Library/LaunchAgents/ai.openclaw.relay-bridge.plist

# Load both
launchctl load ~/Library/LaunchAgents/ai.openclaw.gateway.plist
launchctl load ~/Library/LaunchAgents/ai.openclaw.relay-bridge.plist

# Verify
launchctl list | grep openclaw
curl http://localhost:18789/health
```

**Critical plist settings (learned the hard way):**
- `ThrottleInterval`: **10** (not 1). With 1s, if the gateway crashes and port 8787 isn't released yet, launchd restarts it immediately → EADDRINUSE → infinite crash loop.
- `KeepAlive`: true for both gateway and relay-bridge.

---

## Step 8: Install Scripts

```bash
cp scripts/* ~/.openclaw/scripts/
chmod +x ~/.openclaw/scripts/*.sh ~/.openclaw/scripts/*.py
```

---

## Step 9: Set Up Cron Jobs

```bash
# Edit crontab
crontab -e
```

Paste the contents of `config/crontab.template`. **Read it carefully** — wrong times here cost you a morning briefing every day.

---

## Step 10: Install Skills

```bash
cd ~/.openclaw/workspace

# Copy custom skills from this repo
cp -r workspace/skills/* skills/

# Install ClawHub skills (run from workspace dir)
npx clawhub@latest install extract-youtube-transcript --dir skills
npx clawhub@latest install file-organizer --dir skills
npx clawhub@latest install personal-ontology --dir skills
npx clawhub@latest install gcal --dir skills
npx clawhub@latest install gmail --dir skills
npx clawhub@latest install contacts --dir skills
npx clawhub@latest install photo-vault --dir skills
npx clawhub@latest install remember --dir skills
npx clawhub@latest install video-download --dir skills
npx clawhub@latest install agent-browser-clawdbot --dir skills
npx clawhub@latest install tavily-web-search-for-openclaw --dir skills
```

---

## Step 11: SOUL.md

Copy `workspace/SOUL.md` to `~/.openclaw/workspace/SOUL.md`.

**Update every absolute path in the file** to match your new machine's username. Search for `/Users/axiom` and replace with `/Users/YOUR_USERNAME`.

```bash
sed -i '' 's|/Users/axiom|/Users/'$(whoami)'|g' ~/.openclaw/workspace/SOUL.md
```

**Why this matters:** SOUL.md contains the absolute script path for every skill. Without it, the bot detects the intent ("track a flight") but gives a generic answer ("go to Expedia") instead of running the script. The absolute path is what forces execution.

---

## Step 12: Watchdog Cron

The watchdog (`scripts/watchdog.py`) checks gateway + relay-bridge every 5 minutes and:
- Auto-restarts either if they're down
- Sends you a Telegram alert when it does
- Auto-resets the session if context exceeds 400KB

Without this, the bot can be down for hours before you notice. This is the single most important reliability improvement.

---

## Verification Checklist

```bash
# 1. Gateway live
curl http://localhost:18789/health
# → {"ok":true,"status":"live"}

# 2. LaunchAgents running
launchctl list | grep openclaw
# → two entries, both with PIDs

# 3. Watchdog runs clean
python3 ~/.openclaw/scripts/watchdog.py
# → "All systems nominal"

# 4. Telegram responds
# Send "hello" in Telegram → bot should reply within 10s

# 5. Morning briefing works
python3 ~/.openclaw/workspace/skills/morning-briefing/scripts/briefing.py YOUR_CHAT_ID
# → "Sent. (XXXX chars)"

# 6. OCR test
python3 ~/.openclaw/workspace/skills/ocr-contacts/scripts/ocr_contacts.py /path/to/business-card.jpg
# → extracts contact, saves to Google Contacts

# 7. Thai writer test
python3 ~/.openclaw/workspace/skills/thai-writer/scripts/thai_writer.py \
  --task translate --text "Good morning" --to thai
# → สวัสดีตอนเช้า
```

---

## Lessons Learned (Don't Repeat These)

### 1. Discord Causes Crash Loops
**What happened:** Discord channel was enabled but the bot token wasn't working. Discord kept failing → gateway crashed → LaunchAgent restarted in 1s → port 8787 still held → gateway crashed again → loop every 15 minutes all night. Morning briefing never ran.

**Fix:** `openclaw.json` → `channels.discord.enabled: false`. Only enable Discord if you have a working, tested Discord bot token.

### 2. ThrottleInterval 1s = EADDRINUSE
**What happened:** Default `ThrottleInterval` in the gateway plist was 1 second. On any crash, launchd would restart faster than the OS released port 8787.

**Fix:** Set `ThrottleInterval` to **10** in `ai.openclaw.gateway.plist`. Also added explicit `kill -9` of port 8787 in `start-gateway.sh` before the gateway starts.

### 3. Morning Briefing Was Running at Midnight
**What happened:** Cron was `0 0 * * *` (midnight) not `0 7 * * *` (7am). Ran at wrong time for months.

**Fix:** See `config/crontab.template` — times are correct and commented.

### 4. Telegram Token Hardcoded in Script → GitHub Exposure
**What happened:** `briefing.py` had the Telegram bot token hardcoded. When committed to GitHub, GitHub's secret scanning flagged it immediately. Token had to be rotated.

**Fix:** Token loaded from file: `open("~/.openclaw/credentials/telegram-token.txt").read().strip()`. The credentials file is in `.gitignore`.

### 5. Skills Ignored Without SOUL.md Absolute Paths
**What happened:** Flight monitor was installed and working but when asked "track flights to London," the bot said "try Expedia." The skill existed but wasn't in SOUL.md — so the bot detected intent but had no path to execute.

**Fix:** Every skill needs an entry in SOUL.md with its **absolute script path**. The path is the execution guarantee. Intent without path = generic answer.

### 6. relay-bridge Ran Manually, Not as LaunchAgent
**What happened:** relay-bridge wasn't set up as a LaunchAgent — it only ran when manually started. After a reboot, Telegram messages were queued at Fly.io but never delivered.

**Fix:** `ai.openclaw.relay-bridge.plist` as a LaunchAgent with `RunAtLoad: true` and a 120-second startup wait for the gateway to come up first.

### 7. Session Bloat Causes Erratic Behavior
**What happened:** After heavy use, the session JSONL grew to 240KB+. The bot started giving wrong answers, ignoring instructions, hallucinating context.

**Fix:** Watchdog auto-resets session above 400KB. Weekly cron reset on Sunday as a backstop.

### 8. OCR Fails on Compressed Business Cards
**What happened:** Tesseract fails on small-font or compressed JPEG business cards. The heuristic `is_business_card()` then rejects the result and nothing gets saved.

**Fix:** Two-pass approach in `ocr_contacts.py`: Tesseract first, then GPT-4o-mini vision as fallback if heuristic fails. Vision path is ~100% reliable for well-photographed cards.

### 9. Ollama on Weak Hardware = Silent Failures
If Ollama is configured but models aren't pulled (or the machine is too slow), requests to local models silently fail or time out.

**Fix:** On any machine without dedicated GPU/CPU headroom, remove Ollama from `openclaw.json` entirely. Use `openai/gpt-4o-mini` as primary. Cost: ~$0.002 per typical conversation.

---

## API Keys You Need

| Service | Cost | What for | Where to get |
|---------|------|----------|-------------|
| OpenAI | ~$0-5/month | Primary model (gpt-4o-mini) | platform.openai.com |
| Tavily | Free tier | Web search | tavily.com |
| ThaiLLM | Free | Thai language tasks | thaillm.or.th |
| Telegram Bot | Free | Chat interface | BotFather in Telegram |
| Google OAuth | Free | Gmail, Calendar, Contacts | Google Cloud Console |
| GitHub PAT | Free | Morning briefing GitHub section | github.com/settings/tokens |

Total estimated monthly cost: **$1–5 USD** depending on usage. Mostly OpenAI tokens.

---

## File Map (this repo → your machine)

| This repo | Your machine |
|-----------|-------------|
| `config/openclaw.json.template` | `~/.openclaw/openclaw.json` (fill in secrets) |
| `config/launchagents/*.plist.template` | `~/Library/LaunchAgents/*.plist` (update paths) |
| `config/crontab.template` | `crontab -e` (paste contents) |
| `scripts/*` | `~/.openclaw/scripts/` |
| `workspace/SOUL.md` | `~/.openclaw/workspace/SOUL.md` (update paths) |
| `workspace/skills/` | `~/.openclaw/workspace/skills/` |
| `credentials-structure.md` | Reference only — never commit real credentials |
