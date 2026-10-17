from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from datetime import datetime
from sqlalchemy.orm import selectinload
from app.models.user import User
from app.models.game_state import GameState
from app.services.p2e import credit_user, get_max_energy

MAX_PASSIVE_ACCUMULATION_TIME = 3600  # 1 hour in seconds
MINUTE_INTERVAL = 60  # Apply income every minute when in-app
MAX_LEVEL = 7  # Maximum level for the game
MAX_ENERGY = 100
ENERGY_RESTORE_AMOUNT = 1

def base_click_income(level: int) -> int:
    return 1 + (level - 1)


def required_score_for_level(level: int) -> int:
    return level * 100


async def process_click(db: AsyncSession, telegram_id: int) -> dict:
    # Получаем пользователя по telegram_id
    result = await db.execute(
        select(User)
        .options(selectinload(User.game_state))
        .options(selectinload(User.daily_game_state))
        .filter(User.telegram_id == telegram_id)
    )
    user = result.scalars().first()

    if not user:
        return {"error": "User not found"}

    game_state = user.game_state
    if not game_state:
        return {"error": "Game state not found"}

    # Energy is the spend guard for the legacy click — it must be checked
    # BEFORE crediting (previously clicks paid out at any energy, even
    # negative, so a script could mint CSM + referral shares indefinitely).
    if (game_state.energy or 0) <= 0:
        return {"error": "Not enough energy"}

    # Рассчитываем награду (verified +10% и 5% рефереру — внутри credit_user)
    base_income = base_click_income(game_state.level)
    reward = await credit_user(
        db, user, base_income * game_state.boost_multiplier,
        mined=True, apply_verified=True,
    )

    # Обновляем состояние игры
    game_state.score += reward
    game_state.last_click_at = datetime.utcnow()
    
    game_state.energy -= 1

    daily_game_state = user.daily_game_state
    if not daily_game_state:
        return {"error": "Daily game state not found"}
    


    daily_game_state.score += 1
    daily_game_state.balance += reward
    daily_game_state.energy_spent += 1
    
    # Проверяем, можно ли повысить уровень
    leveled_up = False
    
    # Проверяем, не достигнут ли максимальный уровень
    if game_state.level < MAX_LEVEL:
        required_score = required_score_for_level(game_state.level)
        
        if game_state.score >= required_score:
            game_state.level += 1
            game_state.score = 0
            leveled_up = True

    
   

    # Делаем commit только один раз в конце всей функции
    await db.commit()


    return {
        "reward": reward,
        "new_score": game_state.score,
        "new_balance": game_state.balance,
        "level": game_state.level,
        "leveled_up": leveled_up,
        "energy": game_state.energy
    }


async def get_user_game_state(db: AsyncSession, telegram_id: int):
    """Get user's game state or raise exception if not found"""
    result = await db.execute(
        select(User)
        .options(selectinload(User.game_state))
        .filter(User.telegram_id == telegram_id)
    )
    user = result.scalars().first()
    
    if not user or not user.game_state:
        return None
    
    return user


async def calculate_passive_income(db: AsyncSession, telegram_id: int) -> dict:
    """Calculate passive income based on time since last update"""
    user = await get_user_game_state(db, telegram_id)
    if not user:
        return {"error": "User or game state not found"}
    
    game_state = user.game_state
    
    # Calculate accumulated income
    current_time = datetime.now()
    time_since_last_update = (current_time - game_state.last_income_at).total_seconds()
    effective_time = min(time_since_last_update, MAX_PASSIVE_ACCUMULATION_TIME)
    
    passive_income_per_second = game_state.passive_income / 3600.0
    accumulated_income = effective_time * passive_income_per_second
    
    return {
        "passive_income_rate": game_state.passive_income,  # CSM/hour
        "accumulated_income": accumulated_income,          # CSM accumulated
        "max_accumulation_time": MAX_PASSIVE_ACCUMULATION_TIME,  # Max time in seconds
        "time_accumulated": effective_time,                # Time accumulated (seconds)
        "user": user,
        "game_state": game_state,
        "current_time": current_time
    }



