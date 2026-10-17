"""Shared Play-2-Earn helpers: OG status, verified boost, referral credits, milestones."""
import secrets
import time
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload
from app.models.user import User
from app.models.game_state import GameState
from app.services.admin_state import referrals_enabled, get_setting as _get_setting


async def econ_int(db: AsyncSession, key: str, default: int) -> int:
    """Admin-tunable economy value (admin panel → admin_settings), parsed
    safely: a missing/corrupt setting falls back to the built-in default."""
    try:
        raw = await _get_setting(db, key, "")
        return int(raw) if raw not in ("", None) else int(default)
    except (TypeError, ValueError):
        return int(default)

# --- constants ---
REFERRAL_CUT = 0.05
VERIFIED_BONUS = 1.10
REFERRAL_MILESTONES = [(5, 500), (25, 5000), (100, 25000)]  # (invites, reward)
STREAK_MILESTONES = [(7, 1000), (30, 10000), (100, 50000)]  # (days, reward)
MINING_SESSION_SECONDS = 6 * 3600
MINING_BASE_RATE = 100  # CSM per hour
OG_PASS_COST = 50000
OG_PASS_DAYS = 30
OG_MINING_MULTIPLIER = 2
WELCOME_REWARD = 250
WITHDRAW_MIN = 1000

# --- ATF-style mining algorithm: mine faster by referring more or holding more ---
# Referral mining: +5% rate per qualified referral (lifetime_earned >= 100), capped at 20.
REFERRAL_MINING_PCT = 0.05
REFERRAL_MINING_CAP = 20
# Holdings mining: balance tiers multiply the rate (hold CSM -> mine faster).
HOLDINGS_TIERS = [  # (min_balance, multiplier), highest first
    (200000, 2.20),
    (50000, 1.60),
    (10000, 1.25),
    (1000, 1.10),
]


async def qualified_referral_count(db: AsyncSession, user: User) -> int:
    """Referrals who have MINED >= 100 lifetime (anti-farmed: bonuses,
    escrow releases and referral income never count toward qualification)."""
    result = await db.execute(
        select(func.count(User.id)).where(
            User.referred_by_id == user.id,
            User.lifetime_mined >= 100,
        )
    )
    return result.scalar() or 0


def holdings_multiplier(balance: int) -> float:
    for min_balance, mult in HOLDINGS_TIERS:
        if balance >= min_balance:
            return mult
    return 1.0


async def compute_mining_rate(db: AsyncSession, user: User) -> dict:
    """ATF-style rate: base x boosts x (1 + 5%/qualified referral, cap 20) x holdings tier x OG x verified.

    Returns {"rate": int, "breakdown": {...}} with the breakdown for the UI.
    """
    base_rate = await econ_int(db, "econ_base_rate", MINING_BASE_RATE)
    base = int(base_rate * (user.game_state.boost_multiplier or 1))
    qualified = await qualified_referral_count(db, user)
    referral_mult = 1 + REFERRAL_MINING_PCT * min(qualified, REFERRAL_MINING_CAP)
    hold_mult = holdings_multiplier(user.game_state.balance or 0)
    task_pct = float(getattr(user.game_state, "task_boost_pct", 0) or 0)
    admin_pct = float(getattr(user.game_state, "admin_boost_pct", 0) or 0)
    og = is_og_active(user)
    verified = is_verified(user)
    rate = base * referral_mult * hold_mult * (1 + (task_pct + admin_pct) / 100)
    if og:
        rate *= OG_MINING_MULTIPLIER
    if verified:
        rate *= VERIFIED_BONUS
    return {
        "rate": int(rate),
        "breakdown": {
            "base": base,
            "referral_pct": round((referral_mult - 1) * 100),
            "qualified_referrals": qualified,
            "holdings_mult": hold_mult,
            "holdings_tier": next((mb for mb, _ in HOLDINGS_TIERS if (user.game_state.balance or 0) >= mb), 0),
            "og_active": og,
            "verified": verified,
            "task_boost_pct": task_pct,
            "admin_boost_pct": admin_pct,
        },
    }


