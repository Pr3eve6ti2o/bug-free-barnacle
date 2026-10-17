from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.user import User
from app.models.p2e import MiningSession
from app.services.p2e import (
    issue_challenge, verify_challenge, credit_user, compute_mining_rate, econ_int,
    MINING_SESSION_SECONDS, MINING_BASE_RATE,
)

router = APIRouter(prefix="/mining", tags=["Mining"])


class MiningStartRequest(BaseModel):
    telegram_id: int
    challenge_id: str | None = None
    answer: int | None = None


async def _get_user(db: AsyncSession, telegram_id: int) -> User:
    result = await db.execute(
        select(User).options(selectinload(User.game_state)).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if not user or not user.game_state:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def _active_session(db: AsyncSession, user_id: int) -> MiningSession | None:
    result = await db.execute(
        select(MiningSession)
        .where(MiningSession.user_id == user_id, MiningSession.claimed == False)  # noqa: E712
        .order_by(MiningSession.id.desc())
    )
    return result.scalars().first()


def _utc(dt: datetime | None) -> datetime | None:
    """Coerce a possibly-naive DB datetime (stored as UTC) to aware UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.post("/challenge")
async def get_challenge(telegram_id: int, db: AsyncSession = Depends(get_db)):
    user = await _get_user(db, telegram_id)
    # Always mint a fresh challenge: a running session is deliberately left
    # untouched so a failed captcha can be retried without losing mining time.
    return issue_challenge(user.id)


@router.post("/start")
async def start_session(req: MiningStartRequest, db: AsyncSession = Depends(get_db)):
    user = await _get_user(db, req.telegram_id)
    uid = user.id  # plain int: the ORM object expires on rollback
    # Captcha is optional: the 6-hour farming loop starts with one press.
    # When a challenge is supplied it is still verified (anti-bot clients).
    if req.challenge_id is not None:
        if req.answer is None or not verify_challenge(uid, req.challenge_id, req.answer):
            raise HTTPException(status_code=400, detail="Wrong or expired answer")
    computed = await compute_mining_rate(db, user)
    existing = await _active_session(db, user.id)
    if existing:
        return {
            "session_id": existing.id,
            "hourly_rate": existing.hourly_rate,
            "ends_at": _utc(existing.ends_at).isoformat(),
            "breakdown": computed["breakdown"],
        }
    rate = computed["rate"]
    now = datetime.now(timezone.utc)
    session_hours = await econ_int(db, "econ_session_hours", MINING_SESSION_SECONDS // 3600)
    session = MiningSession(
        user_id=user.id,
        started_at=now,
        ends_at=now + timedelta(seconds=session_hours * 3600),
        hourly_rate=rate,
    )
    db.add(session)
    try:
        await db.commit()
    except IntegrityError:
        # ux_mining_unclaimed: a parallel start won the race. Recover in a
        # FRESH session — the failed transaction leaves this one unusable
        # for follow-up reads (pending object would autoflush again).
        await db.rollback()
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db2:
            existing = await _active_session(db2, uid)
            if existing:
                return {
                    "session_id": existing.id,
                    "hourly_rate": existing.hourly_rate,
                    "ends_at": _utc(existing.ends_at).isoformat(),
                    "breakdown": computed["breakdown"],
                }
        raise HTTPException(status_code=409, detail="Mining session already exists")
    return {
        "session_id": session.id,
        "hourly_rate": rate,
        "ends_at": _utc(session.ends_at).isoformat(),
        "breakdown": computed["breakdown"],
    }


@router.get("/status/{telegram_id}")
async def session_status(telegram_id: int, db: AsyncSession = Depends(get_db)):
    user = await _get_user(db, telegram_id)
    computed = await compute_mining_rate(db, user)
    potential = {"hourly_rate": computed["rate"], "breakdown": computed["breakdown"]}
    session = await _active_session(db, user.id)
    if not session:
        return {"state": "none", "potential": potential}
    now = datetime.now(timezone.utc)
    started_at = _utc(session.started_at)
    ends_at = _utc(session.ends_at)
    total_seconds = max(0, int((ends_at - started_at).total_seconds()))
    elapsed = max(0, (now - started_at).total_seconds())
    if now >= ends_at:
        accrued = session.hourly_rate * total_seconds // 3600
        return {
            "state": "claimable",
            "session_id": session.id,
            "accrued": accrued,
            "hourly_rate": session.hourly_rate,
            "potential": potential,
        }
    accrued = int(session.hourly_rate * min(elapsed, total_seconds) / 3600)
    return {
        "state": "active",
        "session_id": session.id,
        "ends_at": ends_at.isoformat(),
        "seconds_left": int((ends_at - now).total_seconds()),
        "accrued_estimate": accrued,
        "hourly_rate": session.hourly_rate,
        "potential": potential,
    }


@router.post("/claim")
async def claim_session(telegram_id: int, db: AsyncSession = Depends(get_db)):
    user = await _get_user(db, telegram_id)
    state = user.game_state
    if state is None:
        # Users created before the game tables existed have no state row yet.
        from app.models import GameState
        state = GameState(user_id=user.id, balance=0)
        db.add(state)
        await db.flush()
        user.game_state = state
    session = await _active_session(db, user.id)
    if not session:
        raise HTTPException(status_code=400, detail="No active session")
    if datetime.now(timezone.utc) < _utc(session.ends_at):
        raise HTTPException(status_code=400, detail="Session not finished yet")
    # Atomic claim gate: exactly one concurrent claim wins the UPDATE;
    # the rest see rowcount 0 and stop before any credit happens.
    gate = await db.execute(
        update(MiningSession)
        .where(MiningSession.id == session.id, MiningSession.claimed.is_(False))
        .values(claimed=True, claimed_at=datetime.now(timezone.utc))
    )
    if gate.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Already claimed")
    # Pay for the window the session was CREATED under (its stored
    # ends_at - started_at), not today's constant — a config change must
    # not retroactively re-price in-flight sessions. Clamped at 0: a
    # corrupted row pays nothing rather than a negative amount.
    window_seconds = max(0, int((_utc(session.ends_at) - _utc(session.started_at)).total_seconds()))
    amount = session.hourly_rate * window_seconds // 3600
    credited = await credit_user(db, user, amount, mined=True)
    new_balance = state.balance
    session.claimed = True
    session.claimed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"claimed_amount": credited, "new_balance": new_balance}
