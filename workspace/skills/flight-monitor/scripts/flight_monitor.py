#!/usr/bin/env python3
"""
Flight Price Monitor — Google Flights scraper via agent-browser.

Commands:
  add    --from BKK --to LHR --max-price 35000 [--currency THB] [--dates "2026-07 2026-08"]
  check  [--route BKK-LHR] [--all]
  list
  remove --route BKK-LHR

Storage: ~/.openclaw/workspace/state/flights.json
"""
import sys, os, json, argparse, subprocess, re, datetime

STATE_FILE = os.path.expanduser("~/.openclaw/workspace/state/flights.json")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"routes": []}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# Thai domestic airports — Google Flights uses full city names better than IATA for domestic
THAI_AIRPORTS = {
    "BKK": "Bangkok", "DMK": "Bangkok Don Mueang", "NST": "Nakhon Si Thammarat",
    "HKT": "Phuket", "CNX": "Chiang Mai", "UTP": "Pattaya U-Tapao",
    "HDY": "Hat Yai", "KBV": "Krabi", "USM": "Koh Samui",
    "CEI": "Chiang Rai", "KKC": "Khon Kaen", "UDN": "Udon Thani",
    "UBP": "Ubon Ratchathani", "NKT": "Nakhon Ratchasima", "TDX": "Trat",
}

def is_domestic_thai(origin, dest):
    thai_codes = set(THAI_AIRPORTS.keys())
    return origin.upper() in thai_codes and dest.upper() in thai_codes

def build_google_flights_url(origin, dest, dates=None):
    """Build a Google Flights search URL for the route."""
    o = THAI_AIRPORTS.get(origin.upper(), origin)
    d = THAI_AIRPORTS.get(dest.upper(), dest)
    return f"https://www.google.com/travel/flights?q=flights+from+{o.replace(' ', '+')}+to+{d.replace(' ', '+')}"

def build_airasia_url(origin, dest):
    """AirAsia direct search — best for Thai domestic."""
    return f"https://www.airasia.com/en/gb/flights?origin={origin.upper()}&destination={dest.upper()}&triptype=O&adult=1"

def scrape_price_agent_browser(url):
    """Use agent-browser to open Google Flights and extract prices from accessibility tree."""
    try:
        r1 = subprocess.run(["agent-browser", "open", url], capture_output=True, timeout=30)
        if r1.returncode != 0:
            return None, None, "agent-browser open failed"

        import time; time.sleep(4)
        r2 = subprocess.run(["agent-browser", "snapshot", "--json"], capture_output=True, timeout=30)
        snapshot_text = r2.stdout.decode("utf-8", errors="replace")

        import json as _json
        data = _json.loads(snapshot_text)
        refs = data.get("data", {}).get("refs", {})

        # Parse structured flight listings from accessibility tree
        # Format: "From 21549 Thai baht round trip total. N stop(s) flight with Airline."
        flights = []
        cheapest_pattern = re.compile(
            r'From\s+([\d,]+)\s+Thai\s+baht.*?(\d+\s+stops?|Nonstop)\s+flight\s+with\s+([^.]+)',
            re.IGNORECASE
        )
        for ref in refs.values():
            name = ref.get("name", "")
            m = cheapest_pattern.search(name)
            if m:
                price = int(m.group(1).replace(",", ""))
                stops = m.group(2).strip()
                airline = m.group(3).strip()
                if 5000 < price < 500000:
                    flights.append({"price": price, "stops": stops, "airline": airline})

        # Also check "Cheapest from X" summary line
        for ref in refs.values():
            name = ref.get("name", "")
            m = re.search(r'Cheapest from ([\d,]+) Thai baht', name, re.IGNORECASE)
            if m:
                price = int(m.group(1).replace(",", ""))
                if 5000 < price < 500000 and not any(f["price"] == price for f in flights):
                    flights.append({"price": price, "stops": "?", "airline": "?"})

        if not flights:
            return None, None, "No prices found in accessibility tree"

        flights.sort(key=lambda x: x["price"])
        best = flights[0]
        # Return price and top-3 options as a summary string
        summary_lines = []
        for f in flights[:4]:
            summary_lines.append(f"  {f['price']:,} THB — {f['stops']} ({f['airline']})")
        summary = "\n".join(summary_lines)
        return best["price"], summary, None

    except Exception as e:
        return None, None, str(e)

