# SpaceHunter — Gradient Farming: Game Guide

This guide has two parts: **Part 1** (the game: entry, mining, tasks, referrals, bonuses) and **Part 2** (operations & internals: economy, payouts, admin panel, security, architecture, data model).

---

# Part 1 — The game

## What the game is

SpaceHunter, published as **Gradient Farming**, is a play-to-earn Telegram Mini App built around a single in-game currency, **CSM**. You run timed mining sessions to accrue CSM, complete auto-verified tasks for token payouts and permanent mining boosts, invite other players to earn a share of their yield, and spend what you earn on upgrades, the OG Pass, and arcade spins. Everything — mining, social layers, payouts — runs as a web app inside Telegram, so there is nothing to install.

## Getting in: @FARMGradientbot

The bot **@FARMGradientbot** (displayed name "Gradient Farming") is the front door.

- **Menu button.** The bot's chat menu button is labelled **Play** and deep-links straight into the game URL, so it is always one tap away once you have opened the chat.
- **/start and the Play button.** Sending `/start` returns a message with an inline **Play** button. Pressing it opens the game as a web app.
- **Invite deep links.** Referral invites use `?start=` deep links. The referrer is registered **server-side** when the invitee opens the link, which is why you should always join through a friend's link rather than navigating to the app cold.

The plain website link serves the application shell only. With authentication enabled, both play and admin functions happen inside Telegram — the browser tab is not a play surface.

## How to play

The in-game footer has three tabs: **Mining**, **Tasks**, **Me**.

### Mining (Mining tab)

Press **Start** to open a mining session. A session runs for **6 hours** by default (`MINING_SESSION_SECONDS=21600`); admins can tune the window between 1 and 72 hours. An optional captcha may appear on start. Come back when the session ends and **claim** it — CSM is credited at claim time, not continuously.

Your **hourly rate** is built from a stack of multipliers:

- A **base of 100 CSM/hour**.
- Your **boost multiplier**.
- A **referral bonus**: +5% per qualified referral, capped at 20% — that is, four referrals max out this term.
- Your **holdings-tier multiplier**.
- Your **OG Pass multiplier**, if you hold a pass.
- A **verified** multiplier.
- A **task and admin boost percentage** added together as `(1 + (task_boost_pct + admin_boost_pct)/100)`.

Two things follow from this. First, sessions already in flight keep the rate they started with — upgrades and boosts apply from your next session, so claim before buying. Second, the Mining tab shows a **live rate breakdown**, which is the quickest way to see which term is holding your rate back.

### Tasks (Tasks tab)

Tasks are the second income stream, and the only one that permanently raises your rate. Each task pays either **CSM tokens** or a **permanent mining-power multiplier**. All task boosts together are capped at **+100%**.

Every task is **auto-detected server-side** — no screenshots, no manual proof, no waiting on a reviewer. There are **9 starter tasks** to work through. Claiming is **atomic**: the claim gate re-checks `is_completed` inside the same `UPDATE` statement, so a race condition or double-tap cannot pay a task twice.

### Me (Me tab)

The Me tab is your account dashboard:

- **Profile** and a **stats grid** (your headline numbers at a glance).
- **Invite block** — your share link plus a list of your crew.
- **Withdraw form** and your **withdrawal history**.
- A **Recent payouts** feed, built from real in-game payout events rather than promotional placeholders.

## Referrals and tiers

### Instant bonuses and escrow

When someone registers through your link, **the invitee receives +50 CSM immediately** and **you receive +100 CSM**.

The invitee also receives a **+500 CSM escrow bonus**. It does not land at registration: it releases on their **first mining credit after their lifetime mined reaches 100 CSM**.

That qualification rule is deliberate. **Bonus and other credit payments never count toward lifetime mined** — the gate reads mining production only. Alt accounts cannot self-qualify by shuffling bonuses between themselves, and paid-out referral bonuses cannot be used to unlock the next referral bonus.

**Qualified** means exactly one thing: `lifetime_mined >= 100`.

### Tier-1 yield share

As an inviter you receive a share of each qualified crew member's mining yield. The band is set by **your own qualified crew size**:

| Qualified crew | Tier-1 yield share |
|---|---|
| ≤ 5 | 12% |
| ≤ 20 | 8% |
| ≤ 50 | 5% |
| ≤ 100 | 2% |
| > 100 | 0% |

