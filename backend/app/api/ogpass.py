from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.user import User
from app.models.game_state import GameState
from app.services.p2e import is_og_active, OG_PASS_COST, OG_PASS_DAYS, econ_int

router = APIRouter(prefix="/ogpass", tags=["OGPass"])


async def _get_user(db: AsyncSession, telegram_id: int) -> User:
    result = await db.execute(
        select(User).options(selectinload(User.game_state)).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if not user or not user.game_state:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/status/{telegram_id}")
async def status(telegram_id: int, db: AsyncSession = Depends(get_db)):
    user = await _get_user(db, telegram_id)
    active = is_og_active(user)
    cost = await econ_int(db, "econ_og_cost", OG_PASS_COST)
    return {
        "active": active,
        "expires_at": user.og_pass_expires_at.isoformat() if user.og_pass_expires_at else None,
        "cost": cost,
        "days": OG_PASS_DAYS,
    }


@router.post("/purchase")
async def purchase(telegram_id: int, db: AsyncSession = Depends(get_db)):
    user = await _get_user(db, telegram_id)
    cost = await econ_int(db, "econ_og_cost", OG_PASS_COST)
    # Atomic conditional debit: parallel purchases can't spend the same CSM twice.
    debit = await db.execute(
        update(GameState)
        .where(GameState.user_id == user.id, GameState.balance >= cost)
        .values(balance=GameState.balance - cost)
    )
    if debit.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Not enough CSM")
    await db.refresh(user.game_state)
    base = user.og_pass_expires_at if is_og_active(user) else datetime.now()
    user.og_pass_expires_at = base + timedelta(days=OG_PASS_DAYS)
    # ATF-style: the inviter earns 15% commission on a friend's OG Pass purchase
    if user.referred_by_id:
        from app.services.p2e import _load_user, _pay_referral, OG_COMMISSION
        referrer = await _load_user(db, user.referred_by_id)
        if referrer:
            await _pay_referral(db, referrer, user, int(cost * OG_COMMISSION), tier=1, kind="og")
    await db.commit()
    return {
        "expires_at": user.og_pass_expires_at.isoformat(),
        "new_balance": user.game_state.balance,
    }
