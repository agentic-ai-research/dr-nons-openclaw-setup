---
name: thai-writer
description: Write, translate, draft, summarize, or rewrite text in Thai using the free ThaiLLM model (OpenThaiGPT). Use for any Thai language task — formal letters, translations, summaries of Thai documents, or freeform Thai writing.
---

# Thai Writer — Powered by ThaiLLM (Free)

## When to Use
- User says "แปล...", "ช่วยเขียน...", "ร่าง...", "สรุป...", "เขียนใหม่..."
- User says "translate to Thai", "translate to English", "write in Thai"
- User says "draft formal Thai", "write a Thai letter/email"
- User says "summarize this in Thai"
- Any Thai language writing or translation task

## Command

```
python3 /Users/axiom/.openclaw/workspace/skills/thai-writer/scripts/thai_writer.py --task <task> [options]
```

### Tasks

| Task | Options | Example |
|------|---------|---------|
| `translate` | `--text "..."` `--to thai\|english` | Translate any text |
| `draft` | `--instruction "..."` | Draft Thai content from instruction |
| `summarize` | `--text "..."` | Summarize text in Thai bullet points |
| `rewrite` | `--text "..."` | Rewrite Thai text to be clearer |
| `freeform` | `--prompt "..."` | Any open-ended Thai language request |

### Examples

```bash
# Translate to Thai
python3 .../thai_writer.py --task translate --text "The meeting is at 10am Monday." --to thai

# Translate Thai to English
python3 .../thai_writer.py --task translate --text "การประชุมจะเริ่มต้นในวันจันทร์" --to english

# Draft a formal letter
python3 .../thai_writer.py --task draft --instruction "Write a polite follow-up email to a government ministry asking about project status"

# Summarize Thai text
python3 .../thai_writer.py --task summarize --text "..."

# Freeform
python3 .../thai_writer.py --task freeform --prompt "อธิบายว่า machine learning คืออะไร"
```

## Notes
- Uses OpenThaiGPT 8B — optimized for Thai, also handles English well
- Free, no cost per call
- Rate limit: 200 requests/minute (more than enough for personal use)
- `<think>` reasoning traces are stripped automatically — output is clean
- Context limit: 16k tokens — keep input text under ~8,000 words
