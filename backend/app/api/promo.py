from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.models.user import User
from app.models.p2e import PromoCode, PromoRedemption
from app.services.p2e import credit_user

router = APIRouter(prefix="/promo", tags=["Promo"])


class RedeemRequest(BaseModel):
    telegram_id: int
    code: str


@router.post("/redeem")
async def redeem(req: RedeemRequest, db: AsyncSession = Depends(get_db)):
    code = (req.code or "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Enter a code")
    result = await db.execute(
        select(User).options(selectinload(User.game_state)).where(User.telegram_id == req.telegram_id)
    )
    user = result.scalar_one_or_none()
    if not user or not user.game_state:
        raise HTTPException(status_code=404, detail="User not found")

    promo = (await db.execute(select(PromoCode).where(PromoCode.code == code))).scalar_one_or_none()
    if not promo or not promo.active:
        raise HTTPException(status_code=400, detail="Unknown code")
    if promo.expires_at and promo.expires_at < datetime.now():
        raise HTTPException(status_code=400, detail="This code has expired")
    if promo.max_uses is not None and promo.uses >= promo.max_uses:
        raise HTTPException(status_code=400, detail="This code is fully redeemed")
    already = (await db.execute(
        select(PromoRedemption).where(
            PromoRedemption.user_id == user.id, PromoRedemption.code_id == promo.id
        )
    )).scalar_one_or_none()
    if already:
        raise HTTPException(status_code=400, detail="You already used this code")

    db.add(PromoRedemption(user_id=user.id, code_id=promo.id))
    promo.uses += 1
    credited = await credit_user(db, user, promo.reward)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="You already used this code")
    return {"reward": credited, "new_balance": user.game_state.balance}
