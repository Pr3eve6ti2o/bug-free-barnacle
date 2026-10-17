from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.user import User
from app.models.boost import Boost
from app.models.user_boosts import UserBoost


async def get_all_boosts(db: AsyncSession):
    result = await db.execute(select(Boost))
    return result.scalars().all()


async def get_user_boosts(db: AsyncSession, telegram_id: int):
    # Получаем пользователя
    result = await db.execute(
        select(User)
        .options(selectinload(User.boosts).selectinload(UserBoost.boost))
        .filter(User.telegram_id == telegram_id)
    )
    user = result.scalars().first()
    
    if not user:
        return {"error": "User not found"}
    
    # Получаем все бусты (для отображения неприобретенных)
    all_boosts_result = await db.execute(select(Boost))
    all_boosts = all_boosts_result.scalars().all()
    
    # Формируем ответ с информацией о бустах пользователя
    user_boosts = []
    
    for boost in all_boosts:
        # Ищем буст пользователя
        user_boost = next((ub for ub in user.boosts if ub.boost_id == boost.id), None)
        level = user_boost.level if user_boost else 0
        
        # Рассчитываем текущую стоимость апгрейда
        current_cost = boost.base_cost * (1.5 ** level) if level < boost.max_level else -1
        
        user_boosts.append({
            "boost_id": boost.id,
            "name": boost.name,
            "category": boost.category,
            "description": boost.description,
            "icon_name": boost.icon_name,
            "passive_income": boost.passive_income,
            "click_multiplier": boost.click_multiplier,
            "level": level,
            "max_level": boost.max_level,
            "current_cost": current_cost
        })
    
    return user_boosts


async def upgrade_boost(db: AsyncSession, telegram_id: int, boost_id: int):
    # Получаем пользователя
    result = await db.execute(
        select(User)
        .options(selectinload(User.game_state))
        .filter(User.telegram_id == telegram_id)
    )
    user = result.scalars().first()
    
    if not user:
        return {"error": "User not found"}
    
    game_state = user.game_state
    if not game_state:
        return {"error": "Game state not found"}
    
    # Получаем буст
    result = await db.execute(select(Boost).filter(Boost.id == boost_id))
    boost = result.scalars().first()
    
    if not boost:
        return {"error": "Boost not found"}
    
    # Ищем, есть ли у пользователя этот буст
    result = await db.execute(
        select(UserBoost).filter_by(user_id=user.id, boost_id=boost.id)
    )
    user_boost = result.scalars().first()
    
    current_level = user_boost.level if user_boost else 0
    
    # Проверяем, можно ли улучшить
    if current_level >= boost.max_level:
        return {"error": "Boost already at max level"}
    
    # Рассчитываем стоимость апгрейда
    upgrade_cost = int(boost.base_cost * (1.5 ** current_level))
    upgrade_click_multiplier = boost.click_multiplier * 0.2 * (1.5 ** current_level)
    upgrade_passive_income = boost.passive_income * (1.5 ** current_level)

    # Atomic conditional debit: parallel upgrades can't spend the same CSM twice.
    from sqlalchemy import update as _update
    from app.models.game_state import GameState as _GS
    debit = await db.execute(
        _update(_GS)
        .where(_GS.user_id == user.id, _GS.balance >= upgrade_cost)
        .values(balance=_GS.balance - upgrade_cost)
    )
    if debit.rowcount != 1:
        await db.rollback()
        return {"error": "Not enough balance"}

    # Claim the level atomically: the guarded UPDATE only lands if the level
    # is still what we read — a concurrent upgrade of the same boost loses
    # here, and its debit (same transaction) rolls back with it, so a
    # double-tap can no longer charge twice for one level.
    if user_boost:
        claim = await db.execute(
            _update(UserBoost)
            .where(UserBoost.user_id == user.id, UserBoost.boost_id == boost.id,
                   UserBoost.level == current_level)
            .values(level=current_level + 1)
        )
        if claim.rowcount != 1:
            await db.rollback()
            return {"error": "Upgrade conflict, please retry"}
    else:
        user_boost = UserBoost(user_id=user.id, boost_id=boost.id, level=1)
        try:
            async with db.begin_nested():
                db.add(user_boost)
                await db.flush()
        except IntegrityError:
            await db.rollback()
            return {"error": "Upgrade conflict, please retry"}

    # Stat increments are SQL-side too — an ORM += loses a concurrent
    # upgrade landing in the same instant (even of a different boost).
    await db.execute(
        _update(_GS)
        .where(_GS.user_id == user.id)
        .values(boost_multiplier=_GS.boost_multiplier + upgrade_click_multiplier,
                passive_income=_GS.passive_income + upgrade_passive_income)
    )

    await db.commit()
    await db.refresh(game_state)
    await db.refresh(user_boost)
    
    # Рассчитываем новую стоимость апгрейда
    new_level = user_boost.level
    new_cost = boost.base_cost * (1.5 ** new_level) if new_level < boost.max_level else -1
    
    return {
        "boost_id": boost.id,
        "name": boost.name,
        "level": new_level,
        "max_level": boost.max_level,
        "new_balance": game_state.balance,
        "new_cost": new_cost,
        "new_passive_income": game_state.passive_income,
        "new_click_multiplier": game_state.boost_multiplier
    }
