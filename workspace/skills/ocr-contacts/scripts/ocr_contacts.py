#!/usr/bin/env python3
"""
OCR a business card or any image, extract text and contact info,
and save directly to Google Contacts.
Usage: ocr_contacts.py <image_path> [--no-save]

Requires: brew install tesseract
"""
import sys, os, json, re, subprocess, urllib.request, urllib.parse, pickle

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
TOKEN_FILE = os.path.expanduser("~/.openclaw/credentials/google-token.pkl")

def get_openai_key():
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    with open(config_path) as f:
        return json.load(f)["models"]["providers"]["openai"]["apiKey"]

def run_tesseract(image_path):
    image_path = os.path.realpath(image_path)  # resolve /tmp → /private/tmp on macOS
    result = subprocess.run(
        ["tesseract", image_path, "stdout", "--psm", "6"],
        capture_output=True, timeout=30
    )
    stdout = result.stdout.decode("utf-8", errors="replace").strip()
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        return None, stderr
    return stdout, None

def parse_contact_with_gpt(raw_text, api_key):
    prompt = (
        "Extract contact information from this business card or image text. "
        "Return ONLY a JSON object with these keys (null for missing):\n"
        '{"name": "", "title": "", "company": "", "phone": "", "email": "", "website": "", "address": ""}\n\n'
        f"Text:\n{raw_text}\n\nJSON only:"
    )
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(OPENAI_URL, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())
        text = result["choices"][0]["message"]["content"].strip()
    match = re.search(r"\{[^{}]+\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return None

def save_to_google_contacts(contact):
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    with open(TOKEN_FILE, "rb") as f:
        creds = pickle.load(f)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
    service = build("people", "v1", credentials=creds)

    body = {}
    if contact.get("name"):
        parts = contact["name"].split(" ", 1)
        body["names"] = [{"givenName": parts[0], "familyName": parts[1] if len(parts) > 1 else ""}]
    if contact.get("phone"):
        body["phoneNumbers"] = [{"value": contact["phone"]}]
    if contact.get("email"):
        body["emailAddresses"] = [{"value": contact["email"]}]
    if contact.get("company") or contact.get("title"):
        body["organizations"] = [{"name": contact.get("company",""), "title": contact.get("title","")}]
    if contact.get("website"):
        body["urls"] = [{"value": contact["website"]}]
    if contact.get("address"):
        body["addresses"] = [{"formattedValue": contact["address"]}]

    result = service.people().createContact(body=body).execute()
    return result.get("resourceName", "saved")

def parse_contact_with_vision(image_path, api_key):
    """Direct vision fallback — send image to GPT-4o-mini when Tesseract text is insufficient."""
    import base64
    with open(image_path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode()
    ext = image_path.lower().split(".")[-1]
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": (
                    "This is a business card image. Extract contact information and return ONLY a JSON object with: "
                    '{"name": "", "title": "", "company": "", "phone": "", "email": "", "website": "", "address": ""} '
                    "(null for missing fields). JSON only, no explanation."
                )},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
            ]
        }],
        "max_tokens": 300
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(OPENAI_URL, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())
        text = result["choices"][0]["message"]["content"].strip()
    match = re.search(r"\{[^{}]+\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return None

def describe_image(raw_text, api_key):
    """If not a business card, just describe what was OCR'd."""
    prompt = f"Here is text extracted from an image via OCR. What is this? Summarize it briefly:\n\n{raw_text}"
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(OPENAI_URL, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())
        return result["choices"][0]["message"]["content"].strip()

def is_business_card(contact):
    """Heuristic: if name + (phone or email) are present, treat as contact."""
    return bool(contact and contact.get("name") and
                (contact.get("phone") or contact.get("email")))

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("image_path")
    parser.add_argument("--no-save", action="store_true", help="Don't save to Google Contacts")
    args = parser.parse_args()

    if not os.path.exists(args.image_path):
        print(f"Error: file not found: {args.image_path}")
        sys.exit(1)

    api_key = get_openai_key()

    # Step 1: OCR
    raw_text, error = run_tesseract(args.image_path)
    if error:
        print(f"OCR error: {error}")
        sys.exit(1)
    if not raw_text:
        print("No text found in image.")
        sys.exit(0)

    # Step 2: Parse (Tesseract text → GPT)
    contact = parse_contact_with_gpt(raw_text, api_key)

    # Step 2b: Vision fallback — if Tesseract text didn't yield a valid contact
    if not is_business_card(contact):
        print("(Tesseract parse inconclusive — retrying with vision...)")
        contact = parse_contact_with_vision(args.image_path, api_key)

    if is_business_card(contact):
        # Step 3a: It's a contact — save to Google Contacts
        lines = ["Contact extracted:"]
        for field in ["name","title","company","phone","email","website","address"]:
            val = contact.get(field)
            if val and val != "null":
                lines.append(f"  {field.capitalize()}: {val}")
        print("\n".join(lines))

        if not args.no_save:
            try:
                resource = save_to_google_contacts(contact)
                print(f"\nSaved to Google Contacts. ({resource})")
            except Exception as e:
                print(f"\nCould not save to Google Contacts: {e}")
                # Fallback link
                params = {}
                if contact.get("name"):
                    parts = contact["name"].split(" ", 1)
                    params["givenName"] = parts[0]
                    if len(parts) > 1:
                        params["familyName"] = parts[1]
                if contact.get("phone"): params["phoneNumber"] = contact["phone"]
                if contact.get("email"): params["email"] = contact["email"]
                url = "https://contacts.google.com/new?" + urllib.parse.urlencode(params)
                print(f"Manual link: {url}")
    else:
        # Step 3b: Not a contact — describe what it is
        description = describe_image(raw_text, api_key)
        print(f"Image content:\n{description}")
        print(f"\nRaw text:\n{raw_text[:500]}")

if __name__ == "__main__":
    main()
