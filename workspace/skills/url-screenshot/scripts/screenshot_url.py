#!/usr/bin/env python3
"""
Screenshot a URL using agent-browser (headless Chromium),
then optionally summarize with GPT-4o-mini vision.

Usage:
  screenshot_url.py <url> [--full-page] [--summarize] [--output <path>]
"""
import sys, os, argparse, subprocess, json, base64, urllib.request, datetime

OPENAI_URL = "https://api.openai.com/v1/chat/completions"

def get_openai_key():
    config = json.load(open(os.path.expanduser("~/.openclaw/openclaw.json")))
    return config["models"]["providers"]["openai"]["apiKey"]

def screenshot_with_agent_browser(url, output_path, full_page=False):
    """Use agent-browser CLI to screenshot a URL."""
    # Open the page
    result = subprocess.run(
        ["agent-browser", "open", url],
        capture_output=True, timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to open URL: {result.stderr.decode()}")

    # Take screenshot — agent-browser syntax: screenshot <path>
    import time; time.sleep(3)  # let page fully render
    result = subprocess.run(
        ["agent-browser", "screenshot", output_path],
        capture_output=True, timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(f"Screenshot failed: {result.stderr.decode()}")

    return output_path

def screenshot_with_playwright(url, output_path, full_page=False):
    """Playwright fallback via Python."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.screenshot(path=output_path, full_page=full_page)
            browser.close()
        return output_path
    except ImportError:
        raise RuntimeError("playwright not installed. Run: pip3 install playwright && playwright install chromium")

def summarize_with_vision(image_path, url, api_key):
    """Send screenshot to GPT-4o-mini vision for summary."""
    with open(image_path, "rb") as f:
        image_b64 = base64.standard_b64encode(f.read()).decode()

    payload = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (f"This is a screenshot of {url}. "
                             "Summarize what's on this page: key headlines, main content, "
                             "any notable data or calls to action. Be concise and structured.")
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"}
                }
            ]
        }],
        "max_tokens": 800
    }).encode()

    req = urllib.request.Request(OPENAI_URL, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"].strip()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--full-page", action="store_true")
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    # Generate output path
    if args.output:
        output_path = args.output
    else:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        domain = args.url.replace("https://","").replace("http://","").split("/")[0].replace(".","_")
        output_path = f"/tmp/screenshot_{domain}_{ts}.png"

    # Try agent-browser first, fall back to playwright
    try:
        screenshot_with_agent_browser(args.url, output_path, args.full_page)
    except Exception as e1:
        try:
            screenshot_with_playwright(args.url, output_path, args.full_page)
        except Exception as e2:
            print(f"Screenshot failed.\nagent-browser: {e1}\nplaywright: {e2}")
            sys.exit(1)

    print(f"Screenshot saved: {output_path}")

    if args.summarize:
        try:
            api_key = get_openai_key()
            summary = summarize_with_vision(output_path, args.url, api_key)
            print(f"\nSummary:\n{summary}")
        except Exception as e:
            print(f"\nVision summary failed: {e}")
            print("(Screenshot is still saved — view it manually)")

if __name__ == "__main__":
    main()
