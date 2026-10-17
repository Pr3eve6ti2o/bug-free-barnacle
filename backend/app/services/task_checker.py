from datetime import date, datetime, time
from sqlalchemy import case, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.user_tasks import UserTask
from app.models.task import Task
from app.models.daily_game_state import DailyGameState
from app.models.game_state import GameState
from app.models.user import User
from app.models.p2e import MiningSession, BotStart


async def check_daily_reset(db: AsyncSession, user_id: int) -> bool:
    """Проверяет, нужно ли сбросить ежедневный прогресс"""
    # Получаем ежедневное состояние пользователя
    result = await db.execute(
        select(DailyGameState)
        .filter(DailyGameState.user_id == user_id)
    )
    daily_state = result.scalar_one_or_none()
    
    if not daily_state:
        # Если нет ежедневного состояния, создаем его
        daily_state = DailyGameState(
            user_id=user_id,
            score=0,
            energy_spent=0,
            balance=0,
            day_start=datetime.now()
        )
        db.add(daily_state)
        await db.flush()
        return True
    
    # Проверяем, начался ли новый день
    today = datetime.now().date()
    if daily_state.day_start.date() < today:
        # Сбрасываем ежедневный прогресс
        daily_state.score = 0
        daily_state.energy_spent = 0
        daily_state.balance = 0
        daily_state.day_start = datetime.now()
        daily_state.last_update = datetime.now()
        
        # Сбрасываем прогресс по ежедневным заданиям
        stmt = (select(UserTask)
            .join(Task)
            .filter(
                UserTask.user_id == user_id,
                Task.type == "daily"
            ))
        
        result = await db.execute(stmt)
        daily_tasks = result.scalars().all()
        
        for user_task in daily_tasks:
            user_task.progress = 0
            user_task.is_completed = False
            user_task.is_claimed = False
            user_task.last_updated = datetime.now()
        
        await db.flush()
        return True
    
    return False



