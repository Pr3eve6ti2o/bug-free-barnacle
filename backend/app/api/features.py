"""Folded-in features from the evaluated repos, rebuilt on SpaceHunter's economy:

- Arcade (from maliksab1213/StoryVibe): spin wheel + coin flip mini-games.
- The Button (from ButtonMania): one shared community reactor — every press
  counts towards a global milestone chest.
- Timed Drops (from Kennix88/Token-Giver): scheduled limited-pool claim events.

All payouts go through services.p2e.credit_user so balances and lifetime
earnings stay consistent. Winnings are house-paid (mined=False): referral
yield shares apply to mining income, not arcade/drop payouts.
"""
import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.features import ArcadeDaily, ArcadeResult, ButtonState, ButtonUser, DropClaim, DropCounter
from app.models.game_state import GameState
from app.models.user import User
from app.services import admin_state
from app.services.p2e import credit_user


async def _debit(db: AsyncSession, user_id: int, amount: int) -> bool:
    """Atomic conditional debit; False when the balance can't cover it.
    Keeps parallel plays from spending the same CSM twice."""
    res = await db.execute(
        update(GameState)
        .where(GameState.user_id == user_id, GameState.balance >= amount)
        .values(balance=GameState.balance - amount)
    )
    if res.rowcount != 1:
        await db.rollback()
        return False
    return True

# ---------------------------------------------------------------- arcade ---

arcade_router = APIRouter(prefix="/arcade", tags=["Arcade"])

WHEEL_SEGMENTS = [0, 10, 25, 50, 100, 250, 1000]
WHEEL_WEIGHTS = [30, 25, 20, 12, 8, 4, 1]          # EV 41.5 per spin
FREE_SPINS_PER_DAY = 3
PAID_SPIN_COST = 75                                 # house edge vs EV above
FLIP_MIN_STAKE = 10
FLIP_MAX_STAKE = 500
FLIP_PAYOUT_MULT = 1.9                              # 5% house edge

_rng = random.SystemRandom()


class FlipRequest(BaseModel):
    telegram_id: int
    choice: str                                     # "heads" | "tails"
    stake: int


class TelegramOnly(BaseModel):
    telegram_id: int