Read the bands carefully: the percentage steps **down** as your crew grows. Small, quality crews earn the highest per-head share; very large crews earn nothing at Tier-1. Plan recruitment accordingly rather than chasing raw headcount.

### Tier-2 (friend-of-friend)

Your share continues one level deeper: **4%** of the yield mined by your referrals' referrals.

### Qualification bonus

You receive a **one-time +1,000 CSM** each time one of your referrals qualifies (lifetime mined reaches 100). This is separate from, and in addition to, your ongoing yield share.

### Milestones

**Referral-count milestones** pay rewards as your crew passes set thresholds.

A **10,000 CSM lifetime-mined milestone** pays the inviter **+2,500 CSM** and the invitee **+1,000 CSM**.

## OG Pass

The **OG Pass** costs **50,000 CSM** and lasts **30 days**. It adds its own multiplier to your mining rate for the duration, stacked with your other terms. If you were invited by someone, **your inviter earns a 15% commission** on your pass purchase — so a pass bought inside an active crew benefits both sides.

## Arcade

The Arcade holds two mini-games: a **spin wheel** and a **coin flip**. You get **3 free spins per day**, enforced server-side rather than by the client. Additional spins are paid for in CSM, drawn from a **bounded drop pool that cannot over-draw** — the pool's accounting is checked at spend time, so spins cannot be paid out beyond what the pool holds.

## Drops

**Drop windows** run on a schedule and pay **per-claim amounts from a fixed pool** — the pool is finite, and once it is exhausted the window pays nothing further. Admins can **force-start** a drop window early, but the start time is clamped to **at most 7 days ahead**, so no window can be queued indefinitely into the future.

## Daily bonus and streaks

Claim a **daily bonus** on a **10-day cycle**. Consecutive claim days build a **streak**, and the streak carries **milestone awards** at set points along the way. Missing a day resets the streak, so the value here is consistency rather than size.

## Welcome bonus

New players start with a **welcome bonus of 250 CSM**. The amount is admin-tunable, but 250 CSM is the default figure — enough to get moving without distorting the early game.

---

*Part 1 covers entry, mining, tasks, referrals, upgrades and bonuses. **See Part 2** for withdrawals and payout mechanics, the admin and configuration surface, and operational notes.*

---

# Part 2 — Operations & internals

This part covers the economy as shipped, the withdrawal and payout machinery, the admin panel, the security model that holds it together, the architecture and data model, and the day-to-day operational notes. Part 1 covers player-facing gameplay.

---

## 1. Economy reference

Every constant below is a **default**. The values are not compiled in: they live in the database and can be overridden from the admin panel's **Economy** tab without a redeploy.

| Constant | Default | Overridable | Notes |
|---|---|---|---|
| Base mining rate | 100 CSM/h | Yes — `econ_base_rate` | Baseline for an unboosted session |
| Session length | 6 h | Yes — `econ_session_hours` | In-flight sessions keep their stored terms |
| Welcome reward | 250 CSM | Yes — `econ_welcome_reward` | Credited once per account |
| Invitee instant bonus | +50 CSM | Yes | Paid to the invited player on registration |
| Inviter instant bonus | +100 CSM | Yes | Paid to the referrer on registration |
| Referral escrow | +500 CSM | Yes | Released once `lifetime_mined >= 100` |
| Referral qualification bonus | +1,000 CSM | Yes | To the inviter, on the invitee qualifying |
| Milestone 10k — inviter | +2,500 CSM | Yes | When the invitee reaches 10,000 lifetime mined |
| Milestone 10k — invitee | +1,000 CSM | Yes | Paired with the line above |
| OG Pass price | 50,000 CSM | Yes — `econ_og_cost` | — |
| OG Pass duration | 30 days | Yes | 30-day term from purchase |
| OG inviter commission | 15% | Yes | Share of the pass price to the inviter |
| Tier-1 referral rates | 12 / 8 / 5 / 2 / 0 % | Yes | By crew depth, first five levels |
| Tier-2 referral rate | 4% | Yes | Second-tier crew |
| Task boost cap | +100% | Yes | Ceiling on combined task multiplier |
| Verified wallet bonus | +10% | Yes | Applies to credits **and** mining |
| Arcade free spins | 3 / day | Yes | Reset daily |
| Withdrawal minimum | 1,000 CSM | Yes | Requests below this are refused |

**"Verified"** has a precise meaning: the player has a Telegram username set **and** a wallet connected. Both conditions, or the +10% does not apply. It is one flag, not two partial bonuses.

