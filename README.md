# daily-motivation

Just me playing around with the Anthropic API. Every day it generates a motivational quote tied to something that happened in history on that date.

## What it does

Hits the Anthropic API once a day (claude-haiku), asks it for a notable historical event and a relevant motivational quote, caches the result, and serves it through a simple terminal-styled web UI.

## Stack

- **Python / Flask** — tiny backend, a couple of routes
- **Anthropic API** — the brains, using `claude-haiku-4-5-20251001`
- **TinyDB** — flat-file JSON cache so the API only gets called once per day
- **Docker** — containerised with gunicorn
- **Nginx** — reverse proxy for production

## Running it

Copy `.env.example` to `.env` and fill in your values:

```
ANTHROPIC_API_KEY=your_key_from_console.anthropic.com
SITE_URL=https://motivation.yoursite.com
SITE_TITLE=Daily Motivation
SITE_DESC=A daily motivational quote tied to today in history.
DEFAULT_NAME=Kat  # your name — shows in the greeting
```

Then:

```bash
docker compose up -d --build
```

App runs on `http://localhost:5000`.

## Deploying

On your server:

```bash
git clone git@github.com:katpadi/daily-motivation.git
cd daily-motivation
cp .env.example .env
nano .env
docker compose up -d --build
```

To update:

```bash
cd ~/daily-motivation
git pull
docker compose up -d --build
```

**Nginx** — copy `nginx.conf` to `/etc/nginx/sites-available/`, symlink it, reload:

```bash
sudo cp nginx.conf /etc/nginx/sites-available/daily-motivation
sudo ln -s /etc/nginx/sites-available/daily-motivation /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**SSL:**

```bash
sudo certbot --nginx -d motivation.yoursite.com
```

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /` | Browser UI |
| `GET /api/motivation` | JSON response |

## Logs

```bash
docker compose logs -f
```