async def _get_user(db: AsyncSession, telegram_id: int) -> User:
    result = await db.execute(
        select(User).options(selectinload(User.game_state)).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if not user or not user.game_state:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def _wheel_spins_today(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(func.count(ArcadeResult.id)).where(
            ArcadeResult.user_id == user_id,
            ArcadeResult.game == "wheel",
            ArcadeResult.day == _today(),
        )
    )
    return int(result.scalar() or 0)


def _arcade_state(user: User, spins_today: int) -> dict:
    return {
        "balance": user.game_state.balance,
        "wheel": {
            "segments": WHEEL_SEGMENTS,
            "free_spins_left": max(0, FREE_SPINS_PER_DAY - spins_today),
            "free_spins_per_day": FREE_SPINS_PER_DAY,
            "paid_spin_cost": PAID_SPIN_COST,
        },
        "flip": {"min_stake": FLIP_MIN_STAKE, "max_stake": FLIP_MAX_STAKE, "payout_mult": FLIP_PAYOUT_MULT},
    }


async def _require_arcade(db: AsyncSession) -> None:
    if not await admin_state.arcade_enabled(db):
        raise HTTPException(status_code=403, detail="The Arcade is switched off right now")


@arcade_router.get("/state")
async def arcade_state(telegram_id: int, db: AsyncSession = Depends(get_db)):
    await _require_arcade(db)
    user = await _get_user(db, telegram_id)
    return _arcade_state(user, await _wheel_spins_today(db, user.id))


@arcade_router.post("/wheel/spin")
async def wheel_spin(req: TelegramOnly, db: AsyncSession = Depends(get_db)):
    await _require_arcade(db)
    user = await _get_user(db, req.telegram_id)
    spins_today = await _wheel_spins_today(db, user.id)
    # Atomically claim one of today's free slots (guarded upsert): parallel
    # spins cannot all slip under the free limit — exactly FREE_SPINS_PER_DAY
    # slots exist, decided by the database, not by a stale count.
    slot = sqlite_insert(ArcadeDaily).values(user_id=user.id, day=_today(), spins=1)
    slot = slot.on_conflict_do_update(
        index_elements=["user_id", "day"],
        set_={"spins": ArcadeDaily.spins + 1},
        where=ArcadeDaily.spins < FREE_SPINS_PER_DAY,
    ).returning(ArcadeDaily.spins)
    free = (await db.execute(slot)).scalar_one_or_none() is not None
    stake = 0 if free else PAID_SPIN_COST
    if not free:
        if not await _debit(db, user.id, PAID_SPIN_COST):
            raise HTTPException(status_code=400, detail="Not enough CSM for a paid spin")
        await db.refresh(user.game_state)

    segment_index = _rng.choices(range(len(WHEEL_SEGMENTS)), weights=WHEEL_WEIGHTS, k=1)[0]
    payout = WHEEL_SEGMENTS[segment_index]
    if payout > 0:
        await credit_user(db, user, payout)
    db.add(ArcadeResult(user_id=user.id, game="wheel", stake=stake, payout=payout,
                        outcome=str(segment_index), day=_today()))
    await db.commit()
    await db.refresh(user.game_state)
    state = _arcade_state(user, spins_today + 1)
    return {"segment_index": segment_index, "payout": payout, "was_free": free, **state}


@arcade_router.post("/flip/play")
async def flip_play(req: FlipRequest, db: AsyncSession = Depends(get_db)):
    await _require_arcade(db)
    if req.choice not in ("heads", "tails"):
        raise HTTPException(status_code=400, detail="Choice must be heads or tails")
    if not (FLIP_MIN_STAKE <= req.stake <= FLIP_MAX_STAKE):
        raise HTTPException(status_code=400, detail=f"Stake must be {FLIP_MIN_STAKE}–{FLIP_MAX_STAKE} CSM")
    user = await _get_user(db, req.telegram_id)
    if not await _debit(db, user.id, req.stake):
        raise HTTPException(status_code=400, detail="Not enough CSM")
    await db.refresh(user.game_state)

    result = _rng.choice(["heads", "tails"])
    won = result == req.choice
    payout = int(req.stake * FLIP_PAYOUT_MULT) if won else 0
    if payout > 0:
        await credit_user(db, user, payout)
    db.add(ArcadeResult(user_id=user.id, game="flip", stake=req.stake, payout=payout,
                        outcome=result, day=_today()))
    await db.commit()
    await db.refresh(user.game_state)
    return {"result": result, "won": won, "payout": payout, "balance": user.game_state.balance}


# ---------------------------------------------------------------- button ---

button_router = APIRouter(prefix="/button", tags=["Button"])

BUTTON_MILESTONE = 1000        # presses per community milestone
BUTTON_CHEST = 100             # CSM per chest
BUTTON_MIN_PRESS_GAP_MS = 800
BUTTON_CLAIM_MIN_PRESSES = 10


async def _button_state_row(db: AsyncSession) -> ButtonState:
    row = await db.get(ButtonState, 1)
    if row is None:
        try:
            async with db.begin_nested():
                row = ButtonState(id=1, total_presses=0)
                db.add(row)
                await db.flush()
        except IntegrityError:
            row = await db.get(ButtonState, 1)
    return row


async def _button_user(db: AsyncSession, user_id: int) -> ButtonUser:
    row = await db.get(ButtonUser, user_id)
    if row is None:
        try:
            async with db.begin_nested():
                row = ButtonUser(user_id=user_id, presses=0, claimed_milestone=0)
                db.add(row)
                await db.flush()
        except IntegrityError:
            row = await db.get(ButtonUser, user_id)
    return row


def _button_payload(state: ButtonState, bu: ButtonUser) -> dict:
    milestone = int(state.total_presses) // BUTTON_MILESTONE
    into = int(state.total_presses) % BUTTON_MILESTONE
    can_claim = (
        milestone >= 1
        and bu.claimed_milestone < milestone
        and bu.presses >= BUTTON_CLAIM_MIN_PRESSES
    )
    return {
        "total_presses": int(state.total_presses),
        "milestone": milestone,
        "presses_into_milestone": into,
        "presses_to_next": BUTTON_MILESTONE - into,
        "milestone_size": BUTTON_MILESTONE,
        "chest_amount": BUTTON_CHEST,
        "my_presses": int(bu.presses),
        "can_claim_chest": can_claim,
        "claim_min_presses": BUTTON_CLAIM_MIN_PRESSES,
    }


@button_router.get("/state")
async def button_state(telegram_id: int, db: AsyncSession = Depends(get_db)):
    user = await _get_user(db, telegram_id)
    state = await _button_state_row(db)
    bu = await _button_user(db, user.id)
    return _button_payload(state, bu)


@button_router.post("/press")
async def button_press(req: TelegramOnly, db: AsyncSession = Depends(get_db)):
    user = await _get_user(db, req.telegram_id)
    state = await _button_state_row(db)
    bu = await _button_user(db, user.id)
    uid = bu.user_id
    now = datetime.utcnow()
    # Atomic throttle + press count: the 800 ms gap lives in the WHERE, so
    # parallel presses can't all pass on the same stale timestamp.
    threshold = now - timedelta(milliseconds=BUTTON_MIN_PRESS_GAP_MS)
    gate = await db.execute(
        update(ButtonUser)
        .where(ButtonUser.user_id == uid,
               or_(ButtonUser.last_press_at.is_(None), ButtonUser.last_press_at <= threshold))
        .values(presses=ButtonUser.presses + 1, last_press_at=now)
    )
    if gate.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=429, detail="Too fast — the reactor needs a breath")
    await db.execute(
        update(ButtonState).where(ButtonState.id == 1)
        .values(total_presses=ButtonState.total_presses + 1)
    )
    await db.commit()
    state = await _button_state_row(db)
    bu = await _button_user(db, uid)
    return _button_payload(state, bu)


