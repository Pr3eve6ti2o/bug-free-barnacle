from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.user import get_user_by_telegram_id, create_user, create_user_with_referral, get_user_referrals_by_telegram_id
from app.schemas.user import UserCreate, UserWithGameState, UserReferralCreate
from app.database import get_db
from app.models.user import User
from app.models.game_state import GameState
from app.services.p2e import is_og_active, REFERRAL_MILESTONES
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from typing import Optional, List

router = APIRouter(prefix="/users", tags=["Users"])


async def _ensure_game_state(db: AsyncSession, user: Optional[User]) -> Optional[User]:
    """Гарантирует наличие GameState у пользователя (идемпотентно)."""
    if user is None:
        return None

    existing = await db.execute(
        select(GameState.user_id).where(GameState.user_id == user.id).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return user

    try:
        async with db.begin_nested():
            db.add(GameState(user_id=user.id))
            await db.flush()
    except IntegrityError:
        # A concurrent first-touch request created the row first.
        pass
    return await get_user_by_telegram_id(db, user.telegram_id)


# Эндпоинт для регистрации пользователя (при первом заходе в игру)
@router.post("/register", response_model=UserWithGameState)
async def register_user(user_create: UserCreate, db: AsyncSession = Depends(get_db)):
    # Проверяем, существует ли уже пользователь с таким telegram_id
    existing_user = await get_user_by_telegram_id(db, user_create.telegram_id)

    if existing_user:
        # Идемпотентность: повторная регистрация возвращает существующего пользователя
        return await _ensure_game_state(db, existing_user)

    # Если не существует, создаем нового пользователя
    try:
        await create_user(db, user_create)
    except IntegrityError:
        # Параллельная регистрация: пользователь уже создан другим запросом
        await db.rollback()
        existing_user = await get_user_by_telegram_id(db, user_create.telegram_id)
        if existing_user is None:
            raise HTTPException(status_code=409, detail="Registration conflict, retry") from None
        return await _ensure_game_state(db, existing_user)

    new_user = await get_user_by_telegram_id(db, user_create.telegram_id)
    return await _ensure_game_state(db, new_user)


# Эндпоинт для получения пользователя по telegram_id
@router.get("/{telegram_id}", response_model=UserWithGameState)
async def get_user(telegram_id: int, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_telegram_id(db, telegram_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/register_with_referral", response_model=UserWithGameState)
async def register_user_with_referral(
    # Используем схему Pydantic для получения данных из тела запроса
    user_data: UserReferralCreate,
    db: AsyncSession = Depends(get_db)
):
    # Проверяем, существует ли уже пользователь с таким telegram_id
    existing_user = await get_user_by_telegram_id(db, user_data.telegram_id)
    if existing_user:
        # Просто возвращаем существующего пользователя (с гарантированным GameState)
        return await _ensure_game_state(db, existing_user)

    # Создаем нового пользователя с реферальной системой
    try:
        new_user = await create_user_with_referral(db, user_data)
    except IntegrityError:
        # Параллельная регистрация: пользователь уже создан другим запросом
        await db.rollback()
        existing_user = await get_user_by_telegram_id(db, user_data.telegram_id)
        if existing_user is None:
            raise HTTPException(status_code=409, detail="Registration conflict, retry") from None
        return await _ensure_game_state(db, existing_user)

    return await _ensure_game_state(db, new_user)


@router.get("/referrals/{telegram_id}", response_model=List[UserWithGameState])
async def get_user_referrals(telegram_id: int, db: AsyncSession = Depends(get_db)):
    """Получение списка пользователей, приглашенных по реферальной ссылке."""
    user = await get_user_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Получаем список рефералов
    referrals = await get_user_referrals_by_telegram_id(db, telegram_id)
    return referrals

class ConsentRequest(BaseModel):
    telegram_id: int
    terms_version: int


@router.post("/consent")
async def accept_terms(req: ConsentRequest, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_telegram_id(db, req.telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if req.terms_version > (user.terms_accepted_version or 0):
        user.terms_accepted_version = req.terms_version
        await db.commit()
    return {"accepted_version": user.terms_accepted_version or 0}


@router.get("/consent/{telegram_id}")
async def get_consent(telegram_id: int, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"accepted_version": user.terms_accepted_version or 0}


@router.get("/referral-stats/{telegram_id}")
async def get_referral_stats(telegram_id: int, db: AsyncSession = Depends(get_db)):
    """Referral overview: counts, ATF-style yield earnings (T1/T2 split), milestones,
    and per-friend contributions from the earnings ledger."""
    result = await db.execute(
        select(User).options(selectinload(User.game_state)).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    qualified = (await db.execute(
        select(func.count(User.id)).where(
            User.referred_by_id == user.id, User.lifetime_mined >= 100
        )
    )).scalar() or 0
    total = (await db.execute(
        select(func.count(User.id)).where(User.referred_by_id == user.id)
    )).scalar() or 0
    claimed = set(x for x in (user.referral_milestones_claimed or "").split(",") if x)
    milestones = [
        {"invites": m, "reward": r, "claimed": str(m) in claimed, "reached": qualified >= m}
        for m, r in REFERRAL_MILESTONES
    ]
    # Earnings split by tier from the ledger
    from app.models.p2e import ReferralEarning
    tier_rows = (await db.execute(
        select(ReferralEarning.tier, func.coalesce(func.sum(ReferralEarning.amount), 0))
        .where(ReferralEarning.referrer_id == user.id)
        .group_by(ReferralEarning.tier)
    )).all()
    tier_map = {t: int(a) for t, a in tier_rows}
    # Per-friend contributions (direct crew only)
    friend_rows = (await db.execute(
        select(User, func.coalesce(func.sum(ReferralEarning.amount), 0))
        .outerjoin(ReferralEarning, and_(
            ReferralEarning.from_user_id == User.id,
            ReferralEarning.referrer_id == user.id,
            ReferralEarning.tier == 1,
        ))
        .where(User.referred_by_id == user.id)
        .group_by(User.id)
    )).all()
    friends = [
        {
            "telegram_id": f.telegram_id,
            "username": f.username,
            "earned_for_you": int(earned or 0),
            "qualified": (f.lifetime_mined or 0) >= 100,
        }
        for f, earned in friend_rows
    ]
    friends.sort(key=lambda x: -x["earned_for_you"])
    from app.services.p2e import tier1_share_rate
    return {
        "total_invites": total,
        "qualified_invites": qualified,
        "earnings_total": user.referral_earnings or 0,
        "earnings_tier1": tier_map.get(1, 0),
        "earnings_tier2": tier_map.get(2, 0),
        "tier1_rate_pct": round(tier1_share_rate(qualified) * 100),
        "tier2_rate_pct": 4,
        "milestones": milestones,
        "friends": friends,
    }