async def check_task_progress(db: AsyncSession, user_id: int):
    """
    Проверяет прогресс по всем заданиям пользователя.
    Для ежедневных заданий использует daily_game_state,
    для глобальных - обычный game_state или user.
    """
    
    # Получаем данные пользователя
    user_result = await db.execute(
        select(User)
        .options(
            selectinload(User.game_state),
            selectinload(User.daily_game_state),
            selectinload(User.tasks).selectinload(UserTask.task)
        )
        .filter(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()

    if not user or not user.game_state:
        return []

    # Гарантируем, что у пользователя есть строки по всем заданиям
    # (иначе проверка прогресса зависит от порядка вызовов API)
    all_tasks = (await db.execute(select(Task))).scalars().all()
    existing_task_ids = {ut.task_id for ut in user.tasks}
    for task in all_tasks:
        if task.id not in existing_task_ids:
            new_ut = UserTask(
                user_id=user.id,
                task_id=task.id,
                progress=0,
                is_completed=False,
                is_claimed=False,
            )
            try:
                async with db.begin_nested():
                    db.add(new_ut)
                    await db.flush()
                user.tasks.append(new_ut)
            except IntegrityError:
                pass  # a parallel check created the row first (ux_user_task)
    await db.flush()
    
    # Убедимся, что у пользователя есть daily_game_state
    daily_state = user.daily_game_state
    if not daily_state:
        daily_state = DailyGameState(
            user_id=user.id,
            score=0,
            energy_spent=0,
            balance=0,
            day_start=datetime.now()
        )
        db.add(daily_state)
        await db.flush()
    
    # Метрики для постоянных заданий: считаются один раз из реальных данных
    async def _count(stmt):
        return (await db.execute(stmt)).scalar() or 0

    metrics = {
        "level": user.game_state.level or 0,
        "passive_income": user.game_state.passive_income or 0,
        "balance": user.game_state.balance or 0,
        "mining_sessions": await _count(
            select(func.count(MiningSession.id)).filter(MiningSession.user_id == user.id)
        ),
        "mining_claims": await _count(
            select(func.count(MiningSession.id)).filter(
                MiningSession.user_id == user.id, MiningSession.claimed == True  # noqa: E712
            )
        ),
        "referrals": await _count(
            select(func.count(User.id)).filter(User.referred_by_id == user.id)
        ),
        "bot_started": await _count(
            select(func.count(BotStart.telegram_id)).filter(BotStart.telegram_id == user.telegram_id)
        ),
        "wallet_connected": 1 if user.ton_wallet_address else 0,
    }

    # Получаем все задания пользователя
    completed_tasks = []
    
    for user_task in user.tasks:
        task = user_task.task
        
        # Пропускаем задания, которые уже выполнены и получены
        if user_task.is_completed and user_task.is_claimed:
            continue
        
        # Для ежедневных заданий проверяем состояние в daily_game_state
        if task.type == "daily" and task.condition_type in ["taps", "energy_spent", "daily_balance"]:
            # Получаем значение из правильного поля
            current_value = 0
            if task.condition_type == "taps":
                current_value = daily_state.score
            elif task.condition_type == "energy_spent":
                current_value = daily_state.energy_spent
            elif task.condition_type == "daily_balance":
                current_value = daily_state.balance
            
            # Устанавливаем прогресс на текущее значение
            user_task.progress = current_value
            user_task.last_updated = datetime.now()
            
            # Проверяем выполнение
            if current_value >= task.condition_value and not user_task.is_completed:
                user_task.is_completed = True
                user_task.completed_at = datetime.now()
                completed_tasks.append(user_task)
            
        # Для глобальных заданий проверяем состояние в game_state и метрики
        elif task.type == "permanent":
            if task.condition_type in metrics:
                current_value = metrics[task.condition_type]

                # Устанавливаем прогресс на текущее значение
                user_task.progress = current_value

                # Проверяем выполнение
                if current_value >= task.condition_value and not user_task.is_completed:
                    user_task.is_completed = True
                    user_task.completed_at = datetime.now()
                    completed_tasks.append(user_task)
    
    await db.commit()
    return completed_tasks


async def claim_task_reward(db: AsyncSession, user_telegram_id: int, user_task_id: int):
    """
    Получает награду за выполненное задание
    """
    # Получаем пользователя
    result = await db.execute(
        select(User)
        .options(selectinload(User.game_state))
        .filter(User.telegram_id == user_telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        return {"success": False, "error": "User not found"}
    
    # Получаем задание пользователя
    result = await db.execute(
        select(UserTask)
        .options(selectinload(UserTask.task))
        .filter(
            UserTask.id == user_task_id, 
            UserTask.user_id == user.id,
            UserTask.is_completed == True,
            UserTask.is_claimed == False
        )
    )
    user_task = result.scalar_one_or_none()
    
    if not user_task:
        return {"success": False, "error": "Task not found or already claimed"}

    # Atomic claim gate: exactly one concurrent claim flips the flag, and
    # the completion predicate is re-checked inside the same UPDATE — a
    # daily reset landing between the SELECT above and this gate cannot
    # resurrect a claim on an un-completed task.
    gate = await db.execute(
        update(UserTask)
        .where(UserTask.id == user_task.id, UserTask.is_claimed.is_(False),
               UserTask.is_completed.is_(True))
        .values(is_claimed=True)
    )
    if gate.rowcount != 1:
        await db.rollback()
        return {"success": False, "error": "Task not found or already claimed"}
    user_task.is_claimed = True

    # Начисляем награду: токены на баланс или +% к скорости майнинга
    task = user_task.task
    if getattr(task, "reward_type", "token") == "multiplier":
        pct = float(task.multiplier_pct or 0)
        current = float(user.game_state.task_boost_pct or 0)
        # SQL-side clamped increment (total task boost capped at +100%):
        # an ORM read-modify-write here lost one of two concurrent claims.
        boosted = func.coalesce(GameState.task_boost_pct, 0) + pct
        await db.execute(
            update(GameState)
            .where(GameState.user_id == user.id)
            .values(task_boost_pct=case((boosted > 100.0, 100.0), else_=boosted))
        )
        await db.refresh(user.game_state)
        new_total = float(user.game_state.task_boost_pct or 0)
        await db.commit()
        return {
            "success": True,
            "reward": 0,
            "reward_type": "multiplier",
            "multiplier_pct": new_total - current,
            "task_boost_pct": new_total,
            "new_balance": user.game_state.balance,
            "task_id": user_task.id,
        }

    reward = task.reward
    # Atomic SQL-side credit: an ORM += here could overwrite a concurrent
    # credit (mining claim, welcome) landing in the same instant.
    await db.execute(
        update(GameState)
        .where(GameState.user_id == user.id)
        .values(balance=GameState.balance + reward)
    )
    await db.refresh(user.game_state)

    await db.commit()

    return {
        "success": True,
        "reward": reward,
        "reward_type": "token",
        "new_balance": user.game_state.balance,
        "task_id": user_task.id
    }