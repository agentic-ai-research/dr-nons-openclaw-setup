# Dr Non's OpenClaw Setup

**A personal AI gateway — Telegram-first, Google Workspace integrated, Thai-language capable.**

This is the honest, battle-scarred record of getting [OpenClaw](https://github.com/openclaw/openclaw) actually working in daily production. Not the marketing version. Every wall hit, every mistake made, every fix found — documented so you don't repeat any of it.

**Moving to a new machine?** Read [SETUP.md](SETUP.md) first. It's the migration bible.

If you're on 16GB RAM (or an old MacBook) wondering why your bot crashes, sleeps, or stares at you blankly — this is for you.

---

## What Is OpenClaw

OpenClaw is a personal AI agent you install on your own machine. It connects to your messaging apps (Telegram, WhatsApp, iMessage, Discord) and responds to you with AI — wherever you are, from your phone. You can ask it to check your calendar, summarize emails, download videos, look things up, organize files, or run any custom script you write.

It runs 24/7 as a background service. It's free to self-host. The catch: it needs a brain — a language model — and choosing the wrong one is where everything falls apart.

---

## The Story of How I Got Here (Skip If You Just Want the Config)

### Chapter 1: Local Models — The Dream

The pitch for running local models is compelling. Free forever. Private. No API bills. No rate limits. Just download a model and go.

So I installed Ollama, pulled `qwen2.5-coder:14b`, wired it into OpenClaw, and sent my first Telegram message.

It took 45 seconds to respond. The second message took 30. The third crashed the session entirely because the context window filled up. Meanwhile, my Mac sounded like a jet engine and Chrome had become unusably slow because the 14B model was sitting on 9GB of RAM while the OS needed another 4–5GB, leaving nothing for anything else.

That's the dirty math nobody puts in the README:

```
qwen2.5-coder:14b  =  9.0 GB
macOS idle         =  4–5 GB
──────────────────────────────
Total              =  13–14 GB on a 16 GB machine
One Chrome window  =  You're now swapping to disk
```

It works. It's just not livable.

### Chapter 2: Switch to Smaller Models — The Compromise

Fine. Use `qwen2.5:7b` instead. Only 4.7GB. Leaves real headroom.

It's noticeably less capable on complex tasks, but for a personal assistant bot — calendar checks, news summaries, quick lookups — it's fine. I ran with this for a while.

The deeper problem: OpenClaw runs 24/7. Even with 7B sitting at ~4.7GB, the machine was always a little sluggish. Every app launch was slightly slower. Anything that touched memory — Xcode, a big browser tab, Figma — felt like it was fighting the model for resources.

I wasn't coding *with* the AI. I was babysitting the RAM allocation.

### Chapter 3: Groq Free Tier — The False Hope

Someone told me: use Groq's free tier. It's an API. No model running locally. Fast inference. Free.

I signed up, got the key, dropped it into OpenClaw.

First message: `413 — Limit 12000, Requested 54976`.

OpenClaw's system prompt — the file that explains who the bot is, what skills it has, what rules to follow — is roughly **18,000 tokens** when your skill library grows. Groq's free tier has a **12,000 token per request hard limit**. Not 12,000 tokens of output. 12,000 tokens total, input included.

My system prompt alone exceeds that. Every. Single. Request.

There is no way around this on Groq's free tier. The limit isn't something you can optimize past. The system prompt is what makes the bot useful — strip it down to fit and you're left with a bot that doesn't know what it is.

### Chapter 4: OpenAI GPT-4o-mini — What Actually Works

`gpt-4o-mini` costs $0.15 per million input tokens. $0.60 per million output tokens.

My morning briefing — which pulls weather, markets, calendar events, GitHub activity, AI news, and summarizes emails — costs roughly **$0.003**. Three tenths of a cent. Running it daily for a year: about **$1.10**.

Casual conversations, file organization, video downloads, calendar lookups: another dollar or two a year at most, assuming moderate use.

128,000 token context window. No per-request limit. Responses in 1–3 seconds. No RAM consumed on my machine. The bot handles the system prompt, the skill library, and a full conversation history without breaking a sweat.

I stopped thinking about the model. That's the win.

---

## The Setup That Works

### Hardware

16GB RAM, Apple Silicon Mac (M2). Everything below is tuned for this constraint.

### Architecture

```
Telegram / WhatsApp / iMessage
        │
        ▼
   relay-bridge.py          ← polls Fly.io relay, forwards to localhost (60s timeout)
        │
        ▼
   OpenClaw Gateway          ← LaunchAgent, starts on boot, port 18789
        │
        ▼
   OpenAI GPT-4o-mini        ← primary model, vision-enabled (cloud API)
        │
   Ollama (fallback)         ← qwen2.5:7b or phi4-mini, local only
```

OpenClaw handles the conversation. GPT-4o-mini generates the response. Ollama stays available as a fallback for things I want to run locally.

### openclaw.json — The Core Config

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "openai/gpt-4o-mini"
      },
      "llm": {
        "idleTimeoutSeconds": 0
      },
      "compaction": {
        "reserveTokensFloor": 8000
      }
    }
  },
  "models": {
    "providers": {
      "openai": {
        "baseUrl": "https://api.openai.com/v1",
        "api": "openai-responses",
        "apiKey": "YOUR_OPENAI_KEY",
        "models": [
          {
            "id": "gpt-4o-mini",
            "name": "GPT-4o Mini",
            "reasoning": false,
            "input": ["text", "image"],
            "cost": {
              "input": 0.15,
              "output": 0.6,
              "cacheRead": 0.075,
              "cacheWrite": 0
            },
            "contextWindow": 128000,
            "maxTokens": 16384
          }
        ]
      },
      "ollama": {
        "baseUrl": "http://127.0.0.1:11434",
        "api": "ollama",
        "apiKey": "ollama-local",
        "models": [
          {
            "id": "qwen2.5:7b",
            "name": "Qwen 2.5 7B",
            "reasoning": false,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 32768,
            "maxTokens": 8192
          }
        ]
      }
    }
  }
}
```

**Key fields to get right:**
- `"api": "openai-responses"` — NOT `"openai"`. That's not a valid value and will throw a schema error with zero explanation.
- `"baseUrl"` — Required even for standard OpenAI. OpenClaw won't infer it.
- `"primary": "openai/gpt-4o-mini"` — The prefix `openai/` must match the provider key exactly.
- `"input": ["text", "image"]` — Required to enable vision. Without this, the bot can't read business cards or screenshots.
- No `fallback` key inside model entries. OpenClaw's schema rejects unknown fields silently — or rather, noisily at restart.

### Ollama Models Installed

These stay installed for occasional local use, but none of them are the primary:

| Model | Size | Use |
|-------|------|-----|
| `phi4-mini:latest` | 2.5GB | Lightest option, fast, good for simple tasks |
| `qwen2.5:7b` | 4.7GB | Solid general model, OpenClaw fallback |
| `qwen2.5-coder:7b` | 4.7GB | Coding-specific, used in Continue.dev |
| `deepseek-r1:7b` | 4.7GB | Reasoning, Continue.dev only |
| `qwen2.5-coder:14b` | 9.0GB | **Do not use with OpenClaw on 16GB** |

The 14B model is there for focused, manual coding sessions in Continue.dev — close everything else first, run it, close it when done. It is never the OpenClaw primary.

---

## Skills Installed

OpenClaw's power comes from skills — Python scripts the bot runs when you ask for something. These live in `~/.openclaw/workspace/skills/`.

### Core Skills (ClawHub)

| Skill | What It Does |
|-------|-------------|
| `gmail` | Read, search, send email from Google account |
| `gcal` | View and create Google Calendar events (Bangkok timezone) |
| `contacts` | Save and search Google Contacts |
| `file-organizer` | Sort files sent by user into Google Drive automatically |
| `ocr-contacts` | Scan business card photo → extract → save to Google Contacts (Tesseract + GPT-4o-mini vision fallback) |
| `video-download` | Download video from YouTube/Twitter/TikTok/Instagram via yt-dlp |
| `web-search` | Search the web via Tavily |
| `web-fetch` | Fetch and summarize a URL |
| `summarize` | Summarize any text or document |
| `translate` | Translate text |
| `remember` | Store and recall notes persistently |
| `photo-vault` | Save photos to Google Drive |
| `illustrate` | Generate images |
| `ask` | One-shot GPT-4o-mini question outside of conversation context |
| `agent-browser-clawdbot` | Headless Chromium browser automation |
| `self-improving-proactive-agent` | Learns from corrections, builds persistent memory in `~/self-improving/` |
| `tavily-web-search-for-openclaw` | Tavily API search (requires `TAVILY_API_KEY` in LaunchAgent plist) |
| `extract-youtube-transcript` | Pull full transcript from any YouTube video |
| `personal-ontology` | Palantir-style persona graph — beliefs, values, goals, writing style |

### Custom Skills (Built In-House)

| Skill | What It Does |
|-------|-------------|
| `url-screenshot` | Screenshot any URL with headless Chromium, summarize with GPT-4o-mini vision |
| `youtube-comment` | Transcribe YouTube video → reason in your voice → optionally post comment |
| `flight-monitor` | Track flight routes, alert on price drops, integrates with morning briefing |
| `morning-briefing` | Daily 7am briefing: weather, markets, calendar, GitHub, AI news, email digest, flight alerts |

### Morning Briefing

Runs at 7:00 AM Bangkok time via cron (`0 7 * * *`).
⚠️ Common mistake: `0 0 * * *` is midnight, not 7am. See `config/crontab.template`. Covers:

- Bangkok weather + AQI (Open-Meteo primary, wttr.in fallback)
- Markets: BTC price, Gold, Oil (WTI), USD/THB rate
- Today's Google Calendar events
- Recent GitHub repo activity
- Top AI/tech news filtered from Hacker News (score ≥ 50, AI-keyword matched)
- Newsletter digest: unread Gmail newsletters summarized to 3 bullets each via GPT-4o-mini
- Flight alerts: any tracked routes below price threshold

Cron entry:
```
0 0 * * * /opt/homebrew/bin/python3 ~/.openclaw/workspace/skills/morning-briefing/scripts/briefing.py CHAT_ID >> ~/.openclaw/logs/morning-briefing.log 2>&1
```

Estimated cost per briefing: **~$0.003**. Daily for a year: **~$1.10**.

### OCR Contacts — How It Works

The `ocr-contacts` skill uses a two-pass approach for reliability:

1. **Tesseract OCR** extracts raw text from the image
2. **GPT-4o-mini parses** the text into structured contact fields
3. If no valid contact is found (complex layout, compressed JPEG, unusual font) → **GPT-4o-mini vision fallback**: sends the image directly instead of the text
4. Saves automatically to Google Contacts via People API

This means business cards with tricky layouts (rotated text, minimal contrast, Thai characters) still get captured correctly.

### URL Screenshot

Send the bot any URL and ask it to screenshot or summarize the page:

```
Screenshot techcrunch.com and summarize the top 3 stories
```

Pipeline: `agent-browser open <url>` → 3s render wait → `agent-browser screenshot <path>` → GPT-4o-mini vision summary → reply.

### YouTube Comment in Your Voice

```
Watch this video and write a comment I would post: https://youtube.com/...
```

Pipeline: extract transcript → load persona from `~/self-improving/memory.md` → GPT-4o-mini generates comment in your style → dry-run shown first, `--post` flag required to actually post.

Requires: YouTube Data API v3 enabled in Google Console + `youtube.force-ssl` OAuth scope.

### Flight Monitor

```
Track BKK to London under 35000 THB
Check my flights
```

Routes stored in `~/.openclaw/workspace/state/flights.json`. Scrapes Google Flights via headless browser. Alerts appear in morning briefing when prices drop below threshold.

---

## Stability Infrastructure (The Stuff That Keeps It Running)

### Watchdog (Most Important)
`scripts/watchdog.py` runs every 5 minutes via cron. It:
- Pings the gateway health endpoint
- Checks relay-bridge is alive
- Auto-restarts either if they're down
- **Sends you a Telegram alert** when it does anything
- Auto-resets the session if context exceeds 400KB

Without this, the bot can be silent for hours before you notice. This alone would have caught a Discord-triggered crash loop that ran all night.

### Crash-Proof Gateway Startup
`scripts/start-gateway.sh` explicitly kills any process on port 8787 before starting. Prevents EADDRINUSE even if the gateway crashes mid-operation.

### Relay Bridge with Retry Queue
`scripts/relay-bridge.py` polls Fly.io relay every 2s. If the gateway isn't ready, messages go into a pending queue and are retried on every loop — messages survive machine sleep, gateway restarts, and cold boots.

### Session Auto-Reset
Handled by watchdog at 400KB. Weekly cron reset on Sunday as backstop. Prevents context bloat from causing erratic bot behavior.

---

## Files That Matter

```
~/.openclaw/
├── openclaw.json                          ← Main config. Touch carefully.
├── workspace/
│   ├── SOUL.md                            ← Bot personality + rules (with absolute skill paths)
│   ├── MEMORY.md                          ← Persistent facts about you
│   ├── AGENTS.md                          ← Agent behavior rules (keep trimmed)
│   ├── HEARTBEAT.md                       ← Background monitoring rules
│   └── skills/                            ← All skill scripts
│       ├── gmail/
│       ├── gcal/
│       ├── contacts/
│       ├── morning-briefing/
│       ├── ocr-contacts/
│       ├── url-screenshot/
│       ├── youtube-comment/
│       ├── flight-monitor/
│       ├── personal-ontology/
│       ├── self-improving-proactive-agent/
│       └── ...
│   └── state/
│       └── flights.json                   ← Tracked flight routes + last prices
├── credentials/
│   ├── google-oauth.json                  ← Google OAuth app credentials (NEVER in cloud sync)
│   ├── google-token.pkl                   ← Google OAuth token (10 scopes incl. YouTube write)
│   └── github-token.txt                   ← GitHub PAT
├── agents/main/sessions/
│   └── sessions.json                      ← Session registry. Wipe to reset.
├── scripts/
│   ├── reset-session.sh                   ← The fix for most bot problems
│   ├── google-auth.py                     ← One-time OAuth setup
│   └── organize-downloads.py             ← Bulk sort ~/Downloads into Google Drive
└── logs/
    └── morning-briefing.log               ← Briefing output