async def apply_passive_income(db: AsyncSession, telegram_id: int, is_returning: bool = False) -> dict:
    """Apply passive income to user balance
    
    Args:
        db: Database session
        telegram_id: User's telegram ID
        is_returning: If True, user is returning to app after being offline
    """
    income_data = await calculate_passive_income(db, telegram_id)
    
    if "error" in income_data:
        return income_data
    
    game_state = income_data["game_state"]
    bal_before = game_state.balance  # plain value: ORM expires on rollback
    current_time = income_data["current_time"]
    
    # For returning users (coming back to app), apply all accumulated income at once
    if is_returning:
        # Round income to integer before adding to balance
        rounded_income = int(income_data["accumulated_income"])

        if rounded_income > 0:
            # CAS gate: only the caller that advances last_income_at from the
            # observed value gets to credit — parallel collects can't double-pay.
            gate = await db.execute(
                update(GameState)
                .where(GameState.user_id == game_state.user_id,
                       GameState.last_income_at == game_state.last_income_at)
                .values(last_income_at=current_time)
            )
            if gate.rowcount != 1:
                await db.rollback()
                return {"applied_income": 0, "new_balance": bal_before, "is_returning": True}

        # Apply accumulated income to user's balance (5% рефереру — внутри credit_user)
        await credit_user(db, income_data["user"], rounded_income, mined=True)

        # Update last income timestamp
        game_state.last_income_at = current_time

        # Save changes to DB
        await db.commit()

        
        
        return {
            "applied_income": rounded_income,
            "new_balance": game_state.balance,
            "is_returning": True
        }
    
    # For in-app users, apply income for the minute interval
    else:
        time_since_last_update = (current_time - game_state.last_income_at).total_seconds()
        
        # Only apply if at least a minute has passed
        if time_since_last_update >= MINUTE_INTERVAL:
            # Calculate income for the minute (hourly rate / 60)
            minute_income = int(game_state.passive_income / 60)

            if minute_income > 0:
                # CAS gate on last_income_at — parallel collects can't double-pay.
                gate = await db.execute(
                    update(GameState)
                    .where(GameState.user_id == game_state.user_id,
                           GameState.last_income_at == game_state.last_income_at)
                    .values(last_income_at=current_time)
                )
                if gate.rowcount != 1:
                    await db.rollback()
                    return {
                        "applied_income": 0,
                        "new_balance": bal_before,
                        "is_returning": False
                    }

            # Apply income (5% рефереру — внутри credit_user)
            await credit_user(db, income_data["user"], minute_income, mined=True)
            
            # Update last income timestamp
            game_state.last_income_at = current_time
            
            # Save changes to DB
            await db.commit()
            
            return {
                "applied_income": minute_income,
                "new_balance": game_state.balance,
                "is_returning": False
            }
        
        # Not enough time has passed for in-app income
        return {
            "applied_income": 0,
            "new_balance": game_state.balance,
            "is_returning": False
        }
    
async def calculate_energy_restore(db: AsyncSession, telegram_id: int) -> dict:
    """Расчет восстановления энергии"""
    user = await get_user_game_state(db, telegram_id)
    if not user:
        return {"error": "User or game state not found"}
    
    game_state = user.game_state
    current_time = datetime.now()
    elapsed_sec10 = (current_time - game_state.last_energy_update).total_seconds() /10
    energy_to_restore = int(elapsed_sec10 * ENERGY_RESTORE_AMOUNT)
    max_energy = get_max_energy(user)

    return {
        "current_energy": game_state.energy,
        "energy_to_restore": energy_to_restore,
        "max_energy": max_energy,
        "game_state": game_state,
        "current_time": current_time
    }

async def apply_energy_restore(db: AsyncSession, telegram_id: int) -> dict:
    """Применение восстановления энергии"""
    result = await calculate_energy_restore(db, telegram_id)
    if "error" in result:
        return result
    
    game_state = result["game_state"]
    current_time = result["current_time"]
    energy_to_restore = result["energy_to_restore"]
    
    if energy_to_restore > 0 and game_state.energy < result["max_energy"]:
        game_state.energy = min(
            game_state.energy + energy_to_restore,
            result["max_energy"]
        )
        game_state.last_energy_update = current_time
        await db.commit()

    return {
        "new_energy": game_state.energy,
        "restored_amount": energy_to_restore,
        "max_energy": result["max_energy"]
    }