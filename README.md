# SpaceHunter (Gradient Farming)

A play-to-earn Telegram Mini App where players farm CSM (in-game coins) — FastAPI backend, React + TypeScript frontend, a Telegram bot entry point, and TON smart contracts in FunC.

## Features

**Player**
- Full game loop inside Telegram as a Mini App; play state and balances are server-authoritative.
- Entry via the bot `@FARMGradientbot` ("Gradient Farming"): `/start` returns an inline **Play** button that opens the game as a `web_app`, and the chat menu button (**Play**) deep-links straight to the game URL.
- Referral invites use `?start=` deep links, registered server-side at the moment the payload is received.
- On-chain assets on TON: jetton (CSM) and NFT collection/item contracts.

**Admin**
- Admin panel at `/SpaceHunter/admin` (Overview, Players, Withdrawals, Tasks, Economy, Comms, Controls), gated behind configured Telegram admin IDs.
- Withdrawal queue with escrow debit at request and a double-pay guard; payouts are settled manually and marked paid with a transaction hash.
- One-click Excel export (`GET /api/admin/export.xlsx`, admin-only): a formatted five-sheet workbook — Summary, Players, Withdrawals, Referral Ledger, Admin Actions.
- One-off scripts in `backend/scripts/` provision the schema and constraints.

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

- Python 3.12 (a virtualenv is created in the repo as `./venv`)
- Node.js 20+ with `npm` / `npx` available on `PATH`
- A Telegram bot token (BotFather) for the Mini App entry point
- Optional: a tunnel client (pinggy) if you need public access without a domain

## Installation

```bash
git clone https://github.com/Pr3eve6ti2o/bug-free-barnacle.git spacehunter
cd spacehunter

python3 -m venv venv
./venv/bin/pip install -r backend/requirements.txt

cd frontend && npm install && cd ..
```

Create `backend/.env` from the template and populate the keys listed under [Configuration](#configuration). Do not commit it.

```bash
cp backend/.env.example backend/.env   # then edit in your values
```

Then build the database (next section) and the frontend bundle:

```bash
cd frontend && NODE_ENV=development VITE_API_URL= npx vite build && cd ..
```

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

## Database setup and migrations

The application does not create its schema at startup. On a fresh clone, build it in this order (all commands from the repo root, using the project venv):

```bash
./venv/bin/python backend/scripts/create_feature_tables.py   # feature tables (arcade, drops, admin, referrals)
./venv/bin/python backend/scripts/migrate_security_fixes.py  # security hardening constraints
./venv/bin/python backend/scripts/migrate_boost_unique.py    # ux_user_boost uniqueness
./venv/bin/python backend/scripts/migrate_admin_panel.py     # admin panel schema
./venv/bin/python backend/scripts/migrate_referral_unique.py # uq_referral_oneshot partial index
./venv/bin/python backend/scripts/reseed_tasks_v2.py         # the 9 starter tasks (Tasks v2)
```

The scripts live in `backend/scripts/`, are one-off and idempotent — safe to re-run; do not reorder them, as later steps assume the schema left by earlier ones. Historical Alembic versions are kept under `backend/alembic/` for reference; the scripts above are the supported path for this build. The operator restart script (`game-runners/restart-all.sh`, outside the repo) re-runs the four migrations on every stack rebuild.

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
│   ├── scripts/                 one-off setup + migration scripts (see Database setup)
│   ├── requirements.txt         pinned backend dependencies
│   ├── .env.example             configuration template (copy to .env)
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