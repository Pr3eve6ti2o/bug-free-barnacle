from datetime import date, timedelta
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.user import User
from app.models.daily_bonus import DailyBonus, UserDailyBonus
from app.models.daily_game_state import DailyGameState
from app.models.game_state import GameState
from app.models.p2e import DailyClaim
from app.services.p2e import get_streak_info, award_streak_milestones


async def claim_daily_bonus(telegram_id: int, db: AsyncSession):
    # 1. Получаем пользователя
    user_result = await db.execute(
        select(User)
        .options(selectinload(User.game_state), selectinload(User.daily_bonus), selectinload(User.daily_game_state))
        .where(User.telegram_id == telegram_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return {"error": "User not found"}

    # 2. Получаем или создаём запись UserDailyBonus
    bonus_result = await db.execute(select(UserDailyBonus).where(UserDailyBonus.user_id == user.id))
    bonus_data = bonus_result.scalar_one_or_none()
    today = date.today()

    if not bonus_data:
        bonus_data = UserDailyBonus(user_id=user.id, current_day=1, last_claimed_date=today - timedelta(days=1))
        db.add(bonus_data)
        try:
            await db.flush()
        except IntegrityError:
            # A concurrent first claim created the row first. Rollback
            # expires every loaded object, so reload both rows fresh and
            # let the normal guards below resolve the race.
            await db.rollback()
            user = (await db.execute(
                select(User)
                .options(selectinload(User.game_state), selectinload(User.daily_bonus), selectinload(User.daily_game_state))
                .where(User.telegram_id == telegram_id)
            )).scalar_one_or_none()
            if user is None:
                return {"error": "User not found"}
            bonus_data = (await db.execute(
                select(UserDailyBonus).where(UserDailyBonus.user_id == user.id)
            )).scalar_one_or_none()
            if bonus_data is None:
                return {"error": "Bonus state unavailable, retry"}

    # 3. Проверка на пропущенный день или что уже забирал бонус
    if bonus_data.last_claimed_date and (today - bonus_data.last_claimed_date).days > 1:
        bonus_data.current_day = 1  # сброс прогресса

    if bonus_data.last_claimed_date == today:
        return {
            "error": "Already claimed today",
            "current_day": bonus_data.current_day,
            "can_claim": False
        }

    # 4. Получаем бонус из таблицы DailyBonus
    bonus_result = await db.execute(select(DailyBonus).where(DailyBonus.day_number == bonus_data.current_day))
    daily_bonus = bonus_result.scalar_one_or_none()
    if not daily_bonus:
        return {"error": "Bonus config not found"}

    # 4b. Claim the day FIRST — the DailyClaim row is the gate, not a
    # receipt. Inserting it before any credit closes the window where a
    # competitor's committed row made the old code skip the insert and pay
    # anyway (double credit), and the flush sits inside the try so a lost
    # race resolves to "already claimed", never a 500.
    existing_claim = (await db.execute(
        select(DailyClaim).where(DailyClaim.user_id == user.id, DailyClaim.claim_date == today)
    )).scalar_one_or_none()
    if existing_claim:
        return {
            "error": "Already claimed today",
            "current_day": bonus_data.current_day,
            "can_claim": False
        }
    # Capture the day BEFORE the flush: a failed flush expires every ORM
    # instance, so reading bonus_data.current_day inside the handler would
    # trigger a lazy load on the failed transaction (PendingRollbackError).
    cd = bonus_data.current_day
    db.add(DailyClaim(user_id=user.id, claim_date=today))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return {
            "error": "Already claimed today",
            "current_day": cd,
            "can_claim": False
        }

    # 5. Выдаём бонус (atomic SQL-side credits — an ORM += can overwrite a
    # concurrent credit landing in the same instant)
    if daily_bonus.reward_type == "coins":
        if user.game_state is None:
            await db.rollback()
            return {"error": "Game state missing, claim not applied"}
        amt = daily_bonus.reward_amount
        game_state_result = await db.execute(
            update(GameState).where(GameState.user_id == user.id)
            .values(balance=GameState.balance + amt)
        )
        daily_state_result = await db.execute(
            update(DailyGameState).where(DailyGameState.user_id == user.id)
            .values(balance=DailyGameState.balance + amt)
        )
        if game_state_result.rowcount != 1 or daily_state_result.rowcount != 1:
            await db.rollback()
            return {"error": "Game state missing, claim not applied"}
        await db.refresh(user.game_state)
        
    elif daily_bonus.reward_type == "nft":
        # TODO: логика выдачи nft
        pass

    # 6. Обновляем данные
    current_day = bonus_data.current_day
    bonus_data.last_claimed_date = today
    bonus_data.current_day = 1 if bonus_data.current_day >= 10 else bonus_data.current_day + 1

    # 7. Стрик: строка клейма уже вставлена на шаге 4b — считаем стрик и
    # выдаём майлстоуны
    streak_info = await get_streak_info(db, user.id)
    streak_awards = await award_streak_milestones(db, user, streak_info["streak"])

    cd = bonus_data.current_day
    uid = user.id
    try:
        await db.commit()
    except IntegrityError:
        # DailyClaim UNIQUE(user, date): a parallel claim won; this whole
        # transaction (including the balance credit above) rolls back.
        await db.rollback()
        # Rollback expires every ORM instance, so re-check with a plain
        # SELECT using values captured before the rollback.
        winning_claim = (await db.execute(
            select(DailyClaim).where(DailyClaim.user_id == uid, DailyClaim.claim_date == today)
        )).scalar_one_or_none()
        if winning_claim is None:
            raise
        return {
            "error": "Already claimed today",
            "current_day": cd,
            "can_claim": False
        }
    return {
        "success": True,
        "message": f"Bonus for day {daily_bonus.day_number} claimed!",
        "reward_type": daily_bonus.reward_type,
        "reward_amount": daily_bonus.reward_amount,
        "current_day": current_day,  # день, за который получен бонус
        "next_day": bonus_data.current_day,  # следующий доступный день
        "can_claim": False,
        "last_claimed_date": today.isoformat(),
        "new_balance": user.game_state.balance if daily_bonus.reward_type == "coins" else None,
        "streak": streak_info["streak"],
        "streak_awards": streak_awards,
    }
