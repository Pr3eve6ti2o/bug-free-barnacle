# SpaceHunter (Gradient Farming)

A play-to-earn Telegram Mini App where players farm CSM (in-game coins) — FastAPI backend, React + TypeScript frontend, a Telegram bot entry point, and TON smart contracts in FunC.

## Features

**Player**
- Full game loop inside Telegram as a Mini App; play state and balances are server-authoritative.
- Entry via the bot `@FARMGradientbot` ("Gradient Farming"): `/start` returns an inline **Play** button that opens the game as a `web_app`, and the chat menu button (**Play**) deep-links straight to the game URL.
- Referral invites use `?start=` deep links, registered server-side at the moment the payload is received.
- On-chain assets on TON: jetton (CSM) and NFT collection/item contracts.

**Admin**
- Admin surface gated behind configured Telegram admin IDs.
- One-off migration script provisions the admin panel schema.

**Security**
- Optional authentication layer (`SPACEHUNTER_AUTH`) — when enabled, the game refuses unauthenticated play.
- Server-side referral registration; no client-trusted identity.
- Payout paths verified exact-once: live race and double-pay exploit probes re-confirmed no duplicate payouts.
- Dedicated security-fix migration for hardening existing data.
- Single-origin serving — the frontend is mounted on the same uvicorn process as the API, so no CORS surface is exposed.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python), SQLite in WAL mode (`demo.db`) |
| Frontend | React + Vite + TypeScript |
| Bot | `bot_runner.py` (Telegram Bot API) |
| Contracts | FunC — jetton minter/wallet, NFT collection/item |
| Serving | `demo_serve.py` — uvicorn on `:8000`, API plus `frontend/dist` mounted as StaticFiles at `/SpaceHunter` |
| Migrations | Alembic (`backend/alembic/`) plus one-off Python scripts |

## Prerequisites

- Python 3 with a virtualenv at `~/workspace/spacehunter-demo/venv`
- Node.js with `npm` / `npx` available on `PATH`
- A Telegram bot token and the TON API endpoint for your network
- Optional: a tunnel client (pinggy) if you need public access

## Installation

```bash
git clone <repo-url> ~/workspace/spacehunter-demo
cd ~/workspace/spacehunter-demo

python3 -m venv venv
./venv/bin/pip install -r backend/requirements.txt

cd frontend && npm install && cd ..
```

Create `backend/.env` and populate the keys listed under [Configuration](#configuration). Do not commit it.

## Configuration

All keys live in `backend/.env` unless noted. Names only — supply your own values.

| Name | Location | Purpose |
|---|---|---|
| `DATABASE_URL` | `backend/.env` | SQLite connection string for `demo.db` |
| `SECRET_KEY` | `backend/.env` | Application signing secret |
| `SPACEHUNTER_ADMIN_IDS` | `backend/.env` | Telegram IDs granted admin access |
| `SPACEHUNTER_AUTH` | `backend/.env` | Toggles the authentication layer |
| `TELEGRAM_BOT_TOKEN` | `backend/.env` | Bot credentials used by the backend |
| `TON_API_ENDPOINT` | `backend/.env` | TON API base endpoint |
| `.bot-token` | repo root | Token file for `@FARMGradientbot` |
| `.game-url` | repo root | Current public tunnel URL, read and pushed to the bot menu button |

Frontend build-time configuration is passed on the command line rather than a file — see [How to run](#how-to-run). The mock Telegram environment used for the browser demo path is DEV-gated and is not active in a production build.

## Database migrations

Apply in this order. `game-runners/restart-all.sh` runs the whole sequence as part of rebuilding the stack, so a stack restart is normally all you need.

1. **Alembic versions** — `backend/alembic/`, brought up to date with Alembic's upgrade command.
2. **`backend/migrate_security_fixes.py`** — security hardening.
3. **`backend/migrate_boost_unique.py`** — boost uniqueness constraints.
4. **`backend/migrate_admin_panel.py`** — admin panel schema.

The three scripts are one-off and idempotent-safe to re-run via the restart script; do not reorder them, as later steps assume the schema left by earlier ones.

## How to run

**Backend + frontend (single origin)**

```bash
cd ~/workspace/spacehunter-demo
./venv/bin/uvicorn demo_serve:app --host 127.0.0.1 --port 8000
```

`demo_serve.py` serves the API and mounts `frontend/dist` at `/SpaceHunter`, with SPA fallback so deep links resolve. One process, one port, no CORS.

**Frontend build**

```bash
cd frontend
NODE_ENV=development VITE_API_URL= npx vite build
```

Rebuild and restart the backend whenever frontend sources change, since `dist` is served statically.

**Telegram bot**

```bash
python bot_runner.py
```

The bot answers `/start` with the **Play** `web_app` button, exposes **Play** as the chat menu button, and registers referral payloads server-side.

**Optional: public tunnel**

Expose `:8000` through a free pinggy tunnel, then write the resulting URL to `.game-url` and refresh the bot menu button:

```bash
# start the tunnel, capture its public URL, then:
echo "<public-url>" > .game-url
```

**Full stack rebuild**

```bash
game-runners/restart-all.sh
```

## Testing and verification

- Backend test battery: green.
- Browser QA: 7/7 pass.
- Auth tests: 14/14.
- Live race and double-pay exploit probes: re-verified exact-once payouts.
- Golden-battery numbers hold exactly — combo 850, golden battery +800 / +1036. Any deviation indicates a regression in payout logic.

## Project structure

```
spacehunter-demo/
├── backend/
│   ├── app/                     FastAPI application
│   ├── alembic/                 schema migrations (versions/)
│   ├── migrate_security_fixes.py
│   ├── migrate_boost_unique.py
│   ├── migrate_admin_panel.py
│   └── .env                     local config, not committed
├── frontend/
│   ├── src/                     React + TypeScript Mini App
│   └── dist/                    build output, served as StaticFiles
├── SmartContracts/              FunC jetton + NFT contracts
├── game-runners/
│   └── restart-all.sh           rebuilds the stack, runs migrations
├── demo_serve.py                uvicorn entrypoint (API + static frontend)
├── bot_runner.py                Telegram bot
├── demo.db                      SQLite database (WAL)
├── .bot-token
└── .game-url
```

## Operational notes

**Free-tunnel expiry.** The pinggy tunnel used for public access expires after roughly 60 minutes. When it does, the URL changes, so the bot menu button and `.game-url` go stale and the Mini App stops opening. Restart the tunnel, write the new URL to `.game-url`, and re-push it to the bot's menu button. Long-term the correct fix is stable hosting behind a domain rather than a rotating tunnel.

**Auth ON consequence.** With authentication enabled, the plain website link serves the application shell only — it renders but cannot play. All play and all admin activity happen inside Telegram, where the Mini App carries a verified identity. Testers hitting the bare URL and seeing an inert shell are seeing expected behaviour, not a bug.