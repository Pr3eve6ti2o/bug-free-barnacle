# SpaceHunter v2 — Deep Game Plan

*Built from: a DeepSeek deep-study (16 passes across both AgentRouter APIs — visual
teardowns of Notcoin, DOGS, CATS, Blum; an ATF referral deep dive; viral-loop,
economy and retention studies) + facts about ATF verified from public sources
during this project. Opus synthesis passes were attempted repeatedly on
2026-10-13 — both Opus budget pools were exhausted (HTTP 402 on both API keys
and the backup domain); an Opus critique pass remains queued for when they refill.*

*Study sources: ~/workspace/delegate-jobs/game-study-20261013-out/ and
game-study-20261013b-out/*

---

## 1. The design in one line

**SpaceHunter revolves around your crew.** Mining alone is deliberately modest;
mining with a crew is where the game is won. Every system — rate, rewards,
leaderboards, the OG Pass — feeds the referral core, copied from ATF's model:
*invites pay instantly on qualification, pay forever as a yield share, and
raise your own mining rate.*

## 2. What is actually verified about ATF (anchors, not guesses)

- Referrals pay **instant ATF + ongoing claim rewards** (ATF's own guide copy).
- **Referrals increase your mining rate** ("increase your mining rate through
  referrals" — ATF tutorial material).
- **Holding ATF upgrades your miner level** — balance itself is progression.
- Mining runs in **1-hour cycles** with a **math captcha** per cycle and
  anti-bot cooldowns/temp bans for inhuman tapping.
- **Withdrawal minimum 500 ATF**; token is listed (DeDust, STON.fi), fixed
  supply, rewards funded from project revenue rather than minting.

ATF does not publish exact referral percentages. The values below are the
study's designed clone values, tuned to SpaceHunter's numbers (100 CSM/h base,
3-hour sessions) — architecture copied, values engineered.

## 3. The referral core — clone spec

### 3.1 Invite flow (reciprocity before request)
1. Invitee arrives via link → sees the inviter's name and crew stats first
   ("@name invited you — their crew has mined N CSM").
2. A **+500 CSM welcome bonus is shown immediately but escrowed**: it credits
   only when the invitee completes their first mining session.
3. Onboarding teaches the loop in ≤3 taps, first session starts, bonus lands
   with the first claim.
4. Immediately after the reward lands: "Want +750 more? Invite your first
   friend" — the invitee becomes an inviter inside the first session.

### 3.2 Rewards (the heart)
| Event | Inviter gets | Invitee gets | When |
|---|---|---|---|
| Friend qualifies (first mining claim, lifetime ≥ 100 CSM) | **+1,000 CSM** | +500 CSM (escrowed bonus) | On qualification |
| Friend reaches 10,000 CSM lifetime | **+2,500 CSM** | +1,000 CSM | Milestone |
| Friend buys OG Pass | **15% of pass price** | — | On purchase |
| Friend's mining yield — Tier 1 (direct) | **yield share, banded** | — | Per claim |
| Friend-of-friend yield — Tier 2 | **4%** | — | Per claim |

**Tier-1 yield share is banded by active crew size** (prevents whale blow-up,
keeps early invites precious):
- Crew 1–5: **12%** each · Crew 6–20: **8%** · Crew 21–50: **5%** · Crew 51–100: **2%**
- Cuts are computed on the friend's *base-derived* yield only (their own team
  income is excluded) — no recursive compounding. Tier 2 is flat 4%, depth stops at 2.

### 3.3 Team mining rate (ATF: referrals raise YOUR rate)
Kept from the current build and now framed as the headline: your mining rate =
100/h × boosts × **(1 + 5% per qualified crew member, cap 20)** × holdings tier
(1k→×1.10, 10k→×1.25, 50k→×1.60, 200k→×2.20) × OG ×2 × verified ×1.1.
Two levers, both social/economic: **bring crew, or hold CSM.**

### 3.4 Qualification & anti-fraud
- A referral counts only after: account age > 1h, first mining claim completed,
  lifetime_earned ≥ 100 CSM. Self-referral and same-device clusters are rejected.
- Yield share pays only on claims from qualified accounts.
- Invite codes are opaque (`ref_<code>_<check>`), never raw user IDs.

### 3.5 Milestone ladder (inviter progression)
5 crew → +500 · 25 → +5,000 · 100 → +25,000 CSM (already live), extended in v2
with rate-cap raises at 50 and 100 qualified crew.

### 3.6 Display rules (from the study)
- The crew screen shows: crew size, qualified count, **earned from crew (total,
  split T1/T2)**, per-friend earnings in the friends list, next milestone progress.
- Every crew payout fires a visible event (toast/feed line): "+36 CSM from
  @friend's mining" — the yield must *feel* alive.

## 4. Core loop

Tap (energy) → start 3h mining session (captcha) → claim → **crew yield lands**
→ rate grows with crew & holdings → invite to grow crew → OG Pass multiplies →
withdraw at 1,000 CSM. Tasks, streaks, promo codes and NFTs orbit this loop;
none of them out-earns a good crew.

## 5. Screen-by-screen UI spec (patterns from the four games)

Visual language (verified from real screenshots in this project): near-black
background, ONE gold accent, oversized tabular numerals, radical reduction
(Blum), hero tap target (Notcoin), colour-coded stat chips (Hamster),
thick energy bar with fraction inside (YesCoin).

- **FLY (main)** — Notcoin pattern: giant gold balance hero; chips (per tap /
  mining rate / level); 264px ship in glow halo; thick energy bar; mining hero
  ring with rate breakdown; NEW: a **crew strip** — "Crew +X CSM/h · N members"
  that deep-links to the Crew screen, so the referral core is visible from the
  main screen, not buried.
- **CREW (Me tab rebuilt)** — Notcoin's Frens pattern: big crew count, gold
  "Invite friends" share button + copy link, earnings summary (total / T1 / T2),
  milestone ladder with progress bars, friends list showing each friend's
  contribution, qualification state per friend. DOGS lesson: keep it to one
  screen, no tiers-within-tiers clutter.
- **BOOST** — Hamster pattern: OG Pass as the premium card on top (CATS: pass
  framed as status + yield, not a discount), boost cards with level/cost pills.
- **TASKS** — CATS pattern: daily code card first (promo redemption as a daily
  ritual), then daily tasks, then global tasks; every task shows reward in gold.
- **DROP** — Blum pattern: wallet-first; balance, connect state, withdrawal
  card with the 1,000 CSM threshold shown as progress ("279 / 1,000"), history.

## 6. Economy parameters (from the economy study)

- Base emission at 10k users ≈ 94.5M CSM/month (avg user ~315 CSM/day ≈ 1
  session/day). Referral emission target ≈ 10% of base (qualification bonuses
  + yield share ≈ 10.3M in the model) — large enough to matter, small enough
  to stay sustainable.
- Sinks: boost upgrades (primary), OG Pass at 50,000 CSM (500 buyers at 5%
  adoption ≈ 6.25M sunk when half pay in CSM), NFT unlocks.
- Session cap: max 8 sessions/day implied by the 3h cycle; withdrawal minimum
  1,000 CSM stays — it is ~3 days of solo mining, ~1 day for a crewed player:
  the gap *is* the referral incentive.

## 7. Retention skeleton (from the retention study)

- Session rhythm: 3h sessions → up to 8 return visits/day; claim-or-lose-nothing
  (sessions stay claimable — no punishment, per current build).
- Daily: streak with milestones (7/30/100 days), daily promo-code ritual (CATS),
  crew yield notifications ("your crew earned you X while you were away").
- Weekly: referral leaderboard reset with a top-crew prize pool.
- Day 1–30 onboarding arc: escrowed bonus (D1) → first milestone chase (D2–3)
  → streak establishment (D7) → OG decision point (D10–14) → crew ladder (D30).

## 8. Build order (this demo)

1. **Backend — referral core v2**: Tier-2 yield share (4%), banded Tier-1 share,
   qualification bonus (+1,000) and milestone bonus (+2,500 at 10k lifetime),
   escrowed invitee bonus (+500 on first claim), OG commission (15%),
   referral-stats endpoint (T1/T2 split, per-friend earnings).
2. **Frontend — Crew screen**: Me tab rebuilt as Crew (hero count, invite CTA,
   earnings, milestones, friends with contributions); Fly crew strip;
   Drop threshold progress.
3. Verify end-to-end (register referred user → claim → inviter paid), visual
   check, hand over link.
