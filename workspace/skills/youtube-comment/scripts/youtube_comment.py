#!/usr/bin/env python3
"""
YouTube "Think Like Me" Commenter

Fetches transcript → loads user persona → generates comment in user's voice → optionally posts.

Usage:
  youtube_comment.py <url> [--post] [--lang en] [--dry-run]

Requires:
  pip3 install youtube_transcript_api requests --break-system-packages
  YouTube Data API v3 enabled + google-token.pkl with youtube.force-ssl scope (for --post)
"""
import sys, os, argparse, json, urllib.request, pickle

TOKEN_FILE   = os.path.expanduser("~/.openclaw/credentials/google-token.pkl")
MEMORY_FILE  = os.path.expanduser("~/self-improving/memory.md")
DOMAINS_DIR  = os.path.expanduser("~/self-improving/domains/")
OPENAI_URL   = "https://api.openai.com/v1/chat/completions"
YT_COMMENT_URL = "https://www.googleapis.com/youtube/v3/comments?part=snippet"

def get_openai_key():
    config = json.load(open(os.path.expanduser("~/.openclaw/openclaw.json")))
    return config["models"]["providers"]["openai"]["apiKey"]

def load_persona():
    """Load user persona from self-improving memory files."""
    persona_parts = []

    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE) as f:
            content = f.read().strip()
        if content:
            persona_parts.append(f"=== User Memory ===\n{content}")

    if os.path.exists(DOMAINS_DIR):
        for fname in sorted(os.listdir(DOMAINS_DIR)):
            fpath = os.path.join(DOMAINS_DIR, fname)
            if os.path.isfile(fpath) and fname.endswith(".md"):
                with open(fpath) as f:
                    content = f.read().strip()
                if content:
                    persona_parts.append(f"=== {fname} ===\n{content}")

    if not persona_parts:
        # Fallback: basic persona from MEMORY.md
        mem_path = os.path.expanduser("~/.openclaw/workspace/MEMORY.md")
        if os.path.exists(mem_path):
            with open(mem_path) as f:
                persona_parts.append(f.read().strip())

    return "\n\n".join(persona_parts) if persona_parts else ""

def get_transcript(url, lang="en"):
    """Fetch transcript using youtube_transcript_api."""
    from youtube_transcript_api import YouTubeTranscriptApi
    from urllib.parse import urlparse, parse_qs

    url = url.strip()
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")

    if host in ("youtube.com", "m.youtube.com"):
        video_id = parse_qs(parsed.query).get("v", [""])[0]
        if not video_id and "/shorts/" in parsed.path:
            video_id = parsed.path.split("/shorts/")[1].split("/")[0]
    elif host == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0]
    else:
        video_id = url  # assume raw ID

    if not video_id:
        raise ValueError(f"Could not extract video ID from: {url}")

    api = YouTubeTranscriptApi()
    try:
        transcript = api.fetch(video_id, languages=[lang, "en"])
    except Exception:
        # Try any available language
        transcript_list = api.list(video_id)
        transcript = transcript_list.find_transcript(
            [t.language_code for t in transcript_list]
        ).fetch()

    return video_id, " ".join(s.text for s in transcript)

def generate_comment(transcript, video_url, persona, api_key):
    """Generate a comment in the user's voice using GPT-4o-mini."""
    persona_section = f"\n\nUser persona and preferences:\n{persona}" if persona else ""

    system = (
        "You are generating a YouTube comment on behalf of a specific person. "
        "The comment must sound authentically like them — matching their vocabulary, "
        "tone, opinions, sense of humor, and level of depth. "
        "Do NOT be generic. Do NOT sound like AI. Do NOT be sycophantic. "
        "The comment should be 1-4 sentences, opinionated, direct, and specific to the video content."
        + persona_section
    )

    user_msg = (
        f"Video URL: {video_url}\n\n"
        f"Transcript (first 3000 chars):\n{transcript[:3000]}\n\n"
        "Write a comment this person would actually post. "
        "Make it feel like a real human reaction, not a summary. "
        "If the transcript reveals something worth challenging, agreeing with strongly, "
        "or adding nuance to — do that. "
        "Return ONLY the comment text, nothing else."
    )

    payload = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg}
        ],
        "max_tokens": 300,
        "temperature": 0.85
    }).encode()

    req = urllib.request.Request(OPENAI_URL, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"].strip()

def post_comment(video_id, comment_text):
    """Post comment via YouTube Data API v3."""
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    with open(TOKEN_FILE, "rb") as f:
        creds = pickle.load(f)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    svc = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {
            "videoId": video_id,
            "topLevelComment": {
                "snippet": {"textOriginal": comment_text}
            }
        }
    }
    result = svc.commentThreads().insert(part="snippet", body=body).execute()
    return result["id"]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--post", action="store_true", help="Post the comment after generating")
    parser.add_argument("--lang", default="en")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = get_openai_key()

    # Step 1: Transcript
    print("Fetching transcript...")
    try:
        video_id, transcript = get_transcript(args.url, args.lang)
        word_count = len(transcript.split())
        print(f"Transcript: {word_count} words fetched.")
    except Exception as e:
        print(f"Transcript unavailable: {e}")
        print("Generating comment from URL only (no transcript).")
        video_id = args.url.split("v=")[-1].split("&")[0] if "v=" in args.url else args.url
        transcript = f"[Transcript not available for this video: {args.url}]"

    # Step 2: Load persona
    persona = load_persona()
    if persona:
        print(f"Persona loaded ({len(persona.split())} words).")
    else:
        print("No persona found — generating without personal context.")

    # Step 3: Generate comment
    print("\nGenerating comment...")
    comment = generate_comment(transcript, args.url, persona, api_key)
    print(f"\nGenerated comment:\n  \"{comment}\"")

    # Step 4: Post (if requested)
    if args.post and not args.dry_run:
        print("\nPosting...")
        try:
            comment_id = post_comment(video_id, comment)
            print(f"Posted. (comment ID: {comment_id})")
        except Exception as e:
            print(f"Post failed: {e}")
            print("Ensure YouTube Data API v3 is enabled and OAuth token has youtube.force-ssl scope.")
            print("Re-run: python3 ~/.openclaw/scripts/google-auth.py")
    elif args.post:
        print("\n[dry-run] Would have posted the comment above.")

if __name__ == "__main__":
    main()