@button_router.post("/claim")
async def button_claim(req: TelegramOnly, db: AsyncSession = Depends(get_db)):
    user = await _get_user(db, req.telegram_id)
    state = await _button_state_row(db)
    bu = await _button_user(db, user.id)
    payload = _button_payload(state, bu)
    if not payload["can_claim_chest"]:
        raise HTTPException(status_code=400, detail="No chest available to claim")
    # Atomic claim gate: exactly one claim per milestone wins the UPDATE.
    gate = await db.execute(
        update(ButtonUser)
        .where(ButtonUser.user_id == bu.user_id,
               ButtonUser.claimed_milestone < payload["milestone"])
        .values(claimed_milestone=payload["milestone"])
    )
    if gate.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=400, detail="No chest available to claim")
    bu.claimed_milestone = payload["milestone"]
    await credit_user(db, user, BUTTON_CHEST)
    await db.commit()
    await db.refresh(user.game_state)
    payload = _button_payload(state, bu)
    payload["balance"] = user.game_state.balance
    payload["claimed"] = BUTTON_CHEST
    return payload


# ----------------------------------------------------------------- drops ---

drops_router = APIRouter(prefix="/drops", tags=["Drops"])

DROP_WINDOW_S = 30 * 60        # a new drop every 30 minutes
DROP_LIVE_S = 15 * 60          # live for 15 minutes
DROP_POOL = 5000
DROP_PER_CLAIM = 50