**Admin boosts** are a separate, orthogonal multiplier in the Players tab (see §3). They fold into the same rate breakdown that the base rate, task boost, and verified bonus feed, so a player's displayed rate is always the arithmetic product of the inputs they can see — no hidden factors.

### Admin overrides: how they behave

The four named override keys — `econ_base_rate`, `econ_session_hours`, `econ_og_cost`, `econ_welcome_reward` — plus the referral and arcade toggles are edited in the Economy tab and take effect on the next evaluation. The one carve-out is deliberate: **in-flight mining sessions keep the terms stored on the session row**, so changing `econ_base_rate` or `econ_session_hours` mid-session never retroactively re-prices a claim a player has already started. New sessions pick up the new values. This removes an entire class of "the rate changed while I was mining" disputes and race conditions.

---

## 2. Withdrawals and the admin payout flow

Withdrawals are the only path by which CSM leaves the ledger, and they are handled as a small state machine with escrow at the front and a human in the middle.

### Player side

The player calls `POST /withdraw/request` with an amount and a TON wallet address. The request is rejected unless the amount is **at least 1,000 CSM** and the address is well-formed. On acceptance, **the amount is debited into escrow at request time** — not at approval, not at payout. The balance is gone from the spendable ledger the moment the request exists. This is the single most important design decision in the flow: a player cannot request two withdrawals against the same balance, because the first request already removed the funds.

### Admin side — the Payouts queue

The request lands in the **Payouts** tab as pending. Three transitions are available:

| Action | Result | Escrow | Guard |
|---|---|---|---|
| **Approve** | Status → `approved` | Held | Status flip must be pending → approved |
| **Reject** | Status → `rejected` | Refunded **exactly once** | Guarded status flip |
| **Mark paid** | Status → `paid` | Held, now settled | Requires a transaction hash or link |

**Reject** performs a guarded status flip, and only the winning flip triggers the escrow refund. Two concurrent rejects — a double-clicked button, a retried request, two admins racing — resolve to one refund, because the second flip matches zero rows and therefore issues no credit. There is no separate "refund" button that could be pressed twice; the refund is a side effect of a transition that can only happen once.

**Mark paid** will not proceed without a **transaction hash or link**. That hash is what makes the payout auditable and what feeds the proof post.

### Proofs and the daily digest

On mark-paid, a **real** payout proof is posted to the configured proofs channel: the amount, the wallet address **masked**, and a tonviewer link for the transaction. Alongside the per-payout posts, a **daily digest** reports real paid totals for the period, at the digest hour set in the Comms tab. Both the proof feed and the digest are driven by actual events and actual rows — see the no-fake-proofs rule in §4.

### Exact-once guarantees

The flow is built so that each economic event happens once and only once:

- Escrow debit happens at request time, so the same funds cannot back two requests.
- Refund is bound to a guarded transition, so concurrent double-reject refunds once.
- Approval and mark-paid each carry their own guarded transitions, so a payout cannot be advanced twice or double-settled.
- **Double-pay guards are applied on every transition**, not just the refund path.

These properties were verified by live race and double-pay exploit probes, which were re-run and confirmed to produce exact-once payouts.

---

## 3. The admin panel

The panel has **seven tabs** and requires an **owner-signed Telegram identity**: the caller's verified signer must be on the owner allowlist (§4). Everyone else gets 403 regardless of what the frontend renders.

### Overview

Totals and stats: the operational dashboard. Player counts, mined totals, payout position — the state of the system at a glance before you touch anything.

### Players

Search a player, then act on them:

- **Set level**, bounded **1..100**.
- **Grant boost**, bounded **−90% .. +500%**. The boost folds into the player's rate breakdown, so the effect is visible to the player rather than a silent multiplier.
- **Grant referral bonus** — writes a ledger entry with `kind=admin_grant`, keeping manual credits distinguishable from earned ones.
- **Set referrer** — cycle-guarded, so an admin cannot build a referral loop that would pay commissions to itself forever.
- **Ban / unban** with a reason. Banned users' signed calls return **403 "Account suspended"**. **Admins cannot be banned** — the check runs before the write.

### Payouts

The withdrawals queue described in §2: approve, reject-with-escrow-refund, mark-paid with transaction hash.

### Tasks

Create, patch, and hide tasks. Bounds: **reward ≤ 100,000**, **multiplier ≤ 100%**, and the **condition must be on the allowlist** — a task cannot carry an arbitrary condition expression, only a recognised type.

