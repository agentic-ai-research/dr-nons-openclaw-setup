---
name: screenshot
description: Take a screenshot of the MAC DESKTOP SCREEN ONLY and send to Telegram. Use ONLY when the user says "screenshot my screen", "capture my screen", or "show me what's on screen" with no URL. Do NOT use this for URLs or websites — use url-screenshot for that.
---

# Screenshot

Captures the screen (or a specific website) and delivers it to the user via Telegram.

## Case 1: Website / URL screenshot

Use this when the user wants to see a specific webpage.

**Step 1** — Use the `browser` tool to capture the page:
```
action: screenshot
targetUrl: <the URL>
```

**Step 2** — Send the captured image to Telegram:
```bash
bash /Users/axiom/.openclaw/workspace/skills/screenshot/scripts/send-screenshot.sh <chat_id>
```

The `send-screenshot.sh` script finds the latest browser screenshot and sends it via Telegram `sendPhoto`. No other steps needed.

## Case 2: Full desktop screenshot

Use this when the user says "take a screenshot" without specifying a URL.

```bash
bash /Users/axiom/.openclaw/workspace/skills/screenshot/scripts/screenshot.sh <chat_id>
```

## Important

- `chat_id` is always available as `message.chat.id` from the incoming message.
- For website screenshots: ALWAYS do Step 1 (browser tool) THEN Step 2 (send-screenshot.sh). Do NOT skip either.
- After the script runs, reply with a short confirmation: "Screenshot sent!"
- Do NOT try to send images yourself any other way.
