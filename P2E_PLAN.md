# SpaceHunter — Play-2-Earn Feature Plan

Inspiration: @ATF_AIRDROP_bot (timed mining sessions, anti-bot captcha, withdrawals, KYC-gated boosts)
and @catsgang_bot (instant welcome reward, daily streaks, promo codes, referral tiers, OG Pass, seasons).
Scope: demo clone at `~/workspace/spacehunter-demo/`. Backend (FastAPI + SQLAlchemy) and frontend
(React + TS + Tailwind, sleek-minimal dark theme #06070c / gold #f5c518, en-GB). Nothing is pushed anywhere.

## Design principles
- Every new feature plugs into the existing game loop; no existing flow is removed or renamed.
- All numbers are balanced for a demo economy (documented below); rates are server-side and changeable.
- Mobile-first; every section verified at 360 / 390 / 768 px. Container max-width 480px centred.
  Touch targets ≥ 44px. No horizontal overflow at any width.
- English only, en-GB spelling.

## F1 — Mining sessions (ATF-inspired)
- User starts a mining session: 3 hours, one active session at a time.
- **ATF-style rate algorithm** (2026-10-13 revision — user ordered ATF's "refer more or hold more" model):
  `rate = 100 CSM/h × boost_multiplier × (1 + 5% × qualified_referrals, cap 20) × holdings_tier × OG(×2) × verified(×1.1)`
  - qualified_referrals = referrals with lifetime_earned ≥ 100 (anti-farmed)
  - holdings_tier: ≥1k CSM → ×1.10; ≥10k → ×1.25; ≥50k → ×1.60; ≥200k → ×2.20
  - `GET /api/mining/status` and `POST /api/mining/start` return the rate `breakdown`
    so the UI shows exactly what drives the rate (referral %, holdings tier, OG, verified).
- On expiry the session becomes claimable and stays claimable (no expiry pressure).
- Claiming a finished session is required before starting a new one.
- Anti-bot: server issues a simple arithmetic challenge (e.g. "8 + 5 = ?") when starting;
  the answer must be correct and the challenge unexpired (5 min TTL). Wrong/expired → 400.
- Backend: `MiningSession` (id, user_id, started_at, ends_at, hourly_rate, claimed, claimed_at).
  - `POST /api/mining/challenge` → {challenge_id, question}
  - `POST /api/mining/start` {telegram_id, challenge_id, answer} → session or 400
  - `GET /api/mining/status/{telegram_id}` → {active|claimable|none, ends_at, accrued_estimate}
  - `POST /api/mining/claim` {telegram_id} → {claimed_amount, new_balance}
- Frontend: mining card on FlyPage below the energy bar — live countdown, accrued estimate
  ticking, "Claim" gold button when ready, "Start mining" otherwise (opens challenge inline).

## F2 — Daily streaks (CATS-inspired, extends existing 10-day bonus)
- Keep the existing 10-day bonus config/amounts; add streak tracking on top.
- `DailyClaim` records each claim; streak = consecutive calendar days (UTC).
- Streak milestones: 7 days → +1,000 CSM; 30 days → +10,000 CSM; 100 days → +50,000 CSM,
  auto-credited with a celebratory modal.
- Missing a day resets the streak to 1 (shown clearly before it happens: "claim within HH:MM").
- Backend: `DailyClaim` (user_id, claimed_at); extend `GET /api/bonus/daily/status/{telegram_id}`
  with {streak, next_milestone, next_milestone_in_days, resets_in_seconds}.
- Frontend: bonus modal shows flame + streak count + milestone progress bar.

## F3 — Promo codes (CATS-inspired)
- Redeemable codes granting CSM. Seeded: WELCOME100 → 100 CSM (1 use per user),
  MINER500 → 500 CSM (first 1,000 users), GOLD1000 → 1,000 CSM (expires in 30 days).
- One redemption per user per code. Server validates: exists, active, not expired,
  under max uses, not already redeemed by this user.
- Backend: `PromoCode` (id, code unique, reward, max_uses, uses, expires_at, active),
  `PromoRedemption` (user_id, code_id, redeemed_at).
  - `POST /api/promo/redeem` {telegram_id, code} → {reward, new_balance} or 400 with reason.
- Frontend: redeem card in Tasks tab (input + button, uppercase transform, clear error text).

## F4 — Referral tiers (ATF + CATS)
- Keep existing invite link flow. Add:
  - Ongoing: referrer earns 5% of each referral's mined CSM (taps + mining claims +
    passive income), credited automatically with a feed line in Me tab.
  - Milestones: 5 invites → 500 CSM; 25 → 5,000 CSM; 100 → 25,000 CSM (auto-credited once each).
- Anti-fraud: self-referral blocked (already), milestone requires referred users to have
  earned ≥ 100 CSM lifetime — tracked via a new `lifetime_earned` counter on the user
  (incremented on every earning event, never decremented by spends).
- Implementation hooks: the 5% credit must fire in three places — tap rewards
  (`POST /api/game/click`), mining claims (`POST /api/mining/claim`), and passive income
  application. Same three hooks apply the F9 verified +10%.
- Backend: `referral_earnings` on user stats; milestone flags; extend
  `GET /api/users/referrals/{telegram_id}` with {count, earnings_total, milestones}.
- Frontend: Me tab — earnings row, milestone progress bars (5/25/100).

## F5 — OG Pass (CATS-inspired)
- Purchasable with CSM: 50,000 CSM → 30 days. Benefits: 2× mining session rate,
  gold "OG" badge on profile/leaderboard, +10 max energy (110).
- One active pass at a time; repurchase extends from expiry (not from now).
- Backend: `og_pass_expires_at` on user; `POST /api/ogpass/purchase` {telegram_id}
  → {expires_at} or 400 (insufficient balance). `GET /api/ogpass/status/{telegram_id}`.
  Energy endpoints must read max energy dynamically (100 base, 110 with active OG pass)
  instead of the current hardcoded 100.
- Frontend: OG card in Boost tab (price, benefits list, buy button, countdown when active).

## F6 — Global leaderboard
- `GET /api/rating/global?limit=50` → [{rank, username, balance, level, og_badge}].
  Cached 60s server-side (simple in-memory TTL) to protect the DB.
- Frontend: Me tab gets segmented Friends / Global control; global rows show rank,
  name, balance, level pill, OG badge. Current user highlighted if in top 50.

## F7 — Welcome bonus (CATS-inspired instant gratification)
- First app open: celebratory bottom-sheet granting 250 CSM, one tap to claim.
- Backend: `welcome_claimed` flag; `POST /api/bonus/welcome/{telegram_id}` (idempotent).
- Frontend: FlyPage checks on mount; modal with coin burst styling, "Claim 250 CSM".

## F8 — Withdrawal requests (ATF-inspired, demo rails)
- Minimum 1,000 CSM. User enters TON address (basic format validation: 48 chars,
  starts with EQ/UQ/kQ/0Q). Balance is debited immediately into escrow;
  request status starts `pending` (demo: stays pending — settlement is out of scope).
- Backend: `WithdrawalRequest` (id, user_id, amount, address, status, created_at).
  - `POST /api/withdraw/request` {telegram_id, amount, address} → request or 400
  - `GET /api/withdraw/history/{telegram_id}` → list.
- Frontend: Drop tab — withdrawal card under the wallet section: amount input,
  address input, request button, history list with status pills. Copy warns:
  "Demo build — requests are recorded, settlement is manual."

## F9 — Verified profile boost (ATF-inspired)
- Complete both: (a) Telegram username set, (b) wallet connected → permanent +10% on
  tap rewards and mining rate. Shown as a checklist in Me tab with the active boost.
- Backend: computed in rate/reward calculation from user record + wallet status.
  No new endpoints (uses existing user/wallet reads).

## F10 — Terms & Conditions (simple but proper for P2E)
- Full T&C document covering: 1) The game & eligibility (18+, one account per person,
  Telegram required); 2) CSM points (in-game only, no monetary value, not an investment
  or security); 3) Earning & rates (rates may change; rewards not guaranteed);
  4) Fair play (no bots/scripts/multi-accounts/exploits — violations forfeit earnings
  and ban); 5) Referrals (genuine invites only; farmed referrals don't count);
  6) Mining sessions & streaks (rules, reset policy); 7) OG Pass (duration, non-refundable
  in CSM); 8) Withdrawals (minimums, review, timing not guaranteed, demo settlement);
  9) Changes & termination; 10) Liability (no investment advice, as-is);
  11) Privacy (Telegram profile data + game data only); 12) Contact.