### Economy

The override and toggle surface from §1: `econ_base_rate`, `econ_session_hours`, `econ_og_cost`, `econ_welcome_reward`, plus the referrals and arcade toggles. In-flight sessions keep their stored terms.

### Comms

- **Broadcast** to all players — HTML-escaped and paced so a large send does not hammer Telegram.
- **Announcement banner** text.
- **Proofs channel** configuration and the realtime toggle.
- **Digest hour** for the daily paid-totals digest.

### Controls

- Settings.
- **Drop force key / until** — the scheduled drop control.
- **Audit CSV export**, with formula-injection guarding on exported cells.

**Every admin action is logged to the audit trail.** There is no unlogged admin write.

---

## 4. Security model

The threat model assumes a hostile client: the mini app is JavaScript the user controls, so nothing that arrives from it is trusted until it has been tied to a Telegram-signed identity.

### initData HMAC authentication

On every `/api` request, when `SPACEHUNTER_AUTH=on`, the Telegram WebApp `initData` is verified using the **official WebApp HMAC scheme**. This has been live since October 2025.

The verification is strict about *who* is speaking:

- **The claimed `admin_id` / `telegram_id` must BE the verified signer.** Supplying someone else's ID does not escalate you; it fails.
- Parsing is strict, and the check covers **all occurrences in both query and body** — a second copy of the field elsewhere in the request cannot smuggle a different identity past the check.
- The implementation is **encoding-gap safe**: parameters that could be interpreted differently by different parsers do not create a bypass.

### Authorisation and credentials

- **Owner allowlist** — `SPACEHUNTER_ADMIN_IDS` in `backend/.env`. Admin panel access requires a verified signer in this list.
- **Scoped bot token** — the bot authenticates with `X-Bot-Token`, a scoped server credential valid **only** for `POST /api/users/register` and `POST /api/users/register_with_referral`. It grants nothing else. A leak of that header cannot read balances, request withdrawals, or reach the admin surface.

### Data-integrity controls

- **SQLite in WAL mode with `busy_timeout`** — concurrent readers and a writer without spurious lock errors.
- **Every credit path is an atomic guarded SQL `UPDATE`**, not read-modify-write. This covers withdrawal, mining claim, welcome, task claim, OG, boost, arcade, escrow, and milestones. The guard is in the `WHERE` clause, so the database arbitrates races rather than the application.
- **UNIQUE guards** make duplicate economic rows impossible at the schema level:
- `mining_sessions(user_id) WHERE claimed=0` (partial unique index: one open mining session per user)
- `UNIQUE user_tasks(user_id, task_id)` — a task can be claimed once by a user
- `ux_user_boost UNIQUE(user_id, boost_id)` — one row per user/boost pair, so boost purchase is idempotent
- `uq_daily_claim_user_date UNIQUE(user_id, claim_date)` — one daily claim per user per day

These are schema-level guards, not application checks. Two concurrent requests that both pass the same in-code validation still collide at the index, so double-claiming, double-mining and duplicate boost purchases are impossible by construction rather than by careful ordering. The application treats the resulting `IntegrityError` as "already done" and returns the existing state instead of a 5xx.

### 4.2 No-fake-proofs policy

Payout proofs, the "Recent payouts" feed and the daily digest render **real payout events and rows only** — actual `withdrawal_requests` entries with their status, `tx_hash` and `paid_at`. Nothing in that surface is generated, templated or staged.

Fabricated withdrawal-proof content was proposed during development and declined. The shipped feed is honest real-data; where there is nothing to show, the surface is empty rather than padded. This is a standing constraint on any future change to the feed: a payout is shown because it exists in the database, not because the layout looks better with something in it.

## 5. Architecture & data model

### 5.1 Components

| Layer | Location | Responsibility |
|---|---|---|
| API | `backend/app/` | FastAPI application; all business endpoints |
| Routers | `backend/app/api/` | `users`, `boosts`, `game`, `tasks`, `rating`, `nft`, `bonus`, `wallet`, `mining`, `ogpass`, `withdraw`, `admin`, `admin_ext` (full admin panel API), `features` (arcade / button / drops) |
| Services | `backend/app/services/` | `p2e` (referral and mining core), `auth` (Telegram initData HMAC verification), `bonus`, `task_checker` |
| CRUD | `backend/app/crud/` | Data-access layer; the only place that talks to the database |
| Background tasks | in-process | `passive_income`, energy restore |
| Mini App | `frontend/src/` | React + Vite + TypeScript Telegram Mini App |
| Bot | `bot_runner.py` | `/start` with a web_app Play button, chat menu button Play, server-side referral registration from `?start=` payloads |
| Contracts | `SmartContracts/` | TON smart contracts in FunC: jetton minter and wallet, NFT collection and item |
| Database | `demo.db` | SQLite in WAL mode with `busy_timeout` set so writers queue instead of failing |