def is_og_active(user: User) -> bool:
    return bool(user.og_pass_expires_at and user.og_pass_expires_at > datetime.now())


def is_verified(user: User) -> bool:
    """Verified = Telegram username set AND wallet connected."""
    return bool(user.username and user.username.strip()) and bool(user.ton_wallet_address)


def get_max_energy(user: User) -> int:
    return 110 if is_og_active(user) else 100


def _claimed_set(raw: str | None) -> set:
    return set(x for x in (raw or "").split(",") if x)


def _claimed_str(items: set) -> str:
    return ",".join(sorted(items, key=int))


async def check_referral_milestones(db: AsyncSession, referrer: User) -> list:
    """Award unclaimed referral milestones. Returns list of (milestone, reward)."""
    awarded = []
    claimed = _claimed_set(referrer.referral_milestones_claimed)
    # count referred users who have MINED >= 100 lifetime (bonuses don't count)
    result = await db.execute(
        select(func.count(User.id)).where(
            User.referred_by_id == referrer.id,
            User.lifetime_mined >= 100,
        )
    )
    qualified = result.scalar() or 0
    # Each threshold is claimed with a compare-and-set on the claimed-set
    # string itself: two concurrent credit paths for this referrer both see
    # the threshold unclaimed, but only the one whose UPDATE still matches
    # the old string pays — the loser skips instead of double-paying.
    current_raw = referrer.referral_milestones_claimed
    for milestone, reward in REFERRAL_MILESTONES:
        key = str(milestone)
        if qualified >= milestone and key not in claimed:
            new_claimed = claimed | {key}
            new_str = _claimed_str(new_claimed)
            gate = await db.execute(
                update(User)
                .where(User.id == referrer.id,
                       func.coalesce(User.referral_milestones_claimed, "") == (current_raw or ""))
                .values(referral_milestones_claimed=new_str))
            if gate.rowcount != 1:
                continue
            await atomic_credit(db, referrer, reward)
            claimed = new_claimed
            current_raw = new_str
            referrer.referral_milestones_claimed = new_str
            awarded.append({"milestone": milestone, "reward": reward})
    return awarded


# --- referral core v2 constants (ATF-style, see GAME_PLAN_V2.md) ---
TIER2_CUT = 0.04            # friend-of-friend yield share
QUAL_BONUS_INVITER = 1000   # paid to inviter when a referral qualifies
MILESTONE_LIFETIME = 10000  # referral lifetime that triggers the milestone bonus
MILESTONE_BONUS_INVITER = 2500
MILESTONE_BONUS_INVITEE = 1000
OG_COMMISSION = 0.15        # inviter's cut of a friend's OG Pass purchase
INVITEE_ESCROW_BONUS = 500  # shown at invite, paid on first mining claim


def tier1_share_rate(qualified_count: int) -> float:
    """Banded Tier-1 yield share by the INVITER's qualified crew size."""
    if qualified_count <= 5:
        return 0.12
    if qualified_count <= 20:
        return 0.08
    if qualified_count <= 50:
        return 0.05
    if qualified_count <= 100:
        return 0.02
    return 0.0


async def _pay_referral(db: AsyncSession, referrer: User, from_user: User,
                        amount: int, tier: int, kind: str) -> None:
    """Credit a referral payout + write the ledger row. Does NOT commit."""
    from app.models.p2e import ReferralEarning
    if amount <= 0 or not referrer or not referrer.game_state:
        return
    if referrer.id == from_user.id:
        return  # never pay a user their own referral share
    await atomic_credit(db, referrer, amount, referral_delta=amount)
    db.add(ReferralEarning(
        referrer_id=referrer.id, from_user_id=from_user.id,
        amount=amount, tier=tier, kind=kind,
    ))


