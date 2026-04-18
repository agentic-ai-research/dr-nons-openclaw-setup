# Dr Non's OpenClaw Setup

**A personal AI gateway that runs 24/7 on your phone — without destroying your RAM or your wallet.**

This is the honest, battle-scarred record of how I got [OpenClaw](https://github.com/openclaw/openclaw) actually working on a 16GB Mac. Not the marketing version. The real one — including every wall I hit, every thing I misunderstood, and the exact config that finally worked.

If you're on 16GB RAM and wondering why your bot crashes, sleeps, or just stares at you blankly — this is for you.

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
   relay-bridge.py          ← polls Fly.io relay, forwards to localhost
        │
        ▼
   OpenClaw Gateway          ← LaunchAgent, starts on boot, port 18789
        │
        ▼
   OpenAI GPT-4o-mini        ← primary model (cloud API)
        │
   Ollama (fallback)         ← qwen2.5:7b or phi4-mini, local only
```

OpenClaw handles the conversation. GPT-4o-mini generates the response. Ollama stays available as a fallback for things I want to run locally (image description, quick one-off tasks where latency doesn't matter).

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
            "input": ["text"],
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
          },
          {
            "id": "phi4-mini:latest",
            "name": "Phi 4 Mini",
            "reasoning": false,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 16384,
            "maxTokens": 4096
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
- No `fallback` key inside model entries. OpenClaw's schema rejects unknown fields silently — or rather, noisily at restart.

### Ollama Models Installed

These stay installed for occasional local use, but none of them are the primary:

| Model | Size | Use |
|-------|------|-----|
| `phi4-mini:latest` | 2.5GB | Lightest option, fast, good for simple tasks |
| `phi4-mini-16k:latest` | 2.5GB | Same, extended context |
| `qwen2.5:7b` | 4.7GB | Solid general model, OpenClaw fallback |
| `qwen2.5-coder:7b` | 4.7GB | Coding-specific, used in Continue.dev |
| `qwen32k:latest` | 4.7GB | Extended context variant |
| `qwen2.5-coder-32k:latest` | 4.7GB | Extended context coder |
| `deepseek-r1:7b` | 4.7GB | Reasoning, Continue.dev only |
| `qwen3.5:9b` | 6.6GB | Newer, better quality than 7B |
| `qwen2.5-coder:14b` | 9.0GB | **Do not use with OpenClaw on 16GB** |

The 14B model is there for focused, manual coding sessions in Continue.dev — close everything else first, run it, close it when done. It is never the OpenClaw primary.

---

## Skills Installed

OpenClaw's power comes from skills — Python scripts the bot runs when you ask for something. These live in `~/.openclaw/workspace/skills/`.

| Skill | What It Does |
|-------|-------------|
| `gmail` | Read, search, send email from Google account |
| `gcal` | View and create Google Calendar events (Bangkok timezone) |
| `contacts` | Save and search Google Contacts |
| `file-organizer` | Sort files sent by user into Google Drive automatically |
| `morning-briefing` | Daily 7am briefing: weather, markets, calendar, GitHub, AI news, email digest |
| `ocr-contacts` | Scan business card photo → extract → save to Google Contacts |
| `video-download` | Download video from YouTube/Twitter/TikTok/Instagram via yt-dlp |
| `web-search` | Search the web |
| `web-fetch` | Fetch and summarize a URL |
| `screenshot` | Screenshot a URL |
| `summarize` | Summarize any text or document |
| `translate` | Translate text |
| `remember` | Store and recall notes persistently |
| `photo-vault` | Save photos to Google Drive |
| `illustrate` | Generate images |
| `ask` | One-shot GPT-4o-mini question outside of conversation context |

### Morning Briefing

Runs at 7:00 AM Bangkok time (00:00 UTC) via cron. Covers:

- Bangkok weather + AQI (Open-Meteo + WAQI)
- Markets: BTC price, Gold, Oil (WTI), USD/THB rate
- Today's Google Calendar events
- Recent GitHub repo activity
- Top AI/tech news filtered from Hacker News (score ≥ 50, AI-keyword matched)
- Newsletter digest: unread Gmail newsletters summarized to 3 bullets each via GPT-4o-mini

Cron entry:
```
0 0 * * * /opt/homebrew/bin/python3 ~/.openclaw/workspace/skills/morning-briefing/scripts/briefing.py CHAT_ID >> ~/.openclaw/logs/morning-briefing.log 2>&1
```

Estimated cost per briefing: **~$0.003**. Daily for a year: **~$1.10**.

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

---

## What I Would Do Differently From Day One

1. **Skip Ollama as the OpenClaw primary entirely.** Keep it for Continue.dev (VS Code coding). For OpenClaw — the 24/7 bot — use a cloud API from minute one. On 16GB, it's not a compromise, it's the right call.

2. **Get an OpenAI key before setting up OpenClaw.** The onboarding assumes you have a model ready. GPT-4o-mini costs nothing at this scale. Don't try to cheap out with Groq free tier — the token limit makes it incompatible.

3. **Trim system prompt files before the first session.** AGENTS.md and HEARTBEAT.md shipped with content that was never relevant to my setup — Discord emoji reactions, ElevenLabs TTS config, email monitoring for a tool I don't have. That's ~2,000 extra tokens on every single request. Audit and strip before first use.

4. **Wipe sessions.json completely when installing new skills.** OpenClaw freezes the skill list in a snapshot at session start. If you install a skill and the bot doesn't use it, the session is stale. Don't just restart the gateway — wipe the snapshot too.

5. **Never add unknown fields to openclaw.json.** The schema validator is strict and the error messages are bad. Test every config change with `openclaw doctor` before restarting the gateway.

---

## Estimated Monthly Cost (Real Numbers)

Based on actual usage at moderate volume:

| Usage | Tokens/month (est.) | Cost |
|-------|---------------------|------|
| Morning briefing (daily) | ~900k input | $0.135 |
| Casual bot conversations (10–20/day) | ~600k input | $0.09 |
| Skill calls (calendar, email, etc.) | ~300k input | $0.045 |
| **Total** | **~1.8M tokens** | **~$0.27/month** |

Worst case with heavy use: under **$2/month**. That's less than a single ChatGPT message with image generation.

---

## Files That Matter

```
~/.openclaw/
├── openclaw.json                          ← Main config. Touch carefully.
├── workspace/
│   ├── SOUL.md                            ← Bot personality + rules
│   ├── MEMORY.md                          ← Persistent facts about you
│   ├── AGENTS.md                          ← Agent behavior rules (keep trimmed)
│   ├── HEARTBEAT.md                       ← Background monitoring rules
│   └── skills/                            ← All skill scripts
│       ├── gmail/
│       ├── gcal/
│       ├── contacts/
│       ├── morning-briefing/
│       └── ...
├── credentials/
│   ├── google-token.pkl                   ← Google OAuth token (9 scopes)
│   └── github-token.txt                   ← GitHub PAT
├── agents/main/sessions/
│   └── sessions.json                      ← Session registry. Wipe to reset.
├── scripts/
│   └── reset-session.sh                   ← The fix for most bot problems
└── logs/
    └── morning-briefing.log               ← Briefing output
```

---

## License

MIT. Do whatever. If this saves you the hours I lost, that's the point.

---

*Built on [OpenClaw](https://github.com/openclaw/openclaw) · Runs on GPT-4o-mini · Bangkok, Thailand*
