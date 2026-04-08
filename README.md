# Homegate Triage Assistant

Local-first personal tooling for your Zurich relocation search. It ingests Homegate search alert emails, enriches listings best-effort with Playwright, scores deterministic factors, uses `gpt-5.4` only for ambiguous factors, and gives you a small inbox UI for `inspect / ignore / contact`.

## Stack

- `uv` for Python environment and dependency management
- `Taskfile.yml` for common workflows
- SQLite for local persistence
- IMAP for Homegate alert ingestion
- Playwright with a persistent Chrome profile for best-effort extraction
- FastAPI for the local inbox webpage

## Setup

1. Put `OPENAI_API_KEY` in `.env`.
2. Add IMAP credentials to `.env` if you want live mailbox ingestion:
   - `IMAP_HOST`
   - `IMAP_PORT`
   - `IMAP_USERNAME`
   - `IMAP_PASSWORD`
3. Adjust [config.toml](/Users/mert/dev/personal/zurich-home-search/config.toml) if needed.
4. Create the Homegate instant search alert for Zurich rentals under CHF 1,800.
5. Make sure your local Chrome profile can access Homegate without getting stuck on Cloudflare verification. The extractor uses a disposable copy of that profile under `data/chrome-profile-copy`.

## Commands

- `task setup`
- `task imap-check`
- `task gmail-auth`
- `task gmail-check`
- `task run`
- `task triage-once`
- `task rescore`
- `task test`

## Notes

- V1 treats Homegate alert emails as the source of truth for new listings.
- Browser extraction is best-effort. If Homegate blocks the browser session, the listing is still stored and routed toward inspection with lower confidence.
- If `GOOGLE_CLIENT_ID` is set, the app can use Gmail API access instead of IMAP after `task gmail-auth`.
- The inbox is available at `http://127.0.0.1:8000` by default.
