import time
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database import get_db
from app.crud.user import get_user_by_telegram_id
from app.services.rating import get_friends_balance_rating
from app.services.p2e import is_og_active
from app.models.user import User
from app.models.game_state import GameState

router = APIRouter()


@router.get("/users/friends-rating")
async def get_friends_rating(telegram_id: int, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    friends_ranking = await get_friends_balance_rating(user.id, db)
    return {"friends": [{"username": u, "balance": b} for u, b in friends_ranking]}


# Simple in-memory TTL cache: {limit: (expires_at, payload)}
_leaderboard_cache: dict = {}
LEADERBOARD_TTL = 60


@router.get("/rating/global")
async def get_global_rating(limit: int = Query(50, le=100), db: AsyncSession = Depends(get_db)):
    now = time.time()
    cached = _leaderboard_cache.get(limit)
    if cached and cached[0] > now:
        return cached[1]
    rows = (await db.execute(
        select(User, GameState)
        .join(GameState, GameState.user_id == User.id)
        .order_by(desc(GameState.balance))
        .limit(limit)
    )).all()
    board = []
    for rank, (user, gs) in enumerate(rows, start=1):
        board.append({
            "rank": rank,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "balance": gs.balance,
            "level": gs.level,
            "og_badge": is_og_active(user),
        })
    payload = {"leaders": board}
    _leaderboard_cache[limit] = (now + LEADERBOARD_TTL, payload)
    return payload
