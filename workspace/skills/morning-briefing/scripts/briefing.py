#!/usr/bin/env python3
"""
Morning Briefing for Dr. Non — 7:00 AM Bangkok
Sections: Weather/AQI · Markets · Calendar · GitHub · Tech/AI News · Newsletter Digest
Usage: briefing.py <chat_id>
"""
import sys, os, json, urllib.request, urllib.error, pickle, base64, re
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

TELEGRAM_TOKEN = open(os.path.expanduser("~/.openclaw/credentials/telegram-token.txt")).read().strip()
TELEGRAM_API   = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
TOKEN_FILE     = os.path.expanduser("~/.openclaw/credentials/google-token.pkl")
GITHUB_TOKEN   = open(os.path.expanduser("~/.openclaw/credentials/github-token.txt")).read().strip()
LAT, LON       = 13.7563, 100.5018
CHAT_ID        = sys.argv[1] if len(sys.argv) > 1 else None

# ── helpers ──────────────────────────────────────────────────────────────────

def fetch(url, headers=None, timeout=10):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "OpenClaw/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def openai_summarize(text, prompt_prefix, max_tokens=400):
    config = json.load(open(os.path.expanduser("~/.openclaw/openclaw.json")))
    # Use Gemini (free) — fall back to OpenAI if Gemini key unavailable
    gemini_cfg = config.get("models", {}).get("providers", {}).get("gemini")
    if gemini_cfg and gemini_cfg.get("apiKey"):
        key = gemini_cfg["apiKey"]
        model = "gemini-flash-latest"
        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    else:
        key = config["models"]["providers"]["openai"]["apiKey"]
        model = "gpt-4o-mini"
        url = "https://api.openai.com/v1/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": f"{prompt_prefix}\n\n{text[:3000]}"}],
        "max_tokens": max_tokens
    }).encode()
    req = urllib.request.Request(url, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()

def send_telegram(text):
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        payload = json.dumps({"chat_id": CHAT_ID, "text": chunk, "parse_mode": "Markdown"}).encode()
        req = urllib.request.Request(f"{TELEGRAM_API}/sendMessage", data=payload,
            headers={"Content-Type":"application/json"})
        urllib.request.urlopen(req, timeout=15)

def google_service(api, version):
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    with open(TOKEN_FILE, "rb") as f:
        creds = pickle.load(f)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "wb") as f: pickle.dump(creds, f)
    return build(api, version, credentials=creds)

# ── sections ─────────────────────────────────────────────────────────────────

