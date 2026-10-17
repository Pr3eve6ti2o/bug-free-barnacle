from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.user import User
from app.models.game_state import GameState
from app.models.p2e import WithdrawalRequest
from app.services.p2e import WITHDRAW_MIN

router = APIRouter(prefix="/withdraw", tags=["Withdraw"])

VALID_PREFIXES = ("EQ", "UQ", "kQ", "0Q")


class WithdrawRequest(BaseModel):
    telegram_id: int
    amount: int
    address: str


def _valid_ton_address(address: str) -> bool:
    a = (address or "").strip()
    return len(a) == 48 and a[:2] in VALID_PREFIXES


@router.post("/request")
async def request_withdrawal(req: WithdrawRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).options(selectinload(User.game_state)).where(User.telegram_id == req.telegram_id)
    )
    user = result.scalar_one_or_none()
    if not user or not user.game_state:
        raise HTTPException(status_code=404, detail="User not found")
    if req.amount < WITHDRAW_MIN:
        raise HTTPException(status_code=400, detail=f"Minimum withdrawal is {WITHDRAW_MIN} CSM")
    if not _valid_ton_address(req.address):
        raise HTTPException(status_code=400, detail="Invalid TON address")
    # Atomic conditional debit: concurrent requests cannot overdraw —
    # the UPDATE only lands when the balance still covers the amount.
    debit = await db.execute(
        update(GameState)
        .where(GameState.user_id == user.id, GameState.balance >= req.amount)
        .values(balance=GameState.balance - req.amount)
    )
    if debit.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Not enough CSM")
    wr = WithdrawalRequest(user_id=user.id, amount=req.amount, address=req.address.strip())
    db.add(wr)
    await db.commit()
    await db.refresh(user.game_state)
    return {
        "id": wr.id,
        "amount": wr.amount,
        "status": wr.status,
        "new_balance": user.game_state.balance,
    }


@router.get("/history/{telegram_id}")
async def history(telegram_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    rows = (await db.execute(
        select(WithdrawalRequest)
        .where(WithdrawalRequest.user_id == user.id)
        .order_by(WithdrawalRequest.id.desc())
        .limit(20)
    )).scalars().all()
    return [
        {
            "id": r.id,
            "amount": r.amount,
            "address": r.address,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def _mask_name(username: str | None) -> str:
    name = (username or "").strip()
    if not name:
        return "Pilot ***"
    return (name[:2] + "***") if len(name) > 2 else (name + "***")


def _mask_address(address: str) -> str:
    a = (address or "").strip()
    return (a[:4] + "…" + a[-3:]) if len(a) > 8 else a


@router.get("/recent")
async def recent_payouts(db: AsyncSession = Depends(get_db)):
    """Public activity feed for the Me screen: real in-game payout events —
    withdrawal requests and crew (referral) earnings, newest first, with
    names and addresses masked."""
    from app.models.p2e import ReferralEarning

    events = []

    wrows = (await db.execute(
        select(WithdrawalRequest, User.username)
        .join(User, User.id == WithdrawalRequest.user_id)
        .order_by(WithdrawalRequest.id.desc())
        .limit(10)
    )).all()
    for wr, username in wrows:
        events.append({
            "kind": "withdrawal",
            "name": _mask_name(username),
            "amount": wr.amount,
            "status": wr.status,
            "detail": _mask_address(wr.address),
            "created_at": wr.created_at.isoformat() if wr.created_at else None,
        })

    erows = (await db.execute(
        select(ReferralEarning, User.username)
        .join(User, User.id == ReferralEarning.referrer_id)
        .order_by(ReferralEarning.id.desc())
        .limit(10)
    )).all()
    for earning, username in erows:
        events.append({
            "kind": "crew_payout",
            "name": _mask_name(username),
            "amount": earning.amount,
            "status": "paid",
            "detail": "crew earnings",
            "created_at": earning.created_at.isoformat() if earning.created_at else None,
        })

    events.sort(key=lambda e: e["created_at"] or "", reverse=True)
    return events[:12]
