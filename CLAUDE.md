# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

Requires a `.env` file (copy from `.env.example`):
```
ANTHROPIC_API_KEY=your_key
SITE_URL=https://quote.yoursite.com
SITE_TITLE=Daily Quote
SITE_DESC=A daily motivational quote tied to today in history.
```

```bash
mkdir -p data
docker compose up -d --build   # start
docker compose logs -f          # tail logs
docker compose down             # stop
```

For local dev without Docker:
```bash
pip install -r requirements.txt
python app.py   # runs on :5000
```

## Architecture

Single-file Flask backend (`app.py`) + single-file frontend (`index.html` served as static).

**Request flow:**
1. Browser loads `index.html` (static), which calls `GET /api/quote`
2. `get_daily_quote()` checks TinyDB (`cache.json`) for today's date key
3. Cache miss → calls Anthropic API (`claude-haiku-4-5-20251001`) with a date-aware prompt requesting JSON `{reason, quote, author}`
4. On any Anthropic failure, falls back to `FALLBACK_QUOTES` (hardcoded list in `app.py`)
5. Result is cached in TinyDB and returned — one API call per day max

**Endpoints:**
- `GET /` — serves `index.html`
- `GET /api/quote` — JSON for the browser UI
- `GET /quote[?name=X]` — plain text for curl
- `GET /feed.xml` — RSS of last 30 cached days

**Storage:** TinyDB flat-file (`cache.json` locally, mounted as `./data` volume in Docker). One record per date.

**Frontend:** Vanilla JS in `index.html`. Fakes a terminal loading sequence, then fetches `/api/quote` and renders the result. Supports `?name=` query param and dark/light theme toggle (persisted in `localStorage`).

**Deployment:** Docker container on port 5000 (bound to `127.0.0.1` only), fronted by Nginx reverse proxy with rate limiting (10 req/min per IP on `/api/quote` and `/quote`).
