---
name: translate
description: Translate text between non-Thai languages (e.g. Japanese→English, French→Spanish, Chinese→English). Do NOT use for anything involving Thai language — use thai-writer for all Thai tasks (translation, drafting, summarizing in Thai).
---

# Translate

Translates plain text or a URL's content using the local language model. No internet required. No API key. Fully private.

## When to Use

- User sends text in Thai, Chinese, Japanese, Arabic, French, etc. and wants it in English
- User shares a URL and says "what does this say?" or "translate this"
- User explicitly asks to translate something into a specific language

## How to Use

**Translate plain text:**
```
python3 /Users/axiom/.openclaw/workspace/skills/translate/scripts/translate.py --text "ข้อความที่ต้องการแปล" --to English
```

**Translate a URL's content:**
```
python3 /Users/axiom/.openclaw/workspace/skills/translate/scripts/translate.py --url "https://example.com/article" --to English
```

**Translate to a language other than English:**
```
python3 /Users/axiom/.openclaw/workspace/skills/translate/scripts/translate.py --text "Hello world" --to Thai
```

## Arguments

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--text` | one of these | — | The raw text to translate |
| `--url` | one of these | — | A URL whose content will be fetched and translated |
| `--to` | no | English | Target language |

## Output

Prints the translation to stdout. Read it and send it back to the user directly — no extra formatting needed.

## Notes

- Large pages are truncated to ~4000 chars before translation to fit within model context
- The model will detect the source language automatically
- For Thai ↔ English, this works very well with qwen2.5:7b