def scrape_price_kayak(origin, dest):
    """Fallback: scrape Kayak via agent-browser."""
    url = f"https://www.kayak.com/flights/{origin}-{dest}/flexible-3"
    return scrape_price_agent_browser(url)

def scrape_price_domestic_thai(origin, dest):
    """For Thai domestic routes: try AirAsia + Thai Lion Air URLs via agent-browser."""
    # AirAsia Thailand domestic
    url_aa = f"https://www.airasia.com/en/gb/flights?origin={origin.upper()}&destination={dest.upper()}&triptype=O&adult=1&child=0&infant=0&locale=th_TH"
    price, summary, err = scrape_price_agent_browser(url_aa)
    if price:
        return price, summary, err

    # Thai Lion Air
    url_lion = f"https://www.lionairthai.com/en/searchFlight?origin={origin.upper()}&destination={dest.upper()}&departDate=&tripType=OW&adult=1"
    price, summary, err = scrape_price_agent_browser(url_lion)
    if price:
        return price, summary, err

    # Google Flights with Thai city names (last resort)
    url_gf = build_google_flights_url(origin, dest)
    return scrape_price_agent_browser(url_gf)

def cmd_add(args):
    state = load_state()
    route_key = f"{args.from_}-{args.to}"

    # Check if already exists
    for r in state["routes"]:
        if r["route"] == route_key:
            print(f"Route {route_key} already tracked. Use 'check' to see current price.")
            return

    route = {
        "route": route_key,
        "from": args.from_,
        "to": args.to,
        "max_price": args.max_price,
        "currency": args.currency,
        "dates": args.dates or "flexible",
        "last_price": None,
        "last_checked": None,
        "added": datetime.datetime.now().isoformat()
    }
    state["routes"].append(route)
    save_state(state)
    print(f"Tracking added: {args.from_} → {args.to} (alert ≤ {args.max_price:,} {args.currency})")
    print(f"Checking current price now...\n")

    # Immediately check price so user gets a real answer
    if is_domestic_thai(args.from_, args.to):
        price, options_summary, err = scrape_price_domestic_thai(args.from_, args.to)
    else:
        url = build_google_flights_url(args.from_, args.to)
        price, options_summary, err = scrape_price_agent_browser(url)
        if price is None:
            price, options_summary, err = scrape_price_kayak(args.from_, args.to)

    now = datetime.datetime.now().isoformat()
    if price:
        alert = " 🚨 BELOW YOUR THRESHOLD" if price <= args.max_price else ""
        print(f"Cheapest now: {price:,} {args.currency}{alert}")
        if options_summary:
            print(f"\nTop options:\n{options_summary}")
        print(f"\nThreshold: {args.max_price:,} {args.currency}")
        # Persist the price we just found
        state2 = load_state()
        for r in state2["routes"]:
            if r["route"] == route_key:
                r["last_price"] = price
                r["last_checked"] = now
        save_state(state2)
    else:
        print(f"Price check failed ({err}) — route is saved, try 'check --route {route_key}' later.")