~/self-improving/
├── memory.md                              ← Persistent persona: values, style, preferences
├── corrections.md                         ← Bot learns from your corrections
├── domains/                               ← Topic-specific knowledge files
└── projects/                              ← Per-project context
```

---

## Problems With Ollama on 16GB — Reference Card

| Symptom | Cause | Fix |
|---------|-------|-----|
| Bot responds in 30–60 seconds | 14B model on 16GB, swapping to disk | Switch primary to `phi4-mini` or use cloud API |
| Mac runs hot all day, fans on | 14B loaded 24/7 as OpenClaw primary | Use `phi4-mini` (2.5GB) or `qwen2.5:7b` (4.7GB) as primary |
| Everything feels slow | Model holds 9GB resident memory | Close it or switch to API |
| Session crashes mid-conversation | Context limit hit + memory pressure | Cloud API has 128k context; local 7B has 32k |
| `413 — Limit 12000, Requested 54976` | Groq free tier; system prompt alone is ~18k tokens | Use paid API. Groq free tier is incompatible with OpenClaw's full skill library |
| `Config invalid: Unrecognized key` | Unknown field in openclaw.json | Remove it. Common culprit: `"fallback"` inside a model entry |
| `api: "openai" is not a valid enum` | Wrong `api` value for OpenAI provider | Use `"openai-responses"` or `"openai-completions"` |
| Bot doesn't pick up new skills | Stale session snapshot | Reset: `bash ~/.openclaw/scripts/reset-session.sh` |
| Port 8787 already in use on restart | Gateway killed before it released the port | Unload LaunchAgent first, wait 5s, then kill port 8787, then reload |
| Bot silent despite HTTP 200 from relay | Session JSONL too large (240KB+), context bloat | Session reset. Normal after heavy testing sessions. |
| Business card OCR saves first card, not second | Tesseract fails on compressed JPEG / complex layout | Fixed: vision fallback added to `ocr_contacts.py` |
| relay-bridge `forward error: timed out` | Default 10s timeout too short for LLM processing | Fixed: both `urlopen` calls changed to `timeout=60` |

---

## What I Would Do Differently From Day One

1. **Skip Ollama as the OpenClaw primary entirely.** Keep it for Continue.dev (VS Code coding). For OpenClaw — the 24/7 bot — use a cloud API from minute one. On 16GB, it's not a compromise, it's the right call.

2. **Get an OpenAI key before setting up OpenClaw.** The onboarding assumes you have a model ready. GPT-4o-mini costs nothing at this scale. Don't try to cheap out with Groq free tier — the token limit makes it incompatible.

3. **Enable `"input": ["text", "image"]` from the start.** Without this, the bot can't read images, business cards, or screenshots. One line in openclaw.json, but easy to miss.

4. **Trim system prompt files before the first session.** AGENTS.md and HEARTBEAT.md shipped with content that was never relevant to my setup — Discord emoji reactions, ElevenLabs TTS config, email monitoring for a tool I don't have. That's ~2,000 extra tokens on every single request. Audit and strip before first use.

5. **Wipe sessions.json completely when installing new skills.** OpenClaw freezes the skill list in a snapshot at session start. If you install a skill and the bot doesn't use it, the session is stale. Don't just restart the gateway — wipe the snapshot too.

6. **Never add unknown fields to openclaw.json.** The schema validator is strict and the error messages are bad. Test every config change with `openclaw doctor` before restarting the gateway.

7. **Keep Google OAuth credentials out of cloud-synced folders.** The `client_secret_*.json` file from Google Console should live in `~/.openclaw/credentials/`, not `~/Downloads/` which syncs to Drive.

---

## Estimated Monthly Cost (Real Numbers)

Based on actual usage at moderate volume:

| Usage | Tokens/month (est.) | Cost |
|-------|---------------------|------|
| Morning briefing (daily) | ~900k input | $0.135 |
| Casual bot conversations (10–20/day) | ~600k input | $0.09 |
| Skill calls (calendar, email, etc.) | ~300k input | $0.045 |
| OCR + vision (business cards, screenshots) | ~200k input | $0.03 |
| YouTube transcripts + comments | ~100k input | $0.015 |
| **Total** | **~2.1M tokens** | **~$0.32/month** |

Worst case with heavy use: under **$2/month**. That's less than a single ChatGPT message with image generation.

---

## License

MIT. Do whatever. If this saves you the hours I lost, that's the point.

---

*Built on [OpenClaw](https://github.com/openclaw/openclaw) · Runs on GPT-4o-mini · Bangkok, Thailand*