- Stored as `src/data/terms.ts` (versioned: `TERMS_VERSION = 1`).
- First-open consent: modal with 6-line plain-English summary + "I agree" →
  `POST /api/users/consent` {telegram_id, terms_version}. The game UI stays locked
  behind a non-dismissible modal until accepted; declining shows a locked screen
  with a "Read terms" button to reopen it (no gameplay without consent).
- Re-acceptance: if TERMS_VERSION bumps, consent modal shows again on next open.
- Always accessible: help (?) modal → "Terms & Conditions" opens full reader.

## Responsive requirements (applies to every section, old and new)
- Breakpoints verified: 360px, 390px, 768px (browser task screenshots at each).
- App column max-width 480px centred; cards full-bleed within it.
- Grids: boost cards 2-col ≥360px, 3-col ≥768px; leaderboard rows single-col always.
- Touch targets ≥44px; tap zone ≥200px. No horizontal scroll; long addresses truncate
  with ellipsis. Modals are bottom-sheets on mobile, centred dialogs ≥768px.
- Numbers use tabular-nums; no layout shift when counters tick (fixed-width containers).

## Backend implementation notes
- New models in `backend/app/models/`; tables via `Base.metadata.create_all`
  (no alembic in repo). SQLite-compatible types only (no PG-specific DDL —
  `seed_daily.py`'s TRUNCATE precedent).
- Idempotency: claim/redeem/purchase endpoints must be safe to retry
  (unique constraints + pre-checks, not just try/except).
- Challenge answers: never trust client math — challenge stored server-side with TTL.
- All new endpoints under existing `/api` prefix; response shapes documented in plan.

## Out of scope (Phase 2, noted not built)
- Seasons with snapshot/reset; on-chain token mint/claim; admin panel for promo codes
  (seed via script); real captcha service; TON transaction settlement for withdrawals.

## Acceptance
- `npx tsc --noEmit` clean; `NODE_ENV=development VITE_API_URL= npx vite build` succeeds.
- All new endpoints exercised via curl against the demo backend.
- Browser-task screenshots at 360/390/768px: every tab renders, no overflow, no overlap.