Request flow: Mini App → router → service → CRUD → SQLite. Every authenticated call passes through the `auth` service, which validates initData with the bot token's HMAC before any user row is read or written.

### 5.2 Serving

`demo_serve.py` mounts `frontend/dist` as `StaticFiles` at `/SpaceHunter` on the same uvicorn process and port (`:8000`) that serves the API. One origin, so there is no CORS configuration and no separate front-end host to keep in sync.

`SPAStaticFiles` falls back to `index.html` for extensionless paths, so client-side deep links resolve on a hard refresh instead of 404ing.

### 5.3 Migrations (in order)

| # | Step | Purpose |
|---|---|---|
| 1 | `backend/alembic/versions` | Base schema and incremental revisions |
| 2 | `backend/scripts/migrate_security_fixes.py` | Security-related constraints and columns |
| 3 | `backend/scripts/migrate_boost_unique.py` | `ux_user_boost` |
| 4 | `backend/scripts/migrate_admin_panel.py` | Admin panel tables and fields |

All four run from `game-runners/restart-all.sh`, which rebuilds the stack; they are not applied by hand.

### 5.4 Key tables

`users`

| Column | Notes |
|---|---|
| `telegram_id` | Telegram identity |
| `referred_by_id` | Referrer link |
| `lifetime_mined`, `lifetime_earned` | Cumulative counters |
| `pending_invite_bonus`, `qual_bonus_paid` | Invite bonus state |
| `ref_milestone_paid`, `referral_milestones_claimed`, `streak_milestones_claimed` | Milestone bookkeeping |
| `banned`, `ban_reason` | Moderation |
| `og_pass_expires_at` | OG pass expiry |

`game_states` — one row per user, `user_id` is the primary key: `balance`, `boost_multiplier`, `task_boost_pct`, `admin_boost_pct`, `passive_income`.

Supporting tables:

| Table | Purpose |
|---|---|
| `mining_sessions` | Individual mining runs; `claimed` marks a closed session |
| `boosts`, `user_boosts` | Boost catalogue and per-user holdings |
| `tasks`, `user_tasks` | Task catalogue and per-user completion |
| `daily_claims` | Daily claim log |
| `withdrawal_requests` | Payouts; `status` is `pending` / `approved` / `rejected` / `paid`, with `tx_hash` and `paid_at` |
| `referral_earnings` | Ledger of referral payouts |
| `admin_actions` | Audit trail of admin operations |
| `daily_bonus`, `user_daily_bonus` | Bonus definition and per-user claim state |

## 6. Operational notes

### 6.1 Tunnel expiry

The free pinggy tunnel expires after roughly 60 minutes. When it dies the public URL changes, and anything that hard-coded the old URL stops working. Two things must be refreshed after each restart:

- `.game-url` — the file the stack and tooling read the current public URL from
- the bot's menu button — otherwise Play still opens the dead host

The durable fix is stable hosting with a domain, which removes both refresh steps. Until then, treat the URL as ephemeral.

### 6.2 Auth enabled

With `SPACEHUNTER_AUTH=on`, the plain website link serves the shell only — the API rejects unauthenticated calls, so there is nothing to play and nothing to administer outside Telegram. Play and admin both happen inside Telegram, where initData is available. Use the bot entry point rather than a browser tab when testing anything behind auth.

### 6.3 Rebuild path

`game-runners/restart-all.sh` is the single way to bring the stack up: it applies the migrations in the order given in §5.3 and restarts the services. Prefer it over restarting uvicorn alone, which leaves schema changes unapplied and produces confusing failures in the CRUD layer.

### 6.4 Open item: BotFather `/newapp`

BotFather `/newapp` registration is still open. Completing it enables one-tap invite attribution via `?startapp=`, which is more reliable than the `?start=` payload path used today because attribution survives the Mini App launch without a server round trip. Until it is registered, server-side referral registration from `?start=` payloads in `bot_runner.py` remains the working mechanism.
