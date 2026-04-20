# Disabled Skills

These skills are installed by ClawHub but disabled to prevent routing conflicts
or hallucination (skill exists but nothing runs). Rename from `.disabled` back
to the original name to re-enable.

| Skill | Why Disabled |
|-------|-------------|
| `web-search` | Uses DuckDuckGo — loses routing race against Tavily. Bot would pick this first, get empty results, and hallucinate "I searched but found nothing". Tavily is the only search tool. |
| `summarize` | 3-way conflict with `web-fetch` and `url-screenshot`. Also uses local LLM which may not be available. Covered fully by the other two. |
| `illustrate` | Empty scripts directory — skill exists in SKILL.md but no script to run. Guaranteed hallucination. Re-enable only after adding a working script. |

## Conflict Map (resolved)

What each active skill owns — no overlaps:

| Skill | Owns |
|-------|------|
| `tavily-web-search-for-openclaw` | ALL web searches, news, current events |
| `web-fetch` | Read a specific URL the user shared |
| `url-screenshot` | Visual screenshot + summary of a URL |
| `screenshot` | Desktop screen capture only (no URL) |
| `thai-writer` | All Thai language tasks (translate, draft, summarize) |
| `translate` | Non-Thai language translation only |