def section_weather():
    codes = {0:"Clear",1:"Mostly clear",2:"Partly cloudy",3:"Overcast",
             45:"Foggy",51:"Drizzle",61:"Rain",63:"Moderate rain",65:"Heavy rain",
             80:"Showers",95:"Thunderstorm"}
    weather_line = None

    # Primary: Open-Meteo
    try:
        w = fetch(f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
                  f"&current=temperature_2m,weathercode,windspeed_10m"
                  f"&daily=precipitation_sum,temperature_2m_max,temperature_2m_min"
                  f"&timezone=Asia%2FBangkok&forecast_days=1")
        cur = w["current"]; d = w["daily"]
        desc = codes.get(cur["weathercode"], "?")
        rain = d["precipitation_sum"][0]
        rain_str = f" | Rain: {rain}mm" if rain > 0 else ""
        weather_line = (f"  {cur['temperature_2m']}°C, {desc} | "
                        f"High {d['temperature_2m_max'][0]}° Low {d['temperature_2m_min'][0]}°{rain_str}")
    except Exception:
        pass

    # Fallback: wttr.in (no rate limit, no key)
    if not weather_line:
        try:
            req = urllib.request.Request(
                "https://wttr.in/Bangkok?format=j1",
                headers={"User-Agent": "curl/7.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                wj = json.loads(r.read())
            cc = wj["current_condition"][0]
            temp = cc["temp_C"]
            desc = cc["weatherDesc"][0]["value"]
            feels = cc["FeelsLikeC"]
            weather_line = f"  {temp}°C (feels {feels}°C), {desc}"
        except Exception as e2:
            weather_line = f"  unavailable ({e2})"

    # AQI — Open-Meteo air quality (free, no key needed)
    aqi_line = ""
    try:
        aq = fetch(f"https://air-quality-api.open-meteo.com/v1/air-quality"
                   f"?latitude={LAT}&longitude={LON}&current=us_aqi,pm2_5")
        aqi = aq["current"]["us_aqi"]
        pm25 = aq["current"]["pm2_5"]
        aqi_label = ("Good" if aqi<=50 else "Moderate" if aqi<=100 else
                     "Unhealthy for sensitive" if aqi<=150 else "Unhealthy" if aqi<=200 else "Very Unhealthy")
        aqi_line = f"\n  AQI: {aqi} ({aqi_label}) — PM2.5: {pm25:.1f} µg/m³"
    except Exception:
        pass

    return f"🌤 *Bangkok Weather*\n{weather_line}{aqi_line}"

def section_markets():
    try:
        btc = fetch("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd")["bitcoin"]["usd"]
        gold = fetch("https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF?range=1d&interval=1d",
                     headers={"User-Agent":"Mozilla/5.0"})["chart"]["result"][0]["meta"]["regularMarketPrice"]
        oil = fetch("https://query1.finance.yahoo.com/v8/finance/chart/CL%3DF?range=1d&interval=1d",
                    headers={"User-Agent":"Mozilla/5.0"})["chart"]["result"][0]["meta"]["regularMarketPrice"]
        fx = fetch("https://open.er-api.com/v6/latest/USD")["rates"]["THB"]
        return (f"📈 *Markets*\n"
                f"  BTC: ${btc:,.0f} | Gold: ${gold:,.0f}/oz | Oil (WTI): ${oil:.1f}/bbl\n"
                f"  USD/THB: {fx:.2f}")
    except Exception as e:
        return f"📈 Markets: unavailable ({e})"

def section_calendar():
    try:
        svc = google_service("calendar", "v3")
        now = datetime.now(timezone.utc)
        events = svc.events().list(calendarId="primary",
            timeMin=now.isoformat(), timeMax=(now+timedelta(days=1)).isoformat(),
            maxResults=8, singleEvents=True, orderBy="startTime").execute().get("items", [])
        if not events:
            return "📅 *Calendar*: No events today"
        lines = ["📅 *Today's Calendar*"]
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date",""))
            t = datetime.fromisoformat(start).strftime("%H:%M") if "T" in start else "All day"
            lines.append(f"  {t} — {e.get('summary','(no title)')}")
        return "\n".join(lines)
    except Exception as e:
        return f"📅 Calendar: unavailable ({e})"

def section_github():
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "User-Agent": "OpenClaw/1.0"}
        repos = fetch("https://api.github.com/user/repos?sort=pushed&per_page=5", headers=headers)
        lines = ["🐙 *GitHub* (recent activity)"]
        for r in repos[:4]:
            pushed = r.get("pushed_at","")[:10]
            stars = r.get("stargazers_count", 0)
            issues = r.get("open_issues_count", 0)
            star_str = f" ⭐{stars}" if stars > 0 else ""
            issue_str = f" 🐛{issues} open" if issues > 0 else ""
            lines.append(f"  {r['full_name']}{star_str}{issue_str} (pushed {pushed})")
        return "\n".join(lines)
    except Exception as e:
        return f"🐙 GitHub: unavailable ({e})"

def section_tech_news():
    try:
        # Fetch top HN stories, filter for AI/tech relevance
        ids = fetch("https://hacker-news.firebaseio.com/v0/topstories.json")[:40]
        ai_keywords = {"ai","llm","gpt","claude","gemini","openai","anthropic","model","agent",
                       "llama","mistral","deepseek","qwen","transformer","neural","diffusion",
                       "ml","machine learning","robotics","nvidia","chip","gpu","inference"}
        tech_keywords = {"startup","launch","open source","github","api","tool","framework",
                         "developer","cloud","data","benchmark","research"}

        ai_picks, tech_picks = [], []
        for sid in ids:
            try:
                item = fetch(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5)
                title = item.get("title","").lower()
                score = item.get("score", 0)
                if score < 50: continue
                if any(k in title for k in ai_keywords):
                    ai_picks.append((score, item.get("title"), item.get("url","")))
                elif any(k in title for k in tech_keywords):
                    tech_picks.append((score, item.get("title"), item.get("url","")))
                if len(ai_picks) >= 4 and len(tech_picks) >= 2: break
            except: continue

        lines = ["🤖 *Tech & AI News* (Hacker News)"]
        for _, title, url in sorted(ai_picks, reverse=True)[:4]:
            lines.append(f"  • {title}")
        for _, title, url in sorted(tech_picks, reverse=True)[:2]:
            lines.append(f"  • {title}")
        return "\n".join(lines) if len(lines) > 1 else "🤖 Tech/AI News: nothing notable today"
    except Exception as e:
        return f"🤖 Tech/AI News: unavailable ({e})"

def section_newsletters():
    try:
        svc = google_service("gmail", "v1")
        # Priority senders — keep adding as you subscribe to more
        priority_senders = [
            "therundown", "importai", "tldr", "tldrai", "mittechreview",
            "benazir", "asean", "undp", "unescap", "adb",
            "tkc", "depa", "axios", "superhuman", "substack",
            "newsletter", "digest", "weekly", "briefing", "morning"
        ]
        # Build query in two halves (Gmail OR limit)
        half = len(priority_senders) // 2
        q1 = "is:unread newer_than:1d (" + " OR ".join(f"from:{s}" for s in priority_senders[:half]) + ")"
        q2 = "is:unread newer_than:1d (" + " OR ".join(f"from:{s}" for s in priority_senders[half:]) + ")"
        msgs1 = svc.users().messages().list(userId="me", q=q1, maxResults=8).execute().get("messages", [])
        msgs2 = svc.users().messages().list(userId="me", q=q2, maxResults=8).execute().get("messages", [])
        # Deduplicate by id
        seen = set()
        messages = []
        for m in msgs1 + msgs2:
            if m["id"] not in seen:
                seen.add(m["id"]), messages.append(m)

        if not messages:
            # Broader fallback: any unread — skip only transactional noise
            results = svc.users().messages().list(
                userId="me",
                q='is:unread newer_than:1d -subject:"thank you for your order" -subject:"your receipt" -subject:"invoice" -subject:"payment"',
                maxResults=8).execute()
            messages = results.get("messages", [])

        if not messages:
            return "📧 *Newsletters*: Nothing new in the last 24h"

        # Extract text from each email
        summaries = []
        skip_subjects = ["calendar invite", "thank you for your purchase", "read receipt",
                         "out of office", "automatic reply", "unsubscribe confirmation"]
        urgent_keywords = ["urgent", "deadline", "call for proposals", "endorsement",
                           "action required", "response needed", "asap"]

        for m in messages[:6]:
            try:
                msg = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
                headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
                subject = headers.get("Subject", "")
                sender = headers.get("From", "")

                # Skip noise
                if any(s in subject.lower() for s in skip_subjects):
                    continue

                # Extract plain text body
                body = ""
                parts = msg["payload"].get("parts", [msg["payload"]])
                for part in parts:
                    if part.get("mimeType") == "text/plain":
                        data = part["body"].get("data", "")
                        if data:
                            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                            break
                if not body:
                    body = msg.get("snippet", "")

                # Summarize
                is_urgent = any(k in (subject+body).lower() for k in urgent_keywords)
                prompt = ("Summarize this newsletter in 3 bullet points. Be direct. Focus on: "
                         "(1) what's new/announced, (2) what's actionable, (3) skip the fluff. "
                         "Each bullet max 15 words.")
                summary = openai_summarize(body[:2000], prompt, max_tokens=150)
                flag = "🚨 URGENT — " if is_urgent else ""
                summaries.append(f"{flag}*{subject[:50]}* (from {sender[:30]})\n{summary}")
            except:
                continue

        if not summaries:
            return "📧 *Newsletters*: Nothing relevant in the last 24h"

        return "📧 *Newsletter Digest*\n\n" + "\n\n".join(summaries)
    except Exception as e:
        return f"📧 Newsletters: unavailable ({e})"

# ── main ─────────────────────────────────────────────────────────────────────

def main():
    if not CHAT_ID:
        print("Usage: briefing.py <chat_id>"); sys.exit(1)

    bkk = datetime.now(timezone(timedelta(hours=7)))
    header = f"☀️ *Morning Briefing — {bkk.strftime('%A, %d %B %Y')}*\n"

    # Fetch all sections concurrently
    tasks = {
        "weather":     section_weather,
        "markets":     section_markets,
        "calendar":    section_calendar,
        "github":      section_github,
        "tech_news":   section_tech_news,
        "newsletters": section_newsletters,
    }

    results = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            results[futures[future]] = future.result()

    # Assemble in order
    order = ["weather", "markets", "calendar", "github", "tech_news", "newsletters"]
    sections = [header] + [results[k] for k in order if results.get(k) is not None]
    message = "\n\n".join(sections)

    send_telegram(message)
    print(f"Sent. ({len(message)} chars)")

if __name__ == "__main__":
    main()
