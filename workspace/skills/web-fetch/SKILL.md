---
name: web-fetch
description: Fetch and read the TEXT CONTENT of a specific URL the user has shared. Use when user pastes a link and says "read this", "what does this say", or "explain this article". Do NOT use for news searches (use tavily), do NOT use for visual page summaries (use url-screenshot).
---

# Web Fetch

Fetches a URL and returns its readable text content.

## When to Use

Use this skill whenever the user shares a URL and asks what it's about, or asks you to read/summarize a webpage.

## How to Use

Run this exact command, replacing the URL:

```bash
python3 /Users/axiom/.openclaw/workspace/skills/web-fetch/scripts/fetch.py "URL_HERE"
```

Read the output and summarize it for the user.

## Example

User asks about https://example.com:

```bash
python3 /Users/axiom/.openclaw/workspace/skills/web-fetch/scripts/fetch.py "https://example.com"
```

Do NOT call a tool named `web_fetch` — that does not exist. Use the bash command above.
