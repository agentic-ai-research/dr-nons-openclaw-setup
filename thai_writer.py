#!/usr/bin/env python3
"""
Thai Writer — calls ThaiLLM (OpenThaiGPT) for Thai language tasks.
Uses the free ThaiLLM API with apikey: header (not Authorization: Bearer).

Usage:
  thai_writer.py --task translate --text "..." [--to thai|english]
  thai_writer.py --task draft --instruction "..."
  thai_writer.py --task summarize --text "..."
  thai_writer.py --task rewrite --text "..."
  thai_writer.py --task freeform --prompt "..."
"""
import sys, os, json, re, argparse, urllib.request

CONFIG_PATH = os.path.expanduser("~/.openclaw/credentials/thaillm.json")

SYSTEM_PROMPTS = {
    "translate": "You are a professional translator. Translate the given text accurately and naturally. Output the translation only — no explanation, no commentary.",
    "draft":     "You are a Thai writing assistant. Write formal, natural, polished Thai based on the user's instruction. Output the Thai text only.",
    "summarize": "Summarize the following text as clear, concise Thai bullet points. Be direct. Output bullet points only.",
    "rewrite":   "Rewrite the following Thai text to be clearer, more natural, and more polished. Output the rewritten text only.",
}


def load_config():
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    url = cfg.get("url")
    key = cfg.get("apiKey")
    if not url or not key:
        print("Error: url and apiKey not found in ~/.openclaw/credentials/thaillm.json")
        sys.exit(1)
    return url, key


def strip_think(text):
    """Remove <think>...</think> reasoning traces from model output."""
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()


def call_thaillm(url, key, system_prompt, user_message):
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_message})

    payload = json.dumps({
        "model": "/model",
        "messages": messages,
        "max_tokens": 2048,
        "temperature": 0.3,
    }).encode()

    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "apikey": key,
        "User-Agent": "Mozilla/5.0",
    })

    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode())

    raw = result["choices"][0]["message"]["content"]
    return strip_think(raw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True,
                        choices=["translate", "draft", "summarize", "rewrite", "freeform"])
    parser.add_argument("--text",        default="")
    parser.add_argument("--instruction", default="")
    parser.add_argument("--prompt",      default="")
    parser.add_argument("--to",          default="thai", choices=["thai", "english"])
    args = parser.parse_args()

    url, key = load_config()

    if args.task == "translate":
        if not args.text:
            print("Error: --text required for translate"); sys.exit(1)
        lang = "Thai" if args.to == "thai" else "English"
        system = SYSTEM_PROMPTS["translate"]
        user_msg = f"Translate the following to {lang}:\n\n{args.text}"

    elif args.task == "draft":
        if not args.instruction:
            print("Error: --instruction required for draft"); sys.exit(1)
        system = SYSTEM_PROMPTS["draft"]
        user_msg = args.instruction

    elif args.task == "summarize":
        if not args.text:
            print("Error: --text required for summarize"); sys.exit(1)
        system = SYSTEM_PROMPTS["summarize"]
        user_msg = args.text

    elif args.task == "rewrite":
        if not args.text:
            print("Error: --text required for rewrite"); sys.exit(1)
        system = SYSTEM_PROMPTS["rewrite"]
        user_msg = args.text

    elif args.task == "freeform":
        if not args.prompt:
            print("Error: --prompt required for freeform"); sys.exit(1)
        system = None
        user_msg = args.prompt

    result = call_thaillm(url, key, system, user_msg)
    print(result)


if __name__ == "__main__":
    main()
