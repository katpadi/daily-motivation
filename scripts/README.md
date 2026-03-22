# Maintenance Scripts

## repopulate_cache.py

Re-fetches quotes from the Anthropic API for specific dates and overwrites the existing TinyDB cache entries. Useful after a prompt change or when you want to regenerate content for specific dates.

### Usage

Copy the script into the running container, then run it:

```bash
# 1. Copy script into container
docker compose cp scripts/repopulate_cache.py daily-motivation:/app/repopulate_cache.py

# 2. Run for one or more dates
docker compose exec daily-motivation python repopulate_cache.py <date1> [date2 ...]
```

**Examples:**

```bash
# Single date
docker compose exec daily-motivation python repopulate_cache.py 2026-03-22

# Multiple dates
docker compose exec daily-motivation python repopulate_cache.py 2026-03-21 2026-03-22
```

### After running

Restart the container so TinyDB picks up the updated cache file:

```bash
docker compose restart
```

### Notes

- Dates must be in `YYYY-MM-DD` format
- If an entry for the date already exists, it will be removed and replaced
- Falls back to nothing on API error — check output for any exceptions
