"""
Clears the motivations cache and repopulates it for a list of dates
using the same prompt logic as app.py.

Usage:
    python repopulate_cache.py 2026-03-21 2026-03-22
"""

import sys
import os
import re
import json
import httpx
from tinydb import TinyDB, Query
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 300

os.makedirs("data", exist_ok=True)
db = TinyDB("data/cache.json")
QuoteTable = db.table("motivations")
Q = Query()


def build_prompt(date_str: str) -> str:
    return (
        f"Today is {date_str}. "
        "Identify one notable event for this exact date in history. "
        "Choose from these categories: Science, Technology, Business & Innovation, Music, Pop Culture, Internet & Digital Culture, Space & Exploration, or Cultural History. "
        "Pick a high-impact, widely recognized event — avoid obscure or trivial ones. If no strong event exists in one category, try another. "
        "In 'reason', give a 2-sentence explanation of the event. "
        "Then provide a motivational quote under 25 words, grounded in that specific event — avoid generic or cliché quotes. The quote must be positive and uplifting. "
        "Respond ONLY with valid JSON, no markdown, no explanation. "
        'Format: {"reason": "...", "quote": "...", "author": "..."}'
    )


def fetch_for_date(date_str: str) -> dict:
    prompt = build_prompt(date_str)
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

    usage = data.get("usage", {})
    parsed["input_tokens"] = usage.get("input_tokens", 0)
    parsed["output_tokens"] = usage.get("output_tokens", 0)
    parsed["tokens"] = parsed["input_tokens"] + parsed["output_tokens"]
    parsed["model"] = data.get("model", MODEL)
    return parsed


def main(dates: list[str]):
    for date_str in dates:
        print(f"Processing {date_str}...")
        # Remove existing entry
        QuoteTable.remove(Q.date == date_str)

        parsed = fetch_for_date(date_str)
        entry = {"date": date_str, **parsed}
        QuoteTable.insert(entry)
        print(f"  reason : {entry['reason']}")
        print(f"  quote  : {entry['quote']}")
        print(f"  author : {entry['author']}")
        print(f"  tokens : {entry['tokens']}")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python repopulate_cache.py <date1> [date2 ...]")
        print("Example: python repopulate_cache.py 2026-03-21 2026-03-22")
        sys.exit(1)
    main(sys.argv[1:])