async def _load_user(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(
        select(User).options(selectinload(User.game_state)).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def atomic_credit(
    db: AsyncSession,
    user: User,
    amount: int,
    *,
    mined_delta: int = 0,
    count_lifetime: bool = True,
    referral_delta: int = 0,
) -> None:
    """Credit a balance with SQL-side increments — the ONLY safe way to pay.

    ORM `game_state.balance += x` is a read-modify-write on a snapshot: two
    credits landing concurrently (e.g. welcome bonus + mining claim) each
    flush their own absolute total and one credit is silently lost (proven
    live in audit round 2). Here the database does the arithmetic, and the
    in-memory objects are refreshed so no stale balance is ever flushed
    back over the increment. Does NOT commit (caller does)."""
    amount = int(amount)
    if amount <= 0 and mined_delta <= 0 and referral_delta <= 0:
        return
    if amount > 0:
        await db.execute(
            update(GameState)
            .where(GameState.user_id == user.id)
            .values(balance=GameState.balance + amount)
        )
    user_values: dict = {}
    if count_lifetime and amount > 0:
        user_values["lifetime_earned"] = User.lifetime_earned + amount
    if mined_delta > 0:
        user_values["lifetime_mined"] = func.coalesce(User.lifetime_mined, 0) + mined_delta
    if referral_delta > 0:
        user_values["referral_earnings"] = User.referral_earnings + referral_delta
    if user_values:
        await db.execute(update(User).where(User.id == user.id).values(**user_values))
    if amount > 0 and user.game_state is not None:
        await db.refresh(user.game_state)
    if user_values:
        await db.refresh(user, attribute_names=list(user_values.keys()))


async def credit_user(
    db: AsyncSession,
    user: User,
    amount: int,
    *,
    mined: bool = False,
    apply_verified: bool = False,
) -> int:
    """Credit CSM to a user. Applies verified +10% when asked, bumps lifetime_earned.

    On mined earnings from a referred user (ATF-style referral core):
    - releases the escrowed invite bonus on the first mining claim,
    - pays the inviter a banded Tier-1 yield share and the grand-inviter 4% Tier-2,
    - pays one-time qualification (+1,000) and 10k-lifetime milestone bonuses.
    Does NOT commit (caller does)."""
    amount = int(amount)
    if amount <= 0:
        return 0
    if apply_verified and is_verified(user):
        amount = int(amount * VERIFIED_BONUS)

    escrow = 0
    milestone_invitee = 0
    new_lifetime_mined = (user.lifetime_mined or 0) + (amount if mined else 0)
    if mined and (user.pending_invite_bonus or 0) > 0 and new_lifetime_mined >= 100:
        # Escrowed invitee bonus lands once genuine mining reaches the
        # qualification threshold (100 lifetime mined) — the escrow itself
        # and bonus credits never count toward it (see lifetime_mined note
        # in audit fixes). The amount-equality UPDATE is the claim: if a
        # concurrent credit zeroes the escrow first, this matches 0 rows
        # and the bonus is not paid twice.
        wanted = int(user.pending_invite_bonus)
        escrow_claim = await db.execute(
            update(User).where(User.id == user.id, User.pending_invite_bonus == wanted)
            .values(pending_invite_bonus=0))
        if escrow_claim.rowcount == 1:
            escrow = wanted
            user.pending_invite_bonus = 0

    # One atomic credit for everything this call pays the user directly.
    await atomic_credit(db, user, amount + escrow, mined_delta=amount if mined else 0)

    if mined and user.referred_by_id and await referrals_enabled(db):
        referrer = await _load_user(db, user.referred_by_id)
        if referrer:
            qualified_now = new_lifetime_mined >= 100
            if qualified_now:
                # Tier-1 yield share (banded by the inviter's crew size)
                crew = await qualified_referral_count(db, referrer)
                cut = int(amount * tier1_share_rate(crew))
                await _pay_referral(db, referrer, user, cut, tier=1, kind="yield")
                # Tier-2: the inviter's own inviter takes 4%
                if referrer.referred_by_id:
                    grand = await _load_user(db, referrer.referred_by_id)
                    if grand:
                        cut2 = int(amount * TIER2_CUT)
                        await _pay_referral(db, grand, user, cut2, tier=2, kind="yield")
                # One-time qualification bonus — claimed by guarded flag
                # flip so concurrent credits of this user cannot pay twice.
                qual_claim = await db.execute(
                    update(User).where(User.id == user.id, User.qual_bonus_paid.is_(False))
                    .values(qual_bonus_paid=True))
                if qual_claim.rowcount == 1:
                    user.qual_bonus_paid = True
                    await _pay_referral(db, referrer, user, QUAL_BONUS_INVITER, tier=1, kind="qual")
                await check_referral_milestones(db, referrer)
            # 10k-mined milestone (inviter +2,500, invitee +1,000)
            if new_lifetime_mined >= MILESTONE_LIFETIME:
                ms_claim = await db.execute(
                    update(User).where(User.id == user.id, User.ref_milestone_paid.is_(False))
                    .values(ref_milestone_paid=True))
                if ms_claim.rowcount == 1:
                    user.ref_milestone_paid = True
                    await _pay_referral(db, referrer, user, MILESTONE_BONUS_INVITER, tier=1, kind="milestone")
                    milestone_invitee = MILESTONE_BONUS_INVITEE
    if milestone_invitee:
        await atomic_credit(db, user, milestone_invitee)
    return amount


# --- streaks ---
async def get_streak_info(db: AsyncSession, user_id: int) -> dict:
    """Streak = consecutive UTC calendar days with a DailyClaim, ending today or yesterday."""
    from datetime import date as date_cls, datetime as dt_cls
    from app.models.p2e import DailyClaim
    rows = (await db.execute(
        select(DailyClaim.claim_date)
        .where(DailyClaim.user_id == user_id)
        .order_by(DailyClaim.claim_date.desc())
        .limit(400)
    )).scalars().all()
    days = set(rows)
    today = date_cls.today()
    streak = 0
    cursor = today if today in days else (today - timedelta(days=1) if (today - timedelta(days=1)) in days else None)
    while cursor and cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    next_milestone = next((m for m, _ in STREAK_MILESTONES if m > streak), None)
    now = dt_cls.now()
    midnight = dt_cls.combine(today + timedelta(days=1), dt_cls.min.time())
    return {
        "streak": streak,
        "next_milestone": next_milestone,
        "next_milestone_in_days": (next_milestone - streak) if next_milestone else None,
        "resets_in_seconds": int((midnight - now).total_seconds()),
    }


async def award_streak_milestones(db: AsyncSession, user: User, streak: int) -> list:
    awarded = []
    claimed = _claimed_set(user.streak_milestones_claimed)
    for milestone, reward in STREAK_MILESTONES:
        key = str(milestone)
        if streak >= milestone and key not in claimed:
            await atomic_credit(db, user, reward)
            claimed.add(key)
            awarded.append({"milestone": milestone, "reward": reward})
    user.streak_milestones_claimed = _claimed_str(claimed)
    return awarded


# --- math challenge store (in-memory, single worker) ---
_challenges: dict = {}
CHALLENGE_TTL = 300  # 5 minutes


def issue_challenge(user_id: int) -> dict:
    import random
    a = random.randint(2, 20)
    b = random.randint(2, 20)
    challenge_id = secrets.token_urlsafe(16)
    now = time.time()
    # opportunistic cleanup
    for cid in [c for c, v in _challenges.items() if v[2] < now]:
        del _challenges[cid]
    _challenges[challenge_id] = (user_id, a + b, now + CHALLENGE_TTL)
    return {"challenge_id": challenge_id, "question": f"{a} + {b} = ?"}


def verify_challenge(user_id: int, challenge_id: str, answer: int) -> bool:
    entry = _challenges.get(challenge_id)
    if not entry:
        return False
    owner_id, correct, expires = entry
    if owner_id != user_id:
        return False  # never consume another user's challenge
    _challenges.pop(challenge_id, None)  # single attempt for the owner
    return time.time() < expires and int(answer) == correct
