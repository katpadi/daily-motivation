import os
import re
import json
import random
import httpx
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from flask import Flask, jsonify, send_from_directory, request
from tinydb import TinyDB, Query
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="static")

# ── TinyDB setup ──────────────────────────────────────────────────────────────
os.makedirs("data", exist_ok=True)
db = TinyDB("data/cache.json")
QuoteTable = db.table("motivations")
Q = Query()

# ── Constants ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 300
SITE_URL = os.getenv("SITE_URL", "https://motivation.yoursite.com")
SITE_TITLE = os.getenv("SITE_TITLE", "Daily Motivation")
SITE_DESC = os.getenv("SITE_DESC", "A daily motivational quote tied to today in history.")
DEFAULT_NAME = os.getenv("DEFAULT_NAME", "")

FALLBACK_QUOTES = [
    {"quote": "The secret of getting ahead is getting started.", "author": "Mark Twain", "reason": "A timeless reminder to take that first step.", "tokens": None, "model": None},
    {"quote": "It does not matter how slowly you go as long as you do not stop.", "author": "Confucius", "reason": "Persistence beats speed every time.", "tokens": None, "model": None},
    {"quote": "In the middle of every difficulty lies opportunity.", "author": "Albert Einstein", "reason": "Challenges are just opportunities in disguise.", "tokens": None, "model": None},
    {"quote": "It always seems impossible until it's done.", "author": "Nelson Mandela", "reason": "Every great achievement started as an impossible dream.", "tokens": None, "model": None},
    {"quote": "The only way to do great work is to love what you do.", "author": "Steve Jobs", "reason": "Passion is the foundation of excellence.", "tokens": None, "model": None},
]


# ── Helpers ───────────────────────────────────────────────────────────────────
def resolve_zone(tz: str):
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, Exception):
        return timezone.utc


def today_str(tz: str = "UTC") -> str:
    return datetime.now(resolve_zone(tz)).strftime("%Y-%m-%d")


def seconds_until_midnight(tz: str = "UTC") -> int:
    zone = resolve_zone(tz)
    now = datetime.now(zone)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((midnight - now).total_seconds())


def fetch_quote(date_str: str) -> dict:
    """Return cached quote for the given date, or fetch from Anthropic and cache it."""
    rows = QuoteTable.search(Q.date == date_str)
    if rows:
        return rows[0]

    prompt = (
        f"Today is {date_str}. "
        "Identify one notable event for this exact date in history. "
        "Choose from these categories: Science, Technology, Business & Innovation, Music, Pop Culture, Internet & Digital Culture, Space & Exploration, or Cultural History. "
        "Pick a high-impact, widely recognized event — avoid obscure or trivial ones. If no strong event exists in one category, try another. "
        "Ensure category diversity. Prefer a category not used recently. Only choose the most dominant event if it is significantly more impactful than alternatives."
        "In 'reason', give a 2-sentence explanation of the event. "
        "Then provide a motivational quote under 25 words, grounded in that specific event — avoid generic or cliché quotes. The quote must be positive and uplifting. "
        "Respond ONLY with valid JSON, no markdown, no explanation. "
        'Format: {"reason": "...", "quote": "...", "author": "..."}'
    )

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(ANTHROPIC_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw = data["content"][0]["text"].strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```[^\n]*\n?", "", raw)
                raw = re.sub(r"```$", "", raw).strip()
            raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw)
            parsed = json.loads(raw)

        assert "reason" in parsed and "quote" in parsed and "author" in parsed
        usage = data.get("usage", {})
        parsed["input_tokens"] = usage.get("input_tokens", 0)
        parsed["output_tokens"] = usage.get("output_tokens", 0)
        parsed["tokens"] = parsed["input_tokens"] + parsed["output_tokens"]
        parsed["model"] = data.get("model", MODEL)
    except Exception as e:
        import traceback; traceback.print_exc()
        parsed = random.choice(FALLBACK_QUOTES)

    entry = {"date": date_str, **parsed}
    QuoteTable.insert(entry)
    return entry


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/motivation")
def api_motivation():
    """JSON endpoint for the browser."""
    tz = request.args.get("tz", "UTC")
    date_str = today_str(tz)
    entry = fetch_quote(date_str)
    resp = jsonify({
        "date": entry["date"],
        "reason": entry["reason"],
        "quote": entry["quote"],
        "author": entry["author"],
        "tokens": entry.get("tokens"),
        "model": entry.get("model"),
    })
    resp.headers["Cache-Control"] = f"public, max-age={seconds_until_midnight(tz)}"
    return resp



@app.route("/api/database")
def api_database():
    """Return all cached quotes sorted by date descending."""
    entries = QuoteTable.all()
    entries.sort(key=lambda x: x.get("date", ""), reverse=True)
    return jsonify([
        {"date": e.get("date", ""), "quote": e.get("quote", ""), "author": e.get("author", ""), "reason": e.get("reason", "")}
        for e in entries
    ])


@app.route("/api/usage")
def api_usage():
    entries = QuoteTable.all()
    # Only count entries that have split token data (stored going forward)
    tracked = [e for e in entries if "input_tokens" in e and "output_tokens" in e]
    input_tokens  = sum(e["input_tokens"]  for e in tracked)
    output_tokens = sum(e["output_tokens"] for e in tracked)
    # Haiku pricing: $0.80/M input, $4.00/M output
    cost = (input_tokens * 0.80 + output_tokens * 4.00) / 1_000_000
    return jsonify({
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost, 6),
        "tracked_days": len(tracked),
    })


@app.route("/api/config")
def api_config():
    return jsonify({"name": DEFAULT_NAME})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
