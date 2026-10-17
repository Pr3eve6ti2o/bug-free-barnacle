from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from app.database import get_db
from app.services.bonus import claim_daily_bonus
from app.services.p2e import get_streak_info, credit_user, WELCOME_REWARD, econ_int
from app.models.daily_bonus import DailyBonus, UserDailyBonus
from app.models.game_state import GameState
from sqlalchemy.future import select
from sqlalchemy import update
from sqlalchemy.orm import selectinload
from app.models.user import User

router = APIRouter(prefix="/bonus", tags=["Bonus"])

@router.get("/daily/status/{telegram_id}")
async def get_daily_bonus_status(telegram_id: int, db: AsyncSession = Depends(get_db)):
    """Получить статус ежедневных бонусов пользователя"""
    # Получаем пользователя
    user_result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Получаем запись о бонусах
    bonus_result = await db.execute(
        select(UserDailyBonus).where(UserDailyBonus.user_id == user.id)
    )
    bonus_data = bonus_result.scalar_one_or_none()

    today = date.today()
    if not bonus_data:
        streak_info = await get_streak_info(db, user.id)
        return {
            "current_day": 1,
            "can_claim": True,
            "next_claim": None,
            "days_streak": 0,
            **streak_info,
        }

    # Проверяем сброс прогресса
    if bonus_data.last_claimed_date:
        days_diff = (today - bonus_data.last_claimed_date).days
        if days_diff > 1:  # Если пропущен день
            bonus_data.current_day = 1
            await db.commit()

    # Проверяем завершение цикла
    if bonus_data.current_day > 10:
        bonus_data.current_day = 1
        await db.commit()

    # Проверяем, можно ли забрать бонус сегодня
    can_claim = not bonus_data.last_claimed_date or bonus_data.last_claimed_date < today

    streak_info = await get_streak_info(db, user.id)
    return {
        "current_day": bonus_data.current_day,
        "can_claim": can_claim,
        "last_claimed": bonus_data.last_claimed_date.isoformat() if bonus_data.last_claimed_date else None,
        "days_streak": bonus_data.current_day - 1,
        **streak_info,
    }

@router.post("/daily/claim/{telegram_id}")
async def claim_daily_bonus_endpoint(telegram_id: int, db: AsyncSession = Depends(get_db)):
    """Получить ежедневный бонус"""
    result = await claim_daily_bonus(telegram_id, db)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result

@router.get("/daily/config")
async def get_daily_bonus_config(db: AsyncSession = Depends(get_db)):
    """Получить конфигурацию ежедневных бонусов"""
    result = await db.execute(select(DailyBonus))
    bonuses = result.scalars().all()
    
    return [{
        "day": bonus.day_number,
        "type": bonus.reward_type,
        "amount": bonus.reward_amount
    } for bonus in bonuses]
@router.post("/welcome/{telegram_id}")
async def claim_welcome_bonus(telegram_id: int, db: AsyncSession = Depends(get_db)):
    """One-time welcome bonus (idempotent)."""
    result = await db.execute(
        select(User).options(selectinload(User.game_state)).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if not user or not user.game_state:
        raise HTTPException(status_code=404, detail="User not found")
    uid = user.id  # plain int: the ORM object expires on rollback
    # Atomic one-time gate: parallel claims flip the flag exactly once.
    gate = await db.execute(
        update(User)
        .where(User.id == user.id, User.welcome_claimed.is_(False))
        .values(welcome_claimed=True)
    )
    if gate.rowcount != 1:
        await db.rollback()
        # Fresh session for the read-back: this session's state after a
        # contended UPDATE + rollback is not reliable for ORM work, and the
        # ORM user object is expired — use the plain int captured earlier.
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db2:
            fresh = (await db2.execute(
                select(GameState.balance).where(GameState.user_id == uid)
            )).scalar_one_or_none()
        return {"already_claimed": True, "new_balance": int(fresh or 0)}
    user.welcome_claimed = True
    reward = await econ_int(db, "econ_welcome_reward", WELCOME_REWARD)
    credited = await credit_user(db, user, reward)
    await db.commit()
    return {"reward": credited, "new_balance": user.game_state.balance}
