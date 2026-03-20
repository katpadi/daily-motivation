import os
import re
import json
import random
import httpx
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, send_from_directory
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
def today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")



def seconds_until_midnight() -> int:
    now = datetime.now(timezone.utc)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((midnight - now).total_seconds())


def fetch_quote() -> dict:
    """Return cached quote for today, or fetch from Anthropic and cache it."""
    date_str = today_str()
    rows = QuoteTable.search(Q.date == date_str)
    if rows:
        return rows[0]

    prompt = (
        f"Today is {date_str}. "
        "Identify one notable historical, scientific, cultural, or holiday event for this date. "
        "Then provide one short motivational quote (under 40 words) that fits the theme of that event. "
        "The quote must be safe, positive, and non-controversial. "
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
            parsed = json.loads(raw)

        assert "reason" in parsed and "quote" in parsed and "author" in parsed
        usage = data.get("usage", {})
        parsed["tokens"] = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        parsed["model"] = data.get("model", MODEL)
    except Exception:
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
    entry = fetch_quote()
    resp = jsonify({
        "date": entry["date"],
        "reason": entry["reason"],
        "quote": entry["quote"],
        "author": entry["author"],
        "tokens": entry.get("tokens"),
        "model": entry.get("model"),
    })
    resp.headers["Cache-Control"] = f"public, max-age={seconds_until_midnight()}"
    return resp



@app.route("/api/config")
def api_config():
    return jsonify({"name": DEFAULT_NAME})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