def _drop_window(now: datetime) -> dict:
    epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)
    elapsed = (now - epoch).total_seconds()
    cycle = int(elapsed // DROP_WINDOW_S)
    starts = epoch + timedelta(seconds=cycle * DROP_WINDOW_S)
    ends = starts + timedelta(seconds=DROP_LIVE_S)
    nxt = starts + timedelta(seconds=DROP_WINDOW_S)
    return {
        "drop_key": f"drop-{cycle}",
        "starts_at": starts.isoformat(),
        "ends_at": ends.isoformat(),
        "next_starts_at": nxt.isoformat(),
        "live": starts <= now < ends,
        "pool_total": DROP_POOL,
        "per_claim": DROP_PER_CLAIM,
    }


async def _drop_payload(db: AsyncSession, user_id: int) -> dict:
    now = datetime.now(timezone.utc)
    win = _drop_window(now)
    # Admin force-start: an override window set from the admin panel.
    force_key = await admin_state.get_setting(db, "drop_force_key", "")
    try:
        force_until = int((await admin_state.get_setting(db, "drop_force_until", "0")) or 0)
    except (TypeError, ValueError):
        force_until = 0  # a corrupt setting must never 500 the drop endpoints
    # int() accepts arbitrarily large values and fromtimestamp() raises
    # OverflowError on them — clamp into a sane window before converting.
    force_until = min(force_until, int(now.timestamp()) + 7 * 86400)
    if force_key and force_until > int(now.timestamp()):
        win = {
            **win,
            "drop_key": force_key,
            "live": True,
            "ends_at": datetime.fromtimestamp(force_until, tz=timezone.utc).isoformat(),
        }
    result = await db.execute(
        select(func.count(DropClaim.id)).where(DropClaim.drop_key == win["drop_key"])
    )
    claims = int(result.scalar() or 0)
    mine = await db.execute(
        select(DropClaim).where(DropClaim.drop_key == win["drop_key"], DropClaim.user_id == user_id)
    )
    claimed = mine.scalar_one_or_none() is not None
    win["claims"] = claims
    win["pool_remaining"] = max(0, DROP_POOL - claims * DROP_PER_CLAIM)
    win["claimed_by_me"] = claimed
    win["claimable"] = bool(win["live"] and not claimed and win["pool_remaining"] >= DROP_PER_CLAIM)
    return win


@drops_router.get("/current")
async def drop_current(telegram_id: int, db: AsyncSession = Depends(get_db)):
    user = await _get_user(db, telegram_id)
    payload = await _drop_payload(db, user.id)
    payload["balance"] = user.game_state.balance
    return payload


@drops_router.post("/claim")
async def drop_claim(req: TelegramOnly, db: AsyncSession = Depends(get_db)):
    user = await _get_user(db, req.telegram_id)
    payload = await _drop_payload(db, user.id)
    if not payload["live"]:
        raise HTTPException(status_code=400, detail="No drop is live right now")
    if payload["claimed_by_me"]:
        raise HTTPException(status_code=400, detail="Already claimed this drop")
    if payload["pool_remaining"] < DROP_PER_CLAIM:
        raise HTTPException(status_code=400, detail="Drop pool exhausted")
    # Authoritative pool gate: a guarded counter upsert decides who gets
    # the remaining slots — a stale COUNT(*) read can't over-draw the pool.
    counter = sqlite_insert(DropCounter).values(drop_key=payload["drop_key"], claimed=1)
    counter = counter.on_conflict_do_update(
        index_elements=["drop_key"],
        set_={"claimed": DropCounter.claimed + 1},
        where=DropCounter.claimed < DROP_POOL // DROP_PER_CLAIM,
    ).returning(DropCounter.claimed)
    if (await db.execute(counter)).scalar_one_or_none() is None:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Drop pool exhausted")
    db.add(DropClaim(drop_key=payload["drop_key"], user_id=user.id, amount=DROP_PER_CLAIM))
    await credit_user(db, user, DROP_PER_CLAIM)
    try:
        await db.commit()
    except IntegrityError:
        # uq_drop_user: a parallel claim for this drop won the race.
        await db.rollback()
        raise HTTPException(status_code=400, detail="Already claimed this drop")
    await db.refresh(user.game_state)
    payload = await _drop_payload(db, user.id)
    payload["balance"] = user.game_state.balance
    payload["claimed_amount"] = DROP_PER_CLAIM
    return payload