def cmd_check(args):
    state = load_state()
    if not state["routes"]:
        print("No routes tracked yet. Use 'add' first.")
        return

    routes = state["routes"]
    if args.route:
        routes = [r for r in routes if r["route"].upper() == args.route.upper()]
        if not routes:
            print(f"Route {args.route} not found.")
            return

    results = []
    for route in routes:
        origin = route["from"]
        dest   = route["to"]
        max_p  = route["max_price"]
        curr   = route["currency"]
        url    = build_google_flights_url(origin, dest, route.get("dates"))

        print(f"Checking {origin} → {dest}...", flush=True)
        if is_domestic_thai(origin, dest):
            price, options_summary, err = scrape_price_domestic_thai(origin, dest)
        else:
            price, options_summary, err = scrape_price_agent_browser(url)
            if price is None:
                price, options_summary, err = scrape_price_kayak(origin, dest)

        now = datetime.datetime.now().isoformat()
        prev_price = route.get("last_price")

        if price:
            change = ""
            if prev_price:
                diff = price - prev_price
                pct = (diff / prev_price) * 100
                arrow = "📉" if diff < 0 else "📈"
                change = f" {arrow} was {prev_price:,} ({'+' if diff>0 else ''}{pct:.1f}%)"

            alert = " 🚨 BELOW YOUR THRESHOLD" if price <= max_p else ""
            print(f"\nCheapest: {price:,} {curr}{change}{alert}")
            if options_summary:
                print(f"\nTop options:\n{options_summary}")
            print(f"\nThreshold: {max_p:,} {curr} | Source: Google Flights")

            route["last_price"] = price
            route["last_checked"] = now
            results.append({
                "route": route["route"],
                "price": price,
                "options_summary": options_summary,
                "prev_price": prev_price,
                "max_price": max_p,
                "currency": curr,
                "below_threshold": price <= max_p
            })
        else:
            print(f"Could not fetch price ({err})")
            route["last_checked"] = now

    save_state(state)

    # Summary
    alerts = [r for r in results if r["below_threshold"]]
    if alerts:
        print(f"\n🎯 {len(alerts)} route(s) below your threshold!")
        for a in alerts:
            print(f"  {a['route']}: {a['price']:,} {a['currency']} (threshold: {a['max_price']:,})")
    elif results:
        print(f"\nAll {len(results)} route(s) checked. No prices below threshold.")

def cmd_list(args):
    state = load_state()
    if not state["routes"]:
        print("No routes tracked.")
        return

    print(f"Tracked routes ({len(state['routes'])}):\n")
    for r in state["routes"]:
        last = f"{r['last_price']:,} {r['currency']}" if r.get("last_price") else "not checked yet"
        checked = r.get("last_checked", "never")[:10] if r.get("last_checked") else "never"
        threshold_met = "✅" if r.get("last_price") and r["last_price"] <= r["max_price"] else "⏳"
        print(f"  {threshold_met} {r['route']}")
        print(f"     Threshold: ≤ {r['max_price']:,} {r['currency']} | Last: {last} (checked {checked})")
        print(f"     Dates: {r.get('dates', 'flexible')}")

def cmd_remove(args):
    state = load_state()
    before = len(state["routes"])
    state["routes"] = [r for r in state["routes"] if r["route"].upper() != args.route.upper()]
    if len(state["routes"]) < before:
        save_state(state)
        print(f"Removed: {args.route}")
    else:
        print(f"Route {args.route} not found.")

def get_briefing_section():
    """Called by morning briefing — returns flight alerts string or None."""
    state = load_state()
    if not state["routes"]:
        return None

    alerts = []
    for r in state["routes"]:
        if r.get("last_price") and r["last_price"] <= r["max_price"]:
            alerts.append(
                f"  ✈️ {r['route']}: {r['last_price']:,} {r['currency']} "
                f"(threshold: {r['max_price']:,})"
            )

    if not alerts:
        return None

    return "✈️ *Flight Alerts*\n" + "\n".join(alerts)

def main():
    parser = argparse.ArgumentParser(description="Flight price monitor")
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add")
    p_add.add_argument("--from", dest="from_", required=True)
    p_add.add_argument("--to", required=True)
    p_add.add_argument("--max-price", type=int, required=True)
    p_add.add_argument("--currency", default="THB")
    p_add.add_argument("--dates", default=None)

    p_check = sub.add_parser("check")
    p_check.add_argument("--route", default=None)
    p_check.add_argument("--all", action="store_true")

    sub.add_parser("list")

    p_rm = sub.add_parser("remove")
    p_rm.add_argument("--route", required=True)

    args = parser.parse_args()

    if args.command == "add":     cmd_add(args)
    elif args.command == "check": cmd_check(args)
    elif args.command == "list":  cmd_list(args)
    elif args.command == "remove": cmd_remove(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
